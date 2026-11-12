"""集中配置：全部来自环境变量，默认值与 .env.example 保持一致。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # 数据库（MySQL 8.0）
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "abcheck"
    db_user: str = "abcheck"
    db_password: str = "abcheck_pw_2026"

    # 安全
    jwt_secret: str = "abcheck-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120

    # 运行时
    redis_url: str = "redis://localhost:6379/0"
    seed_demo: bool = True
    runs_per_minute: int = 12
    min_sample_per_arm: int = 120
    worker_heartbeat_key: str = "abcheck:worker:heartbeat"

    # 统计默认参数（可被实验级覆盖）
    default_alpha: float = 0.05
    default_power: float = 0.8
    default_srm_threshold: float = 0.001
    min_srm_exposures: int = 500
    min_stratum_per_arm: int = 25

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
