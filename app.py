from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from auth import Principal, enforce_metrics_scrape, require_roles, startup_validate_auth
from jobs import JOBS
from metrics import PrometheusMiddleware, metrics_response
from settings import load_settings
from tools.deploy import deploy_app
from tools.logs import get_logs
from tools.rollback import rollback_deployment
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup_validate_auth()
    yield


app = FastAPI(
    title="DevOps MCP Server",
    description=(
        "Authenticated DevOps API: async deploy jobs, label-selected logs, deployment rollback via "
        "revision history, Prometheus metrics."
    ),
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(PrometheusMiddleware)

# --- MCP Server Setup ---
mcp = FastMCP("devops-mcp-server")

@mcp.tool()
async def deploy_tool(name: str, image: str, namespace: str = "default", replicas: int = 1) -> str:
    """Trigger a Kubernetes deployment and return the job_id. Use check_job to poll status."""
    rec = await JOBS.create(
        "deploy",
        {
            "name": name,
            "image": image,
            "namespace": namespace,
            "replicas": replicas,
        },
    )
    asyncio.create_task(
        _deploy_worker(rec.job_id, name, image, namespace, replicas),
    )
    return f"Deployment triggered. Job ID: {rec.job_id}"

@mcp.tool()
def fetch_logs_tool(app_name: str, namespace: str = "default") -> str:
    """Fetch logs for a specific pod by app_name label."""
    out = get_logs(app_name, namespace=namespace)
    if out is None:
        return f"No pod found with label app={app_name!r} in namespace {namespace!r}."
    return out

@mcp.tool()
def rollback_tool(app_name: str, revision: int = 0, namespace: str = "default") -> str:
    """Roll back a deployment to a previous revision. revision=0 means previous."""
    try:
        res = rollback_deployment(app_name, namespace=namespace, revision=revision)
        return f"Rolled back {app_name} to revision {res['to_revision']}."
    except Exception as e:
        return f"Rollback failed: {e}"

@mcp.tool()
async def check_job_tool(job_id: str) -> str:
    """Check the status of an async deploy job."""
    rec = await JOBS.get(job_id)
    if rec is None:
        return "Job not found."
    return f"Status: {rec.status.value}\nDetail: {rec.detail}\nResult: {rec.result}"

app.mount("/mcp", mcp.sse_app())
# ------------------------

from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def root():
    """Redirect to the Swagger UI documentation."""
    return RedirectResponse(url="/docs")


class DeployRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Kubernetes Deployment name / `app` label value.")
    image: str = Field(..., min_length=1, description="Container image (e.g. nginx:latest).")
    namespace: str = Field(default="default", min_length=1)
    replicas: int = Field(default=1, ge=0, le=50)


class LogsRequest(BaseModel):
    app_name: str = Field(
        ...,
        min_length=1,
        description="Value of the `app` label on pods (same as Deployment name when using the bundled deploy tool).",
    )
    namespace: str = Field(default="default", min_length=1)


class RollbackRequest(BaseModel):
    app_name: str = Field(..., min_length=1, description="Deployment name to roll back.")
    namespace: str = Field(default="default", min_length=1)
    revision: int = Field(
        default=0,
        ge=0,
        description="Target `deployment.kubernetes.io/revision`. Use `0` for the previous revision (kubectl rollout undo).",
    )


async def _deploy_worker(job_id: str, name: str, image: str, namespace: str, replicas: int) -> None:
    await JOBS.set_running(job_id)
    try:
        result = await asyncio.to_thread(deploy_app, name, image, namespace, replicas)
        await JOBS.succeed(job_id, result)
    except Exception as e:  # noqa: BLE001 - persist message for job polling
        await JOBS.fail(job_id, str(e))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def prometheus_metrics(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
):
    enforce_metrics_scrape(load_settings(), x_api_key, authorization)
    return metrics_response()


@app.post("/deploy", status_code=status.HTTP_202_ACCEPTED)
async def deploy(
    req: DeployRequest,
    _: Annotated[Principal, Depends(require_roles("admin", "deployer"))],
) -> dict:
    rec = await JOBS.create(
        "deploy",
        {
            "name": req.name,
            "image": req.image,
            "namespace": req.namespace,
            "replicas": req.replicas,
        },
    )
    asyncio.create_task(
        _deploy_worker(rec.job_id, req.name, req.image, req.namespace, req.replicas),
    )
    return {
        "job_id": rec.job_id,
        "status": rec.status.value,
        "kind": rec.kind,
        "created_at": rec.created_at,
    }


@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    _: Annotated[Principal, Depends(require_roles("admin", "deployer", "viewer"))],
) -> dict:
    rec = await JOBS.get(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Unknown job_id.")
    return {
        "job_id": rec.job_id,
        "status": rec.status.value,
        "kind": rec.kind,
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
        "detail": rec.detail,
        "result": rec.result,
        "request": rec.request_summary,
    }


@app.post("/logs")
def logs(
    req: LogsRequest,
    _: Annotated[Principal, Depends(require_roles("admin", "deployer", "viewer"))],
) -> dict:
    try:
        out = get_logs(req.app_name, namespace=req.namespace)
        if out is None:
            raise HTTPException(
                status_code=404,
                detail=f"No pod found with label app={req.app_name!r} in namespace {req.namespace!r}.",
            )
        return {"app_name": req.app_name, "namespace": req.namespace, "logs": out}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/rollback")
def rollback_endpoint(
    req: RollbackRequest,
    _: Annotated[Principal, Depends(require_roles("admin", "deployer"))],
) -> dict:
    try:
        return rollback_deployment(req.app_name, namespace=req.namespace, revision=req.revision)
    except RuntimeError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
