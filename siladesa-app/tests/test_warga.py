"""Data warga: CRUD panel admin dan validasi NIK di percakapan."""

from __future__ import annotations

import random
import re

from conftest import csrf_dari, masuk, nik_unik

IDENTITAS = {
    "jenis_kelamin": "Laki-Laki",
    "tempat_lahir": "Jeneponto",
    "tanggal_lahir": "1990-01-12",
    "agama": "Islam",
    "status_perkawinan": "Kawin",
    "pekerjaan": "Petani",
    "alamat": "Dusun Kalukuang",
    "dusun": "Kalukuang",
    "rt": "002",
    "rw": "001",
    "no_hp": "081234567890",
}


def _tambah(client, nik: str, nama: str = "WARGA UJI", **ubah):
    csrf = csrf_dari(client.get("/admin/warga").text)
    data = {"csrf": csrf, "nik": nik, "nama_lengkap": nama, **IDENTITAS, **ubah}
    return client.post("/admin/warga", data=data)


def _id_warga(client, nik: str) -> int:
    html = client.get(f"/admin/warga?q={nik}").text
    cocok = re.search(rf'/admin/warga/(\d+)"[^>]*>{nik}', html)
    assert cocok, "data warga tidak ditemukan pada daftar"
    return int(cocok.group(1))


def _sesi(client) -> str:
    kontak = "08" + "".join(str(random.randint(0, 9)) for _ in range(10))
    r = client.post("/api/v1/chat/sessions", json={"channel": "web", "kontak": kontak})
    assert r.status_code == 201, r.text[:300]
    return r.json()["session_id"]


def _kirim(client, sid: str, pesan: str) -> dict:
    r = client.post("/api/v1/chat/messages", json={"session_id": sid, "pesan": pesan})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _mulai_domisili(client) -> str:
    sid = _sesi(client)
    _kirim(client, sid, "1")  # ajukan surat
    _kirim(client, sid, "1")  # domisili
    _kirim(client, sid, "ya")  # persetujuan
    return sid


def _teks(data: dict) -> str:
    return "\n".join(data.get("balasan") or [])


def test_crud_warga_operator(client):
    masuk(client, "operator")
    nik = nik_unik()

    r = _tambah(client, nik, nama="SITI UJI")
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert "SITI UJI" in client.get(f"/admin/warga?q={nik}").text

    wid = _id_warga(client, nik)
    csrf = csrf_dari(client.get(f"/admin/warga/{wid}").text)
    r = client.post(
        f"/admin/warga/{wid}",
        data={"csrf": csrf, "nik": nik, "nama_lengkap": "SITI UJI BARU", **IDENTITAS},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert "SITI UJI BARU" in client.get(f"/admin/warga/{wid}").text

    r = client.post(f"/admin/warga/{wid}/aktif", data={"csrf": csrf})
    assert r.status_code == 303
    assert "Nonaktif" in client.get(f"/admin/warga/{wid}").text

    r = client.post(f"/admin/warga/{wid}/hapus", data={"csrf": csrf})
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert f"/admin/warga/{wid}" not in client.get(f"/admin/warga?q={nik}").text


def test_warga_nik_duplikat_ditolak(client):
    masuk(client, "operator")
    nik = nik_unik()
    assert "err" not in _tambah(client, nik).headers["location"]

    r = _tambah(client, nik, nama="DUPLIKAT")
    assert r.status_code == 303 and "err" in r.headers["location"]


def test_warga_nik_harus_16_digit(client):
    masuk(client, "operator")
    r = _tambah(client, "7304")
    assert r.status_code == 303 and "err" in r.headers["location"]


def test_kepala_desa_hanya_boleh_membaca(client):
    masuk(client, "operator")
    nik = nik_unik()
    _tambah(client, nik)
    wid = _id_warga(client, nik)

    masuk(client, "kepala_desa")
    assert client.get("/admin/warga").status_code == 200
    assert client.get(f"/admin/warga/{wid}").status_code == 200

    csrf = csrf_dari(client.get("/admin/warga").text)
    r = client.post(
        "/admin/warga",
        data={"csrf": csrf, "nik": nik_unik(), "nama_lengkap": "TIDAK BOLEH", **IDENTITAS},
    )
    assert r.status_code == 403


def test_hapus_warga_beriwayat_ditolak(client):
    from conftest import buat_pengajuan_domisili

    masuk(client, "operator")
    nik = nik_unik()
    _tambah(client, nik, nama="RIWAYAT UJI")
    wid = _id_warga(client, nik)
    buat_pengajuan_domisili(client, nik)

    csrf = csrf_dari(client.get(f"/admin/warga/{wid}").text)
    r = client.post(f"/admin/warga/{wid}/hapus", data={"csrf": csrf})
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert "RIWAYAT UJI" in client.get(f"/admin/warga/{wid}").text


def test_chat_nik_dikenal_langsung_ke_field_layanan(client):
    masuk(client, "operator")
    nik = nik_unik()
    _tambah(client, nik, nama="SITI RAHMAWATI")

    sid = _mulai_domisili(client)
    data = _kirim(client, sid, nik)
    teks = _teks(data)
    assert "Data warga ditemukan" in teks
    assert "SITI RAHMAWATI" in teks
    assert len(data["pilihan"]) == 3

    data = _kirim(client, sid, "1")
    teks = _teks(data)
    assert "Keperluan" in teks
    assert "Nama Lengkap" not in teks


def test_chat_perbaiki_data_menanyakan_ulang_identitas(client):
    masuk(client, "operator")
    nik = nik_unik()
    _tambah(client, nik, nama="SITI RAHMAWATI")

    sid = _mulai_domisili(client)
    assert "Data warga ditemukan" in _teks(_kirim(client, sid, nik))

    data = _kirim(client, sid, "2")
    teks = _teks(data)
    assert "Nama Lengkap" in teks
    assert "Data 2 dari" in teks


def test_chat_nik_nonaktif_ditolak(client):
    masuk(client, "operator")
    nik = nik_unik()
    _tambah(client, nik)
    wid = _id_warga(client, nik)
    csrf = csrf_dari(client.get(f"/admin/warga/{wid}").text)
    client.post(f"/admin/warga/{wid}/aktif", data={"csrf": csrf})

    sid = _mulai_domisili(client)
    teks = _teks(_kirim(client, sid, nik)).lower()
    assert "nonaktif" in teks
    assert "data warga ditemukan" not in teks


def test_chat_nik_belum_terdaftar_minta_nama(client):
    sid = _mulai_domisili(client)
    teks = _teks(_kirim(client, sid, nik_unik()))
    assert "Nama Lengkap" in teks
