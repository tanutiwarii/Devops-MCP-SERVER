from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request

from settings import Settings, load_settings, validate_auth_config

ROLES_DEPLOY = frozenset({"admin", "deployer"})
ROLES_LOGS = frozenset({"admin", "deployer", "viewer"})


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    auth_method: str


def authenticate(
    settings: Settings,
    x_api_key: str | None,
    authorization: str | None,
) -> Principal:
    if not settings.require_auth:
        return Principal(subject="anonymous", role="admin", auth_method="disabled")

    if authorization and authorization.lower().startswith("bearer "):
        if not settings.jwt_secret:
            raise HTTPException(status_code=401, detail="JWT is not configured on this server.")
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}") from e
        role = str(payload.get("role", "")).strip()
        if role not in ROLES_LOGS:
            raise HTTPException(status_code=401, detail="JWT missing or invalid role claim.")
        sub = str(payload.get("sub", "jwt-user"))
        return Principal(subject=sub, role=role, auth_method="jwt")

    if x_api_key:
        role = settings.api_keys.get(x_api_key)
        if not role:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if role not in ROLES_LOGS:
            raise HTTPException(status_code=500, detail="Misconfigured API key role.")
        masked = x_api_key[:4] + "…" if len(x_api_key) > 4 else "****"
        return Principal(subject=f"apikey:{masked}", role=role, auth_method="api_key")

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Send X-API-Key or Authorization: Bearer <JWT>.",
    )


async def get_principal(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Principal:
    settings: Settings = load_settings()
    principal = authenticate(settings, x_api_key, authorization)
    request.state.principal = principal
    return principal


def enforce_metrics_scrape(
    settings: Settings,
    x_api_key: str | None,
    authorization: str | None,
) -> None:
    if settings.metrics_no_auth:
        return
    principal = authenticate(settings, x_api_key, authorization)
    if principal.role not in ROLES_LOGS:
        raise HTTPException(status_code=403, detail="Insufficient role to access /metrics.")


def require_roles(*allowed: str):
    allowed_set = frozenset(allowed)

    async def _dep(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.role not in allowed_set:
            raise HTTPException(
                status_code=403,
                detail=f"This operation requires one of roles: {', '.join(sorted(allowed_set))}.",
            )
        return principal

    return _dep


def startup_validate_auth() -> None:
    s = load_settings()
    validate_auth_config(s)
