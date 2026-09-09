"""
Get TOKEN string from the request Authorization header
"""

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

# create context variable for TOKEN
REQUEST_TOKEN_CTX_KEY = "request_token"
request_token_ctx_var: ContextVar[str] = ContextVar("request_token", default="")


def get_request_token() -> str:
    return request_token_ctx_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        request_token = request.headers.get("Authorization", None)
        request_token_ctx_var.set(request_token)
        response = await call_next(request)
        return response
