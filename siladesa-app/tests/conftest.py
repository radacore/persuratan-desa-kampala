"""Fixture bersama untuk pengujian SILADESA.

Variabel lingkungan disetel **sebelum** `app` diimpor supaya engine SQLite,
folder penyimpanan, dan folder model menunjuk ke direktori sementara.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="siladesa-tests-"))
os.environ.update(
    {
        "APP_ENV": "testing",
        "SECRET_KEY": "kunci-uji-" + "a" * 40,
        "DATABASE_URL": f"sqlite:///{_TMP / 'uji.db'}",
        "STORAGE_DIR": str(_TMP / "storage"),
        "MODEL_DIR": str(_TMP / "models"),
        "TELEGRAM_WEBHOOK_SECRET": "rahasia-telegram-uji",
        "FONNTE_WEBHOOK_TOKEN": "rahasia-fonnte-uji",
        "LOG_LEVEL": "WARNING",
        # Semua kasus uji datang dari IP yang sama; batas laju diuji terpisah
        # di test_ratelimit.py dengan menyalakannya kembali.
        "RATE_LIMIT_ENABLED": "false",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import constants as C  # noqa: E402

CSRF_RE = re.compile(r'name="csrf" value="([^"]+)"')
SANDI = {
    "admin": ("admin@desakampala.id", "Admin#2026"),
    "operator": ("operator@desakampala.id", "Demo#2026"),
    "sekdes": ("sekdes@desakampala.id", "Demo#2026"),
    "kepala_desa": ("kepaladesa@desakampala.id", "Demo#2026"),
}


@pytest.fixture(scope="session")
def seeded():
    from app.seed import jalankan

    jalankan()
    return True


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import app

    with TestClient(app, follow_redirects=False) as c:
        yield c


def csrf_dari(html: str) -> str:
    cocok = CSRF_RE.search(html)
    assert cocok, "token CSRF tidak ditemukan pada halaman"
    return cocok.group(1)


def masuk(client: TestClient, peran: str = "admin") -> TestClient:
    email, sandi = SANDI[peran]
    client.cookies.clear()
    token = csrf_dari(client.get("/admin/login").text)
    respons = client.post(
        "/admin/login",
        data={"csrf": token, "email": email, "password": sandi, "next": "/admin"},
    )
    assert respons.status_code == 303, respons.text[:300]
    assert "err" not in respons.headers.get("location", "")
    return client


def token_halaman(client: TestClient, path: str) -> str:
    respons = client.get(path)
    assert respons.status_code == 200, respons.text[:300]
    return csrf_dari(respons.text)


def ambil_id(html: str, pola: str) -> int:
    cocok = re.search(pola, html)
    assert cocok, f"pola {pola!r} tidak ditemukan"
    return int(cocok.group(1))


#: Jawaban slot-filling untuk layanan domisili, berurutan.
JAWABAN_DOMISILI = [
    ("NIK", None),  # diisi di fixture pemanggil
    ("Nama Lengkap", "RESKI ADITYA"),
    ("Tempat Lahir", "Jeneponto"),
    ("Tanggal Lahir", "1990-01-12"),
    ("Jenis Kelamin", "Laki-Laki"),
    ("Status Perkawinan", "Kawin"),
    ("Agama", "Islam"),
    ("Pekerjaan", "Petani"),
    ("Alamat", "Dusun Kalukuang"),
    ("Dusun", "Kalukuang"),
    ("RT", "002"),
    ("RW", "001"),
    ("Nomor HP", "081234567890"),
    ("Keperluan", "pendaftaran sekolah anak"),
]


def buat_pengajuan_domisili(client: TestClient, nik: str, kontak: str | None = None) -> str:
    """Jalankan percakapan sampai tiket terbit, kembalikan nomor tiket."""
    if kontak is None:
        import random

        kontak = "08" + "".join(str(random.randint(0, 9)) for _ in range(10))
    sesi = client.post(
        "/api/v1/chat/sessions", json={"channel": "web", "kontak": kontak}
    )
    assert sesi.status_code == 201, sesi.text[:300]
    sid = sesi.json()["session_id"]

    def kirim(pesan: str) -> dict:
        respons = client.post(
            "/api/v1/chat/messages", json={"session_id": sid, "pesan": pesan}
        )
        assert respons.status_code == 200, respons.text[:300]
        return respons.json()

    kirim("1")  # menu: ajukan surat
    kirim("1")  # layanan domisili
    data = kirim("ya")  # persetujuan

    for _ in range(40):
        if data.get("tiket"):
            return data["tiket"]
        teks = "\n".join(data.get("balasan") or [])
        if "data warga ditemukan" in teks.lower():
            data = kirim("1")  # pakai data warga yang sudah tersimpan
            continue
        if "ketik" in teks.lower() and "ya" in teks.lower():
            data = kirim("ya")
            continue
        jawab = None
        for label, nilai in JAWABAN_DOMISILI:
            if label.lower() in teks.lower():
                jawab = nik if nilai is None else nilai
                break
        assert jawab is not None, f"tidak tahu harus menjawab apa: {teks[:300]}"
        data = kirim(jawab)

    raise AssertionError("tiket tidak terbit setelah 40 giliran")


def id_pengajuan(client: TestClient, tiket: str) -> int:
    halaman = client.get(f"/admin/pengajuan?q={tiket}").text
    return ambil_id(halaman, r"/admin/pengajuan/(\d+)")


def nik_unik() -> str:
    import random

    return C.NIK_PREFIX + "".join(str(random.randint(0, 9)) for _ in range(12))
