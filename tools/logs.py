from __future__ import annotations

from k8s_client import get_k8s_clients


def get_logs(app_label: str, namespace: str = "default") -> str | None:
    """
    Fetch logs for a pod selected by the standard Deployment label ``app=<app_label>``.

    Pods are chosen in preference order: first ``Running`` pod, otherwise the first listed pod.
    """
    _, core_v1 = get_k8s_clients()
    pods = core_v1.list_namespaced_pod(namespace, label_selector=f"app={app_label}")
    if not pods.items:
        return None

    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    chosen = running[0] if running else pods.items[0]
    return core_v1.read_namespaced_pod_log(name=chosen.metadata.name, namespace=namespace)
