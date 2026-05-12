# DevOps MCP Server (Python) — Automated Deployment & Monitoring

## Project title

**DevOps MCP Server using Python for Automated Deployment and Monitoring**

## What this project is

This repository is a **FastAPI** service (**v0.2.0**) that exposes DevOps operations as authenticated HTTP endpoints:

- **Deploy** — accepts a deploy request, returns a **job ID**, and runs the Kubernetes create on a **background task** (poll `GET /jobs/{job_id}`).
- **Logs** — fetches pod logs using the label selector **`app=<value>`** (aligned with the `app` label set by the bundled deploy module).
- **Rollback** — restores the Deployment pod template from **ReplicaSet revision history** (same revision annotations as `kubectl rollout undo`), not a fake “restart” patch.

It adds **API key or JWT authentication**, **role-based HTTP authorization** (`admin` / `deployer` / `viewer`), structured **request logging**, and a **`/metrics` Prometheus** exposition endpoint.

The server does **not** implement the full MCP wire protocol by itself; it is an **HTTP API** you can call from an MCP host, CI, or an AI agent. The name reflects *model-context-friendly* tools with predictable JSON.

## Abstract

The DevOps MCP (Model Context Protocol) Server is a backend system designed to expose DevOps operations as structured, callable tools that can be invoked by AI systems or external clients. The server acts as an intermediary between user intent and infrastructure execution by translating high-level commands into concrete operations on containerized environments.

This project leverages Kubernetes and Docker to automate application deployment, log retrieval, and rollback mechanisms through a Python-based API interface.

## Objectives

- **Expose DevOps functionalities as structured APIs (tools)**: deployment, log retrieval, rollback
- **Automate deployment and management of containerized applications** on Kubernetes
- **Enable seamless interaction between AI systems and infrastructure** via callable endpoints
- **Ensure safe and controlled execution** of DevOps operations (see [Security considerations](#security-considerations-recommended-enhancements))

## Problem statement

Modern DevOps workflows require engineers to manually execute commands using CLI tools and dashboards. This process can be:

- **Time-consuming**
- **Error-prone**
- **Hard to integrate** with AI-driven systems

There is a need for a system that abstracts infrastructure operations into programmable and intelligent interfaces.

## Proposed solution

This repository implements a Python-based server that:

- Accepts structured requests (e.g., deploy application, fetch logs, trigger rollback)
- Routes requests to predefined tool modules under `tools/`
- Uses the Kubernetes Python client to execute operations on a cluster
- Returns structured JSON responses suitable for AI agents and automation clients

## System architecture

High-level flow:

```text
User / AI Agent / GitHub Actions
        ↓
   API key or JWT + role check — auth.py, settings.py
        ↓
   API Server (FastAPI) — app.py
        ↓
   Async job queue (deploy) — jobs.py
        ↓
   Tool Layer — tools/deploy.py, tools/logs.py, tools/rollback.py
        ↓
   Kubernetes client — k8s_client.py
        ↓
   Kubernetes Cluster
        ↑
   Metrics / logs — metrics.py (Prometheus + access log)
```

### How Kubernetes is configured

`k8s_client.py` loads configuration in this order:

1. **Kubeconfig** on the machine running the server (typical for Minikube, Kind, or `kubectl`-configured clusters).
2. If that fails, **in-cluster** config (when the app runs as a pod with a service account).

If neither works, endpoints that touch the cluster return **503** with a message explaining that Kubernetes is not reachable.

## Authentication and roles

By default **`DEVOPS_REQUIRE_AUTH`** is **`false`** so you can run `uvicorn` with no `.env`. For anything exposed beyond your laptop, set **`DEVOPS_REQUIRE_AUTH=true`** in `.env` (see **`.env.example`**) and configure keys or JWT.

When auth is **enabled**, protected routes need one of:

- **`X-API-Key: <secret>`** — secrets and roles come from **`DEVOPS_API_KEYS`** (JSON object mapping key string to role).
- **`Authorization: Bearer <jwt>`** — HS256 by default; payload must include **`role`** (`admin` | `deployer` | `viewer`) and typically **`exp`**. Configure **`DEVOPS_JWT_SECRET`**.

| Role | Deploy (`POST /deploy`) | Logs (`POST /logs`) | Rollback (`POST /rollback`) | Job status (`GET /jobs/...`) | Metrics (`GET /metrics`) |
|------|------------------------|---------------------|----------------------------|------------------------------|---------------------------|
| `admin` | Yes | Yes | Yes | Yes | Yes (unless `DEVOPS_METRICS_NO_AUTH=true`) |
| `deployer` | Yes | Yes | Yes | Yes | Yes (same as above) |
| `viewer` | No | Yes | No | Yes | Yes (same as above) |

**`GET /health`** stays **unauthenticated** for probes.

Copy **`.env.example`** to **`.env`** in the project root; variables are loaded automatically via **`python-dotenv`**. You can still `export` overrides in the shell. For production, use your platform’s secret store and set **`DEVOPS_REQUIRE_AUTH=true`** with **`DEVOPS_API_KEYS`** and/or **`DEVOPS_JWT_SECRET`**.

On startup, if auth is required but **no** API keys and **no** JWT secret are set, the process **exits** with an error (fail closed).

## Project layout

| Path | Role |
|------|------|
| `app.py` | FastAPI app, routes, async deploy orchestration |
| `auth.py` | API key / JWT resolution and role checks |
| `settings.py` | Environment-driven configuration |
| `jobs.py` | In-memory job records for async deploy |
| `metrics.py` | Prometheus counters/histograms + request logging middleware |
| `k8s_client.py` | Lazy singleton Kubernetes API clients (`AppsV1Api`, `CoreV1Api`) |
| `tools/deploy.py` | Create a `Deployment` with label `app: <name>` |
| `tools/logs.py` | List pods with `label_selector=app=<app_name>`; prefer a **Running** pod |
| `tools/rollback.py` | Roll back using ReplicaSet **`deployment.kubernetes.io/revision`** history |
| `.github/workflows/call-deploy-api.yml` | Example GitHub Actions workflow calling the API |
| `.env.example` | Sample environment variables |
| `requirements.txt` | Runtime dependencies |

## Core functional modules

### Deployment module

**File**: `tools/deploy.py`

- Accepts app name, container image, namespace, and replicas.
- Creates a Kubernetes `Deployment` with selector and pod template labels `app: <name>`.
- **Note**: Deploying the same `name` in the same namespace again will fail at the API server unless the existing deployment is deleted first.

### Logging module

**File**: `tools/logs.py`

- Lists pods with **`app=<app_name>`** (Kubernetes label selector). With the bundled deploy tool, `app_name` is the same as the Deployment name.
- Prefers a pod in **`Running`** phase; otherwise uses the first pod returned.
- Returns `None` if no pod matches; the HTTP layer responds with **404**.

### Rollback module

**File**: `tools/rollback.py`

- Lists ReplicaSets owned by the Deployment, groups by revision annotation, and **patches the Deployment** so `spec.template` matches the chosen historical ReplicaSet (equivalent intent to **`kubectl rollout undo`**).
- **`revision: 0`** in the JSON body means “previous revision” (second-highest known revision). A positive integer selects a specific revision.
- Requires **at least two** revisions in history when using `revision: 0` (deploy once, change image or patch, then undo).

## API reference

**Base URL (local default)**: `http://127.0.0.1:8000`  
**Interactive docs**: `http://127.0.0.1:8000/docs` (Swagger UI)

Unless `DEVOPS_REQUIRE_AUTH=false`, add **`X-API-Key`** or **`Authorization: Bearer`** to every route except **`GET /health`**.

### `GET /health`

- **Purpose**: Liveness check; does not call Kubernetes; **no auth**.
- **200 response**: `{"status": "ok"}`

### `POST /deploy`

**Roles**: `admin`, `deployer`

**Body (JSON)**:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `name` | string | — | Required; Deployment name and `app` label value |
| `image` | string | — | Required, min length 1 |
| `namespace` | string | `"default"` | Min length 1 |
| `replicas` | integer | `1` | 0–50 |

**Success (202 Accepted)** — async job created:

```json
{"job_id":"…","status":"queued","kind":"deploy","created_at":"…"}
```

Poll **`GET /jobs/{job_id}`** until `status` is `succeeded` or `failed`. On success, **`result`** contains the same payload the synchronous deploy used to return (`status`, `name`, `namespace`, `replicas`, `image`).

**Errors**:

- **401 / 403**: Missing or insufficient auth.
- **422**: Validation error.
- **503**: Kubernetes client could not be configured (job may fail with `failed` and message in **`detail`** after polling).

### `GET /jobs/{job_id}`

**Roles**: `admin`, `deployer`, `viewer`

**200 response**: `job_id`, `status` (`queued` | `running` | `succeeded` | `failed`), `kind`, timestamps, optional `detail` (error message), optional `result`, `request` summary.

**404**: Unknown `job_id`.

### `POST /logs`

**Roles**: `admin`, `deployer`, `viewer`

**Body (JSON)**:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `app_name` | string | — | Value of label **`app`** (e.g. same as Deployment name) |
| `namespace` | string | `"default"` | Min length 1 |

**Success (200)**: `{"app_name":...,"namespace":...,"logs":"<string>"}`

**Errors**:

- **404**: No pod with `app=<app_name>` in the namespace.
- **401 / 403**: Auth.
- **422**: Validation error.
- **503**: Kubernetes unavailable.
- **500**: Other API errors.

### `POST /rollback`

**Roles**: `admin`, `deployer`

**Body (JSON)**:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `app_name` | string | — | Deployment name |
| `namespace` | string | `"default"` | Min length 1 |
| `revision` | integer | `0` | `0` = previous revision; `>0` = specific revision number |

**Success (200)**: `{"status":"rolled_back","name":...,"namespace":...,"to_revision":<int>,"method":"replicaset_history"}`

**Errors**:

- **400**: No rollout history, unknown revision, etc.
- **404**: Deployment not found.
- **401 / 403**: Auth.
- **422**: Validation error.
- **500**: RBAC or patch failure.

### `GET /metrics`

Prometheus text exposition. If **`DEVOPS_METRICS_NO_AUTH=false`** (default), use the same auth as other routes (any role that can access the API). If **`DEVOPS_METRICS_NO_AUTH=true`**, scrapers can call **`/metrics`** without a key (use only on internal networks).

Metrics include `devops_http_requests_total`, `devops_http_request_duration_seconds`, and `devops_http_failures_total` (see `metrics.py`).

### Example `curl` requests

Set a key that matches **`DEVOPS_API_KEYS`** (see `.env.example`):

```bash
export API_KEY='change-me-admin'

curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}'

JOB_ID=$(curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}' | jq -r .job_id)

curl -s "http://127.0.0.1:8000/jobs/$JOB_ID" -H "X-API-Key: $API_KEY"

curl -s -X POST http://127.0.0.1:8000/logs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"app_name":"demo","namespace":"default"}'

curl -s -X POST http://127.0.0.1:8000/rollback \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"app_name":"demo","namespace":"default","revision":0}'

curl -s http://127.0.0.1:8000/metrics -H "X-API-Key: $API_KEY"
```

**JWT example** (requires `DEVOPS_JWT_SECRET` on the server):

```bash
export TOKEN=$(python3 -c "import jwt, time; print(jwt.encode({'sub':'demo','role':'deployer','exp': int(time.time())+300}, 'your-jwt-secret', algorithm='HS256'))")
curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}'
```

## Example test cases

Use these as a **manual test checklist** or as the basis for automated tests (e.g. `pytest` + `httpx` against a running server). Replace URLs, names, and namespaces to match your environment.

### 1. Health check (no cluster required for logic, but server must run)

- **Action**: `GET /health`
- **Expect**: HTTP **200**, body `{"status":"ok"}`

### 2. Auth — missing key when auth enabled

- **Action**: `POST /deploy` with no `X-API-Key` or Bearer token (and `DEVOPS_REQUIRE_AUTH=true`)
- **Expect**: HTTP **401**

### 3. Auth — viewer cannot deploy

- **Action**: `POST /deploy` with a **viewer** API key
- **Expect**: HTTP **403**

### 4. Validation — deploy with invalid replicas

- **Action**: `POST /deploy` with `"replicas": 51` or negative value (with a deployer key)
- **Expect**: HTTP **422**, FastAPI validation error detail

### 5. Validation — empty application name

- **Action**: `POST /deploy` with `"name": ""`
- **Expect**: HTTP **422**

### 6. Kubernetes unavailable (optional)

- **Setup**: Stop Minikube/Kind or point `KUBECONFIG` to an invalid file, restart the server
- **Action**: `POST /deploy` with a valid body and valid API key
- **Expect**: HTTP **202**; poll job until **`failed`** with message about Kubernetes configuration (worker runs after accept)

### 7. Happy path — async deploy, logs, real rollback

- **Action**: `POST /deploy` with deployer/admin key, `name=demo`, `image=nginx:latest`, `namespace=default`, `replicas=2`
- **Expect**: HTTP **202** and a `job_id`; poll `GET /jobs/{job_id}` until **`succeeded`**; `result.status` is `deployed`
- **CLI check**: `kubectl rollout status deploy/demo -n default` succeeds
- **Action**: `POST /logs` with `app_name=demo` (label `app=demo`)
- **Expect**: HTTP **200**, logs contain nginx output
- **Action**: Change the deployment (e.g. `kubectl set image deploy/demo …` or second deploy with different image after delete/recreate) so **two ReplicaSet revisions** exist
- **Action**: `POST /rollback` with `revision: 0`
- **Expect**: HTTP **200**, body includes `rolled_back` and `to_revision`; workload matches prior revision

### 8. Logs — no matching label

- **Setup**: Namespace with no pods labeled `app=ghost`
- **Action**: `POST /logs` with `app_name=ghost`
- **Expect**: HTTP **404**, message mentions label `app=…`

### 9. Deploy — duplicate deployment name

- **Setup**: Successful deploy from case 7
- **Action**: Submit another deploy job with the **same** name without deleting the deployment
- **Expect**: Job ends **`failed`** with Kubernetes conflict / already exists (poll `GET /jobs/...`)

### 10. Custom namespace

- **Setup**: `kubectl create ns test-mcp`
- **Action**: `POST /deploy` with `"namespace":"test-mcp", "name":"api-smoke", ...` and poll job
- **Expect**: Job **succeeded**; `kubectl get deploy -n test-mcp` shows `api-smoke`
- **Follow-up**: `POST /logs` / `POST /rollback` with the same namespace (rollback needs revision history)

### 11. Metrics smoke

- **Action**: `GET /metrics` with a valid key (or with `DEVOPS_METRICS_NO_AUTH=true` and no key)
- **Expect**: `text/plain` body with `devops_http_requests_total` samples

### 12. Swagger / OpenAPI smoke

- **Action**: Open `http://127.0.0.1:8000/docs`, run `/health`, then authorize with a key if your UI supports custom headers (or use **curl** for authenticated routes)
- **Expect**: Behavior matches [API reference](#api-reference)

**Cleanup after cluster tests**:

```bash
kubectl delete deploy demo -n default --ignore-not-found
kubectl delete deploy api-smoke -n test-mcp --ignore-not-found
```

## Screenshots (browser proof)

### Swagger home

<img width="1440" height="248" alt="Screenshot 2026-05-12 at 3 49 55 PM" src="https://github.com/user-attachments/assets/9dbdeb15-25e8-42bd-a1d1-6024b4ba671d" />

### Deploy endpoint — request form

<img width="1440" height="665" alt="Screenshot 2026-05-12 at 3 50 06 PM" src="https://github.com/user-attachments/assets/1cf5c5c3-9918-4cc5-9248-a08e2e9f581f" />

### Deploy endpoint — execute / cURL

<img width="1440" height="900" alt="Screenshot 2026-05-12 at 3 50 15 PM" src="https://github.com/user-attachments/assets/7b464253-9866-4e31-84e9-d47ade77a986" />

### Deploy endpoint — response block

<img width="1440" height="700" alt="Screenshot 2026-05-12 at 3 50 24 PM" src="https://github.com/user-attachments/assets/319bca08-e330-49ec-a65a-2a06612a82a3" />

> **Note:** If any screenshot fails to load, use `/docs` locally — behavior is defined by the code and [API reference](#api-reference) above.

## Real usage and demos

Below is a recording of an AI agent seamlessly interacting with the DevOps MCP Server's Swagger UI to deploy an application, monitor its job status, retrieve its logs, and trigger a rollback:

![AI Agent executing Deploy API using Swagger UI](assets/api_demo_swagger.gif)

### Cluster Proof

While the API was processing the requests, here is the state of the Kubernetes cluster as verified by the terminal:

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

## CI/CD (GitHub Actions)

The workflow **`.github/workflows/call-deploy-api.yml`** shows how to:

- Call **`POST /deploy`** with **`X-API-Key`** from repository secrets.
- Poll **`GET /jobs/{job_id}`** until the job succeeds or fails.

Configure secrets **`DEVOPS_API_BASE`** (e.g. `https://your-api.example.com` with no trailing slash) and **`DEVOPS_API_KEY`**. Use **workflow_dispatch** to run manually with inputs for image and deployment name.

## Technology stack

- **Programming language**: Python
- **API framework**: FastAPI
- **Validation**: Pydantic (v2 via FastAPI)
- **Auth**: API keys + **PyJWT** (HS256 Bearer tokens)
- **Metrics**: **prometheus-client** (`/metrics`)
- **Config**: **python-dotenv** (loads `.env` from the project root)
- **Orchestration client**: `kubernetes` Python SDK
- **ASGI server**: Uvicorn
- **Target workloads**: Container images on Kubernetes (Docker-style images)
- **Local clusters**: Minikube / Kind (recommended)

## Setup and run

### Prerequisites

- Python 3.10+ recommended
- A working Kubernetes context in your kubeconfig (e.g. Minikube/Kind), **or** in-cluster credentials if you run the server inside Kubernetes

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure auth (optional for local; required for production)

```bash
cp .env.example .env
# Edit .env: default example uses DEVOPS_REQUIRE_AUTH=false for quickstart.
# For production, set DEVOPS_REQUIRE_AUTH=true and DEVOPS_API_KEYS (see comments in .env.example).
```

### Start the server

```bash
uvicorn app:app --reload
```

Then open the interactive docs at `http://127.0.0.1:8000/docs`. If **`DEVOPS_REQUIRE_AUTH=true`**, send **`X-API-Key`** or **Bearer JWT** on protected routes; with the default **`false`**, all roles are accepted without a key (local use only).

## Local cluster setup (Minikube + Docker Desktop)

If no Kubernetes cluster is available locally:

```bash
brew install minikube
open -a Docker
minikube start --driver=docker
kubectl config use-context minikube
kubectl get nodes
```

`kubectl` must be able to connect before calling `/deploy`, `/logs`, or `/rollback`.

## End-to-end test flow

```bash
export API_KEY='change-me-admin'   # must match DEVOPS_API_KEYS on the server

curl -s http://127.0.0.1:8000/health

JOB=$(curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}')
echo "$JOB" | jq .
JOB_ID=$(echo "$JOB" | jq -r .job_id)

for i in $(seq 1 120); do
  ST=$(curl -s "http://127.0.0.1:8000/jobs/$JOB_ID" -H "X-API-Key: $API_KEY" | jq -r .status)
  echo "job status: $ST"
  if [ "$ST" = "succeeded" ] || [ "$ST" = "failed" ]; then break; fi
  sleep 1
done
curl -s "http://127.0.0.1:8000/jobs/$JOB_ID" -H "X-API-Key: $API_KEY" | jq .

kubectl rollout status deploy/demo -n default

curl -s -X POST http://127.0.0.1:8000/logs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"app_name":"demo","namespace":"default"}'

# Rollback needs at least two revisions — e.g. change image once, then:
curl -s -X POST http://127.0.0.1:8000/rollback \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"app_name":"demo","namespace":"default","revision":0}'
```

Cleanup:

```bash
kubectl delete deploy demo -n default --ignore-not-found
```

## Security considerations (recommended enhancements)

Built in today: **HTTP authentication** (API key or JWT), **role-based authorization**, structured access logs, and **Prometheus** counters.

For production hardening, still add:

- **Kubernetes RBAC** and least-privilege service accounts for the server’s kube identity
- **Namespace allowlists** in the API layer (reject unknown namespaces)
- **Stricter input policy** (allowed image registries, name patterns)
- **mTLS or OAuth2** at the edge (reverse proxy in front of Uvicorn)
- **Persistent audit store** (who deployed what — extend logging to SIEM)

## Future enhancements

- Multi-cluster routing and per-cluster credentials
- Natural language interface via AI agents (MCP wrapper on top of this HTTP API)
- Canary / blue-green strategies beyond single Deployment rollback
- Optional **`pytest`** + Kind integration tests in CI
- Redis-backed job store for multi-replica API servers
