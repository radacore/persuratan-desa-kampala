"""Ingat NIK per kontak + FAQ lokasi/kontak kantor desa."""

from __future__ import annotations

import random

from conftest import buat_pengajuan_domisili, nik_unik


def _kontak() -> str:
    return "08" + "".join(str(random.randint(0, 9)) for _ in range(10))


def _sesi(client, kontak: str | None = None) -> str:
    r = client.post(
        "/api/v1/chat/sessions", json={"channel": "web", "kontak": kontak or _kontak()}
    )
    assert r.status_code == 201, r.text[:300]
    return r.json()["session_id"]


def _kirim(client, sid: str, pesan: str) -> dict:
    r = client.post("/api/v1/chat/messages", json={"session_id": sid, "pesan": pesan})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _sampai_nik(client, sid: str) -> dict:
    _kirim(client, sid, "1")
    _kirim(client, sid, "1")
    return _kirim(client, sid, "ya")


def _teks(data: dict) -> str:
    return "\n".join(data.get("balasan") or [])


def test_sesi_kedua_ditawari_nik_tersimpan(client):
    nik = nik_unik()
    kontak = _kontak()
    tiket = buat_pengajuan_domisili(client, nik, kontak=kontak)
    assert tiket.startswith("APP-")

    sid = _sesi(client, kontak)
    data = _sampai_nik(client, sid)
    # tawaran NIK muncul segera (KONFIRMASI_NIK), tanpa harus mengetik dulu
    assert data["state"] == "KONFIRMASI_NIK", _teks(data)[:300]
    import re as _re
    assert _re.search(r"\d{16}", _teks(data)) is None, "NIK lengkap tidak boleh tampil"
    assert "****" in _teks(data), "NIK harus tersamar"


def test_pakai_nik_tersimpan_langsung_ke_kartu_warga(client):
    nik = nik_unik()
    kontak = _kontak()
    buat_pengajuan_domisili(client, nik, kontak=kontak)

    sid = _sesi(client, kontak)
    _sampai_nik(client, sid)
    data = _kirim(client, sid, "1")  # Ya, pakai NIK ini
    teks = _teks(data).lower()
    assert "data warga ditemukan" in teks or data["state"] == "KONFIRMASI_WARGA", teks[:300]


def test_tolak_nik_tersimpan_kembali_ke_prompt(client):
    nik = nik_unik()
    kontak = _kontak()
    buat_pengajuan_domisili(client, nik, kontak=kontak)

    sid = _sesi(client, kontak)
    _sampai_nik(client, sid)
    data = _kirim(client, sid, "2")  # Masukkan NIK lain
    assert data["state"] == "SLOT_FILLING", _teks(data)[:300]
    assert "masukkan nik" in _teks(data).lower()


def test_web_anonim_tidak_pernah_ditawari(client):
    nik = nik_unik()
    buat_pengajuan_domisili(client, nik, kontak="web-anonim")

    sid = _sesi(client, "web-anonim")
    data = _sampai_nik(client, sid)
    # langsung prompt NIK biasa, tanpa tawaran "pernah dipakai"
    assert data["state"] == "SLOT_FILLING", _teks(data)[:300]
    teks = _teks(data).lower()
    assert "nik" in teks and "pernah dipakai" not in teks and "7304****" not in teks


def test_lokasi_dijawab_model(client):
    sid = _sesi(client)
    data = _kirim(client, sid, "di mana lokasi kantor desa")
    assert data["intent"] == "INFO_LOKASI", data
    assert data["confidence"] >= 0.65
    teks = _teks(data).lower()
    assert "buntulu" in teks or "kampala" in teks or "poros" in teks


def test_kontak_dijawab_model(client):
    sid = _sesi(client)
    data = _kirim(client, sid, "berapa nomor telepon kantor desa")
    assert data["intent"] == "INFO_KONTAK", data
    assert data["confidence"] >= 0.65


def test_syarat_lama_tidak_berubah(client):
    sid = _sesi(client)
    data = _kirim(client, sid, "apa syarat surat keterangan domisili")
    assert data["intent"] == "INFO_SYARAT_DOMISILI", data
    data = _kirim(client, sid, "berapa biaya bikin surat")
    assert data["intent"] == "INFO_BIAYA", data
    data = _kirim(client, sid, "jam buka kantor")
    assert data["intent"] == "INFO_JAM_LAYANAN", data
