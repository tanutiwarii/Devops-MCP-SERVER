from __future__ import annotations

from k8s_client import get_k8s_clients


def rollback(app_name: str, namespace: str = "default") -> dict:
    apps_v1, _ = get_k8s_clients()
    apps_v1.patch_namespaced_deployment(
        name=app_name,
        namespace=namespace,
        body={
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "restart": "true"
                        }
                    }
                }
            }
        }
    )

    return {"status": "rollback triggered", "name": app_name, "namespace": namespace}