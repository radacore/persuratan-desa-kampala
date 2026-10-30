"""FR-20: pengiriman dokumen ke kanal asal tanpa menggagalkan penerbitan."""

from __future__ import annotations

from app.services import notifications as notif


def test_kanal_web_tidak_push_balik():
    hasil = notif.kirim_dokumen(
        "web",
        "web-anonim",
        berkas=b"%PDF-1.4",
        nama_berkas="surat.pdf",
        tautan="http://contoh/d/abc",
        keterangan="Surat terbit.",
    )
    assert hasil.terkirim is False
    assert hasil.kanal == "web"


def test_kanal_telegram_tanpa_token_tidak_melempar(monkeypatch):
    monkeypatch.setattr(notif.settings, "telegram_bot_token", "")
    hasil = notif.kirim_dokumen(
        "telegram",
        "12345",
        berkas=b"%PDF-1.4",
        nama_berkas="surat.pdf",
        tautan="http://contoh/d/abc",
        keterangan="Surat terbit.",
    )
    assert hasil.terkirim is False
    assert "token" in hasil.keterangan


def test_kanal_whatsapp_tanpa_token_tidak_melempar(monkeypatch):
    monkeypatch.setattr(notif.settings, "fonnte_token", "")
    hasil = notif.kirim_dokumen(
        "whatsapp",
        "081234567890",
        berkas=None,
        nama_berkas="surat.pdf",
        tautan="http://contoh/d/abc",
        keterangan="Surat terbit.",
    )
    assert hasil.terkirim is False
    assert hasil.kanal == "whatsapp"
