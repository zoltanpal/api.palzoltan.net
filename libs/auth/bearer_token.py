from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from starlette.responses import JSONResponse
from jose import JWTError, jwt
from http import HTTPStatus
from config import AUTH_SECRET_KEY

# Secret key and algorithm (for demo purposes)
ALGORITHM = "HS256"


class BearerAuth(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(
            HTTPBearer, self
        ).__call__(request)

        if not credentials:
            return JSONResponse(
                {"detail": "Missing authorization header"},
                status_code=HTTPStatus.UNAUTHORIZED,
            )

        token = credentials.credentials
        try:
            # Decode the JWT token
            payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("email")
            issuer = payload.get("iss")

            if email is None or issuer is None:
                return JSONResponse(
                    {"detail": "Invalid token. Missing email or issuer."},
                    status_code=HTTPStatus.UNAUTHORIZED,
                )

        except JWTError:
            return JSONResponse(
                {"detail": "Invalid token or expired token"},
                status_code=HTTPStatus.UNAUTHORIZED,
            )

        # Return the token if it's valid
        return token

