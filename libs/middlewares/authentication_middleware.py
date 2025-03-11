import jwt
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
            return await call_next(request)
        header_authorization = request.headers.get("Authorization", None)

        if header_authorization is None:
            return JSONResponse(
                {"detail": "Authorization token is missing"},
                status_code=401
            )

        if not header_authorization.lower().startswith("bearer "):
            return JSONResponse(status_code=401, content="Invalid authorization header format.")

        try:
            token = header_authorization.split(" ")[1]  # get the token part
        except BaseException:
            return JSONResponse(status_code=401, content="Invalid token.")

        try:

            # Decode the JWT token
            payload = jwt.decode(token, key=AUTH_SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("email")
            if not email:
                return JSONResponse(status_code=401, content="Invalid token: missing email.")

            issuer = payload.get("iss")
            if not issuer:
                return JSONResponse(status_code=401, content="Invalid token: missing issuer.")

            # Attach the user information to the request state (accessible in other parts of the app)
            request.state.user = {"email": email, "issuer": issuer}

        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content="Token has expired.")
        except jwt.InvalidTokenError as err:
            return JSONResponse(status_code=401, content=f"Invalid token: {str(err)}")

        return await call_next(request)
