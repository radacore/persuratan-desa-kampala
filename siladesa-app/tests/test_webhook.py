"""Webhook Telegram dan WhatsApp."""

from __future__ import annotations


def test_telegram_secret_salah(client):
    r = client.post(
        "/webhooks/telegram/salah",
        json={"message": {"chat": {"id": 1}, "text": "halo"}},
    )
    assert r.status_code == 403


def test_telegram_pesan_kosong_dilewati(client):
    r = client.post("/webhooks/telegram/rahasia-telegram-uji", json={})
    assert r.status_code == 200
    assert r.json().get("dilewati") is True


def test_telegram_start_mengirim_menu(client):
    r = client.post(
        "/webhooks/telegram/rahasia-telegram-uji",
        json={"message": {"chat": {"id": 987654321}, "text": "/start"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data.get("state")


def test_whatsapp_secret_salah(client):
    r = client.post("/webhooks/whatsapp/salah", json={"sender": "62812", "message": "halo"})
    assert r.status_code == 403


def test_whatsapp_pesan_grup_diabaikan(client):
    r = client.post(
        "/webhooks/whatsapp/rahasia-fonnte-uji",
        json={"sender": "62812", "message": "halo", "isgroup": "true"},
    )
    assert r.status_code == 200
    assert r.json().get("dilewati") == "grup"


def test_whatsapp_pesan_masuk_diproses(client):
    r = client.post(
        "/webhooks/whatsapp/rahasia-fonnte-uji",
        json={"sender": "6281200000099", "message": "menu", "isgroup": "false"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
