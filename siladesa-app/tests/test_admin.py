"""CRUD panel admin: katalog, template, FAQ, pejabat, dataset, pengguna, pengaturan."""

from __future__ import annotations

import re

from conftest import csrf_dari, masuk


def test_tambah_ubah_nonaktifkan_faq(client):
    masuk(client, "sekdes")
    csrf = csrf_dari(client.get("/admin/faq").text)

    r = client.post(
        "/admin/faq",
        data={
            "csrf": csrf,
            "pertanyaan": "Apakah layanan surat dikenakan biaya?",
            "jawaban": "Tidak. Semua layanan administrasi Desa Kampala gratis.",
            "kata_kunci": "biaya, gratis, bayar",
            "urutan": "1",
        },
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    halaman = client.get("/admin/faq")
    assert "dikenakan biaya" in halaman.text
    fid = int(re.search(r'/admin/faq/(\d+)"', halaman.text).group(1))

    r = client.post(
        f"/admin/faq/{fid}",
        data={
            "csrf": csrf,
            "pertanyaan": "Apakah layanan surat dikenakan biaya?",
            "jawaban": "Tidak dipungut biaya apa pun.",
            "kata_kunci": "biaya, gratis",
            "urutan": "1",
            "aktif": "1",
        },
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert "Tidak dipungut biaya" in client.get("/admin/faq").text

    r = client.post(f"/admin/faq/{fid}/hapus", data={"csrf": csrf})
    assert r.status_code == 303
    assert "dinonaktifkan" in r.headers["location"].lower() or "dinonaktifkan" in client.get("/admin/faq").text.lower()


def test_pejabat_duplikat_ditolak(client):
    masuk(client, "sekdes")
    csrf = csrf_dari(client.get("/admin/pejabat").text)

    r = client.post(
        "/admin/pejabat",
        data={"csrf": csrf, "nama": "Pejabat Uji", "jabatan": "Kepala Desa", "urutan": "9"},
    )
    assert r.status_code == 303
    assert "err" in r.headers["location"]

    r = client.post(
        "/admin/pejabat",
        data={"csrf": csrf, "nama": "Pejabat Uji", "jabatan": "Kaur Umum", "urutan": "9"},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    halaman = client.get("/admin/pejabat")
    assert "Pejabat Uji" in halaman.text


def test_ubah_layanan(client):
    masuk(client, "sekdes")
    halaman = client.get("/admin/layanan/DOM")
    assert halaman.status_code == 200
    csrf = csrf_dari(halaman.text)

    r = client.post(
        "/admin/layanan/DOM",
        data={
            "csrf": csrf,
            "nama": "Surat Keterangan Domisili",
            "deskripsi": "Menerangkan bahwa seseorang benar berdomisili di Desa Kampala.",
            "estimasi_hari": "2",
            "urutan": "1",
            "aktif": "1",
            "syarat": "KTP asli\nKartu Keluarga\nNomor HP aktif",
        },
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert 'value="2"' in client.get("/admin/layanan/DOM").text


def test_template_versi_baru(client):
    masuk(client, "sekdes")
    halaman = client.get("/admin/template")
    assert halaman.status_code == 200
    tid = int(re.search(r"/admin/template/(\d+)", halaman.text).group(1))
    halaman = client.get(f"/admin/template/{tid}")
    csrf = csrf_dari(halaman.text)
    konten = halaman.text.count("PEMERINTAH") and "#JUDUL#" or "#JUDUL#"

    r = client.post(
        f"/admin/template/{tid}",
        data={
            "csrf": csrf,
            "nama": "Template uji",
            "konten": f"{konten}\nSurat untuk {{nama_lengkap}}.",
            "mode": "baru",
        },
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert "dibuat dan diaktifkan" in r.headers["location"].lower() or "versi" in r.headers["location"].lower()


def test_dataset_tambah_dan_hapus(client):
    masuk(client, "admin")
    csrf = csrf_dari(client.get("/admin/dataset").text)

    r = client.post(
        "/admin/dataset",
        data={"csrf": csrf, "teks": "minta surat domisili untuk keperluan bank", "intent_kode": "AJUKAN_DOMISILI"},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    halaman = client.get("/admin/dataset?q=keperluan%20bank")
    assert "keperluan bank" in halaman.text
    sid = int(re.search(r'/admin/dataset/(\d+)/hapus', halaman.text).group(1))
    r = client.post(f"/admin/dataset/{sid}/hapus", data={"csrf": csrf})
    assert r.status_code == 303


def test_pengguna_baru_dan_duplikat(client):
    masuk(client, "admin")
    csrf = csrf_dari(client.get("/admin/pengguna").text)
    data = {
        "csrf": csrf,
        "nama_lengkap": "Petugas Uji",
        "email": "petugas.uji@desakampala.id",
        "role": "operator",
        "password": "SandiUji#2026",
    }
    r = client.post("/admin/pengguna", data=data)
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert "petugas.uji@desakampala.id" in client.get("/admin/pengguna").text

    r = client.post("/admin/pengguna", data=data)
    assert r.status_code == 303
    assert "err" in r.headers["location"]


def test_pengaturan_tersimpan(client):
    masuk(client, "admin")
    halaman = client.get("/admin/pengaturan")
    csrf = csrf_dari(halaman.text)
    sid = int(re.search(r'name="nilai_(\d+)"', halaman.text).group(1))

    r = client.post("/admin/pengaturan", data={"csrf": csrf, f"nilai_{sid}": "Kampala"})
    assert r.status_code == 303 and "err" not in r.headers["location"]


def test_nomor_surat_dapat_disetel(client):
    masuk(client, "sekdes")
    csrf = csrf_dari(client.get("/admin/nomor").text)
    r = client.post(
        "/admin/nomor",
        data={"csrf": csrf, "tahun": "2026", "bulan": "10", "urutan": "7"},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    halaman = client.get("/admin/nomor")
    assert "008/DKP/X/2026" in halaman.text


def test_audit_mencatat_aksi(client):
    masuk(client, "sekdes")
    halaman = client.get("/admin/audit")
    assert halaman.status_code == 200
    assert "faq.create" in halaman.text or "service.update" in halaman.text
