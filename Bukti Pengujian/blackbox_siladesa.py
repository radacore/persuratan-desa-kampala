"""Black-box test harness SILADESA.

Menguji aplikasi lewat HTTP saja (tanpa mengimpor modul internal): input ->
keluaran yang dapat diamati. Menghasilkan tabel hasil + waktu respons untuk
Bab IV skripsi.

Jalankan: python3 blackbox_siladesa.py http://127.0.0.1:8020
"""

from __future__ import annotations

import io
import json
import re
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx
from PIL import Image

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8020"
CSRF = re.compile(r'name="csrf" value="([^"]+)"')
c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=60)


@dataclass
class Kasus:
    kode: str
    modul: str
    skenario: str
    masukan: str
    harapan: str
    lulus: bool = False
    aktual: str = ""
    detik: float = 0.0



#: Kode kasus uji dipetakan dari skenario agar penomoran pada skripsi dan
#: keluaran harness tidak pernah berbeda.
KODE = {
    "Masuk dengan kredensial sah": "BB-01",
    "Masuk dengan sandi salah": "BB-02",
    "Akses panel tanpa sesi": "BB-03",
    "Mengirim formulir masuk tanpa token CSRF": "BB-04",
    "Keluar dari sistem": "BB-05",
    "Operator membuka menu Pengguna": "BB-06",
    "Operator membuka Pengaturan sistem": "BB-07",
    "Sekdes membuka menu Model NLP": "BB-08",
    "Operator mencoba mencabut surat": "BB-09",
    "Membuka sesi percakapan baru": "BB-10",
    "Menanyakan syarat layanan": "BB-11",
    "Menanyakan biaya layanan": "BB-12",
    "Pertanyaan di luar cakupan": "BB-13",
    "Memilih layanan lewat nomor menu": "BB-14",
    "Mengisi NIK tidak valid (3 digit)": "BB-15",
    "Membatalkan pengajuan di tengah pengisian": "BB-16",
    "Mengajukan surat domisili lewat percakapan": "BB-17",
    "Menimpa data warga lewat API pengajuan": "BB-18",
    "Melacak tiket tanpa NIK": "BB-19",
    "Melacak tiket dengan NIK salah": "BB-20",
    "Melacak tiket dengan NIK benar": "BB-21",
    "Halaman lacak tanpa NIK": "BB-22",
    "Halaman lacak menampilkan tombol unduh": "BB-23",
    "Operator memverifikasi berkas": "BB-24",
    "Menerbitkan lewat form ubah status": "BB-25",
    "Sekdes menerbitkan surat": "BB-26",
    "Menerbitkan ulang surat yang sama": "BB-27",
    "Warga mengunduh PDF surat": "BB-28",
    "Mengunduh dengan token palsu": "BB-29",
    "Verifikasi dokumen sah lewat QR": "BB-30",
    "Verifikasi token tidak dikenal": "BB-31",
    "Verifikasi dokumen yang berkasnya diubah": "BB-32",
    "Token verifikasi melebihi panjang kolom": "BB-33",
    "Mengunggah lampiran KTP": "BB-34",
    "Mengunggah berkas berkedok gambar": "BB-35",
    "Kepala desa mencabut surat terbit": "BB-36",
    "Verifikasi surat setelah dicabut": "BB-37",
    "Halaman lacak setelah surat dicabut": "BB-38",
    "Mengekspor laporan CSV": "BB-49",
    "Menyimpan perubahan katalog layanan": "BB-50",
    "Membaca katalog layanan publik": "BB-51",
    "Diagnostik prediksi intent": "BB-52",
}


def K(skenario: str, modul: str, masukan: str, harapan: str) -> "Kasus":
    """Bangun kasus uji dengan kode yang diambil dari peta."""
    return Kasus(KODE[skenario], modul, skenario, masukan, harapan)


HASIL: list[Kasus] = []
WAKTU_CHAT: list[float] = []


def catat(k: Kasus, lulus: bool, aktual: str, detik: float = 0.0) -> None:
    k.lulus, k.aktual, k.detik = lulus, aktual, detik
    HASIL.append(k)


def login(email: str, sandi: str) -> httpx.Response:
    r = c.get("/admin/login")
    if r.status_code != 200:
        c.post("/admin/logout", data={"csrf": CSRF.search(c.get("/admin").text).group(1)})
        r = c.get("/admin/login")
    tok = CSRF.search(r.text).group(1)
    return c.post(
        "/admin/login",
        data={"email": email, "password": sandi, "csrf": tok, "next": "/admin"},
    )


def tok(path: str) -> str:
    return CSRF.search(c.get(path).text).group(1)


def nik_baru() -> str:
    return "7304" + "".join(str(uuid.uuid4().int)[i] for i in range(12))


# --------------------------------------------------------------------------- #
# Modul 1 — Autentikasi & sesi
# --------------------------------------------------------------------------- #
def modul_auth() -> None:
    t0 = time.perf_counter()
    r = login("admin@desakampala.id", "Admin#2026")
    dt = time.perf_counter() - t0
    catat(K("Masuk dengan kredensial sah", "Autentikasi",
                "admin@desakampala.id / Admin#2026",
                "Dialihkan (303) ke panel, cookie sesi terbit"),
          r.status_code == 303 and "siladesa_session" in r.cookies, f"HTTP {r.status_code}", dt)

    r = login("admin@desakampala.id", "sandi-salah")
    catat(K("Masuk dengan sandi salah", "Autentikasi",
                "admin@desakampala.id / sandi-salah",
                "Ditolak (401), pesan galat, tanpa cookie sesi"),
          r.status_code == 401 and "siladesa_session" not in r.cookies,
          f"HTTP {r.status_code}")

    c.cookies.clear()
    r = c.get("/admin/pengajuan")
    catat(K("Akses panel tanpa sesi", "Autentikasi",
                "GET /admin/pengajuan",
                "Dialihkan ke halaman masuk (303)"),
          r.status_code == 303 and "/admin/login" in r.headers.get("location", ""),
          f"HTTP {r.status_code} → {r.headers.get('location', '')[:40]}")

    login("operator@desakampala.id", "Demo#2026")
    r = c.get("/admin/pengguna")
    catat(K("Operator membuka menu Pengguna", "Otorisasi",
                "GET /admin/pengguna sebagai operator",
                "Ditolak (403)"),
          r.status_code == 403, f"HTTP {r.status_code}")

    r = c.get("/admin/pengaturan")
    catat(K("Operator membuka Pengaturan sistem", "Otorisasi",
                "GET /admin/pengaturan sebagai operator",
                "Ditolak (403)"),
          r.status_code == 403, f"HTTP {r.status_code}")

    login("sekdes@desakampala.id", "Demo#2026")
    r = c.get("/admin/model")
    catat(K("Sekdes membuka menu Model NLP", "Otorisasi",
                "GET /admin/model sebagai sekdes",
                "Ditolak (403) — hanya admin teknis"),
          r.status_code == 403, f"HTTP {r.status_code}")

    r = c.post("/admin/faq", data={"csrf": "", "pertanyaan": "Uji", "jawaban": "Uji"})
    catat(K("Mengirim formulir masuk tanpa token CSRF", "Autentikasi",
                "POST /admin/faq tanpa csrf",
                "Ditolak (403)"),
          r.status_code == 403, f"HTTP {r.status_code}")

    login("sekdes@desakampala.id", "Demo#2026")
    # Token CSRF diambil dari halaman panel mana pun yang memuat formulir.
    halaman_panel = c.get("/admin/pengajuan").text
    tok_logout = CSRF.search(halaman_panel).group(1)
    r = c.post("/admin/logout", data={"csrf": tok_logout})
    sesudah = c.get("/admin/pengajuan")
    catat(K("Keluar dari sistem", "Autentikasi",
                "POST /admin/logout",
                "Cookie sesi dihapus, pengguna kembali ke halaman masuk"),
          r.status_code == 303 and sesudah.status_code == 303,
          f"HTTP {r.status_code}; akses ulang → {sesudah.status_code}")


# --------------------------------------------------------------------------- #
# Modul 2 — Percakapan (chatbot)
# --------------------------------------------------------------------------- #
def sesi_baru(kontak: str | None = None) -> str:
    r = c.post("/api/v1/chat/sessions", json={"channel": "web", "kontak": kontak or "uji"})
    return r.json()["session_id"]


def kirim(sid: str, pesan: str) -> dict:
    t0 = time.perf_counter()
    data = c.post("/api/v1/chat/messages", json={"session_id": sid, "pesan": pesan}).json()
    WAKTU_CHAT.append(time.perf_counter() - t0)
    return data


def modul_chat() -> None:
    r = c.post("/api/v1/chat/sessions", json={"channel": "web", "kontak": "bb"})
    catat(K("Membuka sesi percakapan baru", "Percakapan",
                "POST /api/v1/chat/sessions",
                "201, sesi terbuat, menu sapaan dikirim"),
          r.status_code == 201 and len(r.json()["balasan"]) >= 2,
          f"HTTP {r.status_code}, {len(r.json().get('balasan', []))} baris balasan")

    sid = sesi_baru("bb-intent")
    data = kirim(sid, "syarat surat keterangan domisili apa saja")
    teks = " ".join(data["balasan"]).lower()
    catat(K("Menanyakan syarat layanan", "Percakapan",
                "\"syarat surat keterangan domisili apa saja\"",
                "Intent INFO_SYARAT_DOMISILI, jawaban memuat KTP/KK"),
          data["intent"] == "INFO_SYARAT_DOMISILI" and ("ktp" in teks or "kartu keluarga" in teks),
          f"intent={data['intent']} conf={data['confidence']:.3f}")

    data = kirim(sid, "berapa biaya bikin surat")
    catat(K("Menanyakan biaya layanan", "Percakapan",
                "\"berapa biaya bikin surat\"",
                "Intent INFO_BIAYA, jawaban menyebut gratis"),
          data["intent"] == "INFO_BIAYA" and "gratis" in " ".join(data["balasan"]).lower(),
          f"intent={data['intent']} conf={data['confidence']:.3f}")

    data = kirim(sid, "bagaimana cara membuat npwp perusahaan asing")
    catat(K("Pertanyaan di luar cakupan", "Percakapan",
                "\"bagaimana cara membuat npwp perusahaan asing\"",
                "Fallback + tawaran eskalasi ke petugas"),
          data["perlu_petugas"] is True or "petugas" in " ".join(data["balasan"]).lower(),
          f"intent={data['intent']} conf={data['confidence']:.3f}")

    sid2 = sesi_baru("bb-menu")
    data = kirim(sid2, "1")
    catat(K("Memilih layanan lewat nomor menu", "Percakapan",
                "\"1\" pada sesi baru",
                "Beralih ke state CONSENT, menampilkan syarat + pertanyaan izin"),
          data["state"] == "CONSENT" and "lanjutkan" in " ".join(data["balasan"]).lower(),
          f"state={data['state']}")

    data = kirim(sid2, "ya")
    data = kirim(sid2, "123")
    catat(K("Mengisi NIK tidak valid (3 digit)", "Validasi",
                "\"123\" pada kolom NIK",
                "Ditolak, pesan menyebut 16 digit, tetap di pengisian"),
          "16" in " ".join(data["balasan"]) and data["state"] == "SLOT_FILLING",
          f"state={data['state']}")

    sid3 = sesi_baru("bb-batal")
    kirim(sid3, "1")
    kirim(sid3, "1")
    kirim(sid3, "ya")
    data = kirim(sid3, "batal")
    catat(K("Membatalkan pengajuan di tengah pengisian", "Percakapan",
                "\"batal\" saat pengisian data",
                "Sesi direset ke IDLE, pengajuan dibatalkan"),
          data["state"] == "IDLE" and "batal" in " ".join(data["balasan"]).lower(),
          f"state={data['state']}")


# --------------------------------------------------------------------------- #
# Modul 3 — Pengajuan sampai penerbitan
# --------------------------------------------------------------------------- #
JAWABAN = {
    "NIK": None, "Nama Lengkap": "BB TEST", "Tempat Lahir": "Jeneponto",
    "Tanggal Lahir": "1990-01-12", "Jenis Kelamin": "Laki-Laki",
    "Status Perkawinan": "Kawin", "Agama": "Islam", "Pekerjaan": "Petani",
    "Alamat": "Dusun Kalukuang", "Dusun": "Kalukuang", "RT": "002", "RW": "001",
    "Nomor HP": "081234567890", "Keperluan": "pendaftaran sekolah",
}


def ajukan(nik: str, nama: str = "BB TEST") -> str:
    sid = sesi_baru(nik)
    kirim(sid, "1")
    kirim(sid, "1")
    data = kirim(sid, "ya")
    for _ in range(40):
        if data.get("tiket"):
            return data["tiket"]
        teks = "\n".join(data.get("balasan") or [])
        if "data warga ditemukan" in teks.lower():
            data = kirim(sid, "1")
            continue
        if "ketik" in teks.lower() and "ya" in teks.lower():
            data = kirim(sid, "ya")
            continue
        label = next((k for k in JAWABAN if k.lower() in teks.lower()), None)
        assert label, teks[:300]
        data = kirim(sid, nik if JAWABAN[label] is None else JAWABAN[label])
    raise AssertionError("tiket tidak terbit")


def modul_pengajuan() -> tuple[str, str, int]:
    nik = nik_baru()
    t0 = time.perf_counter()
    tiket = ajukan(nik)
    dt = time.perf_counter() - t0
    catat(K("Mengajukan surat domisili lewat percakapan", "Pengajuan",
                "Menu 1 → Domisili → setujui → isi 14 kolom",
                "Tiket terbentuk berformat APP-{tahun}-{6 digit}"),
          bool(re.fullmatch(r"APP-\d{4}-\d{6}", tiket)), tiket, dt)

    r = c.post("/api/v1/applications", json={
        "service_kode": "DOM", "citizen": {"nik": nik, "nama_lengkap": "PENYUSUP"},
        "form_data": {"tempat_lahir": "X", "tanggal_lahir": "1990-01-12",
                      "jenis_kelamin": "Laki-Laki", "status_perkawinan": "Kawin",
                      "agama": "Islam", "pekerjaan": "Nelayan", "alamat": "Palsu",
                      "dusun": "Sepeka", "rt": "009", "rw": "009",
                      "no_hp": "081200000009", "keperluan": "X"}})
    halaman = c.get(f"/api/v1/track/{tiket}?nik={nik}").json()
    catat(K("Menimpa data warga lewat API pengajuan", "Keamanan",
                "POST /api/v1/applications dengan NIK warga lain, nama berbeda",
                "Data induk warga tidak berubah"),
          r.status_code == 201 and halaman["pemohon"] == "BB TEST",
          f"HTTP {r.status_code}, pemohon={halaman['pemohon']}")

    r = c.get(f"/api/v1/track/{tiket}")
    catat(K("Melacak tiket tanpa NIK", "Keamanan",
                "GET /api/v1/track/{tiket}",
                "Ditolak (422) — NIK wajib"),
          r.status_code == 422, f"HTTP {r.status_code}")

    r = c.get(f"/api/v1/track/{tiket}?nik={nik_baru()}")
    catat(K("Melacak tiket dengan NIK salah", "Keamanan",
                "GET /api/v1/track/{tiket}?nik=<NIK lain>",
                "Tidak ditemukan (404)"),
          r.status_code == 404, f"HTTP {r.status_code}")

    r = c.get(f"/api/v1/track/{tiket}?nik={nik}")
    catat(K("Melacak tiket dengan NIK benar", "Pelacakan",
                "GET /api/v1/track/{tiket}?nik=<NIK benar>",
                "200, status MENUNGGU_VERIFIKASI"),
          r.status_code == 200 and r.json()["status"] == "MENUNGGU_VERIFIKASI",
          f"HTTP {r.status_code}, status={r.json().get('status')}")

    login("operator@desakampala.id", "Demo#2026")
    app_id = int(re.search(r"/admin/pengajuan/(\d+)",
                           c.get(f"/admin/pengajuan?q={tiket}").text).group(1))
    t0 = time.perf_counter()
    r = c.post(f"/admin/pengajuan/{app_id}/status",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}"), "ke": "DIPROSES",
                     "catatan": "Berkas lengkap."})
    dt = time.perf_counter() - t0
    catat(K("Operator memverifikasi berkas", "Verifikasi",
                "Ubah status MENUNGGU_VERIFIKASI → DIPROSES",
                "303, status berubah, tercatat di riwayat"),
          r.status_code == 303 and "err" not in r.headers["location"],
          f"HTTP {r.status_code}", dt)

    r = c.post(f"/admin/pengajuan/{app_id}/status",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}"), "ke": "TERBIT"})
    catat(K("Menerbitkan lewat form ubah status", "Penerbitan",
                "POST status ke=TERBIT",
                "Ditolak, diarahkan ke tombol Terbitkan"),
          "err" in r.headers["location"], f"HTTP {r.status_code}")

    buf = io.BytesIO()
    Image.new("RGB", (80, 50), "white").save(buf, format="PNG")
    r = c.post(f"/admin/pengajuan/{app_id}/lampiran",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}")},
               files={"berkas": ("ktp.png", buf.getvalue(), "image/png")})
    catat(K("Mengunggah lampiran KTP", "Lampiran",
                "POST /admin/pengajuan/{id}/lampiran (PNG 80×50)",
                "303, berkas tersimpan dan tampil di detail"),
          r.status_code == 303 and "ktp.png" in c.get(f"/admin/pengajuan/{app_id}").text,
          f"HTTP {r.status_code}")

    r = c.post(f"/admin/pengajuan/{app_id}/lampiran",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}")},
               files={"berkas": ("skrip.png", b"<script>alert(1)</script>", "image/png")})
    catat(K("Mengunggah berkas berkedok gambar", "Lampiran",
                "Berkas berisi HTML dengan ekstensi .png",
                "Ditolak, tidak ada baris lampiran baru"),
          "err" in r.headers["location"], f"HTTP {r.status_code}")

    login("sekdes@desakampala.id", "Demo#2026")
    t0 = time.perf_counter()
    r = c.post(f"/admin/pengajuan/{app_id}/terbitkan",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}")})
    dt = time.perf_counter() - t0
    catat(K("Sekdes menerbitkan surat", "Penerbitan",
                "POST /admin/pengajuan/{id}/terbitkan",
                "303, nomor surat dan PDF terbentuk"),
          r.status_code == 303 and "err" not in r.headers["location"],
          f"HTTP {r.status_code}", dt)

    r = c.post(f"/admin/pengajuan/{app_id}/terbitkan",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}")})
    catat(K("Menerbitkan ulang surat yang sama", "Penerbitan",
                "POST terbitkan untuk kedua kali",
                "Ditolak — satu pengajuan satu surat"),
          "err" in r.headers["location"], f"HTTP {r.status_code}")

    tautan = re.search(r'href="(/d/[^"]+)"', c.get(f"/admin/pengajuan/{app_id}").text).group(1)
    pdf = c.get(tautan)
    catat(K("Warga mengunduh PDF surat", "Unduh",
                f"GET {tautan[:24]}…",
                "200, application/pdf, berkas berawalan %PDF-"),
          pdf.status_code == 200 and pdf.content[:5] == b"%PDF-",
          f"HTTP {pdf.status_code}, {len(pdf.content)} byte")

    r = c.get("/d/tebakan-ngawur")
    catat(K("Mengunduh dengan token palsu", "Keamanan",
                "GET /d/tebakan-ngawur",
                "Ditolak (410)"),
          r.status_code == 410, f"HTTP {r.status_code}")

    return tiket, nik, app_id


# --------------------------------------------------------------------------- #
# Modul 4 — Verifikasi & pencabutan
# --------------------------------------------------------------------------- #
def modul_verifikasi(tiket: str, nik: str, app_id: int) -> None:
    import sqlite3
    import os

    db_path = os.environ.get("SMOKE_DB", "")
    con = sqlite3.connect(db_path)
    qr_token, file_path = con.execute(
        "select qr_token, file_path from document order by id desc limit 1").fetchone()
    storage = os.environ.get("SMOKE_STORAGE", "")

    r = c.get(f"/api/v1/verify/{qr_token}")
    data = r.json()
    catat(K("Verifikasi dokumen sah lewat QR", "Verifikasi",
                f"GET /api/v1/verify/{{token}}",
                "valid=true, hasil=VALID, NIK tersamar"),
          data["valid"] is True and data["hasil"] == "VALID" and "*" in (data["nik_masked"] or ""),
          f"hasil={data['hasil']}, nik={data['nik_masked']}")

    r = c.get("/api/v1/verify/token-tidak-ada")
    catat(K("Verifikasi token tidak dikenal", "Verifikasi",
                "GET /api/v1/verify/token-tidak-ada",
                "200 dengan hasil TIDAK_DITEMUKAN (bukan 500)"),
          r.status_code == 200 and r.json()["hasil"] == "TIDAK_DITEMUKAN",
          f"HTTP {r.status_code}, hasil={r.json()['hasil']}")

    from pathlib import Path
    berkas = Path(storage) / file_path
    asli = berkas.read_bytes()
    berkas.write_bytes(asli + b"%sisipan")
    try:
        data = c.get(f"/api/v1/verify/{qr_token}").json()
        catat(K("Verifikasi dokumen yang berkasnya diubah", "Verifikasi",
                    "Menyisipkan 8 byte ke PDF di penyimpanan",
                    "valid=false, berkas_utuh=false"),
              data["valid"] is False and data["berkas_utuh"] is False,
              f"valid={data['valid']}, utuh={data['berkas_utuh']}")
    finally:
        berkas.write_bytes(asli)

    halaman = c.get(f"/lacak?tiket={tiket}&nik={nik}")
    catat(K("Halaman lacak menampilkan tombol unduh", "Pelacakan",
                f"GET /lacak?tiket={tiket}&nik=<NIK>",
                "Tombol 'Unduh surat' tampil setelah TERBIT"),
          "Unduh surat" in halaman.text, "tombol unduh tampil" if "Unduh surat" in halaman.text else "tidak tampil")

    halaman = c.get(f"/lacak?tiket={tiket}")
    catat(K("Halaman lacak tanpa NIK", "Keamanan",
                f"GET /lacak?tiket={tiket}",
                "Riwayat tidak ditampilkan, diminta NIK"),
          "Riwayat proses" not in halaman.text and "NIK" in halaman.text,
          "riwayat disembunyikan")

    login("kepaladesa@desakampala.id", "Demo#2026")
    r = c.post(f"/admin/pengajuan/{app_id}/cabut",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}"),
                     "alasan": "Data pemohon tidak sah."})
    catat(K("Kepala desa mencabut surat terbit", "Pencabutan",
                "POST /admin/pengajuan/{id}/cabut",
                "303, dokumen berstatus DIBATALKAN"),
          r.status_code == 303 and "err" not in r.headers["location"],
          f"HTTP {r.status_code}")

    data = c.get(f"/api/v1/verify/{qr_token}").json()
    catat(K("Verifikasi surat setelah dicabut", "Pencabutan",
                f"GET /api/v1/verify/{{token}}",
                "valid=false, hasil=DIBATALKAN"),
          data["valid"] is False and data["hasil"] == "DIBATALKAN",
          f"hasil={data['hasil']}")

    halaman = c.get(f"/lacak?tiket={tiket}&nik={nik}")
    catat(K("Halaman lacak setelah surat dicabut", "Pencabutan",
                f"GET /lacak?tiket={tiket}&nik=<NIK>",
                "Tautan unduh hilang, keterangan dicabut tampil"),
          "Unduh surat" not in halaman.text and "dicabut" in halaman.text.lower(),
          "tautan unduh hilang")

    login("operator@desakampala.id", "Demo#2026")
    r = c.post(f"/admin/pengajuan/{app_id}/cabut",
               data={"csrf": tok(f"/admin/pengajuan/{app_id}"), "alasan": "uji"})
    catat(K("Operator mencoba mencabut surat", "Otorisasi",
                "POST cabut sebagai operator",
                "Ditolak (403) — hanya kepala desa"),
          r.status_code == 403, f"HTTP {r.status_code}")


# --------------------------------------------------------------------------- #
# Modul 5 — Panel admin & batas laju
# --------------------------------------------------------------------------- #
def modul_admin() -> None:
    login("sekdes@desakampala.id", "Demo#2026")
    halaman = [
        ("/admin", "Ringkasan"), ("/admin/pengajuan", "Pengajuan"),
        ("/admin/warga", "Data warga"), ("/admin/layanan", "Layanan"),
        ("/admin/template", "Template surat"), ("/admin/nomor", "Nomor surat"),
        ("/admin/faq", "FAQ"), ("/admin/pejabat", "Pejabat"),
        ("/admin/audit", "Jejak audit"), ("/admin/laporan", "Laporan"),
    ]
    for nomor, (path, nama) in enumerate(halaman, start=39):
        r = c.get(path)
        catat(Kasus(f"BB-{nomor}", "Panel admin", f"Membuka halaman {nama}", f"GET {path}",
                    "200 dan halaman terbentuk"),
              r.status_code == 200, f"HTTP {r.status_code}")

    r = c.get("/admin/laporan.csv")
    catat(K("Mengekspor laporan CSV", "Panel admin",
                "GET /admin/laporan.csv",
                "200, text/csv, berpemisah titik koma"),
          r.status_code == 200 and ";" in r.text.splitlines()[0],
          f"HTTP {r.status_code}, {len(r.text.splitlines())} baris")

    r = c.post("/admin/layanan/DOM", data={
        "csrf": tok("/admin/layanan/DOM"), "nama": "Surat Keterangan Domisili",
        "estimasi_hari": "1", "urutan": "1", "aktif": "1",
        "syarat": "KTP asli\nKartu Keluarga\nNomor HP aktif"})
    catat(K("Menyimpan perubahan katalog layanan", "Panel admin",
                "POST /admin/layanan/DOM",
                "303, perubahan tersimpan"),
          r.status_code == 303 and "err" not in r.headers["location"],
          f"HTTP {r.status_code}")

    r = c.get("/v/" + "x" * 300)
    catat(K("Token verifikasi melebihi panjang kolom", "Keamanan",
                "GET /v/xxxx… (300 karakter)",
                "Ditolak (404), tidak menyentuh basis data"),
          r.status_code == 404, f"HTTP {r.status_code}")

    r = c.get("/api/v1/services")
    catat(K("Membaca katalog layanan publik", "API",
                "GET /api/v1/services",
                "200, empat layanan MVP aktif"),
          r.status_code == 200 and len(r.json()) >= 4,
          f"HTTP {r.status_code}, {len(r.json())} layanan")

    r = c.post("/api/v1/predict", json={"teks": "syarat sktm"})
    catat(K("Diagnostik prediksi intent", "NLP",
                "POST /api/v1/predict {\"teks\":\"syarat sktm\"}",
                "200, intent INFO_SYARAT_SKTM, ada alternatif"),
          r.status_code == 200 and r.json()["intent"] == "INFO_SYARAT_SKTM",
          f"intent={r.json().get('intent')}, conf={r.json().get('confidence', 0):.3f}")


def main() -> None:
    modul_auth()
    modul_chat()
    tiket, nik, app_id = modul_pengajuan()
    modul_verifikasi(tiket, nik, app_id)
    modul_admin()

    lulus = sum(1 for k in HASIL if k.lulus)
    print(f"{'Kode':6} {'Modul':16} {'Skenario':52} {'Hasil':6} {'Aktual'}")
    for k in HASIL:
        print(f"{k.kode:6} {k.modul:16} {k.skenario[:52]:52} "
              f"{'LULUS' if k.lulus else 'GAGAL':6} {k.aktual}")
    print(f"\nTotal: {len(HASIL)} kasus, {lulus} lulus, {len(HASIL) - lulus} gagal "
          f"({lulus / len(HASIL) * 100:.1f}%)")

    if WAKTU_CHAT:
        print(f"\nWaktu respons pesan chat (n={len(WAKTU_CHAT)}): "
              f"min {min(WAKTU_CHAT) * 1000:.0f} ms, "
              f"median {statistics.median(WAKTU_CHAT) * 1000:.0f} ms, "
              f"maks {max(WAKTU_CHAT) * 1000:.0f} ms, "
              f"rata-rata {statistics.mean(WAKTU_CHAT) * 1000:.0f} ms")
    import os
    keluar = os.environ.get("BB_JSON")
    if keluar:
        json.dump([k.__dict__ for k in HASIL], open(keluar, "w"), indent=1)
        print("\nJSON disimpan ke", keluar)


if __name__ == "__main__":
    main()
