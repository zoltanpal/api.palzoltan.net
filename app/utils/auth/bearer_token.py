from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import Request

from config import AUTH_SECRET_KEY

ALGORITHM = "HS256"


class BearerAuth(HTTPBearer):
    """
    FastAPI dependency that validates a Bearer JWT and returns its decoded payload.
    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Dict[str, Any]:
        credentials: Optional[HTTPAuthorizationCredentials] = await super().__call__(request)

        if credentials is None:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Missing authorization header",
            )

        token = credentials.credentials

        try:
            payload = jwt.decode(token, key=AUTH_SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Token has expired")
        except jwt.InvalidTokenError as err:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail=f"Invalid token: {err}",
            )

        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Invalid token: missing email",
            )

        issuer = payload.get("iss")
        if not issuer:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Invalid token: missing issuer",
            )

        return payload  # or: return token
