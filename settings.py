from __future__ import annotations

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _optional_non_empty(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime configuration from environment variables."""

    require_auth: bool
    api_keys: dict[str, str]
    jwt_secret: str | None
    jwt_algorithm: str
    metrics_no_auth: bool


def load_settings() -> Settings:
    # Load `.env` from the current working directory (does not override existing exports).
    load_dotenv()

    raw = os.environ.get("DEVOPS_API_KEYS")
    if raw is None or not str(raw).strip():
        raw = "{}"
    else:
        raw = str(raw).strip()
    try:
        parsed = json.loads(raw)
        api_keys = {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        api_keys = {}

    return Settings(
        # Default off so `uvicorn` works without a `.env`; set DEVOPS_REQUIRE_AUTH=true for production.
        require_auth=_env_bool("DEVOPS_REQUIRE_AUTH", False),
        api_keys=api_keys,
        jwt_secret=_optional_non_empty(os.environ.get("DEVOPS_JWT_SECRET")),
        jwt_algorithm=os.environ.get("DEVOPS_JWT_ALGORITHM", "HS256"),
        metrics_no_auth=_env_bool("DEVOPS_METRICS_NO_AUTH", False),
    )


def validate_auth_config(s: Settings) -> None:
    if not s.require_auth:
        return
    if s.api_keys or s.jwt_secret:
        return
    raise RuntimeError(
        "DEVOPS_REQUIRE_AUTH is true but no credentials are configured. "
        "Set DEVOPS_API_KEYS (JSON object: {\"your-secret\":\"admin\"}) and/or DEVOPS_JWT_SECRET, "
        "or set DEVOPS_REQUIRE_AUTH=false for local-only development."
    )
