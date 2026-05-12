# DevOps MCP Server

A **FastAPI** service that exposes DevOps operations as authenticated HTTP endpoints. It allows AI agents, CI/CD pipelines, or developers to easily trigger and monitor Kubernetes deployments, fetch pod logs, and perform rollbacks.

## Features
- **Model Context Protocol (MCP)**: Exposes operations natively as MCP tools via Server-Sent Events (SSE).
- **Async Deployments**: Start a deployment and track its status via job polling.
- **Log Retrieval**: Fetch logs using Kubernetes label selectors.
- **Rollbacks**: Revert a deployment to a previous state using ReplicaSet revision history.
- **Authentication**: Role-based access control (Admin, Deployer, Viewer) via API keys or JWT (for REST endpoints).
- **Metrics**: Built-in Prometheus `/metrics` endpoint.

## System Architecture

```text
User / AI Agent / GitHub Actions
        ↓
   API Server (FastAPI) — auth.py, app.py
        ↓
   Async job queue — jobs.py
        ↓
   Tool Layer — tools/deploy.py, tools/logs.py, tools/rollback.py
        ↓
   Kubernetes client — k8s_client.py
        ↓
   Kubernetes Cluster
```

## Tech Stack

- **Language**: Python 3.10+
- **API Framework**: FastAPI, Uvicorn, Pydantic
- **Auth**: PyJWT (Bearer Tokens) & API Keys
- **Kubernetes**: `kubernetes` Python SDK
- **Metrics**: `prometheus-client`

## Real usage and demos

Below is a recording of an AI agent interacting with the Server's Swagger UI to deploy an application, monitor job status, retrieve logs, and trigger a rollback:

![AI Agent executing Deploy API using Swagger UI](assets/api_demo_swagger.gif)

### Cluster Proof

State of the Kubernetes cluster as verified by the terminal while the API processed the requests:

```text
NAME                         READY   STATUS    RESTARTS      AGE
pod/demo-dfc8c5966-s5d25     1/1     Running   3 (10m ago)   97m
pod/demo-dfc8c5966-xfs8f     1/1     Running   3 (10m ago)   97m

NAME                 TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
service/kubernetes   ClusterIP   10.96.0.1    <none>        443/TCP   100m

NAME                     READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/demo     2/2     2            2           97m

NAME                               DESIRED   CURRENT   READY   AGE
replicaset.apps/demo-dfc8c5966     2         2         2       97m
```

## Setup & Run

### Prerequisites
- Python 3.10+
- A working Kubernetes cluster (e.g. Minikube/Kind)

### Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Start the Server
```bash
uvicorn app:app --reload
```
Access the interactive API docs at `http://127.0.0.1:8000/docs`.

## Model Context Protocol (MCP) Support

This service natively supports the Model Context Protocol (MCP) using the SSE transport. You can connect compatible MCP clients (like Claude Desktop or custom LangChain/LlamaIndex agents) directly to the server:

**SSE Connection URL:**
```text
http://127.0.0.1:8000/mcp/sse
```

The server exposes the following MCP Tools to connected LLMs:
- `deploy_tool`: Triggers a Kubernetes deployment and returns an async job ID.
- `check_job_tool`: Checks the status of an active deployment job.
- `fetch_logs_tool`: Retrieves logs for a labeled pod.
- `rollback_tool`: Reverts a deployment to a previous ReplicaSet revision.

*(Note: The MCP endpoints do not currently require the X-API-Key used by the standard REST API)*

## API Reference (Quick Look)

Add **`X-API-Key`** or **`Authorization: Bearer`** to protected routes (all except `/health`).

- **`GET /health`**: Liveness check (No auth required)
- **`POST /deploy`**: Creates an async deploy job (Requires `admin` or `deployer` role)
- **`GET /jobs/{job_id}`**: Check deploy status (Requires `admin`, `deployer`, or `viewer` role)
- **`POST /logs`**: Fetch logs for a labeled pod (Requires `admin`, `deployer`, or `viewer` role)
- **`POST /rollback`**: Rollback using ReplicaSet history (Requires `admin` or `deployer` role)
- **`GET /metrics`**: Prometheus metrics exposition

## Example `curl` Usage

```bash
export API_KEY='change-me-admin'

# 1. Trigger Deploy
JOB_ID=$(curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}' | jq -r .job_id)

# 2. Check Job Status
curl -s "http://127.0.0.1:8000/jobs/$JOB_ID" -H "X-API-Key: $API_KEY"

# 3. Get Logs
curl -s -X POST http://127.0.0.1:8000/logs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"app_name":"demo","namespace":"default"}'
```

## CI/CD Integration
See `.github/workflows/call-deploy-api.yml` for an example of triggering the deploy API natively from GitHub Actions.
