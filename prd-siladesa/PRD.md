# PRD: SILADESA

## Executive Summary & Product Vision

Dokumen ini mendefinisikan Product Requirements untuk **SILADESA** (Sistem Layanan Administrasi Desa), aplikasi layanan administrasi **Desa Kampala, Kecamatan Arungkeke, Kabupaten Jeneponto**. SILADESA menggabungkan tiga kemampuan dalam satu sistem:

1. **Chatbot berbasis Natural Language Processing (NLP)** yang memahami pertanyaan warga dalam bahasa Indonesia sehari-hari, termasuk singkatan dan campuran dialek lokal.
2. **Otomasi penerbitan dokumen** surat keterangan desa dalam format PDF, lengkap dengan nomor surat, kop surat, tanda tangan pejabat, dan QR Code verifikasi keabsahan.
3. **Panel admin web** untuk mengelola katalog layanan, template surat, nomor surat, persetujuan dokumen, basis pengetahuan, dan evaluasi model NLP.

Visi produk adalah menjadikan layanan informasi dan penerbitan surat desa **tersedia 24 jam, dapat diaudit, dan dapat diverifikasi pihak ketiga**, tanpa menambah beban kerja aparat desa dan tanpa mengirim data warga ke layanan pihak ketiga.

Sistem dibangun **mandiri (self-hosted)**: model NLP dilatih sendiri dengan dataset lokal, dijalankan pada server desa atau VPS, dan **tidak memanggil API LLM komersial** (ChatGPT, Claude, Gemini). Seluruh pemrosesan bahasa dan data warga berada dalam kendali desa.

Sasaran akhirnya bersifat akademik sekaligus operasional: sistem harus cukup matang untuk diuji secara terukur (akurasi intent, waktu respons, kepuasan pengguna) sebagai bagian dari skripsi, dan cukup sederhana untuk benar-benar dijalankan oleh dua orang operator desa setelah sidang.

## Problem Statement & Target Users

**Problem:** Pelayanan administrasi Desa Kampala masih sepenuhnya manual dan tatap muka. Warga harus datang ke kantor desa pada jam kerja hanya untuk menanyakan persyaratan, sering kembali tanpa dokumen lengkap, dan aparat desa menjawab pertanyaan yang sama berulang kali. Surat yang diterbitkan juga tidak memiliki mekanisme verifikasi cepat, sehingga pihak ketiga (bank, sekolah, dinas) harus menghubungi kantor desa secara manual untuk memastikan keasliannya.

Lima masalah utama yang harus diselesaikan:

| Kode | Masalah | Dampak |
|:--|:--|:--|
| **P1** | Informasi persyaratan hanya tersedia saat jam kerja dan harus ditanyakan langsung | Warga datang berulang, pulang tanpa dokumen lengkap |
| **P2** | Pertanyaan yang sama dijawab berulang oleh aparat desa | Waktu aparat habis untuk pekerjaan repetitif |
| **P3** | Antrean fisik di kantor desa | Pelayanan lambat, kepuasan warga rendah |
| **P4** | Tidak ada mekanisme verifikasi keaslian surat | Risiko pemalsuan, verifikasi manual memakan waktu |
| **P5** | Belum ada kanal digital resmi milik desa | Informasi beredar tidak konsisten dari mulut ke mulut |

**Target Users:**

- **Warga pemohon:** penduduk Desa Kampala usia 17–65 tahun, pengguna aktif WhatsApp, yang membutuhkan informasi atau surat keterangan.
- **Verifikator eksternal:** pihak ketiga (bank, sekolah, dinas, perusahaan) yang menerima surat dan perlu memastikan keasliannya.
- **Operator layanan:** staf kantor desa yang memverifikasi berkas dan menerbitkan dokumen.
- **Sekretaris Desa dan Kepala Desa:** penanggung jawab administrasi dan pejabat penandatangan.
- **Admin teknis:** pengelola sistem, dataset, dan model NLP.

## System Scope & User Roles

Sistem terdiri atas tiga permukaan: **kanal percakapan** (WhatsApp, Telegram, web widget), **portal verifikasi publik**, dan **panel admin**. Scope MVP dibatasi pada empat jenis surat sesuai Batasan Masalah skripsi: Surat Keterangan Domisili, Surat Keterangan Tidak Mampu (SKTM), Surat Keterangan Usaha, dan Surat Pengantar.

| Role | Description | Permissions |
|:---|:---|:---|
| **Warga** (anonymous, teridentifikasi lewat kanal) | Penduduk yang berinteraksi melalui chatbot. Tidak memiliki akun. | - Mengajukan pertanyaan layanan. - Membuat, melihat, dan membatalkan pengajuannya sendiri. - Mengunduh dokumen miliknya. - Memberi umpan balik. |
| **Verifikator** (anonymous) | Siapa pun yang memindai QR pada dokumen. | - Melihat status keabsahan dokumen. - Melihat metadata dokumen yang di-mask. |
| **Operator** | Staf kantor desa yang menangani antrean pengajuan. | - Melihat seluruh pengajuan. - Memverifikasi dan mengoreksi data pemohon. - Menolak pengajuan dengan alasan. - Mengelola basis pengetahuan dan FAQ. |
| **Sekdes** | Sekretaris Desa, penanggung jawab administrasi. | - Seluruh hak Operator. - Menyetujui dan menerbitkan dokumen. - Mengelola katalog layanan, template surat, dan nomor surat. - Melihat audit log dan laporan. |
| **Kepala Desa** | Pejabat penandatangan. | - Seluruh hak Sekdes. - Mengelola pejabat dan scan tanda tangan. - Mencabut dokumen yang sudah terbit. |
| **Admin Teknis** | Pengelola sistem dan model NLP. | - Mengelola akun admin dan pengaturan sistem. - Melabeli dataset, melatih, dan mengaktifkan model. - Mengakses audit log. - Tidak dapat menyetujui dokumen. |

## Functional Requirements

### Kanal Percakapan & Warga

- **FR-01: Kanal Percakapan Multi-Channel:** Menerima dan membalas pesan dari WhatsApp, Telegram, dan web widget melalui satu lapisan adapter, dengan pipeline percakapan yang identik di ketiga kanal.
- **FR-02: Identifikasi & Sesi Pengguna:** Mengidentifikasi pengguna berdasarkan nomor WhatsApp, Telegram user ID, atau cookie sesi web; menyimpan konteks percakapan selama 30 menit sejak aktivitas terakhir.
- **FR-03: Menu Layanan & Onboarding:** Menampilkan menu utama pada percakapan pertama, berisi empat layanan MVP, opsi "Tanya hal lain", dan opsi "Bicara dengan petugas".
- **FR-04: Persetujuan Pemrosesan Data:** Meminta persetujuan eksplisit sebelum pengajuan surat dibuat, serta menyimpan bukti persetujuan (waktu, versi kebijakan, kanal).
- **FR-05: Klasifikasi Intent NLP:** Mengklasifikasikan setiap pesan ke salah satu intent terdaftar dan mengembalikan `intent`, `confidence`, serta tiga kandidat teratas.
- **FR-06: Preprocessing Teks Bahasa Indonesia:** Melakukan case folding, normalisasi singkatan dan dialek lokal, tokenisasi, stopword removal, dan stemming sebelum klasifikasi.
- **FR-07: Ambang Keyakinan & Klarifikasi:** Menjawab langsung bila `confidence` ≥ 0,65; meminta klarifikasi bila 0,40–0,65; dan menawarkan eskalasi bila < 0,40.
- **FR-08: Slot Filling Multi-Turn:** Mengumpulkan field wajib satu per satu melalui percakapan, dengan kemampuan mengoreksi jawaban sebelumnya tanpa mengulang sesi.
- **FR-09: Validasi Data Pemohon:** Memvalidasi NIK (16 digit, prefix wilayah 73.04), nomor KK, tanggal lahir, nomor HP, dan nilai enum (agama, status perkawinan, dusun) sebelum data disimpan.
- **FR-10: Jawaban Informasi Layanan:** Menjawab pertanyaan persyaratan, prosedur, estimasi waktu, dan biaya dari basis data layanan, bukan dari teks yang di-hardcode.
- **FR-11: FAQ & Informasi Operasional:** Menjawab pertanyaan umum tentang jam layanan, lokasi kantor, daftar dusun, dan kontak.
- **FR-12: Pencatatan Pertanyaan Gagal:** Menyimpan pertanyaan yang tidak terklasifikasi ke antrean *unanswered questions* untuk dilabeli dan dipakai retrain.
- **FR-13: Eskalasi ke Petugas:** Membuat tiket eskalasi dan memberi estimasi respons ketika warga meminta bantuan manusia atau ketika intent gagal dikenali dua kali berturut-turut.
- **FR-14: Pembuatan Tiket Pengajuan:** Membuat tiket dengan nomor `APP-{YYYY}-{seq:6d}` dan status awal `DRAFT` ketika warga memulai pengajuan.
- **FR-15: Ringkasan & Konfirmasi:** Menampilkan ringkasan seluruh data sebelum submit, dengan opsi mengubah field tertentu.
- **FR-16: Pencegahan Pengajuan Ganda:** Membatasi maksimal tiga pengajuan aktif per NIK per 24 jam.
- **FR-17: Pelacakan Status:** Menjawab perintah "status" dengan status pengajuan terakhir milik pengguna, termasuk alasan bila ditolak.
- **FR-18: Pembatalan Pengajuan:** Memungkinkan warga membatalkan pengajuan selama status belum `DIPROSES`, tanpa menghanguskan nomor surat yang belum terpakai.
- **FR-19: Notifikasi Perubahan Status:** Mengirim notifikasi ke kanal asal setiap kali status pengajuan berubah.
- **FR-20: Pengiriman Dokumen ke Chat:** Mengirim berkas PDF ke percakapan warga segera setelah dokumen berstatus `TERBIT`.
- **FR-21: Survei Kepuasan:** Meminta penilaian kepuasan setelah dokumen diterima dan menyimpan skor beserta komentar.

### Dokumen & Verifikasi

- **FR-22: Katalog Layanan Administrasi:** Menyimpan katalog layanan (kode, nama, deskripsi, persyaratan, alur, SLA, biaya) yang dapat diubah admin tanpa mengubah kode program.
- **FR-23: Skema Field Dinamis:** Menyimpan definisi field per layanan (label, tipe, wajib, urutan, opsi, aturan validasi) sehingga penambahan layanan baru tidak memerlukan migrasi skema.
- **FR-24: Template Surat & Placeholder:** Mengelola template surat berversi dengan placeholder `{{nama_lengkap}}`, `{{nik}}`, `{{nomor_surat}}`, dan sejenisnya, serta memvalidasi placeholder yang tidak dikenal.
- **FR-25: Alokasi Nomor Surat:** Mengalokasikan nomor `{seq:03d}/DKP/{bulan_romawi}/{tahun}` secara atomik dan unik per layanan per tahun, dengan opsi override manual beralasan.
- **FR-26: Generate PDF Surat:** Menghasilkan PDF A4 dengan kop surat, judul, nomor, isi, dan blok tanda tangan sesuai tata letak arsip desa.
- **FR-27: QR Code Verifikasi:** Menempelkan QR Code pada area tanda tangan yang mengarah ke URL verifikasi bertoken acak.
- **FR-28: Hash & Arsip Dokumen:** Menyimpan hash SHA-256 setiap dokumen dan mengarsipkan PDF beserta metadatanya.
- **FR-29: Watermark Draft:** Menandai dokumen yang belum disetujui pejabat dengan watermark "DRAFT — BELUM SAH".
- **FR-30: Tanda Tangan Pejabat:** Menempelkan scan tanda tangan pejabat aktif sesuai jenis jabatan dan masa berlaku.
- **FR-31: Halaman Verifikasi Publik:** Menyediakan halaman publik tanpa login yang menampilkan status keabsahan, jenis, nomor, tanggal, nama ter-mask, dan hash dokumen.
- **FR-32: API Verifikasi Instansi:** Menyediakan endpoint JSON untuk verifikasi oleh sistem instansi lain dengan rate limit.
- **FR-33: Log Pemindaian QR:** Mencatat setiap pemindaian (waktu, IP ter-hash, user agent) untuk keperluan audit.

### Panel Admin

- **FR-34: Autentikasi Admin & RBAC:** Menyediakan login email + password dengan hashing Argon2id, sesi aman, dan kontrol akses berbasis peran.
- **FR-35: Dashboard Operasional:** Menampilkan ringkasan pengajuan hari ini, antrean verifikasi, dokumen terbit, penolakan, dan akurasi model aktif.
- **FR-36: Manajemen Pengajuan:** Menyediakan daftar dan detail pengajuan dengan filter status, layanan, tanggal, dan dusun, serta pencarian nomor tiket atau NIK.
- **FR-37: Koreksi Data & Audit Perubahan:** Memungkinkan operator mengoreksi data pemohon sebelum terbit, dengan pencatatan siapa mengubah apa dan kapan.
- **FR-38: Persetujuan & Penerbitan:** Memungkinkan Sekdes/Kepala Desa menyetujui pengajuan, yang memicu alokasi nomor, generate PDF, penempelan QR, dan pengiriman ke warga.
- **FR-39: Penolakan dengan Alasan:** Memungkinkan penolakan pengajuan disertai alasan wajib yang diteruskan ke warga.
- **FR-40: Manajemen Template Surat:** Menyediakan editor template dengan pratinjau PDF sebelum diaktifkan, serta riwayat versi.
- **FR-41: Manajemen Pejabat & TTD:** Mengelola data pejabat (nama, jabatan, NIP, scan TTD, masa berlaku) dengan aturan satu pejabat aktif per jabatan.
- **FR-42: Manajemen Nomor Surat:** Menampilkan counter per layanan per tahun, dengan fitur reset dan override manual yang tercatat.
- **FR-43: Manajemen Katalog & Field Layanan:** Menyediakan CRUD layanan beserta skema field-nya, termasuk pengaturan urutan dan status aktif.
- **FR-44: Manajemen Basis Pengetahuan:** Menyediakan CRUD FAQ dan materi jawaban yang dipakai chatbot.
- **FR-45: Manajemen Dataset & Pelabelan:** Menyediakan antrean pertanyaan gagal, pelabelan intent, dan impor dataset dari berkas CSV.
- **FR-46: Pelatihan & Evaluasi Model:** Menjalankan pelatihan model, menampilkan akurasi/macro F1/confusion matrix, dan mengaktifkan versi model tertentu.
- **FR-47: Audit Log:** Mencatat seluruh aksi admin dan perubahan status pengajuan dalam log yang tidak dapat diubah.
- **FR-48: Manajemen Pengguna Admin:** Menyediakan CRUD akun admin beserta perannya, dengan proteksi agar tidak menghapus akun terakhir.
- **FR-49: Pengaturan Sistem:** Mengelola jam layanan, kontak, teks eskalasi, ambang keyakinan, dan parameter operasional lain.
- **FR-50: Laporan & Ekspor:** Menyediakan rekap bulanan per layanan dan status, dapat diekspor ke CSV.

## Non-Functional Requirements

| Category | Requirement | Metric / Target |
|:---|:---|:---|
| **Performance** | Respons chat cepat | - Respons chatbot p95 ≤ 2 detik - Generate PDF p95 ≤ 5 detik - Halaman verifikasi ≤ 1 detik |
| **Performance** | Throughput memadai | - 50 pengguna concurrent - 1.000 pesan/hari tanpa antrean > 1 menit |
| **Reliability** | Ketersediaan layanan | - Uptime ≥ 99% per bulan - RTO ≤ 4 jam - RPO ≤ 24 jam |
| **Security** | Integritas sistem | - HTTPS wajib - Password Argon2id - Proteksi OWASP Top 10 (XSS, CSRF, SQLi) - Rate limit login dan endpoint chat - Audit log immutable |
| **Privacy** | Perlindungan data warga | - Consent sebelum pengajuan - NIK di-mask di semua tampilan publik - Enkripsi at-rest pada tingkat volume/disk dan backup - Retensi sesuai kebijakan desa |
| **Usability** | Mudah dipakai warga dan operator | - Alur pengajuan selesai ≤ 3 menit - Task completion ≥ 80% tanpa bantuan - WCAG 2.1 AA pada portal verifikasi dan panel admin - Target sentuh ≥ 44 px |
| **Compatibility** | Dukungan perangkat | - WhatsApp Android 8+ / iOS 14+ - Chrome, Edge, Firefox, Safari dua versi terakhir - Layout responsif 360 px–1440 px |
| **Maintainability** | Mudah dirawat satu developer | - Test coverage backend ≥ 70% - Lint `ruff` tanpa error - Dokumentasi API OpenAPI 3.1 - Satu perintah untuk deploy |
| **Observability** | Mudah didiagnosis | - Log terstruktur JSON - Error tracking terpusat - Health check endpoint - Uptime monitor eksternal |
| **Localization** | Sesuai konteks lokal | - Bahasa Indonesia - Format tanggal `dd MMMM yyyy` - Zona waktu WITA (UTC+8) |

## Technology Stack & Rationale

Stack dipilih dengan tiga batasan nyata: **dikerjakan satu orang**, **harus jalan di VPS murah**, dan **harus bisa dipertanggungjawabkan di sidang**. Karena itu sistem dibuat sebagai **monolit Python** dengan UI server-rendered, tanpa SPA, tanpa Redis, dan tanpa orkestrasi container yang rumit.

| Component | Technology | Rationale (Why) |
|:---|:---|:---|
| Bahasa & Runtime | Python 3.12 | Satu bahasa untuk web, NLP, dan PDF generation; ekosistem NLP paling matang; sesuai instrumen penelitian di Bab III skripsi. |
| Web Framework | FastAPI + Uvicorn | Async cocok untuk webhook chat dan streaming; validasi request bawaan Pydantic; OpenAPI otomatis sehingga dokumentasi API gratis. |
| Template & UI Admin | Jinja2 + HTMX 2 + Alpine.js 3 | Server-rendered: tidak perlu build SPA, tidak ada state ganda, mudah di-debug. HTMX cukup untuk tabel, filter, dan modal tanpa menulis banyak JavaScript. |
| Styling | Tailwind CSS 3 (standalone CLI) | Utility-first, konsisten, dan dapat dikompilasi tanpa Node.js — penting karena VPS hanya menjalankan Python. |
| Database | SQLite (development) → PostgreSQL 16 (production) | SQLite membuat demo dan pengembangan lokal tanpa setup; PostgreSQL menangani penulisan bersamaan saat alokasi nomor surat dan audit log. |
| ORM & Migrasi | SQLAlchemy 2.0 + Alembic | Model eksplisit, migrasi berversi, dan mudah dipindah antar-dialek. |
| NLP | scikit-learn (TF-IDF + LinearSVC terkalibrasi) + Sastrawi + rapidfuzz | Untuk domain tertutup 4–21 layanan, model linear mencapai akurasi tinggi dengan latensi < 50 ms dan RAM < 200 MB — tidak butuh GPU atau IndoBERT. |
| PDF Generation | ReportLab (Platypus) | Kontrol tata letak presisi (kop surat, blok TTD, posisi QR) yang sulit dicapai dengan konversi HTML. |
| QR Code | `qrcode` + Pillow | Ringan, deterministik, dan mudah ditempel ke koordinat PDF. |
| Chat Channels | Telegram Bot API (`python-telegram-bot`) + Fonnte (WhatsApp gateway) + web widget | Telegram gratis dan instan untuk demo; Fonnte menghindari proses verifikasi Meta yang panjang; web widget menjadi fallback tanpa biaya. |
| Scheduler & Background Job | APScheduler in-process + FastAPI BackgroundTasks | Volume desa kecil; Redis + Celery akan menambah dua komponen operasional tanpa manfaat nyata. |
| Autentikasi Admin | Session cookie bertanda tangan (`itsdangerous`) + Argon2 (`argon2-cffi`) | Lebih sederhana dan lebih aman untuk server-rendered dibanding JWT; tidak ada token yang bocor lewat localStorage. |
| Storage Berkas | Filesystem lokal + Nginx/Caddy `X-Accel` | PDF dan scan TTD berukuran kecil; object storage menambah biaya dan kompleksitas. Backup offsite memakai `restic`. |
| Reverse Proxy & SSL | Caddy 2 | Sertifikat HTTPS otomatis dengan konfigurasi tiga baris; menghilangkan langkah Certbot manual. |
| Deployment | Docker Compose (app + postgres + caddy) di satu VPS | Reproducible dan mudah di-rollback; tetap satu mesin sehingga biaya dan beban operasional minimal. |
| CI/CD | GitHub Actions | Lint, test, dan build image otomatis; deploy via SSH hanya saat tag rilis. |
| Testing | pytest + httpx AsyncClient | Uji unit pipeline NLP, validasi, numbering, dan uji integrasi alur chat → PDF → verifikasi. |
| Monitoring | Uptime Kuma + loguru (JSON) + Sentry free tier | Deteksi gangguan dan error tanpa biaya lisensi. |

**Yang sengaja tidak dipakai dan alasannya:**

| Ditolak | Alasan |
|:---|:---|
| React/Next.js SPA | Menambah build tooling dan duplikasi validasi; panel admin hanya dipakai 2–3 orang. |
| Redis + Celery | Tidak ada kebutuhan antrean berat; scheduler in-process cukup untuk < 1.000 pesan/hari. |
| IndoBERT / TensorFlow | Butuh ≥ 8 GB RAM dan waktu latih lama; akurasi tambahan tidak sebanding dengan risiko operasional pada VPS 2 GB. |
| WhatsApp Cloud API resmi | Memerlukan verifikasi bisnis Meta dan nomor khusus; tidak realistis untuk tahap skripsi. |
| AWS S3 | Biaya dan konfigurasi IAM berlebihan untuk < 10 GB berkas. |
| Kubernetes | Tidak ada masalah skalabilitas yang perlu diselesaikan pada skala satu desa. |

## Success Metrics & KPIs

| Metric | KPI | Target |
|:---|:---|:---|
| Kualitas NLP | Akurasi intent pada test set | ≥ 85% |
| Kualitas NLP | Macro F1-score | ≥ 0,80 |
| Kualitas NLP | Recall kelas `FALLBACK` | ≥ 0,75 (mencegah jawaban salah percaya diri) |
| Kecepatan | Latensi klasifikasi | ≤ 50 ms per pesan |
| Kecepatan | Waktu generate PDF + QR | ≤ 5 detik p95 |
| Efisiensi operasional | Pertanyaan rutin ditangani chatbot | ≥ 50% dari total percakapan |
| Efisiensi operasional | Waktu proses pengajuan (submit → terbit) | ≤ 1 hari kerja |
| Adopsi | Pengajuan mandiri via chatbot | ≥ 30 pengajuan/bulan pada 3 bulan pertama |
| Kepuasan | Skor SUS | ≥ 70 (acceptable) |
| Kepuasan | Rata-rata rating kepuasan | ≥ 4,0 dari 5 |
| Keandalan | Keberhasilan scan QR | ≥ 98% pada 5 perangkat uji |
| Keamanan | Insiden kebocoran data pribadi | 0 |

## Risk Analysis & Mitigation

| Risk | Impact | Probability | Mitigation Strategy |
|:---|:---|:---|:---|
| **Dataset terlalu kecil sehingga akurasi < 85%** | High | Medium | Kumpulkan minimal 500 ujaran berlabel; augmentasi parafrase; aktif learning dari antrean pertanyaan gagal; sediakan mode klarifikasi agar kesalahan tidak langsung menjadi jawaban salah. |
| **Variasi dialek dan typo sulit dikenali** | Medium | High | Kamus normalisasi lokal (minimal 50 istilah); TF-IDF char n-gram; evaluasi terpisah untuk kelompok "santai/dialek". |
| **WhatsApp gateway memblokir nomor** | High | Low | Arsitektur adapter kanal; Telegram dan web widget tetap berfungsi; dokumentasikan prosedur ganti penyedia. |
| **Penyalahgunaan scan tanda tangan Kepala Desa** | High | Low | Akses hanya untuk Kepala Desa dan Admin Teknis; audit log setiap perubahan; QR verifikasi; kebijakan tertulis; watermark pada dokumen draft. |
| **Listrik atau internet kantor desa terputus** | Medium | Medium | UPS; mode intranet untuk admin; antrean pesan pada gateway; monitoring uptime. |
| **Nomor surat duplikat saat dua operator menerbitkan bersamaan** | High | Low | Transaksi database + `UNIQUE (service_id, tahun, seq)`; alokasi memakai `SELECT ... FOR UPDATE`. |
| **Template surat tidak sesuai ketentuan desa** | High | Medium | Validasi Sekdes sebelum aktivasi; versioning template; pratinjau PDF wajib. |
| **Data pribadi bocor melalui log** | High | Low | Log hanya menyimpan ID, bukan NIK/nama; masking pada seluruh tampilan publik; enkripsi volume disk dan backup terenkripsi. |
| **Ketergantungan pada satu pengelola** | Medium | High | Dokumentasi runbook; pelatihan dua operator; backup otomatis; kredensial disimpan di pengelola kata sandi desa. |
| **Beban akademik melebihi waktu pengembangan** | Medium | Medium | MVP dibatasi 4 surat; fitur fase 2 dipisahkan tegas; roadmap memakai potongan vertikal yang bisa didemokan. |

## Constraints & Assumptions

**Constraints:**

- Sistem dibangun dan dioperasikan **mandiri**, tanpa API LLM pihak ketiga.
- MVP hanya mencakup **empat jenis surat**: Domisili, SKTM, Usaha, dan Pengantar.
- Dokumen yang diterbitkan adalah **dokumen resmi desa**, sehingga format, nomor, dan penandatangan harus mengikuti arsip `Format surat/` dan disetujui Sekdes.
- Tanda tangan elektronik tersertifikasi (BSrE) **tidak** termasuk MVP; MVP memakai scan tanda tangan + QR verifikasi.
- Aplikasi harus dapat berjalan pada **satu VPS 2 vCPU / 2 GB RAM**.
- Antarmuka berbahasa Indonesia; tidak ada dukungan multi-bahasa pada MVP.
- Tidak ada aplikasi mobile native; akses warga melalui kanal chat dan web.

**Assumptions:**

- Desa memiliki koneksi internet yang stabil minimal 8 jam/hari dan satu komputer untuk operator.
- Nomor WhatsApp desa tersedia dan dapat dihubungkan ke gateway pihak ketiga.
- Data monografi desa (jumlah penduduk/KK) tersedia untuk perhitungan sampel Slovin.
- Kepala Desa menyetujui penggunaan scan tanda tangan digital untuk dokumen yang dihasilkan sistem.
- Minimal 600 ujaran berlabel dapat dikumpulkan dari wawancara, arsip pertanyaan, dan simulasi.
- Dua operator desa dapat dilatih dalam satu sesi 2 jam.

## Out of Scope

Rilis pertama SILADESA **tidak** mencakup:

- Integrasi langsung ke SIAK/Dukcapil atau verifikasi NIK real-time.
- Penerbitan dokumen yang menurut regulasi wajib ditandatangani pejabat di luar desa (mis. sertifikat tanah BPN).
- Tanda tangan elektronik tersertifikasi BSrE.
- 13 jenis surat di luar empat layanan MVP (direncanakan pada fase 2).
- Pembayaran online, pengaduan hukum, dan layanan di luar administrasi desa.
- Aplikasi mobile native.
- Multi-tenant (satu instalasi untuk satu desa).
- Multi-bahasa dan dukungan difabel berat (hanya kepatuhan WCAG dasar).
- Dasbor analitik lanjutan dan integrasi Business Intelligence.
- Kiosk fisik dan perangkat pemindai KTP.
