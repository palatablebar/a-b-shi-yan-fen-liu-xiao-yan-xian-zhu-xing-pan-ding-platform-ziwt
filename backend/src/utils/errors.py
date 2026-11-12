"""业务异常：携带 HTTP 状态码与稳定错误码，交给全局处理器。"""
from __future__ import annotations

from src.constants import error_codes as codes


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        detail: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


def not_found(entity: str, key: object) -> AppError:
    return AppError(codes.NOT_FOUND, f"{entity} 不存在", f"{entity}={key}", 404)


def forbidden(message: str, detail: str | None = None) -> AppError:
    return AppError(codes.FORBIDDEN, message, detail, 403)


def conflict(message: str, detail: str | None = None) -> AppError:
    return AppError(codes.CONFLICT, message, detail, 409)


def locked(message: str, detail: str | None = None) -> AppError:
    return AppError(codes.LOCKED, message, detail, 423)


def validation_error(message: str, detail: str | None = None) -> AppError:
    return AppError(codes.VALIDATION_FAILED, message, detail, 422)
