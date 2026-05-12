from __future__ import annotations

from kubernetes.client import ApiException

from k8s_client import get_k8s_clients


def rollback_deployment(name: str, namespace: str = "default", revision: int = 0) -> dict:
    """
    Roll back a Deployment using ReplicaSet revision history (same source as ``kubectl rollout undo``).

    - ``revision=0`` rolls back to the previous revision (second-highest known revision).
    - ``revision>0`` rolls back to that specific ``deployment.kubernetes.io/revision`` number.
    """
    apps_v1, _ = get_k8s_clients()
    try:
        dep = apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            raise RuntimeError(f"Deployment {name!r} not found in namespace {namespace!r}.") from e
        raise

    sel = dep.spec.selector.match_labels or {}
    label_selector = ",".join(f"{k}={v}" for k, v in sorted(sel.items()))
    rs_list = apps_v1.list_namespaced_replica_set(namespace=namespace, label_selector=label_selector)

    by_revision: dict[int, object] = {}
    for rs in rs_list.items:
        if not rs.metadata.owner_references:
            continue
        if not any(ref.kind == "Deployment" and ref.name == name for ref in rs.metadata.owner_references):
            continue
        raw_rev = (rs.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0")
        try:
            rev = int(raw_rev)
        except ValueError:
            continue
        if rev <= 0:
            continue
        existing = by_revision.get(rev)
        if existing is None:
            by_revision[rev] = rs
            continue
        prev_ts = existing.metadata.creation_timestamp
        cur_ts = rs.metadata.creation_timestamp
        if cur_ts and prev_ts and cur_ts > prev_ts:
            by_revision[rev] = rs

    if len(by_revision) < 2 and revision == 0:
        raise RuntimeError(
            "No rollout history to undo (need at least two ReplicaSet revisions). "
            "Apply a change to the Deployment first so a new revision is recorded."
        )

    sorted_revs = sorted(by_revision.keys())
    if revision == 0:
        target_rev = sorted_revs[-2]
    else:
        if revision not in by_revision:
            raise RuntimeError(
                f"Revision {revision} not found. Known revisions: {', '.join(map(str, sorted_revs))}."
            )
        target_rev = revision

    target_rs = by_revision[target_rev]
    template = target_rs.spec.template
    body = {"spec": {"template": apps_v1.api_client.sanitize_for_serialization(template)}}

    apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=body)

    return {
        "status": "rolled_back",
        "name": name,
        "namespace": namespace,
        "to_revision": target_rev,
        "method": "replicaset_history",
    }
