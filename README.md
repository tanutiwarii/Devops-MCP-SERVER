# DevOps MCP Server (Python) — Automated Deployment & Monitoring

## Project title

**DevOps MCP Server using Python for Automated Deployment and Monitoring**

## What this project is

This repository is a small **FastAPI** service that exposes three DevOps-style operations as HTTP endpoints: **deploy** a Kubernetes `Deployment`, **fetch logs** from a matching pod, and **trigger a rollout restart** (implemented as a deployment patch). It is intended as a bridge between higher-level automation (including AI agents that can call structured tools) and a real Kubernetes cluster using the official **Kubernetes Python client**.

The server does **not** implement the full MCP wire protocol by itself; it is an **HTTP API** that you can wrap or call from an MCP host. The name reflects the goal: *model-context-friendly* operations with predictable JSON inputs and outputs.

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
User / AI Agent
        ↓
   API Server (FastAPI) — app.py
        ↓
   Tool Layer — tools/deploy.py, tools/logs.py, tools/rollback.py
        ↓
   Kubernetes client — k8s_client.py
        ↓
   Kubernetes Cluster
```

### How Kubernetes is configured

`k8s_client.py` loads configuration in this order:

1. **Kubeconfig** on the machine running the server (typical for Minikube, Kind, or `kubectl`-configured clusters).
2. If that fails, **in-cluster** config (when the app runs as a pod with a service account).

If neither works, endpoints that touch the cluster return **503** with a message explaining that Kubernetes is not reachable.

## Project layout

| Path | Role |
|------|------|
| `app.py` | FastAPI app, request models, routes, HTTP error mapping |
| `k8s_client.py` | Lazy singleton Kubernetes API clients (`AppsV1Api`, `CoreV1Api`) |
| `tools/deploy.py` | Create a `Deployment` with label `app: <name>` |
| `tools/logs.py` | List pods in a namespace; return logs for the first pod whose name **contains** `app_name` |
| `tools/rollback.py` | Patch the deployment pod template to force a rollout (annotation-based restart) |
| `requirements.txt` | Runtime dependencies |

## Core functional modules

### Deployment module

**File**: `tools/deploy.py`

- Accepts app name, container image, namespace, and replicas.
- Creates a Kubernetes `Deployment` with selector and pod template labels `app: <name>`.
- **Note**: Deploying the same `name` in the same namespace again will fail at the API server unless the existing deployment is deleted first.

### Logging module

**File**: `tools/logs.py`

- Lists pods in a namespace and returns logs for the **first** pod whose **metadata name contains** the string `app_name` (substring match, not exact label match).
- Returns `None` if no pod matches; the HTTP layer turns that into **404**.

### Rollback module

**File**: `tools/rollback.py`

- Patches the named `Deployment` to add/update a pod-template annotation so Kubernetes performs a **rollout restart**-style recreation of pods.
- This is **not** a multi-revision `kubectl rollout undo`; it is a controlled restart via spec change.

## API reference

**Base URL (local default)**: `http://127.0.0.1:8000`  
**Interactive docs**: `http://127.0.0.1:8000/docs` (Swagger UI)

### `GET /health`

- **Purpose**: Liveness check; does not call Kubernetes.
- **200 response**: `{"status": "ok"}`

### `POST /deploy`

**Body (JSON)**:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `name` | string | — | Required, min length 1 (deployment name) |
| `image` | string | — | Required, min length 1 |
| `namespace` | string | `"default"` | Min length 1 |
| `replicas` | integer | `1` | 0–50 |

**Success (200)**: `{"status":"deployed","name":...,"namespace":...,"replicas":...,"image":...}`

**Errors**:

- **422**: Validation error (e.g., empty `name`, `replicas` out of range).
- **503**: Kubernetes client could not be configured (no kubeconfig / not in cluster).
- **500**: Other failures (e.g., deployment already exists, RBAC denied, invalid namespace).

### `POST /logs`

**Body (JSON)**:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `app_name` | string | — | Required; substring matched against pod **names** |
| `namespace` | string | `"default"` | Min length 1 |

**Success (200)**: `{"app_name":...,"namespace":...,"logs":"<string>"}`

**Errors**:

- **404**: No pod in the namespace has a name containing `app_name`.
- **422**: Validation error.
- **503**: Kubernetes unavailable.
- **500**: Other API errors.

### `POST /rollback`

**Body (JSON)**:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `app_name` | string | — | Deployment **name** (must exist) |
| `namespace` | string | `"default"` | Min length 1 |

**Success (200)**: `{"status":"rollback triggered","name":...,"namespace":...}`

**Errors**:

- **422**: Validation error.
- **503**: Kubernetes unavailable.
- **500**: Deployment missing, RBAC, or patch failure.

### Example `curl` requests

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}'

curl -s -X POST http://127.0.0.1:8000/logs \
  -H "Content-Type: application/json" \
  -d '{"app_name":"demo","namespace":"default"}'

curl -s -X POST http://127.0.0.1:8000/rollback \
  -H "Content-Type: application/json" \
  -d '{"app_name":"demo","namespace":"default"}'
```

## Example test cases

Use these as a **manual test checklist** or as the basis for automated tests (e.g. `pytest` + `httpx` against a running server). Replace URLs, names, and namespaces to match your environment.

### 1. Health check (no cluster required for logic, but server must run)

- **Action**: `GET /health`
- **Expect**: HTTP **200**, body `{"status":"ok"}`

### 2. Validation — deploy with invalid replicas

- **Action**: `POST /deploy` with `"replicas": 51` or negative value
- **Expect**: HTTP **422**, FastAPI validation error detail

### 3. Validation — empty application name

- **Action**: `POST /deploy` with `"name": ""`
- **Expect**: HTTP **422**

### 4. Kubernetes unavailable (optional)

- **Setup**: Stop Minikube/Kind or point `KUBECONFIG` to an invalid file, restart the server
- **Action**: `POST /deploy` with a valid body
- **Expect**: HTTP **503**, detail mentions Kubernetes configuration

### 5. Happy path — deploy, verify rollout, logs, rollback

- **Action**: `POST /deploy` with `name=demo`, `image=nginx:latest`, `namespace=default`, `replicas=2`
- **Expect**: HTTP **200**, `status` is `deployed`
- **CLI check**: `kubectl rollout status deploy/demo -n default` succeeds
- **Action**: `POST /logs` with `app_name=demo` (substring of pod name like `demo-...`)
- **Expect**: HTTP **200**, `logs` contains nginx startup text or access logs
- **Action**: `POST /rollback` with `app_name=demo`
- **Expect**: HTTP **200**; `kubectl get pods -n default` shows new pod ages after rollout

### 6. Logs — no matching pod

- **Setup**: Use a namespace with no workloads, or `app_name` that matches no pod name substring
- **Action**: `POST /logs` with that `app_name` / `namespace`
- **Expect**: HTTP **404**, detail indicates no matching pod

### 7. Deploy — duplicate deployment name

- **Setup**: Successful deploy from case 5
- **Action**: Repeat the **same** `POST /deploy` without deleting the deployment
- **Expect**: HTTP **500** (Kubernetes rejects create) — useful for testing idempotency gaps

### 8. Custom namespace

- **Setup**: `kubectl create ns test-mcp` (or use an existing non-default namespace)
- **Action**: `POST /deploy` with `"namespace":"test-mcp", "name":"api-smoke", ...`
- **Expect**: HTTP **200**; `kubectl get deploy -n test-mcp` shows `api-smoke`
- **Follow-up**: `POST /logs` and `POST /rollback` with the same namespace and matching `app_name` / deployment name

### 9. Single-replica edge case for logs

- **Action**: Deploy with `replicas: 1`, then call `/logs`
- **Expect**: Logs returned from the only pod whose name contains `app_name`

### 10. Swagger / OpenAPI smoke

- **Action**: Open `http://127.0.0.1:8000/docs`, execute `/health` and one `POST` from the UI
- **Expect**: Responses match the sections above; schemas match [API reference](#api-reference)

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

## Technology stack

- **Programming language**: Python
- **API framework**: FastAPI
- **Validation**: Pydantic (v2 via FastAPI)
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

### Start the server

```bash
uvicorn app:app --reload
```

Then open the interactive docs at `http://127.0.0.1:8000/docs`.

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
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/deploy \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","image":"nginx:latest","namespace":"default","replicas":1}'

kubectl rollout status deploy/demo -n default

curl -s -X POST http://127.0.0.1:8000/logs \
  -H "Content-Type: application/json" \
  -d '{"app_name":"demo","namespace":"default"}'

curl -s -X POST http://127.0.0.1:8000/rollback \
  -H "Content-Type: application/json" \
  -d '{"app_name":"demo","namespace":"default"}'
```

Cleanup:

```bash
kubectl delete deploy demo -n default --ignore-not-found
```

## Security considerations (recommended enhancements)

For safe operation in real environments, add:

- **Role-based access control (RBAC)** and least-privilege Kubernetes service accounts
- **Namespace restrictions** (allowlist) to prevent cross-namespace operations
- **Input validation and sanitization** (expand current validation rules; restrict allowed images or names if needed)
- **Audit logging** for every operation (who/what/when/where)
- **Authentication** on the HTTP API (API keys, mTLS, or reverse proxy auth) before exposing beyond localhost

## Future enhancements

- Integration with CI/CD tools (e.g., GitHub Actions)
- Monitoring with Prometheus and Grafana
- Multi-cluster support
- Natural language interface via AI agents
- Version-based and progressive rollback strategies (canary/blue-green)
- Optional automated test suite in-repo (`pytest`) wired to a disposable Kind cluster
