from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from starlette.concurrency import run_in_threadpool


bearer_scheme = HTTPBearer(auto_error=False)


class FirebaseAuth:
    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ) -> Dict[str, Any]:
        if credentials is None:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Bearer token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            claims = await run_in_threadpool(
                auth.verify_id_token,
                credentials.credentials,
            )
        except auth.CertificateFetchError as exc:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable.",
            ) from exc
        except (auth.InvalidIdTokenError, ValueError) as exc:
            # Includes expired and otherwise invalid ID tokens.
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return claims