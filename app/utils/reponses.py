"""
HTTP exception definitions and helpers
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict

from fastapi import HTTPException


# ---------- Core Structure ----------


@dataclass(frozen=True)
class ApiError:
    status: HTTPStatus
    message: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "status_code": self.status,
            "message": self.message,
        }

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=self.status,
            detail=self.message,
        )


# ---------- Standard HTTP Responses ----------

OK = ApiError(HTTPStatus.OK, "The request was successfully completed.")
CREATED = ApiError(HTTPStatus.CREATED, "A new resource was successfully created.")
BAD_REQUEST = ApiError(HTTPStatus.BAD_REQUEST, "The request was invalid.")
UNAUTHORIZED = ApiError(HTTPStatus.UNAUTHORIZED, "Authorization required.")
FORBIDDEN = ApiError(HTTPStatus.FORBIDDEN, "Forbidden. You don't have permission to this action.")
NOT_FOUND = ApiError(HTTPStatus.NOT_FOUND, "Item not found.")
METHOD_NOT_ALLOWED = ApiError(
    HTTPStatus.METHOD_NOT_ALLOWED, "The method is not supported by the resource."
)
INTERNAL_ERROR = ApiError(
    HTTPStatus.INTERNAL_SERVER_ERROR, "An internal error occurred in the server."
)


# ---------- Domain-Specific Errors ----------

PAGE_NOT_FOUND = ApiError(HTTPStatus.NOT_FOUND, "The API resource not found.")
EMAIL_NOT_VERIFIED = ApiError(HTTPStatus.UNAUTHORIZED, "Email address is not verified.")
EMAIL_NOT_IN_TOKEN = ApiError(HTTPStatus.UNAUTHORIZED, "Missing email address in token.")
EMAIL_VERIFIED_NOT_IN_TOKEN = ApiError(
    HTTPStatus.UNAUTHORIZED, "Missing user information: email_verified."
)
EXPIRED_TOKEN = ApiError(HTTPStatus.UNAUTHORIZED, "Token signature has expired.")
INVALID_TOKEN = ApiError(HTTPStatus.UNAUTHORIZED, "Token is invalid.")
INVALID_EMAIL = ApiError(HTTPStatus.UNAUTHORIZED, "Email address format is invalid.")
