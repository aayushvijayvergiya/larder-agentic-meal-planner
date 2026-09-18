"""API error type and the single JSON error envelope (LLD §2.3)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("larder.errors")


class ApiError(Exception):
    def __init__(self, code: str, status: int, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.details = details

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": self.code, "message": self.message, "details": self.details}},
            status_code=self.status,
        )


def unauthorized(message: str = "Missing or invalid credentials") -> ApiError:
    return ApiError("unauthorized", 401, message)


def forbidden(message: str = "You do not have access to this resource") -> ApiError:
    return ApiError("forbidden", 403, message)


def not_found(message: str = "Not found") -> ApiError:
    return ApiError("not_found", 404, message)


def conflict(message: str) -> ApiError:
    return ApiError("conflict", 409, message)


def job_running(message: str = "A planning job is already running for this plan") -> ApiError:
    return ApiError("job_running", 409, message)


def onboarding_incomplete() -> ApiError:
    return ApiError("onboarding_incomplete", 409, "Finish onboarding before using this feature")


def llm_unavailable(message: str = "The planner is temporarily unavailable") -> ApiError:
    return ApiError("llm_unavailable", 503, message)


def validation(message: str, field: str | None = None) -> ApiError:
    return ApiError("validation_error", 422, message, {"field": field} if field else None)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {"errors": jsonable_encoder(exc.errors())},
                }
            },
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "Something went wrong", "details": None}},
            status_code=500,
        )
