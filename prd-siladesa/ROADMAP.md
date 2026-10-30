# ROADMAP.md: SILADESA

## Overview

Roadmap ini disusun untuk **satu developer** dengan sisa waktu skripsi ±14 minggu, dibagi menjadi enam fase. Setiap fase menghasilkan sesuatu yang **bisa didemokan**, sehingga kemajuan dapat ditunjukkan ke dosen pembimbing tanpa menunggu sistem selesai.

Jadwal memakai **minggu relatif (W1–W14)** agar tidak rapuh terhadap perubahan tanggal. Kolom kalender di bawah adalah contoh bila kickoff dimulai **2 November 2026**; geser seluruhnya bila tanggal mulai berubah.

| Fase | Minggu | Kalender (contoh) | Hasil utama |
|:---|:---|:---|:---|
| Fase 0 — Fondasi | W1–W2 | 2–15 Nov 2026 | Repo, database, auth admin, seed 4 layanan |
| Fase 1 — Chatbot & NLP | W3–W6 | 16 Nov–13 Des 2026 | Chat jalan di 3 kanal, model ≥ 85% |
| Fase 2 — Dokumen & Verifikasi | W7–W9 | 14 Des 2026–3 Jan 2027 | PDF bernomor + QR, halaman verifikasi |
| Fase 3 — Admin & Operasional | W10–W11 | 4–17 Jan 2027 | Alur setujui/tolak, template, nomor surat |
| Fase 4 — Hardening & Pengujian | W12–W13 | 18–31 Jan 2027 | UAT, uji beban, keamanan, dokumentasi |
| Fase 5 — Go-Live & Evaluasi | W14 | 1–7 Feb 2027 | Rilis produksi, pengukuran, data Bab IV |

## Phase 0 — Fondasi (W1–W2)

**Tujuan:** kerangka aplikasi yang dapat dijalankan, database lengkap, dan panel admin yang bisa login.

| Minggu | Pekerjaan | Deliverable |
|:---|:---|:---|
| W1 | Setup repo, struktur modul, `config.py`, logging, Docker Compose lokal | `docker compose up` menjalankan app + postgres |
| W1 | Seluruh model SQLAlchemy (22 tabel) + migrasi Alembic awal | `alembic upgrade head` bersih dari database kosong |
| W2 | Autentikasi admin: login, logout, sesi, RBAC, lockout | 4 peran dapat login; matriks izin teruji |
| W2 | Layout admin (Jinja2 + Tailwind + HTMX), navigasi, komponen dasar | Dashboard kosong tampil di 360 px dan 1440 px |
| W2 | Seed: 4 layanan, field, intent, setting, akun awal | `python -m app.seed` idempoten |

**Gerbang Fase 0 (akhir W2):**
- [ ] Aplikasi berjalan lokal dan di staging
- [ ] Migrasi naik–turun bersih
- [ ] Login + RBAC lolos test
- [ ] CI menjalankan `ruff` + `pytest`

**Risiko fase ini:** skema berubah setelah data ada. Mitigasi: kunci skema inti di akhir W1 dan gunakan migrasi untuk perubahan berikutnya.

## Phase 1 — Chatbot & NLP (W3–W6)

**Tujuan:** percakapan berfungsi end-to-end di tiga kanal dengan model yang memenuhi ambang akademik.

| Minggu | Pekerjaan | Deliverable |
|:---|:---|:---|
| W3 | Kumpulkan & labeli dataset (target 600+ ujaran, 18 intent) | `dataset.csv` + laporan distribusi kelas |
| W3 | Pipeline preprocessing: normalisasi, kamus lokal, stemming | Unit test preprocessing, contoh sebelum/sesudah |
| W4 | Trainer: TF-IDF + LinearSVC terkalibrasi, split 80/20, metrik | Model v1 + confusion matrix + akurasi awal |
| W4 | Adapter kanal: web widget, Telegram, Fonnte | Pesan masuk/keluar berfungsi di tiga kanal |
| W5 | Chat orchestrator: state machine, menu, info layanan, klarifikasi | Alur "tanya syarat" selesai tanpa admin |
| W5 | Slot filling + validasi field + ringkasan + submit | Pengajuan SKTM selesai dari chat |
| W6 | Antrean pertanyaan gagal + halaman pelabelan admin | Pertanyaan < 0,40 masuk antrean |
| W6 | Evaluasi model, iterasi kamus & dataset sampai ≥ 85% | Laporan evaluasi: akurasi, macro F1, per kelas |

**Gerbang Fase 1 (akhir W6):**
- [ ] Akurasi test set ≥ 85%, macro F1 ≥ 0,80
- [ ] Recall `FALLBACK` ≥ 0,75
- [ ] Latensi klasifikasi ≤ 50 ms
- [ ] Pengajuan dapat dibuat penuh dari WhatsApp tanpa campur tangan admin
- [ ] Percakapan tidak pernah "diam" — selalu ada balasan atau eskalasi

**Risiko fase ini:** dataset kurang. Mitigasi: mulai mengumpulkan ujaran sejak W1 (paralel), siapkan parafrase sintetis, dan aktifkan mode klarifikasi sehingga kesalahan tidak langsung menjadi jawaban salah.

## Phase 2 — Dokumen & Verifikasi (W7–W9)

**Tujuan:** surat resmi terbit sebagai PDF bernomor dengan QR yang dapat diverifikasi publik.

| Minggu | Pekerjaan | Deliverable |
|:---|:---|:---|
| W7 | Ekstraksi format dari arsip `Format surat/` → 4 template HTML | 4 template versi 1 dengan placeholder tervalidasi |
| W7 | Renderer ReportLab: kop, judul, isi, blok TTD, margin A4 | PDF contoh 4 layanan sesuai arsip |
| W8 | Alokasi nomor atomik + counter per layanan per tahun | Uji konkurensi: 20 penerbitan paralel, 0 duplikat |
| W8 | QR + token + hash SHA-256 + watermark draft | PDF final dengan QR 2,5 cm yang terpindai di 300 dpi |
| W9 | Halaman verifikasi `/v/{token}` (HTML) + endpoint JSON | Tiga status tampil benar: SAH, DIBATALKAN, tidak ditemukan |
| W9 | Log pemindaian + masking PII | Tidak ada NIK lengkap di respons publik |

**Gerbang Fase 2 (akhir W9):**
- [ ] PDF 4 layanan divalidasi Sekdes (format, redaksi, penomoran)
- [ ] Uji konkurensi penomoran lulus
- [ ] QR terpindai di 5 perangkat (Android, iOS, kamera biasa)
- [ ] Halaman verifikasi ≤ 1 detik dan terbaca di 360 px
- [ ] Tidak ada PII lengkap pada endpoint publik

**Risiko fase ini:** format surat desa tidak konsisten antar-arsip. Mitigasi: keputusan format diambil bersama Sekdes pada W7 dan dikunci sebelum W8.

## Phase 3 — Admin & Operasional (W10–W11)

**Tujuan:** aparat desa dapat menjalankan seluruh siklus layanan tanpa bantuan developer.

| Minggu | Pekerjaan | Deliverable |
|:---|:---|:---|
| W10 | Daftar & detail pengajuan, filter, pencarian, koreksi data | Operator dapat meninjau dan mengoreksi |
| W10 | Setujui/tolak + notifikasi ke warga + pengiriman PDF ke chat | Siklus submit → terbit → terkirim utuh |
| W11 | Editor template + pratinjau PDF + versioning | Sekdes dapat mengubah template sendiri |
| W11 | Manajemen pejabat & TTD, nomor surat, katalog layanan, FAQ | Seluruh konfigurasi tanpa deploy |
| W11 | Audit log, laporan bulanan, ekspor CSV | Rekap satu klik |

**Gerbang Fase 3 (akhir W11):**
- [ ] Operator baru dapat menyelesaikan satu pengajuan penuh setelah membaca panduan satu halaman
- [ ] Semua aksi admin tercatat di audit log
- [ ] Template baru tidak dapat diaktifkan bila placeholder tidak valid
- [ ] Penolakan selalu disertai alasan yang sampai ke warga

## Phase 4 — Hardening & Pengujian (W12–W13)

**Tujuan:** sistem layak dijalankan untuk data warga sebenarnya.

| Minggu | Pekerjaan | Deliverable |
|:---|:---|:---|
| W12 | UAT dengan 2 operator + 10 warga | Daftar temuan + perbaikan prioritas |
| W12 | Uji beban 50 concurrent, uji PDF 100 dokumen berurutan | Laporan performa vs target NFR |
| W13 | Audit keamanan: RBAC, CSRF, XSS, rate limit, unggahan berkas | Checklist keamanan terisi |
| W13 | Backup + uji restore penuh, monitoring, runbook | Restore berhasil dalam ≤ 4 jam |
| W13 | Dokumentasi: panduan operator, panduan admin teknis, OpenAPI | Tiga dokumen siap serah terima |
| W13 | Pengukuran kepuasan (SUS/Likert) pada sampel Slovin | Data mentah siap diolah untuk Bab IV |

**Gerbang Fase 4 (akhir W13):**
- [ ] Coverage ≥ 70%, seluruh test hijau
- [ ] Tidak ada temuan kritis/tinggi yang terbuka
- [ ] Restore backup teruji
- [ ] Target NFR terpenuhi atau selisihnya didokumentasikan
- [ ] Data pengujian terkumpul sesuai instrumen skripsi

## Phase 5 — Go-Live & Evaluasi (W14)

**Tujuan:** sistem berjalan di produksi dan menghasilkan data untuk Bab IV.

| Hari | Pekerjaan |
|:---|:---|
| 1 | Deploy produksi, seed, verifikasi `/healthz`, daftarkan webhook |
| 2 | Uji asap 8 skenario, aktifkan monitoring dan alert |
| 3 | Pelatihan operator (2 jam) + serah terima kredensial |
| 4 | Pengumuman ke warga lewat WhatsApp desa dan papan dusun |
| 5–7 | Pendampingan harian, perbaikan cepat, pengumpulan data awal |

**Gerbang Go-Live:** seluruh item pada checklist go-live di DEPLOYMENT.md tercentang.

## Scope Prioritization (MoSCoW)

### Must Have (MVP — wajib untuk sidang)

| ID | Fitur |
|:---|:---|
| FR-01…FR-07 | Chat multi-kanal, sesi, menu, consent, klasifikasi, preprocessing, ambang keyakinan |
| FR-08…FR-10 | Slot filling, validasi data, jawaban informasi layanan |
| FR-14, FR-15, FR-17 | Tiket pengajuan, ringkasan/konfirmasi, pelacakan status |
| FR-22…FR-28 | Katalog, field dinamis, template, nomor surat, PDF, QR, hash |
| FR-31, FR-33 | Halaman verifikasi publik, log pemindaian |
| FR-34, FR-36, FR-38, FR-39 | Login admin/RBAC, manajemen pengajuan, setujui, tolak |
| FR-41, FR-42, FR-46 | Pejabat & TTD, nomor surat, pelatihan & evaluasi model |
| FR-47 | Audit log |

### Should Have (dikerjakan bila waktu cukup)

| ID | Fitur |
|:---|:---|
| FR-11, FR-12 | FAQ, pencatatan pertanyaan gagal |
| FR-13 | Eskalasi ke petugas |
| FR-16, FR-18, FR-19 | Anti pengajuan ganda, pembatalan, notifikasi status |
| FR-20, FR-21 | Pengiriman PDF ke chat, survei kepuasan |
| FR-29, FR-30, FR-32 | Watermark, TTD pejabat, API verifikasi instansi |
| FR-35, FR-37, FR-40 | Dashboard, koreksi data, editor template |
| FR-43, FR-44, FR-45, FR-48, FR-49, FR-50 | Katalog, FAQ, dataset, pengguna, pengaturan, laporan |

### Could Have (fase 2 produk)

*   13 jenis surat tambahan (Kematian, Lahir, Belum/Sudah Menikah, Penghasilan Orang Tua, Ahli Waris, Jual Beli Tanah, Izin Pesta, SKCK, BDT, Kepemilikan Alat Pertanian, Kuasa, Wali Siswa, Penelitian, Pindah, Undangan, Panggilan).
*   Unggah lampiran dari chat.
*   Integrasi SIAK/Dukcapil.
*   Tanda tangan elektronik BSrE.
*   Model IndoBERT.
*   Aplikasi mobile.

### Won't Have (tidak dikerjakan)

*   Multi-desa / multi-tenant.
*   Pembayaran online.
*   Multi-bahasa.
*   Integrasi WhatsApp Cloud API resmi.

## Milestones & Gates

| Milestone | Minggu | Kriteria lulus | Konsekuensi bila gagal |
|:---|:---|:---|:---|
| **M0** Fondasi siap | W2 | App jalan, DB lengkap, login berfungsi | Mundurkan seluruh jadwal 1 minggu |
| **M1** Chat end-to-end | W5 | Pengajuan dapat dibuat dari WhatsApp | Pangkas fitur Should Have |
| **M2** Akurasi tercapai | W6 | Akurasi ≥ 85% | Tambah 1 minggu khusus dataset; pangkas fase 3 |
| **M3** Dokumen sah | W9 | PDF divalidasi Sekdes + QR terverifikasi | Blokir go-live sampai format benar |
| **M4** Operasional mandiri | W11 | Operator menyelesaikan pengajuan tanpa developer | Tunda go-live, tambah pelatihan |
| **M5** Siap produksi | W13 | Checklist keamanan & backup terpenuhi | Go-live terbatas (1 dusun) |
| **M6** Go-live | W14 | Checklist go-live lengkap | Rilis bertahap, monitoring ketat |

## Dependencies

| Pekerjaan | Bergantung pada | Pemilik | Dampak bila terlambat |
|:---|:---|:---|:---|
| Dataset 600+ ujaran | Wawancara warga + arsip pertanyaan | Developer + Operator | Blokir M2 |
| Validasi format surat | Keputusan Sekdes | Sekdes | Blokir M3 |
| Scan TTD pejabat | Kepala Desa | Kepala Desa | Blokir penerbitan |
| Nomor WhatsApp desa | Fonnte aktif | Sekdes | Blokir uji kanal |
| Domain & DNS | Pembelian domain | Developer | Blokir deploy |
| Data monografi (N/KK) | Arsip desa | Operator | Blokir perhitungan Slovin |
| UAT 10 warga | Koordinasi dusun | Operator | Blokir M5 |
| Surat izin penggunaan sistem | Kepala Desa | Kepala Desa | Blokir go-live |

**Aturan:** setiap dependensi di atas harus sudah dikonfirmasi pada **akhir W1**. Keterlambatan pada baris berstatus "Blokir M3" atau lebih tinggi memicu rapat penjadwalan ulang.

## Effort Estimation

| Fase | Estimasi effort | Catatan |
|:---|:---|:---|
| Fase 0 | 60 jam | Termasuk setup infra dan skema |
| Fase 1 | 120 jam | Termasuk pelabelan dataset (paling tidak terduga) |
| Fase 2 | 90 jam | Renderer PDF adalah bagian paling teknis |
| Fase 3 | 80 jam | Banyak CRUD, bisa dipercepat dengan pola seragam |
| Fase 4 | 70 jam | UAT dan perbaikan |
| Fase 5 | 30 jam | Deploy, pelatihan, pendampingan |
| **Total** | **± 450 jam** | Setara 32 jam/minggu selama 14 minggu |

**Buffer:** 15% (≈ 65 jam) disisihkan untuk hal tak terduga. Bila buffer habis sebelum W12, scope Should Have dipangkas sesuai urutan di tabel MoSCoW.

## Post-Launch Roadmap

### Bulan 1–3 setelah go-live

| Bulan | Fokus | Target |
|:---|:---|:---|
| 1 | Stabilisasi: perbaiki bug UAT, pantau error, dampingi operator | Uptime ≥ 99%, 0 insiden data |
| 2 | Kualitas NLP: labeli 200+ pertanyaan gagal, retrain, aktivasi model baru | Akurasi naik ≥ 3 poin |
| 3 | Evaluasi: rekap layanan, SUS, wawancara operator | Laporan evaluasi + rekomendasi |

### Fase 2 produk (setelah sidang)

| Prioritas | Fitur | Alasan |
|:---|:---|:---|
| 1 | 13 surat tambahan | Permintaan paling sering dari warga |
| 2 | Unggah lampiran dari chat | Mengurangi kunjungan fisik |
| 3 | Notifikasi proaktif (pengingat berkas kurang) | Mengurangi penolakan |
| 4 | Model IndoBERT | Meningkatkan pemahaman parafrase |
| 5 | TTE BSrE | Bila desa menganggarkan sertifikat |
| 6 | Integrasi Dukcapil | Bila ada izin resmi |

## Governance

| Ritme | Aktivitas | Peserta |
|:---|:---|:---|
| Harian (15 menit) | Update status pekerjaan, catat blocker | Developer |
| Mingguan (30 menit) | Demo progres ke pembimbing, putuskan scope | Developer + pembimbing |
| Dua mingguan | Review dengan Sekdes untuk konten & format surat | Developer + Sekdes |
| Akhir fase | Gerbang milestone, keputusan lanjut/geser | Developer + pembimbing |
| Bulanan (pasca-rilis) | Tinjauan operasional & metrik | Sekdes + Admin Teknis |

**Definisi selesai (Definition of Done) untuk setiap pekerjaan:**

1. Kode di-merge ke `main` dengan `ruff` bersih.
2. Ada test yang membuktikan perilaku (unit atau integrasi).
3. Aksi yang mengubah data tercatat di audit log.
4. Perubahan skema memiliki migrasi naik dan turun.
5. Endpoint baru terdokumentasi di API.md dan OpenAPI.
6. Sudah diuji di layar 360 px dan satu perangkat Android nyata.
7. Tidak ada data pribadi di log.

## Change Control

Perubahan scope setelah W6 hanya diterima bila memenuhi salah satu syarat:

*   Diwajibkan regulasi atau permintaan tertulis Kepala Desa.
*   Memperbaiki cacat keamanan atau integritas dokumen.
*   Menggantikan fitur dengan bobot setara (bukan menambah).

Setiap perubahan dicatat pada tabel berikut agar dapat dipertanggungjawabkan di sidang:

| Tanggal | Perubahan | Alasan | Dampak jadwal | Disetujui oleh |
|:---|:---|:---|:---|:---|
| — | — | — | — | — |
