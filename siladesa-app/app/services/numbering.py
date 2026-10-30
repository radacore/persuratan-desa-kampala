"""Penomoran tiket pengajuan dan nomor surat resmi."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import BULAN_ROMAWI
from app.models import Application, LetterNumberCounter


def _sekarang() -> datetime:
    return datetime.now(timezone.utc)


def next_ticket_no(db: Session, app: Application) -> str:
    """Tetapkan `APP-{tahun}-{id:06d}` setelah baris punya id.

    `ticket_no` wajib unik dan NOT NULL, jadi sebelum flush dipakai nilai
    sementara berentropi tinggi agar dua transaksi paralel tidak bertabrakan.
    """
    if not app.ticket_no or not app.ticket_no.startswith("APP-"):
        app.ticket_no = f"TMP{secrets.token_hex(10)}"
    db.flush()
    tahun = (app.created_at or _sekarang()).year
    app.ticket_no = f"APP-{tahun}-{app.id:06d}"
    return app.ticket_no


def next_letter_number(db: Session, kode: str = "DKP", saat: datetime | None = None) -> str:
    """Ambil nomor surat berikutnya dengan format `{seq:03d}/{kode}/{bulan_romawi}/{tahun}`.

    Baris counter dikunci (`SELECT ... FOR UPDATE`) di PostgreSQL sehingga aman
    untuk beberapa operator sekaligus. Di SQLite kunci diabaikan, tetapi SQLite
    hanya menulis satu transaksi pada satu waktu.
    """
    saat = saat or _sekarang()
    tahun, bulan = saat.year, saat.month

    counter = db.execute(
        select(LetterNumberCounter)
        .where(
            LetterNumberCounter.kode == kode,
            LetterNumberCounter.tahun == tahun,
            LetterNumberCounter.bulan == bulan,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if counter is None:
        counter = LetterNumberCounter(kode=kode, tahun=tahun, bulan=bulan, urutan=0)
        db.add(counter)
        try:
            db.flush()
        except IntegrityError:
            # Balapan: transaksi lain membuat baris yang sama lebih dulu.
            db.rollback()
            counter = db.execute(
                select(LetterNumberCounter)
                .where(
                    LetterNumberCounter.kode == kode,
                    LetterNumberCounter.tahun == tahun,
                    LetterNumberCounter.bulan == bulan,
                )
                .with_for_update()
            ).scalar_one()

    counter.urutan += 1
    db.flush()
    return f"{counter.urutan:03d}/{kode}/{BULAN_ROMAWI[bulan]}/{tahun}"


def peek_letter_number(db: Session, kode: str = "DKP", saat: datetime | None = None) -> str:
    """Perkiraan nomor berikutnya tanpa menaikkan counter (untuk pratinjau UI)."""
    saat = saat or _sekarang()
    counter = db.execute(
        select(LetterNumberCounter).where(
            LetterNumberCounter.kode == kode,
            LetterNumberCounter.tahun == saat.year,
            LetterNumberCounter.bulan == saat.month,
        )
    ).scalar_one_or_none()
    urutan = (counter.urutan if counter else 0) + 1
    return f"{urutan:03d}/{kode}/{BULAN_ROMAWI[saat.month]}/{saat.year}"
