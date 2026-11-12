"""全局异常处理：所有错误都返回统一 JSON（code/message/detail）。"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.constants import error_codes as codes
from src.utils.errors import AppError
from src.utils.logger import get_logger

logger = get_logger("abcheck.error")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": codes.VALIDATION_FAILED,
                "message": "请求参数校验失败",
                "detail": exc.errors()[:6],
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": "http_error",
                "message": str(exc.detail) if exc.detail else "请求失败",
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled path=%s error=%s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"code": codes.INTERNAL_ERROR, "message": "服务内部错误，请稍后重试"},
        )
