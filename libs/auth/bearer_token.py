from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from starlette.responses import JSONResponse
import jwt
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
            payload = jwt.decode(token, key=AUTH_SECRET_KEY, algorithms=[ALGORITHM])

            email = payload.get("email")
            if not email:
                return JSONResponse(status_code=401, content="Invalid token: missing email.")

            issuer = payload.get("iss")
            if not issuer:
                return JSONResponse(status_code=401, content="Invalid token: missing issuer.")


        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content="Token has expired.")
        except jwt.InvalidTokenError as err:
            return JSONResponse(status_code=401, content=f"Invalid token: {str(err)}")

        # Return the token if it's valid
        return token

