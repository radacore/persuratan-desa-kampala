# PRD SILADESA

Dokumen ini adalah paket **Product Requirements Document** untuk **SILADESA — Sistem Layanan Administrasi Desa Kampala**, disusun dari skripsi *"Rancang Bangun Chatbot Layanan Administrasi Desa Berbasis Kecerdasan Buatan"* dan arsip `Format surat/` desa.

Paket terdiri atas sembilan dokumen yang saling merujuk. Baca berurutan, atau lompat langsung sesuai kebutuhan.

## Daftar Dokumen

| # | Dokumen | Isi | Bab skripsi terkait |
|:--|:---|:---|:---|
| 1 | [`PRD.md`](./PRD.md) | Ringkasan eksekutif, masalah & tujuan, persona, ruang lingkup, 50 functional requirement, NFR, stack teknologi, KPI, risiko | Bab I (Latar Belakang, Rumusan Masalah, Tujuan, Manfaat), Bab II (Landasan Teori) |
| 2 | [`REQUIREMENTS.md`](./REQUIREMENTS.md) | Seluruh FR dalam bentuk SHALL/MUST, NFR terukur, batasan teknis, asumsi | Bab III (Analisis Kebutuhan Sistem) |
| 3 | [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Diagram komponen, alur request, pipeline NLP, arsitektur keamanan, ADR | Bab III (Perancangan Sistem, Gambar 3.3) |
| 4 | [`DATABASE.md`](./DATABASE.md) | ERD 22 tabel, DDL PostgreSQL 16, indeks, state machine, seeding, retensi | Bab III (Perancangan Basis Data) |
| 5 | [`API.md`](./API.md) | Kontrak endpoint publik & admin, format respons, kode error, rate limit | Bab III (Perancangan Antarmuka) |
| 6 | [`USER_FLOW.md`](./USER_FLOW.md) | 12 alur pengguna dengan diagram, matriks transisi status | Bab III (Perancangan Alur Sistem) |
| 7 | [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md) | Palet warna, tipografi, komponen, aksesibilitas, design token | Bab III (Perancangan Antarmuka Pengguna) |
| 8 | [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Spesifikasi VPS, Docker Compose, CI/CD, backup, runbook, checklist go-live | Bab III (Kebutuhan Non-Fungsional & Implementasi) |
| 9 | [`ROADMAP.md`](./ROADMAP.md) | Jadwal 14 minggu, milestone, prioritas MoSCoW, estimasi effort | Bab III (Tabel 3.1 Rencana Penelitian) |

## Ringkasan Produk

| Aspek | Nilai |
|:---|:---|
| **Nama produk** | SILADESA (Sistem Layanan Administrasi Desa) |
| **Pengguna** | ±1.245 jiwa Desa Kampala, Kec. Arungkeke, Kab. Jeneponto |
| **Aktor** | `warga`, `operator`, `sekdes`, `kepala_desa`, `admin_teknis`, `verifikator` |
| **Kanal** | WhatsApp (Fonnte), Telegram Bot, web widget |
| **Layanan MVP** | 4 surat: Domisili (`DOM`), Tidak Mampu (`SKTM`), Usaha (`USH`), Pengantar (`PGG`) |
| **Target akademik** | Akurasi intent ≥ 85%, macro F1 ≥ 0,80 |
| **Model NLP** | TF-IDF (word + char n-gram) + LinearSVC terkalibrasi, Sastrawi |
| **Basis data** | PostgreSQL 16 (produksi) / SQLite (pengembangan) |
| **Hosting** | 1 VPS 2 vCPU / 2 GB, Docker Compose, Caddy |
| **Estimasi biaya** | ± Rp 250.000–320.000 / bulan |

## Perubahan Teknologi terhadap Bab III Skripsi

Bab III skripsi masih menyebut stack yang lebih berat. Bagian ini mencatat setiap penggantian beserta alasannya, agar skripsi dapat disesuaikan.

| Komponen | Di skripsi | Diganti menjadi | Alasan |
|:---|:---|:---|:---|
| Backend | Laravel / PHP | **FastAPI (Python 3.12)** | Satu bahasa untuk web, NLP, dan PDF — tidak perlu dua runtime |
| Frontend | React SPA | **Jinja2 + HTMX + Alpine.js** | Tidak ada build step JS; panel admin dipakai 2–3 orang |
| CSS | Bootstrap | **Tailwind CSS 3 (standalone CLI)** | Tanpa Node.js; hasil lebih kecil dan konsisten dengan design token |
| Model NLP | IndoBERT / TensorFlow | **TF-IDF + LinearSVC (scikit-learn)** | Dataset ratusan ujaran; IndoBERT butuh GPU dan data jauh lebih banyak |
| Antrean | Redis + Celery | **FastAPI BackgroundTasks + APScheduler** | < 1.000 pesan/hari pada satu mesin; tiga komponen lebih sedikit |
| WhatsApp | WhatsApp Cloud API | **Fonnte (gateway lokal)** | Tidak perlu verifikasi bisnis Meta dan nomor khusus |
| Penyimpanan berkas | AWS S3 | **Volume lokal + backup `restic`** | Biaya nol, latensi rendah, data tetap di Indonesia |
| Orkestrasi | Kubernetes | **Docker Compose** | Satu VPS, satu aplikasi |
| PDF | DomPDF | **ReportLab** | Kontrol tata letak A4 dan font lebih presisi |
| Autentikasi | JWT | **Session cookie + Argon2id** | Sederhana, aman, tidak ada token di `localStorage` |

**Yang tidak berubah** (tetap sesuai skripsi): target akurasi 85%, macro F1 ≥ 0,80, rumus Slovin dengan e = 10%, empat surat MVP, prinsip self-hosted tanpa API LLM komersial, dan seluruh batasan masalah pada Bab I.

## Alur Membaca yang Disarankan

```text
Pembimbing / penguji
  → PRD.md (§ Masalah, Tujuan, Scope, FR)
  → ARCHITECTURE.md (gambar komponen + pipeline NLP)
  → DATABASE.md (ERD)
  → USER_FLOW.md (alur yang didemokan)

Developer yang melanjutkan
  → ARCHITECTURE.md (§ modul & ADR)
  → DATABASE.md (DDL) → API.md (kontrak)
  → DEPLOYMENT.md (cara menjalankan)

Aparat desa
  → USER_FLOW.md (UF-08 s/d UF-12)
  → DESIGN_SYSTEM.md (§ Copy & Tone)
```

## Konvensi Penomoran

| Entitas | Format | Contoh |
|:---|:---|:---|
| Functional requirement | `FR-01` … `FR-50` | `FR-27` — dokumen wajib memuat QR |
| Non-functional requirement | `NFR-<KATEGORI>-<NN>` | `NFR-PERF-02` |
| Alur pengguna | `UF-01` … `UF-12` | `UF-09` — menyetujui & menerbitkan |
| Architecture decision | `ADR-001` … `ADR-007` | `ADR-004` — TF-IDF, bukan IndoBERT |
| Nomor tiket | `APP-{YYYY}-{seq:6d}` | `APP-2026-000128` |
| Nomor surat | `{seq:03d}/DKP/{bulan_romawi}/{tahun}` | `128/DKP/XI/2026` |
| Kode layanan | 3 huruf | `DOM`, `SKTM`, `USH`, `PGG` |

Seluruh FR yang disebut di `API.md`, `USER_FLOW.md`, `ROADMAP.md`, dan `DATABASE.md` merujuk pada penomoran yang sama di `PRD.md` dan `REQUIREMENTS.md`.

## Status Dokumen

| Dokumen | Versi | Status |
|:---|:---|:---|
| PRD.md | 1.0 | Final draf |
| REQUIREMENTS.md | 1.0 | Final draf |
| ARCHITECTURE.md | 1.0 | Final draf |
| DATABASE.md | 1.0 | Final draf |
| API.md | 1.0 | Final draf |
| USER_FLOW.md | 1.0 | Final draf |
| DESIGN_SYSTEM.md | 1.0 | Final draf |
| DEPLOYMENT.md | 1.0 | Final draf |
| ROADMAP.md | 1.0 | Final draf — jadwal mengikuti minggu relatif |

Dokumen versi tunggal sebelumnya (`PRD_CHATBOT_DESA_KAMPALA.md`) diarsipkan di [`_archive/`](./_archive/) dan **tidak lagi menjadi acuan**.

## Catatan Terbuka

Hal-hal berikut masih menunggu keputusan pemilik produk dan perlu diselesaikan sebelum implementasi dimulai:

1. **Nama produk** — "SILADESA" adalah nama kerja; dapat diganti tanpa memengaruhi isi dokumen lain.
2. **Tabel 3.1 skripsi** masih kosong; jadwal di `ROADMAP.md` memakai minggu relatif sampai tanggal mulai ditetapkan.
3. **Jumlah populasi** pada perhitungan Slovin di skripsi masih placeholder (`N = 1.245`); perlu angka monografi resmi desa.
4. **Format nomor surat** perlu pengesahan Kepala Desa sebelum template dikunci.
5. **Berkas tanda tangan pejabat** belum tersedia dalam bentuk digital.
6. **Nomor WhatsApp resmi desa** dan akun Fonnte belum dibuat.
