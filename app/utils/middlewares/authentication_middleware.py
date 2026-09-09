from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, Iterable, Optional, Tuple

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import AUTH_SECRET_KEY

ALGORITHM = "HS256"

# You can expand this as needed (health checks, metrics, etc.)
EXCLUDED_PREFIXES: Tuple[str, ...] = ("/docs",)
EXCLUDED_PATHS: Tuple[str, ...] = ("/openapi.json", "/swagger.json")


def _is_excluded(path: str) -> bool:
    return path in EXCLUDED_PATHS or any(path.startswith(p) for p in EXCLUDED_PREFIXES)


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=HTTPStatus.UNAUTHORIZED,
        content={"detail": detail},
    )


def _extract_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """
    Returns the token if header is a valid Bearer header, otherwise None.
    Accepts e.g. 'Bearer <token>' (case-insensitive).
    """
    if not auth_header:
        return None

    # split on whitespace, tolerate multiple spaces
    parts = auth_header.strip().split()
    if len(parts) != 2:
        return None

    scheme, token = parts[0], parts[1]
    if scheme.lower() != "bearer" or not token:
        return None

    return token


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _is_excluded(request.url.path):
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("Authorization"))
        if token is None:
            return _unauthorized(
                "Missing or invalid Authorization header (expected: Bearer <token>)"
            )

        try:
            payload: Dict[str, Any] = jwt.decode(token, key=AUTH_SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            return _unauthorized("Token has expired")
        except jwt.InvalidTokenError as err:
            return _unauthorized(f"Invalid token: {err}")

        email = payload.get("email")
        if not email:
            return _unauthorized("Invalid token: missing email")

        issuer = payload.get("iss")
        if not issuer:
            return _unauthorized("Invalid token: missing issuer")

        # Make it available downstream (routes, dependencies, etc.)
        request.state.user = {
            "email": email,
            "issuer": issuer,
            "payload": payload,
            "token": token,  # keep if useful; remove if you don't want it
        }

        return await call_next(request)
