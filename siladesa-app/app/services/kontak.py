"""Ingatan NIK terakhir per kontak percakapan.

Dipakai saat pengajuan ulang: warga dari kontak yang sama tidak perlu mengetik
ulang NIK-nya, cukup mengonfirmasi NIK tersimpan yang ditampilkan tersamar.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KontakNik

#: Kontak bersama yang dipakai semua pengguna web; tidak pernah ditawari
#: simpanan NIK karena tidak bisa dipastikan milik siapa.
KONTAK_BERSAMA = frozenset({"web-anonim", "anonim", "-"})


def boleh_tawar(channel: str, kontak: str | None) -> bool:
    """NIK tersimpan hanya boleh ditawarkan ke kontak yang spesifik."""
    if not kontak:
        return False
    return kontak.strip() not in KONTAK_BERSAMA


def ingat_nik(db: Session, channel: str, kontak: str | None, nik: str) -> None:
    """Simpan NIK terakhir untuk pasangan `(channel, kontak)` (upsert)."""
    if not kontak or not kontak.strip():
        return
    kontak = kontak.strip()[:60]
    nik = nik.strip()
    if len(nik) != 16 or not nik.isdigit():
        return
    row = db.execute(
        select(KontakNik).where(
            KontakNik.channel == channel, KontakNik.kontak == kontak
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(KontakNik(channel=channel, kontak=kontak, nik=nik))
    else:
        row.nik = nik
    db.flush()


def nik_tersimpan(db: Session, channel: str, kontak: str | None) -> str | None:
    """NIK yang tersimpan untuk kontak ini, atau None bila tidak ada/tak boleh."""
    if not boleh_tawar(channel, kontak):
        return None
    row = db.execute(
        select(KontakNik).where(
            KontakNik.channel == channel, KontakNik.kontak == kontak.strip()[:60]
        )
    ).scalar_one_or_none()
    return row.nik if row else None


def samar_nik(nik: str) -> str:
    """Samarkan NIK: tampilkan 4 digit awal dan 4 digit akhir saja."""
    if len(nik) != 16:
        return "••••••••••••••••"
    return f"{nik[:4]}********{nik[-4:]}"
