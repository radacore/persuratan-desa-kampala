"""Konfigurasi aplikasi dari variabel lingkungan."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_version: str = "1.0.0"
    app_url: str = "http://localhost:8000"
    secret_key: str = "dev-secret-key-jangan-dipakai-di-produksi"

    database_url: str = ""

    bootstrap_admin_email: str = "admin@desakampala.id"
    bootstrap_admin_password: str = "Admin#2026"
    #: Sandi akun contoh (operator/sekdes/kepala desa); tidak dibuat di produksi.
    bootstrap_demo_password: str = "Demo#2026"

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    fonnte_token: str = ""
    fonnte_webhook_token: str = ""
    fonnte_api_url: str = "https://api.fonnte.com/send"

    confidence_tinggi: float = 0.65
    confidence_rendah: float = 0.40

    storage_dir: str = "data/storage"
    model_dir: str = "data/models"
    max_upload_mb: int = 5
    download_token_ttl_days: int = 7

    #: Batas laju per IP. Dimatikan pada pengujian karena seluruh kasus berjalan
    #: dari satu alamat (TestClient), sehingga kuota habis sebelum suite selesai.
    rate_limit_enabled: bool = True

    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{BASE_DIR / 'data' / 'siladesa.db'}"

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        return path if path.is_absolute() else BASE_DIR / path

    @property
    def model_path(self) -> Path:
        path = Path(self.model_dir)
        return path if path.is_absolute() else BASE_DIR / path

    def ensure_dirs(self) -> None:
        for sub in ("documents", "attachments", "officials"):
            (self.storage_path / sub).mkdir(parents=True, exist_ok=True)
        self.model_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
