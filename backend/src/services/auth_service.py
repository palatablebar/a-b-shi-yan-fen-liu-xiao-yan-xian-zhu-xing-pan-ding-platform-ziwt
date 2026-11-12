"""登录与当前用户。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.base import utcnow
from src.models.user import User
from src.schemas.auth import UserOut
from src.utils.errors import AppError
from src.utils.jwt import create_access_token
from src.utils.password import verify_password


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.db.query(User).filter(User.email == email.lower()).one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise AppError(codes.AUTH_INVALID, "邮箱或密码不正确", f"email={email}", 401)
        if not user.is_active:
            raise AppError(codes.AUTH_INVALID, "账号已停用，请联系增长负责人", f"email={email}", 401)
        user.last_login_at = utcnow()
        self.db.commit()
        token = create_access_token(user.id, user.role, user.email)
        return user, token

    @staticmethod
    def serialize(user: User) -> UserOut:
        return UserOut.from_model(user)
