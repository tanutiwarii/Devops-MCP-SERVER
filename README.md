# DevOps MCP Server (Python) — Automated Deployment & Monitoring

## Project Title

**DevOps MCP Server using Python for Automated Deployment and Monitoring**

## Abstract

The DevOps MCP (Model Context Protocol) Server is a backend system designed to expose DevOps operations as structured, callable tools that can be invoked by AI systems or external clients. The server acts as an intermediary between user intent and infrastructure execution by translating high-level commands into concrete operations on containerized environments.

This project leverages Kubernetes and Docker to automate application deployment, log retrieval, and rollback mechanisms through a Python-based API interface.

## Objectives

- **Expose DevOps functionalities as structured APIs (tools)**: deployment, log retrieval, rollback
- **Automate deployment and management of containerized applications** on Kubernetes
- **Enable seamless interaction between AI systems and infrastructure** via callable endpoints
- **Ensure safe and controlled execution** of DevOps operations

## Problem Statement

Modern DevOps workflows require engineers to manually execute commands using CLI tools and dashboards. This process can be:

- **Time-consuming**
- **Error-prone**
- **Hard to integrate** with AI-driven systems

There is a need for a system that abstracts infrastructure operations into programmable and intelligent interfaces.

## Proposed Solution

This repository implements a Python-based server that:

- Accepts structured requests (e.g., deploy application, fetch logs, trigger rollback)
- Routes requests to predefined tool modules
- Uses the Kubernetes Python client to execute operations on a cluster
- Returns structured responses suitable for AI agents and automation clients

## System Architecture

High-level flow:

```text
User / AI Agent
        ↓
   API Server (FastAPI)
        ↓
   Tool Layer (deploy, logs, rollback)
        ↓
Kubernetes Client (Python SDK)
        ↓
   Kubernetes Cluster
```

## Core Functional Modules

### Deployment Module

**File**: `tools/deploy.py`

- Accepts app name, container image, namespace, and replicas
- Creates a Kubernetes `Deployment`
- Returns a structured deployment result payload

### Logging Module

**File**: `tools/logs.py`

- Lists pods in a namespace and finds pods matching `app_name`
- Fetches logs for the first matching pod
- Returns log text

### Rollback Module

**File**: `tools/rollback.py`

- Triggers a rollout-like restart by patching the Deployment pod template annotations
- Returns a structured response indicating rollback trigger

## API Surface (Callable Tools)

**FastAPI app**: `app.py`

- `GET /health`: health check
- `POST /deploy`: deploy an app
- `POST /logs`: fetch logs for an app
- `POST /rollback`: trigger rollback/restart for an app

Example requests:

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

## Screenshots (Browser Proof)

### Swagger Home
![Swagger Home]('/Users/tannutiwari/Downloads/screenshot/Screenshot 2026-05-12 at 3.49.55 PM.png')

### Deploy Endpoint - Request Form
![Deploy Request Form](/Users/tannutiwari/.cursor/projects/Users-tannutiwari-Downloads-Projects-MCP-Server/assets/Screenshot_2026-05-12_at_3.50.06_PM-ff951ccd-1d31-47b5-9068-16e362e35e98.png)

### Deploy Endpoint - Execute / cURL
![Deploy Execute Curl](/Users/tannutiwari/.cursor/projects/Users-tannutiwari-Downloads-Projects-MCP-Server/assets/Screenshot_2026-05-12_at_3.50.15_PM-41fd2a15-6d66-4ad8-85a1-bb359a33dca4.png)

### Deploy Endpoint - Response Block
![Deploy Response Block](/Users/tannutiwari/.cursor/projects/Users-tannutiwari-Downloads-Projects-MCP-Server/assets/Screenshot_2026-05-12_at_3.50.24_PM-4c4c198a-fd0b-41c4-8ea9-c8dbaf18d39b.png)


## Technology Stack

- **Programming Language**: Python
- **API Framework**: FastAPI
- **Containerization**: Docker (target workloads)
- **Orchestration**: Kubernetes
- **Local Testing**: Minikube / Kind (recommended)

## Setup & Run

### Prerequisites

- Python 3.10+ recommended
- A working Kubernetes context in your kubeconfig (e.g. Minikube/Kind)

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

## Security Considerations (Recommended Enhancements)

For safe operation in real environments, add:

- **Role-based access control (RBAC)** and least-privilege Kubernetes service accounts
- **Namespace restrictions** (allowlist) to prevent cross-namespace operations
- **Input validation & sanitization** (expand current validation rules)
- **Audit logging** for every operation (who/what/when/where)

## Future Enhancements

- Integration with CI/CD tools (e.g., GitHub Actions)
- Monitoring with Prometheus and Grafana
- Multi-cluster support
- Natural language interface via AI agents
- Version-based and progressive rollback strategies (canary/blue-green)
## Local Cluster Setup (Minikube + Docker Desktop)

If no Kubernetes cluster is available locally:

```bash
brew install minikube
open -a Docker
minikube start --driver=docker
kubectl config use-context minikube
kubectl get nodes
```

`kubectl` must be able to connect before calling `/deploy`, `/logs`, or `/rollback`.

## End-to-End Test Flow

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
