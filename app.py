from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from tools.deploy import deploy_app
from tools.logs import get_logs
from tools.rollback import rollback

app = FastAPI(
    title="DevOps MCP Server",
    description="Expose DevOps operations (deploy/logs/rollback) as callable API tools.",
    version="0.1.0",
)


class DeployRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Kubernetes Deployment name / app identifier.")
    image: str = Field(..., min_length=1, description="Container image (e.g. nginx:latest).")
    namespace: str = Field(default="default", min_length=1)
    replicas: int = Field(default=1, ge=0, le=50)


class LogsRequest(BaseModel):
    app_name: str = Field(..., min_length=1, description="App name to match pods.")
    namespace: str = Field(default="default", min_length=1)


class RollbackRequest(BaseModel):
    app_name: str = Field(..., min_length=1, description="Deployment name to rollback.")
    namespace: str = Field(default="default", min_length=1)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/deploy")
def deploy(req: DeployRequest) -> dict:
    try:
        return deploy_app(req.name, req.image, namespace=req.namespace, replicas=req.replicas)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 - surface as HTTP error
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/logs")
def logs(req: LogsRequest) -> dict:
    try:
        out = get_logs(req.app_name, namespace=req.namespace)
        if out is None:
            raise HTTPException(status_code=404, detail="No matching pod found for app_name.")
        return {"app_name": req.app_name, "namespace": req.namespace, "logs": out}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 - surface as HTTP error
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/rollback")
def rollback_endpoint(req: RollbackRequest) -> dict:
    try:
        return rollback(req.app_name, namespace=req.namespace)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 - surface as HTTP error
        raise HTTPException(status_code=500, detail=str(e)) from e