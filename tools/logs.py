from __future__ import annotations

from k8s_client import get_k8s_clients


def get_logs(app_name: str, namespace: str = "default") -> str | None:
    _, core_v1 = get_k8s_clients()
    pods = core_v1.list_namespaced_pod(namespace)

    for pod in pods.items:
        if app_name in pod.metadata.name:
            return core_v1.read_namespaced_pod_log(
                name=pod.metadata.name,
                namespace=namespace
            )

    return None