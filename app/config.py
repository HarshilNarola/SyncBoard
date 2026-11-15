import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'syncboard.db').as_posix()}"
    )


settings = Settings()
