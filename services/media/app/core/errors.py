"""
Standard error responses for the API.

Every error returns:
    {"error": {"code": str, "message": str, "details": dict}}

The frontend switches on `code` (stable), displays `message` (human-friendly),
and uses `details` for extra context (optional).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


class MediaError(Exception):
    """Raised anywhere in the app to produce a structured error response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def install_error_handlers(app: FastAPI) -> None:
    """Register error handlers on the app."""

    @app.exception_handler(MediaError)
    async def media_error_handler(request: Request, exc: MediaError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Something went wrong on our end.",
                    "details": {},
                }
            },
        )
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """
        FastAPI raises this when form/body/query data fails validation 
        (bad types, missing required fields, out-of-range numbers).
        Reshape it to match our standard error format.
        """

        # exc.errors() returns a list of dicts - one per invalid field.
        # We flatten the first one for 'message' and include all in 'details'.
        errors = exc.errors()
        first = errors[0] if errors else {}

        # Human-readable summary
        loc = ".".join(str(p) for p in first.get("loc", []))
        message = f"Invalid input for '{loc}': {first.get('msg', 'validation failed')}"

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": message,
                    "details": {
                        "errors": [
                            {
                                "field": ".".join(str(p) for p in err.get("loc",[])),
                                "message": err.get("msg", ""),
                                "type": err.get("type", ""),
                            }
                            for err in errors
                        ],
                    },
                }
            },
        )