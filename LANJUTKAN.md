# LANJUTKAN — Sesi SILADESA

> Cara pakai: buka sesi BARU (`/new`) di folder ini, paste seluruh isi file ini
> sebagai pesan pertama + kalimat "Lanjutkan dari Next Move".

## Objective
- Build the real SILADESA application from the PRD, working end-to-end, in `siladesa-app/`, then rewrite Bab III of the skripsi (`Skripsi ikram-2_safe.docx`) so it matches the delivered implementation. User's instruction: "buatkan aplikasinya sampai selesai, kerjakan apa yang bisa kamu kerja, buat di folder baru ya", then "lanjut" — continue autonomously.
- **Prioritas terakhir user: "fokus dlu di aplikasi, jangan bab 4-5"** — tutup dulu seluruh gap antara PRD dan implementasi aplikasi; Bab IV–V dan penulisan skripsi ditunda.
- Empat gap yang dipilih user untuk ditutup: (1) unggah TTD pejabat + tempel di PDF (FR-30/41), (2) rate limit 60 req/menit (FR-32), (3) masa berlaku pejabat (FR-41), (4) kirim PDF ke percakapan setelah TERBIT (FR-20). **Keempatnya sudah selesai dan terverifikasi.**

## Requirements
- Respond in Indonesian (mixed ID/EN acceptable).
- PRD split into 9 separate files per the `generate-prd` skill, not one consolidated file.
- Tech stack realistic for a solo undergraduate thesis project; assistant has discretion to choose it.
- Stack may diverge from Bab III of the skripsi — skripsi will be edited afterwards to match.
- Content must stay derived from the skripsi and the `Format surat/` archive.
- Build the app in a **new folder** (not inside `prd-siladesa/`).
- Work autonomously: do as much as possible without asking for confirmation.

## Decisions
- PRD output lives in `prd-siladesa/` — 9 skill docs + `README.md` index; old single-file PRD archived to `prd-siladesa/_archive/PRD_CHATBOT_DESA_KAMPALA_v1.md` (moved, not deleted).
- Product name **SILADESA** (Sistem Layanan Administrasi Desa) is a working title; easily renamed. Used in Bab III text as the system name (still unconfirmed by user).
- Stack: Python 3.12 + FastAPI + Uvicorn; Jinja2 + HTMX 2 + Alpine.js 3 + hand-written CSS (no Node); SQLite (dev) → PostgreSQL 16 (prod) + SQLAlchemy 2.0 + Alembic; scikit-learn TF-IDF + calibrated LinearSVC + Sastrawi + rapidfuzz; ReportLab + `qrcode` + Pillow; Telegram Bot API + **Fonnte** + web widget; BackgroundTasks (no Redis/Celery); signed cookie session via `itsdangerous` + Argon2id; Docker Compose (app + postgres + caddy) on one VPS 2 vCPU/2 GB; Caddy 2; GitHub Actions; pytest + httpx; loguru + Sentry free tier; `restic`/`rclone` backups.
- Explicitly rejected (rationale tables in README + ADRs): React/Next.js SPA, Redis+Celery, IndoBERT/TensorFlow, WhatsApp Cloud API, AWS S3, Kubernetes.
- Kept hard constraints from skripsi: 85% intent accuracy, macro F1 ≥ 0.80, Slovin e=10%, 4 MVP letters (Domisili, SKTM, Usaha, Pengantar), self-hosted without commercial LLM APIs.
- Roles: `operator`, `sekdes`, `kepala_desa`, `admin_teknis` (+ anonymous `warga` and `verifikator`).
- Statuses: `DRAFT`, `MENUNGGU_VERIFIKASI`, `DIPROSES`, `TERBIT`, `DITOLAK`, `DIBATALKAN`.
- Ticket format `APP-{YYYY}-{seq:6d}`; letter number `{seq:03d}/DKP/{bulan_romawi}/{tahun}`.
- FR set renumbered cleanly to **FR-01…FR-50**; 18 intents; MVP service codes `DOM`, `SKTM`, `USH`, `PGG`.
- Confidence thresholds: answer ≥0.65, clarify 0.40–0.65, fallback/escalate <0.40.
- Roadmap uses relative weeks (W1–W14), no absolute dates.
- Reconciliation fixes applied: (1) added `FAQ` table + admin CRUD endpoints (FR-11/FR-44) — table count 21 → **22**; (2) "antrean pertanyaan gagal" derived from `chat_message` query (no separate table); (3) encryption claims aligned to volume/disk + backup level (`pgcrypto` deferred to phase 2).
- App implementation choices: hand-authored `app.css` implementing DESIGN_SYSTEM tokens (no Tailwind CLI / network dependency); server-rendered forms + vanilla JS; model auto-trains from seed dataset on startup if no artifact exists; ReportLab built-in Times-Roman fonts; stateless signed session cookie; dataset authored as Python dict (`intent -> [utterances]`).
- Ticket numbers derived from `Application.id` (`APP-{year}-{id:06d}`) with high-entropy `TMP{hex}` placeholder before flush.
- Download links use signed `itsdangerous` token (`sign_download(document_id)`); QR token is *not* a download capability.
- Letter PDF template convention: plain lines = paragraphs, `| Label | Value` = identity table row, `#JUDUL#` = centered underlined title. Signer resolved from `SETTING` keys `penandatangan_{KODE}` / `saksi_{KODE}` matched against `Official.jabatan`.
- Admin POST handlers are `async def`, use `await request.form()` + `assert_csrf(request, form.get("csrf"))`, enabling dynamic field keys (e.g. `label_{id}`).
- Login page issues its own CSRF cookie on GET since no session exists yet.
- Template versioning: saving with `mode=baru` deactivates all templates for the service and inserts `versi+1` as active; otherwise in-place update.
- Document revocation revokes the `Document` (not the application status); verify page then shows **`DIBATALKAN`** wording.
- Flash messages via redirect query params `?pesan=...&jenis=ok|err` (helper `_kembali`).
- Frontend: no external font/CDN; system font stack; inline SVG icon macro; `--color-primary` = `green-600` (#15803D) for 4.5:1 contrast.
- Display timezone is **WITA** (`ZoneInfo("Asia/Makassar")`, fallback `timezone(+8)`); DB stores UTC. `filter_waktu` returns only `HH:MM`.
- Pagination via `url_dengan(request, page=n)` Jinja global + `partials/paginasi.html` macro `paginasi(info)`; macro **requires `with context`**.
- NIK masked in list/verify views via `mask_nik` filter; `romawi` filter in `app/templating.py`.
- Error pages (`errors/*.html`) are standalone HTML documents (no `extends base.html`).
- Public `/v/{token}` returns **HTTP 200** with a "not found" state; revoked documents also render 200 with "DIBATALKAN".
- Chat API: `POST /api/v1/chat/sessions` returns **201**; `balasan` is a **list of plain strings**.
- Demo role accounts only seeded when `settings.is_production` is false, using `bootstrap_demo_password` (`Demo#2026`).
- Revocation (`application.revoke`) is **kepala_desa only**; sekdes gets 403 by design.
- Admin logout is **POST-only** and requires `Depends(require_login)` so `request.state.csrf` is populated.
- NLP evaluation uses **stratified k-fold cross-validation** (`min(5, min class count)` folds, `random_state=42`, `cross_val_predict`), then final pipeline refit on all samples; method string stored in `HasilLatih.metode` and appended to `NlpModel.catatan` (no new DB column).
- Dataset expanded to **551** utterances (18 intents, min 27, max 36) via a `_TAMBAHAN` dict merged into `DATASET` at module end of `app/seed_data/dataset.py`.
- `Base.metadata.create_all` now runs **only when `not settings.is_production`**; production relies on `alembic upgrade head` executed by the Docker entrypoint.
- Docker entrypoint order: `alembic upgrade head` → `python -m app.seed` (idempotent) → `exec uvicorn ... --proxy-headers --forwarded-allow-ips '*'`.
- Bab III figure numbering: **3.1** flowchart manual (existing image), **3.2** Sistem Pelayanan Otomatis Diusulkan – Chatbot NLP (existing image), **3.3** Arsitektur SILADESA (new), **3.4** Diagram Status Pengajuan Surat (new).
- Bab III table numbering: **3.1** Jadwal Penelitian (author's table, filled with `√`), **3.2** Aktor & Hak Akses, **3.3** Status Pengajuan & Transisi, **3.4** Kelompok Tabel Basis Data, **3.5** Daftar Intent + Contoh Ujaran, **3.6** Ambang Keyakinan, **3.7** Perbandingan Sistem Manual vs Diusulkan (rebuilt fresh, 10 rows), **3.8** Rencana Pengujian.
- Bab III structure finalized: A. Jenis Penelitian (3 numbered eval sub-sections incl. equations), B. Tempat & Waktu (Tabel 3.1), C. Instrumen (hardware/software lists), D. Tahapan Penelitian (6 Waterfall stages with a./b. sub-items), E. Sumber Data, F. Analisis Perancangan Sistem (1 Analisis Sistem Berjalan → Gambar 3.1; 2 Perancangan Sistem Diusulkan → Gambar 3.2 + a. Arsitektur (Gambar 3.3) b. Aktor (Tabel 3.2) c. Alur Status (Gambar 3.4, Tabel 3.3) d. Basis Data (Tabel 3.4) e. Model NLP (Tabel 3.5, 3.6) f. Antarmuka g. Keamanan; 3 Perbandingan (Tabel 3.7); 4 Rencana Pengujian (Tabel 3.8)).
- Bab III uses **manual numbering** (explicit "1.", "a)", "•" prefixes + hanging indents), not Word auto-numbering.
- DAFTAR ISI keeps only Heading 2 entries (A–F) — no new Heading 3 entries.
- New Bab III body style: `List Paragraph`, `ind left=990 firstLine=810`, justified; h2 `Heading 2` left=1080; h3 `Heading 3` left=1530 hanging=450 + bold black Times; a./b. sub-heads bold `List Paragraph` left=1440; list levels 1440/2160/2880 with hanging 360.
- Tables built at total width **7938 twips** (14 cm usable), `Table Grid`, Times New Roman 9 pt, header row bold+centered+`tblHeader`; captions above, bold centered, `keep_with_next`.
- `pytest_cov` is not installed → `requirements-dev.txt` intentionally contains only `-r requirements.txt` + `pytest`.
- **FR-41 masa berlaku**: kolom `Official.berlaku_sampai` (DATE, nullable = tanpa batas). `cari_pejabat()` hanya mengembalikan pejabat `aktif` **dan** belum kedaluwarsa. Saat mendaftarkan pejabat baru, pejabat lama yang sudah lewat masa berlaku dinonaktifkan otomatis agar unique parsial `uq_official_aktif` tidak bentrok. Tidak ada `berlaku_mulai` (tidak diminta FR-41; DATABASE.md sudah disesuaikan).
- **FR-30/41 TTD**: unggah via `POST /admin/pejabat/{id}/ttd` — maks 2 MB, PNG/JPEG (diverifikasi Pillow), dinormalisasi ke RGBA dan disimpan sebagai `storage/officials/ttd-{id}.png`; hapus via `POST /admin/pejabat/{id}/ttd/hapus`. Hanya `kepala_desa` / `admin_teknis`. Gambar ditempel proporsional 3,4 cm di tengah ruang tanda tangan (`_ruang_ttd`), bukan skala paksa.
- **Guard penerbitan**: `terbitkan` menolak dengan pesan "Tidak ada pejabat penanda tangan yang aktif dan masih berlaku…" bila pejabat jabatan terkait tidak tersedia.
- **FR-32 rate limit**: `app/services/ratelimit.py`, in-memory (tanpa dependensi baru), sliding window 60 detik, kunci `request.client.host` (bukan `X-Forwarded-For` mentah, agar tidak bisa diakali), 60 req/menit pada `GET /api/v1/verify/{token}`, balasan 429 + `Retry-After`. Exception handler `main.py` meneruskan `exc.headers`.
- **FR-20 pengiriman**: PDF asli dikirim ke kanal asal (`sendDocument` Telegram, parameter `url` Fonnte), **dan** tautan bertoken selalu disimpan sebagai pesan `out` di percakapan lewat `kirim_pesan_keluar()` yang menelusuri `Application.session_id` (sesi chat sudah di-reset setelah submit). Waktu kirim dicatat di `Document.sent_at`. Kegagalan kanal tidak menggagalkan penerbitan.
- **Widget chat** menyinkronkan riwayat server (`GET /api/v1/chat/sessions/{id}/messages`) saat panel dibuka + polling 15 detik, dengan dedupe berbasis jumlah kemunculan teks — supaya pesan "surat terbit" terlihat tanpa reload. Tanpa ini pesan FR-20 tidak pernah tampil karena widget dulu hanya memakai `sessionStorage`.
- **Format surat mengikuti arsip `Format surat/`**: surat resmi memakai Folio (8,5×14 in) + Bookman Old Style, tetapi aplikasi tetap A4 + Times-Roman (Bookman berlisensi & tidak terpasang; A4 lebih aman dicetak). Yang disamakan adalah tata letaknya, bukan kertas/font.
- **Logo kop**: logo Kabupaten Jeneponto diekstrak dari `word/media/image1.png` di `Ket Domisili.docx`, diratakan ke latar putih, diperbesar 3× (534×495) → `app/static/img/logo-jeneponto.png`. Dirender 2,1 cm dalam tabel kop 3 kolom (kiri logo, tengah teks, kanan spacer kosong) supaya teks kop tetap terpusat pada halaman. Pengaturan `logo_kop` bisa menunjuk berkas lain (kosong = logo bawaan).
- **Margin A4** dinaikkan agar patuh FR-26 (2,5–3 cm): kiri 2,75 cm (arsip desa), kanan 2,5 cm, atas-bawah 2,54 cm. Sebelumnya 2,2/2,2/1,6/2,0 cm — melanggar FR-26. `CONTENT_W` dihitung dari `MARGIN_KIRI + MARGIN_KANAN`.
- **QR verifikasi** 2,5 cm (FR-27 mewajibkan ≥ 2,5 × 2,5 cm; sebelumnya 2,4 cm) dan berdiri sebagai **kolom ketiga** di kanan blok tanda tangan. Sebelumnya QR ditumpuk di bawah nama penanda tangan: pada SKTM (paling banyak baris) blok TTD jadi terlalu tinggi sehingga surat pecah ke halaman 2. Kolom TTD menyempit ke 6,3 cm + 6,3 cm + 2,6 cm.
- **Ukuran kop** 14/14/18 pt bold (kabupaten/kecamatan/desa) + alamat 10 pt, mengikuti ukuran resmi.
- **Urutan judul → nomor**: `#JUDUL#` dipisah dari badan surat oleh `_pisah_judul()` lalu dicetak tebal bergaris bawah **sebelum** `NO : {nomor}` (dulu nomor dulu).
- **Baris identitas** diberi kolom kosong 0,8 cm di depan (meniru indentasi surat resmi), label 4,2 cm, titik dua 0,35 cm.
- **Penanda tangan**: hanya **Kepala Desa** atau **Sekretaris Desa** (`docsvc.JABATAN_PENANDATANGAN`). Sekdes → `Mengetahui :` / `a/n Kepala Desa <desa>` / `(Sekretaris Desa)`; Kepala Desa → `Mengetahui :` / `Kepala Desa <desa>` tanpa `a/n` & tanpa tanda kurung (sesuai sampel resmi Domisili halaman 3). Nama penanda tangan & saksi dicetak **tebal + garis bawah**. Divalidasi di `simpan_pengaturan`, di `terbitkan`, dan dropdown pengaturan hanya menampilkan dua jabatan itu.
- **`#PEMEGANG#`**: penanda template baru; bila ada, kolom kiri blok tanda tangan berisi `Pemegang Surat` + nama pemohon (format Surat Keterangan Usaha). DOM, SKTM, dan PGG memakai blok `Menyaksikan :` (Kapolsek) — `SAKSI` sekarang memuat `DOM`, `SKTM`, dan `PGG`.
- **Pemetaan penanda tangan**: `DOM`/`USH`/`PGG` = Sekretaris Desa (`a/n Kepala Desa`), `SKTM` = Kepala Desa. Ini mengikuti arsip: hampir semua surat ditandatangani `a/n Kepala Desa Kampala (Sekdes)`, hanya Ket Tidak Mampu yang ditandatangani Kepala Desa langsung.
- **Ruang TTD** dihitung dari rasio gambar asli (`ImageReader.getSize()`), diskalakan maks 3,4 cm × 44 pt, lalu diberi spacer agar nama tidak bergeser dan gambar tidak menimpa baris di atasnya. Kolom kiri/kanan disejajarkan dengan menghitung jumlah baris.
- **Template DOM/SKTM/USH/PGG** ditulis ulang mengikuti naskah resmi: label `Tempat / Tgl Lahir`, `Nik`, baris `Keterangan` + `Keperluan` pada SKTM, blok identitas usaha pada USH, dan kalimat penutup "…untuk dipergunakan sebagaimana mestinya".

## Work State
### Completed
- **Data warga (master) + validasi NIK di chat selesai**: `Citizen.aktif` + migrasi `a7f3c9d1e2b4` (terpasang, `alembic current` = head); panel **Data warga** (`/admin/warga`) dengan cari/filter status, tambah, detail + riwayat pengajuan, edit, nonaktifkan, hapus (diblokir bila ada riwayat); izin baru `citizen.read` (4 peran) dan `citizen.manage` (operator/sekdes/admin_teknis). Chat: NIK dikenali → kartu konfirmasi → hanya field khusus layanan yang ditanya (Domisili 14 → **1** pertanyaan; SKTM 16 → 3; Usaha 19 → 6; Pengantar 14 → 1). NIK nonaktif ditolak dengan pesan ke kantor desa. `tests/test_warga.py` (9 tes) menguji CRUD, hak akses, dan alur NIK dikenal/nonaktif/belum terdaftar.
- **Aplikasi: seluruh gap PRD vs implementasi sudah ditutup** (lihat Decisions FR-20/30/32/41). `pytest` **84 passed**. Migrasi terpasang di DB dev: `8b1c4d2e7f90` (berlaku_sampai) → `c4d7a1f93b28` (document.sent_at) → `a7f3c9d1e2b4` (citizen.aktif), `alembic current` = `a7f3c9d1e2b4 (head)`.
- **Format surat resmi selesai** (`app/services/documents.py`, `app/seed_data/katalog.py`, `app/static/img/logo-jeneponto.png`): kop berlogo + ukuran 14/14/18, judul di atas nomor, margin A4 2,75/2,5/2,54 cm, indentasi identitas 0,8 cm, nama tebal+garis bawah, blok tanda tangan `a/n` hanya untuk Sekdes, `Pemegang Surat` untuk USH, QR 2,6 cm, dan pembatasan penanda tangan ke Kepala Desa/Sekretaris Desa (pengaturan + penerbitan). Template + setting DB sudah di-seed ulang. Keempat pratinjau diperiksa lewat `pdftoppm`, dan PDF nyata hasil E2E (`012/DKP/X/2026`) tampil sesuai format.
- Tes baru `tests/test_format_surat.py` (9 tes): urutan judul–nomor, objek gambar kop, `Pemegang Surat` hanya di USH, `a/n` hanya untuk Sekdes, Kepala Desa tanpa `a/n`, Pengantar ditandatangani Sekdes + saksi Kapolsek, penolakan penanda tangan non-Kepala Desa/Sekdes di pengaturan dan saat terbitkan, serta surat ber-QR tetap satu halaman.
- E2E HTTP **32/32 cek lulus** (`/tmp/e2e_cek.py`): sesi chat → intent → AJUKAN → consent → 14 field → tiket → login admin → DIPROSES → TERBIT → unduh PDF → `/v/<token>` (NIK tersamar) → token palsu → `/api/v1/track/<nomor>`.
- Smoke ~37 halaman: tidak ada 500, tidak ada tautan rusak. 403 pada `/admin/model|dataset|pengguna|pengaturan` untuk sekdes memang by design; `/admin/login` → 303 saat sudah login.
- TTD terverifikasi visual: PDF surat `004/DKP/X/2026` naik dari 11.122 → 19.854 byte; render `pdftoppm` menunjukkan tanda tangan tepat di antara "(Sekretaris Desa)" dan "BAHTIAR.B".
- Rate limit terverifikasi lewat HTTP nyata: tepat 60×200 lalu 429 dengan `retry-after: 59`.
- FR-20 terverifikasi lewat HTTP nyata: pesan `out` berisi nomor surat + tautan `/d/`, `document.sent_at` terisi. Widget dibuktikan via Playwright: panel menampilkan pesan "surat sudah terbit" + tautan tanpa reload, tanpa duplikasi (26 pesan, 26 unik).
- Badge `Kedaluwarsa` + tanggal tampil di `/admin/pejabat` saat `berlaku_sampai` di masa lalu (diuji dengan ubah DB sementara lalu dipulihkan). Form tambah punya `berlaku_sampai`; kartu pejabat punya form unggah TTD dan tombol "Hapus tanda tangan" hanya bila berkas ada.
- Tes baru: `tests/test_pejabat_ttd.py`, `tests/test_ratelimit.py`, `tests/test_notifikasi.py`, `test_terbit_tidak_bisa_lewat_form_status`, `test_lacak_terbit_menampilkan_tombol_unduh`, `test_lacak_terbit_tanpa_berkas_memberi_peringatan`, plus `test_tautan_unduh_masuk_ke_chat_setelah_terbit` (meng-assert `Document.sent_at` dan `catatan_operator` tidak tertimpa).
- **Data warga + NIK-first (sesi ini)**: tabel `citizen` dijadikan data induk yang bisa dikelola petugas; chat memvalidasi **NIK saja** lalu menampilkan kartu konfirmasi sebelum memakai datanya. Keputusan yang diambil user: (a) NIK belum terdaftar → lanjut isi data seperti biasa lalu otomatis tersimpan sebagai warga baru; (b) `citizen.manage` untuk operator/sekdes/admin_teknis, kepala_desa hanya `citizen.read`; (c) hapus permanen hanya bila warga belum punya riwayat pengajuan, selain itu nonaktifkan (kolom `citizen.aktif`).
- Kartu konfirmasi warga menawarkan **1) pakai data ini, 2) perbaiki data, 3) batal**. Opsi 2 mengosongkan identitas selain NIK sehingga warga ditanya ulang dari Nama Lengkap; data hasil perbaikan memperbarui data induk saat pengajuan dikirim (`upsert_citizen`).
- Prefill hanya memakai nilai warga yang **lolos `validasi_nilai` field layanan**; nilai yang tidak valid (mis. pilihan dusun berubah) dilewati supaya warga ditanya ulang, bukan gagal di ringkasan.
- **Perbaikan bug alur terbit**: dulu form "Ubah status" menawarkan `TERBIT`, sehingga sekdes bisa menandai surat terbit tanpa nomor surat, PDF, maupun tautan unduh (terjadi pada `APP-2026-000012`). Sekarang (a) `TERBIT` tidak lagi muncul di dropdown `tujuan`, (b) `POST /admin/pengajuan/{id}/status` dengan `ke=TERBIT` ditolak dengan pesan yang mengarahkan ke tombol terbitkan, (c) `/lacak` menampilkan nomor surat + tombol **Unduh surat**, dan bila data lama terbit tanpa berkas muncul peringatan "Berkas surat belum tersedia", (d) catatan verifikasi operator tidak lagi tertimpa catatan penerbitan (`transisi` tidak menulis `catatan_operator` saat `ke == TERBIT`). Data `APP-2026-000012` dikoreksi dan diterbitkan ulang menjadi `008/DKP/X/2026`.
- Dokumentasi as-built disinkronkan: `siladesa-app/README.md` (tautan di chat, rate limit, masa berlaku + TTD, batasan rate limiter in-memory) dan `prd-siladesa/DATABASE.md` (tabel `OFFICIAL` sesuai kolom nyata + catatan unique parsial).
- All 10 files written in `prd-siladesa/` (`README.md` 113, `PRD.md` 230, `REQUIREMENTS.md` 368, `ARCHITECTURE.md` 520, `DATABASE.md` ~1,058, `API.md` ~1,512, `USER_FLOW.md` 485, `DESIGN_SYSTEM.md` 451, `DEPLOYMENT.md` 617, `ROADMAP.md` 273); old single-file PRD archived.
- PRD consistency verified: FR-01…FR-50 defined/referenced consistently; 22 `CREATE TABLE` statements match 22 ERD entities.
- PRD metric wording synced to cross-validation: `DEPLOYMENT.md:579`, `DATABASE.md:578`, `PRD.md:185` ("minimal 500 ujaran").
- Env: Python 3.14.3 (`/usr/local/bin/python3`), fastapi 0.115.6, SQLAlchemy 2.0.50, pydantic 2.13.4, uvicorn 0.34.0, reportlab 5.0.1, pillow, scikit-learn 1.8.0, pytest 9.0.3, httpx, python-multipart, itsdangerous, argon2-cffi, joblib, qrcode, Sastrawi, rapidfuzz, alembic 1.20.0, psycopg 3.3.4, matplotlib 3.10.9. `uvicorn` is **not** on PATH — use `python3 -m uvicorn`. No `dot` (graphviz), no `cairosvg`. LibreOffice at `/usr/local/bin/soffice`. matplotlib has **Times New Roman**.
- `siladesa-app/` complete: all backend modules, 8 services, seed data, 4 routers, channel base, static assets, all templates.
- `python -m app.seed` works: model `v20261017235741`, **accuracy 0.886, macro F1 0.885**, 551 samples, 18 intents, 4 services; admin `admin@desakampala.id` / `Admin#2026`, demo accounts `operator@` / `sekdes@` / `kepaladesa@desakampala.id` / `Demo#2026`.
- **Full pytest suite green: 66 passed** (`tests/`: conftest, publik, auth, chat, pengajuan, admin, nlp, webhook, pejabat_ttd, ratelimit, notifikasi). `test_nlp` accuracy assertion `>= 0.85`.
- End-to-end flow verified (`/tmp/e2e_cek.py`, 32/32) and page smoke test passes (`/tmp/smoke_cek.py`).
- `siladesa-app/README.md`, `Dockerfile` (2-stage, python:3.12-slim, non-root uid 10001, healthcheck), `docker/entrypoint.sh`, `docker/Caddyfile`, `docker-compose.yml` (app + db postgres:16-alpine + caddy), `.dockerignore`, `requirements-dev.txt` written.
- Alembic initialized: `alembic.ini`, `migrations/env.py`, initial autogenerated revision with **22 `op.create_table`**; `alembic upgrade head` verified on fresh SQLite DB (23 tables incl. `alembic_version`).
- `requirements.txt` updated with `alembic==1.20.0` and `psycopg[binary]==3.3.4`; `.dockerignore` extended with `data/*.db-wal` / `data/*.db-shm`; leftover `_PILIHAN_TAMBAHAN` removed from `app/seed_data/katalog.py`.
- `docker compose config` validates (exit 0) with a temporary `.env`.
- `app/templates/admin/model.html` updated: "Metode evaluasi → 5-fold cross-validation berstrata"; metric caption → "dihitung lewat cross-validation".
- Skripsi inspection done: 279 paragraphs, 3 tables, 6 images. Bab III = paragraphs 143–247. Document geometry: A4, margins L 4.0 / R 3.0 / T 4.0 / B 3.0 cm → **usable text width 13.99 cm**; `Normal` double spacing, Times New Roman.
- New figures generated via `/tmp/skripsi_work/buat_gambar.py` (matplotlib, Times New Roman, dpi 220): `/tmp/skripsi_work/fig/arsitektur.png` and `/tmp/skripsi_work/fig/status.png`, both visually verified.
- **Bab III rebuild script written and run successfully**: `/tmp/skripsi_work/bangun_bab3.py` → output `/Users/rada/Downloads/office-skripsi-ikram/Skripsi ikram-2_bab3.docx` (321 paragraphs, 9 tables). Deleted old body 144–246, kept heading 143 and sectPr paragraph, reused both existing drawings (old paras 224/237) and both OMML equations (old paras 150/154), filled Tabel 3.1 with `√` (8 activities × 10 week columns) and rescaled it from 8575→7938 twips with `tblInd=0`.
- PDF render works: `soffice --headless --convert-to pdf` → `/tmp/skripsi_work/out/Skripsi ikram-2_bab3.pdf`, **54 pages** (baseline was 41), text extracted to `/tmp/skripsi_work/out/bab3.txt`, page PNGs rendered at `/tmp/skripsi_work/out/pg-25.png` … `pg-32.png`.

### Active
- Tidak ada perubahan setengah jadi. Aplikasi dalam keadaan hijau: `pytest` **84 passed**, E2E 32/32, smoke bersih (9 temuan lama yang memang by design). Migrasi DB dev = `a7f3c9d1e2b4 (head)`.

### Blocked
- Docker image build belum terverifikasi: daemon Colima tidak jalan (`failed to connect to the docker API at unix:///Users/rada/.colima/default/docker.sock`). Dockerfile baru divalidasi dengan inspeksi + `docker compose config`.
- `alembic downgrade` untuk `c4d7a1f93b28` gagal di DB dev lama karena kolom sudah di-rename manual `terkirim_at` → `sent_at` (SQLite `ALTER TABLE ... RENAME COLUMN`). DB sekarang konsisten (`current` = head), jadi ini hanya catatan sejarah, bukan masalah aktif.

## Next Move
1. (Opsional, aplikasi) PDF lama (`APP-2026-000011/012/013`) sengaja **tidak** diregenerasi: surat sudah terbit dan `Document.sha256` sudah tercatat. Regenerasi hanya bila user memintanya (perlu update hash + berkas).
2. (Opsional, aplikasi) Pertimbangkan memindahkan rate limiter ke Redis bila nanti dijalankan multi-proses — sekarang in-memory per proses.
3. (Opsional, aplikasi) Rapikan drift dokumentasi yang belum tersentuh: `API.md` masih menggambarkan API admin JSON (`/api/v1/admin/officials`) padahal panel admin berupa form server-rendered; `DATABASE.md` tabel `DOCUMENT` masih memuat `versi/seq/tahun/official_id/file_size` yang tidak ada di model.
4. (Skripsi — ditunda atas instruksi user) Bab IV–V, front matter (halaman judul, lembar pengesahan, abstrak, kata pengantar), konfirmasi `N = 1.245`, konfirmasi/gganti judul kerja "SILADESA".
5. (Skripsi) Bila dilanjutkan: pakai skill `skripsi`; perbarui DAFTAR ISI/GAMBAR/TABEL dari PDF hasil render; simpan sebagai `Skripsi ikram-2_v3.docx`.

## Relevant Files
- `siladesa-app/app/routers/admin.py`: `terbitkan` (guard pejabat, `kirim_dokumen`, `sent_at`), unggah/hapus TTD, `_ke_tanggal`, `TTD_MAKS_BYTE`, `daftar_pejabat`, auto-expire di `tambah_pejabat`.
- `siladesa-app/app/services/documents.py`: `pejabat_untuk`, `cari_pejabat`, `path_ttd`, `logo_kop`, `_kop_flowables` (kop berlogo), `_pisah_judul`, `_baris_tabel` (indentasi), `_ruang_ttd`, `_blok_ttd`, `simpan_dokumen`, `JABATAN_PENANDATANGAN`.
- `siladesa-app/app/static/img/logo-jeneponto.png`: logo Kabupaten Jeneponto untuk kop surat.
- `siladesa-app/tests/test_format_surat.py`: 7 tes format surat (judul/nomor, logo, pemegang, a/n, penolakan penanda tangan).
- `siladesa-app/app/services/notifications.py`: `kirim_dokumen_telegram`, `kirim_dokumen_whatsapp`, `kirim_dokumen`, `TEMPLATE`, `HasilKirim`.
- `siladesa-app/app/services/ratelimit.py`: `cek_batas`, `batasi_verifikasi`, `reset`, `BATAS`.
- `siladesa-app/app/services/chat.py`: `kirim_pesan_keluar` (menelusuri `Application.session_id`), `_catat`, `_prompt_field`.
- `siladesa-app/app/static/js/widget.js`: `sinkron()` + polling 15 detik (FR-20 terlihat di UI).
- `siladesa-app/app/templates/admin/pejabat.html`: kartu pejabat, form TTD, badge kedaluwarsa, form tambah.
- `siladesa-app/app/models.py`: `Citizen.aktif`, `Official.berlaku_sampai`, `Document.sent_at`, `Application.session_id`.
- `siladesa-app/app/services/chat.py`: `_nilai_identitas`, `_kartu_warga`, `_tanya_field_berikut`, `_jawab_konfirmasi_warga`, state `KONFIRMASI_WARGA`.
- `siladesa-app/app/services/applications.py`: `cari_citizen`, `upsert_citizen` (menolak NIK nonaktif).
- `siladesa-app/app/routers/admin.py`: seksi **Data warga** (`_baca_warga`, `_opsi_field`, `daftar_warga`, `detail_warga`, `tambah_warga`, `ubah_warga`, `aktif_warga`, `hapus_warga`).
- `siladesa-app/app/templates/admin/warga.html`, `warga_detail.html`, `partials/form_warga.html`: panel data warga.
- `siladesa-app/tests/test_warga.py`: 9 tes CRUD + alur NIK di chat.
- `siladesa-app/migrations/versions/a7f3c9d1e2b4_citizen_aktif.py`: migrasi terbaru (head).
- `siladesa-app/migrations/versions/8b1c4d2e7f90_pejabat_berlaku_sampai.py`, `siladesa-app/migrations/versions/c4d7a1f93b28_document_sent_at.py`: dua migrasi terbaru (sudah terpasang di DB dev).
- `siladesa-app/tests/`: `test_pejabat_ttd.py`, `test_ratelimit.py`, `test_notifikasi.py`, `test_pengajuan.py`, `conftest.py`.
- `/tmp/e2e_cek.py`, `/tmp/smoke_cek.py`, `/tmp/ttd_cek.py`: skrip verifikasi HTTP (server port 8021).
- `/Users/rada/Downloads/office-skripsi-ikram/Skripsi ikram-2_bab3.docx`: current rebuilt output (Bab III rewritten, 54 pages when rendered).
- `/tmp/skripsi_work/bangun_bab3.py`: the rebuild script (content spec + helpers); edit and re-run to iterate.
- `/tmp/skripsi_work/backup.docx`: pristine original skripsi; source of preserved drawings/equations/sectPr.
- `/tmp/skripsi_work/backup.pdf`, `/tmp/skripsi_work/backup.txt`: 41-page baseline render for page-number comparison.
- `/tmp/skripsi_work/out/bab3.txt`, `/tmp/skripsi_work/out/pg-*.png`: rendered output text + page images for visual QA.
- `/tmp/skripsi_work/fig/arsitektur.png`, `/tmp/skripsi_work/fig/status.png`, `/tmp/skripsi_work/buat_gambar.py`: Gambar 3.3/3.4 assets + generator.
- `/Users/rada/Downloads/office-skripsi-ikram/Skripsi ikram-2_safe.docx`: original target document (279 paragraphs, Bab III = 143–247).
- `/Users/rada/Downloads/office-skripsi-ikram/siladesa-app/README.md`: authoritative stack/feature/metric description used for Bab III text.
- `/Users/rada/Downloads/office-skripsi-ikram/prd-siladesa/README.md`: stack-change table + rejected alternatives for Bab III justification.
- `/Users/rada/Downloads/office-skripsi-ikram/siladesa-app/app/constants.py`: `Role`, `Status`, `TRANSISI`, `PERMISSIONS` — source for Tabel 3.2/3.3.
- `/Users/rada/Downloads/office-skripsi-ikram/siladesa-app/app/seed_data/dataset.py`: 551 utterances / 18 intents — source for Tabel 3.5.
- `/Users/rada/Downloads/office-skripsi-ikram/siladesa-app/app/services/nlp.py`: pipeline, k-fold CV, thresholds — source for Tabel 3.6.
- `/Users/rada/Downloads/office-skripsi-ikram/prd-siladesa/DATABASE.md`: 22-table schema for Tabel 3.4.
- `/tmp/skripsi_work/unpacked/word/numbering.xml`, `styles.xml`: numbering/style definitions (abstractNum 0, ilvl 3 → `ind left=3447`; Heading3 has blue theme font needing per-run override).
- `/tmp/e2e_cek.py`, `/tmp/smoke_cek.py`: passing end-to-end and page smoke tests (server on port 8021).

## Important Context
- Paragraph 247 holds the section break (`w:sectPr`) before `DAFTAR PUSTAKA` (248) — preserved as the insertion cursor in the rebuild script.
- Images and equations were preserved by `copy.deepcopy` **before** deleting paragraphs 144–246; the script inserts them via `kursor.addprevious(...)`.
- Helpers insert new elements at end of body then move them before the cursor, so insertion order defines document order; `d.add_table`/`d.add_paragraph` insert before `sectPr`.
- Existing `Tabel 3.1` (author's) has 11 rows × 12 cols with `vMerge` header rows (No / Jenis Kegiatan / Mei II–IV, Juni I–IV, Juli I–III); data rows are 3–10.
- `Tabel 3.1` fill plan used: rows 1:(Mei II,III) 2:(II,III,IV) 3:(IV,Juni I) 4:(Juni I,II,III) 5:(III,IV) 6:(IV,Juli I) 7:(Juli I,II) 8:(Juli III).
- Existing OMML equations: `Akurasi = Jumlah Respons Benar / Total Pengujian × 100` and Slovin `n = N / (1 + N·e²)`.
- Skripsi title (unchanged): "PENERAPAN NATURAL LANGUAGE PROCESSING UNTUK CHATBOT DAN OTOMATISASI PENERBITAN DOKUMEN ADMINISTRASI DESA KAMPALA KECAMATAN ARUNGKEKE KABUPATEN JENEPONTO".
- DAFTAR ISI/DAFTAR GAMBAR/DAFTAR TABEL are static text (`toc 1`/`toc 2` styles), not fields — must be edited manually.
- DB entities singular uppercase (`APPLICATION`, `CITIZEN`, `LETTER_NUMBER_COUNTER`, `FAQ`); ORM classes PascalCase (`Application`, `Citizen`, `ConversationSession`, `ChatMessage`, `NlpModel`, `ModelMetric`, `TrainingSample`, `Intent`, `Faq`, `Official`, `Setting`, `AuditLog`, `LetterNumberCounter`, `AdminUser`, `Service`, `ServiceField`, `LetterTemplate`, `Document`, `ApplicationEvent`, `Attachment`, `VerificationScan`, `FeedbackResponse`).
- 22 tables grouped for Tabel 3.4: kependudukan/pengguna (citizen, admin_user, official); layanan/formulir (service, service_field, letter_template); pengajuan (application, application_event, attachment, verification_scan); dokumen (document, letter_number_counter); percakapan/NLP (conversation_session, chat_message, intent, training_sample, nlp_model, model_metric); pengetahuan/pengaturan (faq, setting, audit_log, feedback_response).
- Partial unique indexes: one active template per service, one active official per `jabatan`, one `aktif` NLP model.
- `application.form_data` is a JSON snapshot so later `citizen` edits don't alter issued documents.
- Append-only tables (`application_event`, `audit_log`, `verification_scan`) have no update/delete endpoints.
- QR token ≥128-bit entropy (`secrets.token_urlsafe(32)`); URL `https://{domain}/v/{qr_token}`; verify page masks NIK, never serves the PDF.
- Download token: `GET /d/{signed_token}`, 7-day TTL; invalid or revoked → **410**.
- Chat enforces max **3 active applications per NIK**; 4th is rejected with a "batas" message. Tests must use a fresh random NIK per run.
- Chat confirmation prompt: "Ketik *ya* untuk mengirim atau *batal* untuk membatalkan."
- `assert_csrf` uses `request.state.csrf` (set only by `current_user`) with fallback to `CSRF_COOKIE`; any new POST route must declare `Depends(require_login)` or it 403s.
- Deleting the SQLite DB requires also removing `data/siladesa.db-shm` and `-wal`, else `sqlite3.OperationalError: disk I/O error`.
- Official header: `PEMERINTAH KABUPATEN JENEPONTO / KECAMATAN ARUNGKEKE / DESA KAMPALA`, `Jl.Poros Dusun Buntulu Desa Kampala Kec.Arungkeke`.
- Signatories: Kepala Desa `Hj. ROSMIATI`, Sekdes `BAHTIAR.B`, Kapolsek `SALMAN SALAM SH.` as witness on DOM letters.
- Dusun enum: Buntulu, Kalukuang, Monroloe, Pinyangkabung, Sepeka. NIK prefix `7304`, 16 digits.
- DOM service has **14 fields** in order: NIK, Nama Lengkap, Tempat Lahir, Tanggal Lahir, Jenis Kelamin, Status Perkawinan, Agama, Pekerjaan, Alamat, Dusun, RT, RW, No. HP, Keperluan. `_fields()` prepends shared `IDENTITAS`.
- ReportLab placeholders: `{pejabat_nama}`, `{pejabat_jabatan}`, `{nama_lengkap}`, `{nik}`, `{tempat_lahir}`, `{tanggal_lahir_panjang}`, `{alamat_penuh}`, `{keperluan}`.
- Admin sidebar order in `_opsi_nav`: Ringkasan, Pengajuan, Pertanyaan gagal, Layanan, Template surat, Nomor surat, FAQ, Pejabat, Model NLP, Dataset latih, Pengguna, Pengaturan, Laporan, Jejak audit.
- Report CSV uses `;` delimiter + `\ufeff` BOM.
- Tests set env vars **before** importing `app.config` (top of `conftest.py`) because `settings` and the SQLAlchemy engine are module-level singletons.
- Intent codes (18): SAPA, INFO_SYARAT_DOMISILI, AJUKAN_DOMISILI, INFO_SYARAT_SKTM, AJUKAN_SKTM, INFO_SYARAT_USAHA, AJUKAN_USAHA, INFO_SYARAT_PENGANTAR, AJUKAN_PENGANTAR, CEK_STATUS, INFO_JAM_LAYANAN, INFO_BIAYA, INFO_LAMA_PROSES, INFO_SYARAT_UMUM, KOMPLAIN, BICARA_PETUGAS, TERIMA_KASIH, LAINNYA.
- Skripsi open issues: placeholder `N = 1.245` in Slovin explanation (needs monografi figure), reference cleanup, no Bab IV–V, no front matter.
- Repo is a git repo, last commit `8370d13`; `prd-siladesa/`, `siladesa-app/`, `Skripsi ikram-2_bab3.docx`, figures and `Format surat/` remain **untracked/uncommitted**.
- Tool output sometimes visually mangles `render_as_batonnection...` as `render_as_batonnection...`; the file bytes were verified correct via `repr()` — do not "fix" it again.
