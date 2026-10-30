"""Pembatas laju permintaan sederhana (in-memory, per proses).

FR-32 mewajibkan endpoint verifikasi JSON dibatasi 60 permintaan per menit per
IP. Satu instance aplikasi cukup memakai deque per IP; bila aplikasi diperbanyak
di belakang load balancer, batas ini perlu dipindah ke penyimpanan bersama
(mis. Redis) agar berlaku lintas proses.

Halaman HTML `/v/{token}` memakai batas yang lebih ketat: setiap permintaan
menulis baris `verification_scan`, jadi tanpa batas siapa pun dapat
menggelembungkan tabel itu dengan token karangan.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings

JENDELA_DETIK = 60
BATAS = 60

#: Batas halaman verifikasi HTML: 20 pemindaian per menit per IP.
BATAS_HALAMAN = 20

#: Batas login: 10 percobaan per menit per IP (menahan tebak sandi).
BATAS_LOGIN = 10

#: Batas pembuatan sesi/pesan chat per IP: menahan banjir baris chat_message.
BATAS_CHAT = 120

#: Batas endpoint diagnostik model.
BATAS_PREDIKSI = 60

#: Batas permintaan webhook per IP.
BATAS_WEBHOOK = 120

_kunci = threading.Lock()
_catatan: dict[str, deque[float]] = defaultdict(deque)


def _bersihkan(sekarang: float) -> None:
    """Buang IP yang tidak lagi punya catatan dalam jendela waktu."""
    for ip in list(_catatan):
        antrean = _catatan[ip]
        while antrean and sekarang - antrean[0] >= JENDELA_DETIK:
            antrean.popleft()
        if not antrean:
            del _catatan[ip]


def cek_batas(
    ip: str, batas: int = BATAS, jendela: int = JENDELA_DETIK, *, kunci: str = ""
) -> None:
    """Catat satu permintaan; lempar 429 bila kuota jendela sudah habis.

    `kunci` memisahkan kuota antar-jenis endpoint (mis. `login` vs `chat`)
    sehingga pemakaian chat tidak menghabiskan jatah login.
    """
    if not settings.rate_limit_enabled:
        return
    sekarang = time.monotonic()
    kunci_ip = f"{kunci}|{ip}" if kunci else ip
    with _kunci:
        if len(_catatan) > 10_000:
            _bersihkan(sekarang)
        antrean = _catatan[kunci_ip]
        while antrean and sekarang - antrean[0] >= jendela:
            antrean.popleft()
        if len(antrean) >= batas:
            sisa = max(1, int(jendela - (sekarang - antrean[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Terlalu banyak permintaan. Coba lagi dalam {sisa} detik.",
                headers={"Retry-After": str(sisa)},
            )
        antrean.append(sekarang)


def _ip_klien(request: Request) -> str:
    """Alamat peer soket, bukan header `X-Forwarded-For` mentah.

    Klien tidak bisa melewati batas dengan memalsukan header. Di produksi
    uvicorn dijalankan dengan `--proxy-headers` (lihat Dockerfile) sehingga
    `request.client` sudah berisi IP asli dari reverse proxy.
    """
    return request.client.host if request.client else "-"


def batasi_verifikasi(request: Request) -> None:
    """Dependensi FastAPI untuk endpoint verifikasi JSON."""
    cek_batas(_ip_klien(request), BATAS, kunci="verify")


def batasi_halaman_verifikasi(request: Request) -> None:
    """Dependensi halaman HTML `/v/{token}`: lebih ketat karena menulis baris."""
    cek_batas(_ip_klien(request), BATAS_HALAMAN, kunci="verify-html")


def batasi_login(request: Request) -> None:
    cek_batas(_ip_klien(request), BATAS_LOGIN, kunci="login")


def batasi_chat(request: Request) -> None:
    cek_batas(_ip_klien(request), BATAS_CHAT, kunci="chat")


def batasi_prediksi(request: Request) -> None:
    cek_batas(_ip_klien(request), BATAS_PREDIKSI, kunci="predict")


def batasi_webhook(request: Request) -> None:
    cek_batas(_ip_klien(request), BATAS_WEBHOOK, kunci="webhook")


def reset() -> None:
    """Kosongkan catatan; dipakai pengujian agar tidak bocor antar-kasus."""
    with _kunci:
        _catatan.clear()
