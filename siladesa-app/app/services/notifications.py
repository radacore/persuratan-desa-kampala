"""Pengiriman notifikasi ke warga melalui WhatsApp (Fonnte) dan Telegram.

Semua kegagalan kanal ditelan dan dicatat ke log: kegagalan notifikasi tidak
boleh menggagalkan transaksi pengajuan yang sudah tersimpan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

log = logging.getLogger("siladesa.notif")


@dataclass
class HasilKirim:
    terkirim: bool
    kanal: str
    keterangan: str = ""


def _normalisasi_hp(no_hp: str) -> str:
    nomor = "".join(c for c in no_hp if c.isdigit() or c == "+")
    if nomor.startswith("+"):
        nomor = nomor[1:]
    if nomor.startswith("0"):
        nomor = "62" + nomor[1:]
    elif nomor.startswith("8"):
        nomor = "62" + nomor
    return nomor


def kirim_whatsapp(no_hp: str | None, pesan: str) -> HasilKirim:
    if not no_hp:
        return HasilKirim(False, "whatsapp", "nomor HP kosong")
    if not settings.fonnte_token:
        log.info("Fonnte belum dikonfigurasi; pesan WhatsApp ke %s dilewati", no_hp)
        return HasilKirim(False, "whatsapp", "token Fonnte belum diisi")

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                settings.fonnte_api_url,
                headers={"Authorization": settings.fonnte_token},
                data={"target": _normalisasi_hp(no_hp), "message": pesan, "countryCode": "62"},
            )
        if resp.status_code == 200 and resp.json().get("status"):
            return HasilKirim(True, "whatsapp")
        log.warning("Fonnte menolak pesan: %s %s", resp.status_code, resp.text[:200])
        return HasilKirim(False, "whatsapp", f"HTTP {resp.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Gagal mengirim WhatsApp: %s", exc)
        return HasilKirim(False, "whatsapp", str(exc)[:120])


def kirim_telegram(chat_id: str | None, pesan: str) -> HasilKirim:
    if not chat_id:
        return HasilKirim(False, "telegram", "chat id kosong")
    if not settings.telegram_bot_token:
        log.info("Telegram belum dikonfigurasi; pesan ke %s dilewati", chat_id)
        return HasilKirim(False, "telegram", "token bot belum diisi")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": pesan})
        if resp.status_code == 200 and resp.json().get("ok"):
            return HasilKirim(True, "telegram")
        log.warning("Telegram menolak pesan: %s %s", resp.status_code, resp.text[:200])
        return HasilKirim(False, "telegram", f"HTTP {resp.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Gagal mengirim Telegram: %s", exc)
        return HasilKirim(False, "telegram", str(exc)[:120])


def beri_tahu_warga(channel: str, kontak: str | None, pesan: str) -> HasilKirim:
    if channel == "whatsapp":
        return kirim_whatsapp(kontak, pesan)
    if channel == "telegram":
        return kirim_telegram(kontak, pesan)
    return HasilKirim(False, channel, "kanal web tidak butuh push")


def kirim_dokumen_telegram(
    chat_id: str | None, berkas: bytes, nama_berkas: str, keterangan: str
) -> HasilKirim:
    """Kirim PDF sebagai lampiran Telegram (FR-20)."""
    if not chat_id:
        return HasilKirim(False, "telegram", "chat id kosong")
    if not settings.telegram_bot_token:
        log.info("Telegram belum dikonfigurasi; dokumen ke %s dilewati", chat_id)
        return HasilKirim(False, "telegram", "token bot belum diisi")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(
                url,
                data={"chat_id": chat_id, "caption": keterangan[:1000]},
                files={"document": (nama_berkas, berkas, "application/pdf")},
            )
        if resp.status_code == 200 and resp.json().get("ok"):
            return HasilKirim(True, "telegram")
        log.warning("Telegram menolak dokumen: %s %s", resp.status_code, resp.text[:200])
        return HasilKirim(False, "telegram", f"HTTP {resp.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Gagal mengirim dokumen Telegram: %s", exc)
        return HasilKirim(False, "telegram", str(exc)[:120])


def kirim_dokumen_whatsapp(
    no_hp: str | None, tautan: str, keterangan: str
) -> HasilKirim:
    """Kirim PDF lewat Fonnte memakai URL publik bertoken (FR-20).

    Fonnte mengunduh berkas dari `url`, jadi tautan harus dapat dijangkau dari
    internet. Tautan yang sama tetap dicadangkan pada percakapan warga.
    """
    if not no_hp:
        return HasilKirim(False, "whatsapp", "nomor HP kosong")
    if not settings.fonnte_token:
        log.info("Fonnte belum dikonfigurasi; dokumen ke %s dilewati", no_hp)
        return HasilKirim(False, "whatsapp", "token Fonnte belum diisi")

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(
                settings.fonnte_api_url,
                headers={"Authorization": settings.fonnte_token},
                data={
                    "target": _normalisasi_hp(no_hp),
                    "message": keterangan,
                    "url": tautan,
                    "countryCode": "62",
                },
            )
        if resp.status_code == 200 and resp.json().get("status"):
            return HasilKirim(True, "whatsapp")
        log.warning("Fonnte menolak dokumen: %s %s", resp.status_code, resp.text[:200])
        return HasilKirim(False, "whatsapp", f"HTTP {resp.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Gagal mengirim dokumen WhatsApp: %s", exc)
        return HasilKirim(False, "whatsapp", str(exc)[:120])


def kirim_dokumen(
    channel: str,
    kontak: str | None,
    *,
    berkas: bytes | None,
    nama_berkas: str,
    tautan: str,
    keterangan: str,
) -> HasilKirim:
    """Kirim PDF ke kanal asal pengajuan; web cukup lewat pesan percakapan."""
    if channel == "telegram" and berkas:
        return kirim_dokumen_telegram(kontak, berkas, nama_berkas, keterangan)
    if channel == "whatsapp":
        return kirim_dokumen_whatsapp(kontak, tautan, keterangan)
    return HasilKirim(False, channel, "kanal web memakai pesan percakapan")


TEMPLATE = {
    "diproses": (
        "Halo {nama}, pengajuan {layanan} ({tiket}) sedang diproses petugas desa.\n"
        "Kami akan mengabari lagi setelah surat terbit. — Desa Kampala"
    ),
    "terbit": (
        "Halo {nama}, surat {layanan} Anda sudah terbit.\n"
        "Nomor surat: {nomor}\n"
        "Unduh: {unduh}\n"
        "Tautan berlaku 7 hari. — Desa Kampala"
    ),
    "ditolak": (
        "Halo {nama}, pengajuan {layanan} ({tiket}) belum dapat diproses.\n"
        "Alasan: {alasan}\n"
        "Silakan hubungi kantor desa bila perlu penjelasan. — Desa Kampala"
    ),
    "dibatalkan": (
        "Halo {nama}, pengajuan {layanan} ({tiket}) telah dibatalkan.\n"
        "Alasan: {alasan}\n— Desa Kampala"
    ),
}
