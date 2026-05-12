from __future__ import annotations

from kubernetes import client

from k8s_client import get_k8s_clients


def deploy_app(name: str, image: str, namespace: str = "default", replicas: int = 1) -> dict:
    apps_v1, _ = get_k8s_clients()
    container = client.V1Container(
        name=name,
        image=image
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": name}),
        spec=client.V1PodSpec(containers=[container])
    )

    spec = client.V1DeploymentSpec(
        replicas=replicas,
        selector=client.V1LabelSelector(match_labels={"app": name}),
        template=template
    )

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=name),
        spec=spec
    )

    apps_v1.create_namespaced_deployment(
        namespace=namespace,
        body=deployment
    )

    return {"status": "deployed", "name": name, "namespace": namespace, "replicas": replicas, "image": image}