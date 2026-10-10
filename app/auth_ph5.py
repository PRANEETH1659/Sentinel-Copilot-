# PURPOSE OF THE FILE -- RBAC: who are you (authentication) and what may you
# do (authorization)?
#
# Every request carries an API key in the `X-API-Key` header. The key maps to
# a USER (for the audit trail) and a ROLE. Roles map to PERMISSIONS:
#
#     analyst -> ask                (all /ask* endpoints)
#     admin   -> ask, audit         (+ read the audit log via GET /audit)
#
# Endpoints ask for a PERMISSION, not a role ("needs 'audit'"), so adding a
# new role later (say "auditor" -> audit only) is one line in PERMISSIONS,
# with no endpoint code changes.
#
# Two different refusals, on purpose:
#   401 Unauthorized -> no key / unknown key   ("I don't know who you are")
#   403 Forbidden    -> valid key, wrong role  ("I know you; you can't do this")
# Both are written to the audit log with status "denied".
#
# Keys are configured with the API_KEYS env var (see app/config_ph1.py).
# Only SHA-256 hashes of the keys are kept in memory, so a crash dump or a
# debugger never shows a usable key. Looking up a hash in a dict also avoids
# comparing the secret character by character.

import hashlib
import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from . import config_ph1 as config
from .audit_ph5 import record_audit

log = logging.getLogger("sentinelcopilot.auth")

PERMISSIONS: dict[str, set[str]] = {
    "analyst": {"ask"},
    "admin": {"ask", "audit"},
}

# Used ONLY when API_KEYS is not set, so the project still runs out of the box
# on a fresh clone. A warning is logged at startup; never ship with these.
DEV_API_KEYS = "dev-analyst-key:analyst1:analyst,dev-admin-key:admin1:admin"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller of one request."""
    user: str
    role: str


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_api_keys(raw: str) -> dict[str, Principal]:
    """'key:user:role,key:user:role' -> {sha256(key): Principal}.
    Raises ValueError on a malformed entry or unknown role, so a typo in the
    config fails loudly at startup instead of silently locking people out."""
    table: dict[str, Principal] = {}
    for entry in filter(None, (e.strip() for e in raw.split(","))):
        parts = entry.split(":")
        if len(parts) != 3 or not all(p.strip() for p in parts):
            raise ValueError(f"bad API_KEYS entry (want key:user:role): {entry.split(':')[0][:4]}...")
        key, user, role = (p.strip() for p in parts)
        if role not in PERMISSIONS:
            raise ValueError(f"unknown role {role!r} for user {user!r}; known: {sorted(PERMISSIONS)}")
        table[_hash(key)] = Principal(user=user, role=role)
    return table


def _load_keys() -> dict[str, Principal]:
    raw = config.API_KEYS
    if not raw:
        log.warning("API_KEYS is not set - using built-in DEV keys. Set API_KEYS before sharing this API.")
        raw = DEV_API_KEYS
    return parse_api_keys(raw)


_KEYS = _load_keys()

# Declaring the header this way also adds an "Authorize" button to /docs.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _client_of(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _deny(request: Request, status_code: int, detail: str, principal: Principal | None):
    record_audit(
        endpoint=request.url.path.lstrip("/"),
        question="",
        client=_client_of(request),
        user=principal.user if principal else "anonymous",
        role=principal.role if principal else "none",
        status="denied",
        error=f"{status_code} {detail}",
    )
    headers = {"WWW-Authenticate": "APIKey"} if status_code == 401 else None
    raise HTTPException(status_code=status_code, detail=detail, headers=headers)


def authenticate(request: Request, api_key: str | None = Depends(_api_key_header)) -> Principal:
    """Who are you? Any valid key passes."""
    principal = _KEYS.get(_hash(api_key)) if api_key else None
    if principal is None:
        _deny(request, 401, "missing or invalid API key (send it in the X-API-Key header)", None)
    return principal


def require(permission: str):
    """What may you do? Use as: `principal: Principal = Depends(require("ask"))`."""

    def checker(request: Request, principal: Principal = Depends(authenticate)) -> Principal:
        if permission not in PERMISSIONS.get(principal.role, set()):
            _deny(request, 403, f"role '{principal.role}' lacks permission '{permission}'", principal)
        return principal

    return checker
