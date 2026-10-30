# SILADESA

**Sistem Layanan Administrasi Desa** — chatbot layanan surat Desa Kampala,
Kecamatan Arungkeke, Kabupaten Jeneponto. Warga mengajukan surat lewat percakapan,
operator memverifikasi di panel, sekdes menerbitkan PDF bertanda tangan dan QR
verifikasi, dan kepala desa dapat mencabut dokumen yang bermasalah.

Aplikasi ini adalah implementasi dari `prd-siladesa/` dan dirancang untuk satu VPS
kecil (2 vCPU / 2 GB) tanpa API LLM komersial.

---

## Daftar isi

1. [Fitur](#fitur)
2. [Tumpukan teknologi](#tumpukan-teknologi)
3. [Struktur folder](#struktur-folder)
4. [Menjalankan di komputer lokal](#menjalankan-di-komputer-lokal)
5. [Akun bawaan](#akun-bawaan)
6. [Perintah sehari-hari](#perintah-sehari-hari)
7. [Alur kerja surat](#alur-kerja-surat)
8. [Kanal percakapan](#kanal-percakapan)
9. [Model NLP](#model-nlp)
10. [Pengujian](#pengujian)
11. [Deploy ke VPS](#deploy-ke-vps)
12. [Perawatan dan pencadangan](#perawatan-dan-pencadangan)
13. [Keamanan dan privasi](#keamanan-dan-privasi)
14. [Batasan yang diketahui](#batasan-yang-diketahui)

---

## Fitur

**Untuk warga (tanpa akun)**

- Chatbot bahasa Indonesia informal: tanya syarat, biaya, lama proses, jam layanan.
- Pengajuan surat dengan pengisian data bertahap (14 kolom untuk surat domisili).
- NIK dikenali lebih dulu: bila sudah terdaftar, data warga ditampilkan untuk
  dikonfirmasi lalu dipakai ulang, sehingga warga hanya menjawab kolom khusus
  layanan (1 kolom untuk domisili, bukan 14).
- Persetujuan pemakaian data sebelum data disimpan.
- Nomor tiket `APP-2026-000123` untuk melacak status. Pelacakan **wajib**
  disertai NIK pemohon, karena nomor tiket berurutan dan mudah ditebak.
- Halaman lacak mandiri: `/lacak` (tiket + NIK), menampilkan nomor surat dan
  tombol unduh begitu status TERBIT; surat yang dicabut ditandai dan tidak
  dapat diunduh.
- Unduh PDF lewat tautan bertanda tangan berlaku 7 hari.
- Setelah surat terbit, tautan unduh langsung muncul di percakapan warga.
- Verifikasi keaslian dokumen lewat `/v/{token}` (NIK disamarkan, PDF tidak disajikan).
- API verifikasi instansi `/api/v1/verify/{token}` dibatasi 60 permintaan per menit
  per IP; halaman `/v/{token}` 20 per menit karena setiap kunjungan menulis baris
  `verification_scan`.

**Untuk petugas**

| Peran | Kewenangan utama |
|---|---|
| `operator` | Verifikasi berkas, ubah status, catat penolakan, kelola data warga |
| `sekdes` | Terbitkan surat (nomor + PDF + QR), kelola layanan, template, FAQ, pejabat, data warga |
| `kepala_desa` | Semua kewenangan sekdes + mencabut dokumen terbit (data warga hanya baca) |
| `admin_teknis` | Pengguna, pengaturan, dataset latih, latih ulang model, jejak audit, data warga |

Pejabat penanda tangan menyimpan nama, NIP, pangkat, masa berlaku, dan scan tanda
tangan (PNG/JPG maks 2 MB). Scan itu ditempel otomatis pada ruang tanda tangan PDF.
Surat tidak dapat diterbitkan bila pejabat untuk jabatan terkait tidak aktif atau
masa berlakunya sudah lewat.

Hanya **Kepala Desa** atau **Sekretaris Desa** yang boleh menjadi penanda tangan.
Bila Sekretaris Desa yang menandatangani, blok tanda tangan ditulis
`Mengetahui : / a/n Kepala Desa <desa> / (Sekretaris Desa)`; bila Kepala Desa yang
menandatangani, barisnya langsung `Kepala Desa <desa>`. Pengaturan yang menunjuk
jabatan lain ditolak, baik saat disimpan maupun saat surat diterbitkan.

Panel admin mencakup: ringkasan harian, antrean pengajuan, data warga, pertanyaan gagal
dijawab, katalog layanan dan kolom formulir, versi template surat, penghitung nomor
surat, FAQ, pejabat penanda tangan, metrik model per kelas, dataset latih, laporan CSV,
dan jejak audit append-only.

**Data warga**

Tabel `citizen` adalah data induk warga: identitas 13 kolom yang dipakai ulang saat
mengajukan surat. Data terisi otomatis saat pengajuan pertama dikirim, dan petugas
dapat menambah/mengubahnya lewat **Panel → Data warga**.

- Warga nonaktif (pindah domisili/meninggal) ditolak saat memakai NIK-nya di chat,
  tetapi riwayat suratnya tetap utuh.
- Hapus permanen hanya tersedia bila warga belum pernah mengajukan surat.
- Mengubah data warga **tidak** mengubah surat yang sudah terbit: PDF dan
  `application.form_data` menyimpan salinan saat pengajuan dikirim.

**Format surat**

Tata letak PDF mengikuti format surat resmi Desa Kampala:

- Kop tiga baris (kabupaten 14 pt, kecamatan 14 pt, nama desa 18 pt, Times bold)
  dengan logo Kabupaten Jeneponto 2,1 cm di kiri, lalu garis ganda.
  Logo bawaan ada di `app/static/img/logo-jeneponto.png`; pengaturan `logo_kop`
  dapat menunjuk berkas lain.
- Judul surat dicetak **di atas** nomor surat (`#JUDUL#` pada template).
- Margin A4: kiri 2,75 cm, kanan 2,5 cm, atas-bawah 2,54 cm (FR-26 mewajibkan 2,5–3 cm).
- Baris identitas menjorok ±0,8 cm, kolom label 4,2 cm, titik dua sejajar.
- Nama penanda tangan dan saksi dicetak tebal bergaris bawah.
- Surat Keterangan Usaha memakai blok kiri `Pemegang Surat` (`#PEMEGANG#`),
  sedangkan Domisili, Tidak Mampu, dan Pengantar memakai blok `Menyaksikan :`
  (Kapolsek).
- Domisili, Usaha, dan Pengantar ditandatangani Sekretaris Desa `a/n Kepala Desa`;
  Surat Keterangan Tidak Mampu ditandatangani Kepala Desa langsung.
- QR verifikasi 2,5 cm berdiri sebagai **kolom ketiga** di samping blok tanda tangan,
  bukan ditumpuk di bawah nama — supaya surat berisi banyak baris tetap satu halaman.

**Empat layanan MVP**

| Kode | Layanan | Kolom formulir |
|---|---|---|
| `DOM` | Surat Keterangan Domisili | 14 |
| `SKTM` | Surat Keterangan Tidak Mampu | 13 |
| `USH` | Surat Keterangan Usaha | 13 |
| `PGG` | Surat Pengantar | 12 |

---

## Tumpukan teknologi

| Lapisan | Pilihan | Alasan singkat |
|---|---|---|
| Bahasa | Python 3.12 | Ekosistem NLP matang, satu bahasa untuk web + ML |
| Web | FastAPI + Uvicorn | Ringan, dokumentasi API otomatis, cocok di VPS 2 GB |
| Tampilan | Jinja2 + HTMX + Alpine.js + CSS sendiri | Tanpa Node/build step, halaman tetap cepat |
| Basis data | SQLite (dev) → PostgreSQL 16 (prod) | SQLAlchemy 2.0 + Alembic, jalur migrasi jelas |
| NLP | TF-IDF (kata + karakter) → LinearSVC terkalibrasi | Latih sendiri, hemat RAM, tanpa API berbayar |
| PDF | ReportLab + `qrcode` + Pillow | Font Times bawaan, tidak perlu LibreOffice |
| Sesi | Cookie bertanda tangan (`itsdangerous`) + Argon2id | Tanpa Redis, tanpa tabel sesi |
| Kanal | Telegram Bot API, Fonnte (WhatsApp), widget web | Fonnte lebih murah dan sederhana dari Cloud API |
| Deploy | Docker Compose (app + db + Caddy) | TLS otomatis, satu perintah naik |

Penjelasan lengkap dan alternatif yang ditolak ada di `prd-siladesa/README.md`.

---

## Struktur folder

```
siladesa-app/
├── app/
│   ├── main.py            # aplikasi FastAPI, lifespan, penanganan galat
│   ├── config.py          # pengaturan dari .env
│   ├── db.py              # engine, sesi, Base
│   ├── models.py          # 22 tabel ORM
│   ├── schemas.py         # skema Pydantic untuk API
│   ├── constants.py       # peran, status, transisi, izin
│   ├── security.py        # sesi, CSRF, token unduh, hash sandi
│   ├── deps.py            # dependensi login/izin/CSRF
│   ├── templating.py      # filter & global Jinja
│   ├── seed.py            # pengisian data awal + latih model
│   ├── seed_data/         # katalog layanan, FAQ, template, dataset intent
│   ├── routers/           # public, api, admin, webhooks
│   ├── services/          # chat, aplikasi, dokumen, NLP, nomor, verifikasi, audit
│   ├── channels/          # adaptor Telegram/WhatsApp/web
│   ├── static/            # app.css, widget.js, favicon
│   └── templates/         # halaman publik, panel admin, galat
├── migrations/            # Alembic (revisi awal: skema 22 tabel)
├── tests/                 # pytest + httpx (108 tes)
├── docker/                # entrypoint.sh, Caddyfile
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Menjalankan di komputer lokal

Butuh Python 3.12+ (diuji pada 3.14) dan tidak perlu Node atau Docker.

```bash
cd siladesa-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env          # nilai bawaan sudah bisa dipakai untuk lokal
python -m app.seed            # buat tabel, isi katalog, latih model pertama
python -m uvicorn app.main:app --reload --port 8000
```

Buka:

- Situs warga — <http://localhost:8000>
- Panel admin — <http://localhost:8000/admin>
- Dokumentasi API — <http://localhost:8000/docs>
- Status kesehatan — <http://localhost:8000/health>

Seed pertama melatih model dari 551 kalimat (sekitar 10–20 detik di laptop biasa).
Model dan PDF disimpan di `data/`.

---

## Akun bawaan

Dibuat oleh `python -m app.seed`:

| Peran | Email | Sandi |
|---|---|---|
| Admin teknis | `admin@desakampala.id` | `Admin#2026` |
| Operator | `operator@desakampala.id` | `Demo#2026` |
| Sekdes | `sekdes@desakampala.id` | `Demo#2026` |
| Kepala desa | `kepaladesa@desakampala.id` | `Demo#2026` |

Akun demo **tidak dibuat** bila `APP_ENV=production`. Ganti sandi admin lewat
`BOOTSTRAP_ADMIN_PASSWORD` **sebelum** seed pertama, atau ubah setelah masuk.

---

## Perintah sehari-hari

```bash
python -m app.seed                # idempoten: aman dijalankan berulang
python -m app.seed --retrain      # latih ulang model dari dataset terbaru
python -m app.seed --reset        # HAPUS semua tabel lalu seed ulang (dev saja)

python -m pytest -q               # 108 tes
python -m alembic revision --autogenerate -m "ubah x"   # revisi baru
python -m alembic upgrade head    # terapkan migrasi
python -m alembic downgrade -1    # batalkan satu revisi
```

`app.seed` hanya **menambah baris yang belum ada**. Layanan, template, FAQ,
pejabat, intent, dan pengaturan yang sudah disunting lewat panel tidak pernah
dikembalikan ke nilai bawaan — termasuk saat kontainer produksi restart, karena
entrypoint menjalankan seed setiap kali naik. Untuk memaksa nilai bawaan,
hapus barisnya lebih dulu (atau `--reset` di lingkungan pengembangan).

Di produksi skema hanya dibuat oleh Alembic; `Base.metadata.create_all` tidak
dijalankan, sehingga tabel baru wajib lewat revisi migrasi.

---

## Alur kerja surat

```
Warga                 Operator              Sekdes                Kepala desa
  │                       │                    │                       │
  ├─ chat + isi data ────►│                    │                       │
  │  (DRAFT)              │                    │                       │
  │                       ├─ verifikasi ──────►│                       │
  │                       │  (MENUNGGU_VERIFIKASI → DIPROSES)           │
  │                       │                    ├─ terbitkan PDF + QR ──►│
  │                       │                    │  (TERBIT)             │
  │◄─ tautan unduh ───────┴────────────────────┤                       │
  │◄─ notifikasi status ──────────────────────┤                       │
  │                       │                    │◄── cabut dokumen ─────┤
  │                       │                    │  (DIBATALKAN)         │
```

- Nomor tiket: `APP-{tahun}-{id urut 6 digit}`.
- Nomor surat: `{urut 3 digit}/DKP/{bulan romawi}/{tahun}`, contoh `007/DKP/X/2026`.
- Status hanya bergerak lewat transisi yang sah di `app/constants.py`; permintaan
  di luar itu ditolak dan tercatat di jejak audit.
- Status `TERBIT` **hanya** bisa dicapai lewat tombol **Terbitkan & buat PDF**.
  Form "Ubah status" sengaja tidak menawarkan `TERBIT`, karena perubahan status
  biasa tidak membuat nomor surat maupun berkas PDF — akibatnya warga melihat
  status terbit tanpa tautan unduh.
- Satu NIK dibatasi 3 pengajuan aktif agar antrean tidak dibanjiri.

---

## Kanal percakapan

| Kanal | Cara pasang |
|---|---|
| Web | Widget mengambang di semua halaman publik (`/api/v1/chat/*`) |
| Telegram | Isi `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET`, lalu daftarkan webhook ke `/webhooks/telegram/{secret}` |
| WhatsApp (Fonnte) | Isi `FONNTE_TOKEN` + `FONNTE_WEBHOOK_TOKEN`, arahkan webhook Fonnte ke `/webhooks/whatsapp/{secret}` |

Rahasia webhook dibandingkan dengan `secrets.compare_digest`, dan permintaan tanpa
rahasia yang cocok ditolak sebelum menyentuh basis data.

---

## Model NLP

Pipeline: normalisasi slang → stemming Sastrawi → TF-IDF kata (1–2 gram) +
TF-IDF karakter (3–5 gram) → LinearSVC terkalibrasi (Platt scaling) agar keluar
probabilitas.

Ambang keputusan:

| Keyakinan | Perilaku bot |
|---|---|
| ≥ 0,65 | Jawab langsung sesuai intent |
| 0,40 – 0,65 | Minta klarifikasi, tampilkan 2–3 pilihan |
| < 0,40 | Fallback + tawarkan bicara dengan petugas; pertanyaan masuk antrean gagal |

**Hasil pengukuran** (5-fold cross-validation berstrata, 551 kalimat, 18 intent):

| Metrik | Nilai | Target skripsi |
|---|---|---|
| Akurasi | 0,886 | ≥ 0,85 |
| Macro F1 | 0,885 | ≥ 0,80 |
| Sampel latih | 551 (27–36 per intent) | — |

Angka ini dihasilkan `python -m app.seed` dan ditampilkan di
**Panel → Model NLP**, termasuk F1 per kelas. Metrik disimpan di tabel
`MODEL_METRIC` setiap kali model dilatih, sehingga riwayat pelatihan bisa diaudit.

Koreksi dari panel (menu *Dataset latih*) menambah sampel baru; latih ulang lewat
tombol **Latih ulang model** agar perbaikan langsung terpakai.

---

## Pengujian

```bash
python -m pytest -q          # 108 lulus
```

Cakupan:

| Berkas | Isi |
|---|---|
| `test_publik.py` | Halaman publik, lacak, verifikasi, unduh, 404 |
| `test_auth.py` | Masuk, sandi salah, CSRF, keluar, akses tamu |
| `test_chat.py` | Percakapan, validasi NIK, batas 3 pengajuan, umpan balik |
| `test_warga.py` | CRUD data warga, hak akses, alur NIK dikenal/nonaktif di chat |
| `test_pengajuan.py` | Alur verifikasi → terbit → cabut, transisi tidak sah |
| `test_admin.py` | FAQ, layanan, template, nomor surat, dataset, pengguna |
| `test_nlp.py` | Klasifikasi contoh kalimat, ambang metrik, keseimbangan dataset |
| `test_webhook.py` | Rahasia webhook Telegram dan Fonnte |
| `test_format_surat.py` | Kop berlogo, urutan judul–nomor, blok tanda tangan |
| `test_pejabat_ttd.py` | Unggah scan TTD, pemisahan tugas, masa berlaku pejabat |
| `test_ratelimit.py` | Kuota verifikasi, login, chat, dan pemisahan kunci per jenis |
| `test_audit_regresi.py` | Regresi K1–K5, M1, M2, M6, M7 (lihat di bawah) |

Tes memakai basis data sementara di direktori tmp; data pengembangan tidak tersentuh.

---

## Deploy ke VPS

Target: Ubuntu 24.04, 2 vCPU, 2 GB RAM, 40 GB disk.

```bash
# 1. Siapkan server
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"   # logout/login agar berlaku

# 2. Ambil kode
git clone <repo> siladesa && cd siladesa/siladesa-app

# 3. Konfigurasi
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY
nano .env
#   APP_ENV=production
#   APP_URL=https://siladesa.desakampala.id
#   SECRET_KEY=<hasil perintah di atas>
#   POSTGRES_PASSWORD=<sandi kuat>
#   DOMAIN=siladesa.desakampala.id
#   BOOTSTRAP_ADMIN_PASSWORD=<sandi kuat>

# 4. Jalankan
docker compose up -d --build
docker compose logs -f app
```

Saat kontainer naik, entrypoint menjalankan `alembic upgrade head` lalu seed
idempoten, baru menyalakan Uvicorn. Caddy mengurus sertifikat Let's Encrypt
otomatis begitu DNS `DOMAIN` mengarah ke IP VPS dan port 80/443 terbuka.

Pembaruan versi:

```bash
git pull
docker compose up -d --build
```

Migrasi berjalan otomatis di entrypoint; tidak ada langkah manual.

---

## Perawatan dan pencadangan

Tiga hal yang harus dicadangkan: basis data, folder `data/storage` (PDF + lampiran),
dan `data/models`.

```bash
# Dump harian
docker compose exec -T db pg_dump -U siladesa siladesa | gzip > /backup/db-$(date +%F).sql.gz

# Berkas dan model
tar czf /backup/berkas-$(date +%F).tar.gz data/storage data/models
```

Simpan hasilnya di luar VPS (rclone ke Google Drive atau restic ke S3-compatible),
jadwalkan lewat cron pukul 02.00 WITA, dan **uji pemulihan** minimal sekali sebelum
sidang.

Pemantauan minimal: Uptime Kuma memantau `/health`, `loguru`/log Docker untuk
kesalahan, dan kuota gratis Sentry untuk jejak eksepsi.

---

## Keamanan dan privasi

- Sandi di-hash Argon2id; sesi ditandatangani dan kedaluwarsa.
- Semua POST panel admin wajib membawa token CSRF dari sesi.
- NIK disamarkan di daftar dan halaman verifikasi; hanya operator yang melihat
  data lengkap saat memverifikasi.
- Token unduh ditandatangani dan berlaku 7 hari; token QR bukan kapabilitas unduh.
- Dokumen yang dicabut tidak bisa diunduh lagi (HTTP 410) dan halaman verifikasi
  menampilkan **DIBATALKAN**.
- Data formulir disimpan sebagai snapshot JSON, sehingga perubahan data warga
  setelah surat terbit tidak mengubah isi dokumen lama.
- Tabel `APPLICATION_EVENT`, `AUDIT_LOG`, dan `VERIFICATION_SCAN` bersifat
  append-only: tidak ada endpoint ubah/hapus.

---

## Batasan yang diketahui

- Unggah berkas persyaratan dari sisi warga belum dibuka; petugas yang
  mengarsipkan KTP/KK/foto lewat **Panel → Pengajuan → Unggah lampiran**
  (PDF/PNG/JPG, maksimal `MAX_UPLOAD_MB`).
- Notifikasi otomatis memerlukan token Telegram/Fonnte yang aktif; tanpa token,
  status tetap bisa dilacak lewat halaman `/lacak` dan tautan unduh tetap
  tersimpan pada percakapan warga.
- Pembatas laju disimpan di memori proses. Bila aplikasi dijalankan lebih dari
  satu proses, kuota perlu dipindah ke Redis agar berlaku menyeluruh. Dapat
  dimatikan dengan `RATE_LIMIT_ENABLED=false` (dipakai suite pengujian).
- Enkripsi kolom (`pgcrypto`) belum aktif — volume disk dan pencadangan yang
  dienkripsi jadi batas perlindungan saat ini (lihat `prd-siladesa/DATABASE.md`).
- Belum ada worker terpisah. Operasi berat (latih model, render PDF, kirim
  WhatsApp/Telegram) dijalankan di threadpool agar event loop tetap melayani
  permintaan lain, tetapi tetap memakai proses yang sama. Cukup untuk beban satu
  desa, bukan untuk banyak desa sekaligus.
- Model masih berbasis TF-IDF; kalimat yang sangat berbeda dari data latih akan
  jatuh ke fallback dan masuk antrean pertanyaan gagal untuk diperbaiki petugas.

---

## Lisensi dan atribusi

Kode ini ditulis untuk keperluan skripsi pada Program Studi Teknik Informatika.
Data desa, nama pejabat, dan format surat mengikuti arsip Desa Kampala. Gunakan
dan ubah sesuai kebutuhan desa; cantumkan atribusi bila dipublikasikan ulang.
