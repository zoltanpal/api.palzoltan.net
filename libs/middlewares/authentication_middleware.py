from fastapi import FastAPI, HTTPException

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import AUTH_SECRET_KEY

# Secret key to decode the JWT token (this should be kept safe in production)
ALGORITHM = "HS256"


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Exclude /docs and /openapi.json from authentication check
        if request.url.path.startswith(
                "/docs") or request.url.path == "/openapi.json" or request.url.path == "/swagger.json":
            # Allow access to these routes without any validation
            response = await call_next(request)
            return response

        token = request.headers.get("Authorization")

        if token is None:
            return JSONResponse(
                {"detail": "Authorization token is missing"},
                status_code=401
            )

        try:
            # The token should be in the form of "Bearer <JWT>"
            if token.startswith("Bearer "):
                token = token[len("Bearer "):]
            else:
                return JSONResponse(
                    {"detail": "Invalid token format"},
                    status_code=401
                )

            # Decode the JWT token
            payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("email")
            issuer = payload.get("iss")

            if email is None or issuer is None:
                return JSONResponse(
                    {"detail": "Invalid token. Missing email or issuer."},
                    status_code=401
                )

            # Attach the user information to the request state (accessible in other parts of the app)
            request.state.user = {"email": email, "issuer": issuer}

        except JWTError as e:
            return JSONResponse(
                {"detail": f"Invalid token. Error: {str(e)}"},
                status_code=401
            )

        response = await call_next(request)
        return response
