"""
HTTP Exceptions and response messages
"""

from http import HTTPStatus

responses = {
    HTTPStatus.OK: {  # 200
        "status_code": HTTPStatus.OK,
        "message": "The request was successfully completed.",
    },
    HTTPStatus.CREATED: {  # 201
        "status_code": HTTPStatus.CREATED,
        "message": "A new resource was successfully created.",
    },
    HTTPStatus.BAD_REQUEST: {  # 400
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "The request was invalid.",
    },
    HTTPStatus.UNAUTHORIZED: {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Authorization Required.",
    },
    HTTPStatus.FORBIDDEN: {  # 403
        "status_code": HTTPStatus.FORBIDDEN,
        "message": "Forbidden. You don't have permission to this action.",
    },
    HTTPStatus.NOT_FOUND: {  # 404
        "status_code": HTTPStatus.NOT_FOUND,
        "message": "Item not found.",
    },
    HTTPStatus.METHOD_NOT_ALLOWED: {  # 405
        "status_code": HTTPStatus.METHOD_NOT_ALLOWED,
        "message": "The method is not supported by the resource.",
    },
    HTTPStatus.INTERNAL_SERVER_ERROR: {  # 500
        "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
        "message": "An internal error occurred in the server.",
    },
    "PAGE_NOT_FOUND": {  # 404
        "status_code": HTTPStatus.NOT_FOUND,
        "message": "The API resource not found.",
    },
    "EMAIL_NOT_VERIFIED": {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Authorization Required. Email address is not verified.",
    },
    "EMAIL_NOT_IN_TOKEN": {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Authorization Required. Missing email address from the token.",
    },
    "EMAIL_VERIFIED_NOT_IN_TOKEN": {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Authorization Required. Missing user information: email_verified.",
    },
    "EXPIRED_TOKEN": {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Token signature has expired.",
    },
    "INVALID_TOKEN": {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Token is invalid, cannot be validated.",
    },
    "INVALID_EMAIL": {  # 401
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Email address cannot be validated because of the wrong format.",
    },
}
