"""Titik masuk aplikasi SILADESA."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import BASE_DIR, settings
from app.db import Base, SessionLocal, engine
from app.deps import RedirectToLogin
from app.models import NlpModel
from app.routers import admin, api, public, webhooks
from app.services.nlp import nlp
from app.templating import render

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("siladesa")


def muat_model_aktif() -> None:
    with SessionLocal() as db:
        model = db.execute(select(NlpModel).where(NlpModel.aktif.is_(True))).scalar_one_or_none()
        if model is None:
            log.warning(
                "Belum ada model NLP aktif. Jalankan `python -m app.seed` untuk melatih model awal."
            )
            return
        path = Path(model.file_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        nlp.muat(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    # Di produksi skema dikelola Alembic (`alembic upgrade head` di entrypoint).
    # create_all tetap dipakai saat pengembangan dan pengujian supaya cepat.
    if not settings.is_production:
        Base.metadata.create_all(bind=engine)
    muat_model_aktif()
    log.info("SILADESA %s berjalan (%s)", settings.app_version, settings.app_env)
    yield


app = FastAPI(
    title="SILADESA — Sistem Layanan Administrasi Desa",
    description="Layanan administrasi Desa Kampala berbasis chatbot dan panel operator.",
    version=settings.app_version,
    lifespan=lifespan,
)

STATIC_DIR = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(RedirectToLogin)
async def _redirect_login(request: Request, exc: RedirectToLogin):
    return RedirectResponse(url=f"/admin/login?next={exc.next_url}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _galat_http(request: Request, exc: StarletteHTTPException):
    """Halaman HTML memakai template; jalur API tetap mengembalikan JSON."""
    if request.url.path.startswith("/api/") or request.url.path.startswith("/webhooks/"):
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )
    if exc.status_code == 404:
        return render(request, "errors/404.html", {}, status_code=404)
    if exc.status_code in {403, 401}:
        return render(
            request, "errors/403.html", {"pesan_galat": exc.detail}, status_code=exc.status_code
        )
    return render(
        request,
        "errors/umum.html",
        {"kode": exc.status_code, "pesan_galat": exc.detail},
        status_code=exc.status_code,
    )


@app.get("/health", tags=["sistem"])
def health() -> dict:
    return {
        "status": "ok",
        "versi": settings.app_version,
        "model_nlp": nlp.versi,
        "model_siap": nlp.siap,
    }


app.include_router(public.router)
app.include_router(api.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/webhooks")
app.include_router(admin.router, prefix="/admin")
