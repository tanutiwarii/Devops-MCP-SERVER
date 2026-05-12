from __future__ import annotations

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

_apps_v1: client.AppsV1Api | None = None
_core_v1: client.CoreV1Api | None = None


def init_k8s_clients() -> tuple[client.AppsV1Api, client.CoreV1Api]:
    """
    Initialize Kubernetes API clients.

    Tries local kubeconfig first (Minikube/Kind/dev), then in-cluster config.
    """
    try:
        config.load_kube_config()
        return client.AppsV1Api(), client.CoreV1Api()
    except ConfigException as kubeconfig_err:
        try:
            config.load_incluster_config()
            return client.AppsV1Api(), client.CoreV1Api()
        except ConfigException as incluster_err:
            raise RuntimeError(
                "Kubernetes configuration is not available. "
                "Fix by ensuring `kubectl get pods` works (start Kind/Minikube or set a valid kubecontext), "
                "or run this server inside a cluster with a ServiceAccount. "
                f"(kubeconfig error: {kubeconfig_err}; in-cluster error: {incluster_err})"
            ) from incluster_err


def get_k8s_clients() -> tuple[client.AppsV1Api, client.CoreV1Api]:
    global _apps_v1, _core_v1
    if _apps_v1 is None or _core_v1 is None:
        _apps_v1, _core_v1 = init_k8s_clients()
    return _apps_v1, _core_v1