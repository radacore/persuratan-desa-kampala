# REQUIREMENTS.md: SILADESA

## 1. Functional Requirements

### 1.1. Kanal Percakapan & Warga

**FR-01: Kanal Percakapan Multi-Channel**
The system SHALL menerima dan membalas pesan warga melalui WhatsApp, Telegram, dan web widget menggunakan satu pipeline percakapan yang sama.
*   Setiap kanal MUST memiliki adapter yang menormalkan payload masuk ke struktur `{channel, external_user_id, message, message_id, received_at}`.
*   Balasan SHALL dikirim kembali ke kanal asal pesan.
*   Kegagalan pada satu kanal MUST NOT menghentikan pemrosesan kanal lain.
*   Sistem SHOULD menolak pesan dari kanal yang tidak terdaftar dengan status 404.

**FR-02: Identifikasi & Sesi Pengguna**
The system SHALL mengidentifikasi warga berdasarkan nomor WhatsApp, Telegram user ID, atau cookie sesi web, dan menyimpan konteks percakapan.
*   Sesi MUST kedaluwarsa otomatis setelah 30 menit tanpa aktivitas.
*   Sistem MUST menyimpan riwayat pesan dalam sesi untuk keperluan klarifikasi dan audit.
*   Warga MUST dapat melanjutkan percakapan yang sama selama sesi belum kedaluwarsa.
*   Sesi baru SHALL dibuat otomatis ketika warga mengirim pesan setelah sesi lama kedaluwarsa.

**FR-03: Menu Layanan & Onboarding**
The system SHALL menampilkan menu layanan utama pada percakapan pertama setiap sesi.
*   Menu MUST memuat empat layanan MVP (Domisili, SKTM, Usaha, Pengantar), opsi "Tanya hal lain", dan opsi "Bicara dengan petugas".
*   Menu SHOULD ditampilkan sebagai tombol cepat pada kanal yang mendukung (Telegram, web widget).
*   Pada WhatsApp yang tidak mendukung tombol, menu SHALL dikirim sebagai teks bernomor yang dapat dibalas dengan angka.
*   Menu MUST dapat ditutup dan dipanggil ulang dengan perintah `menu`.

**FR-04: Persetujuan Pemrosesan Data**
The system SHALL meminta persetujuan eksplisit sebelum membuat pengajuan surat.
*   Persetujuan MUST disimpan bersama timestamp, versi kebijakan, kanal, dan ID sesi.
*   Pengajuan MUST NOT dibuat bila persetujuan belum diberikan.
*   Warga SHALL dapat menolak, dan sistem MUST menghentikan alur pengajuan tanpa menyimpan data pribadi.
*   Teks kebijakan SHOULD dapat diubah admin melalui pengaturan sistem.

**FR-05: Klasifikasi Intent NLP**
The system SHALL mengklasifikasikan setiap pesan warga ke salah satu intent terdaftar.
*   Respons klasifikasi MUST memuat `intent`, `confidence`, dan tiga kandidat intent teratas.
*   Sistem MUST menggunakan model aktif yang tercatat pada tabel `NLP_MODEL`.
*   Bila tidak ada model aktif, sistem MUST menolak melayani klasifikasi dan mencatat error, bukan menebak jawaban.
*   Klasifikasi MUST selesai dalam ≤ 50 ms pada perangkat produksi.

**FR-06: Preprocessing Teks Bahasa Indonesia**
The system SHALL melakukan preprocessing sebelum klasifikasi.
*   Tahapan MUST mencakup case folding, pembersihan karakter non-alfanumerik, normalisasi singkatan, tokenisasi, stopword removal, dan stemming.
*   Kamus normalisasi MUST memuat minimal 50 istilah lokal dan singkatan layanan (mis. `sktm`, `domisili`, `kk`, `ktp`, `surat usaha`).
*   Preprocessing MUST bersifat idempoten: teks yang sudah dinormalisasi tidak berubah bila diproses ulang.
*   Sistem SHOULD menyimpan teks asli dan teks hasil preprocessing secara terpisah untuk keperluan evaluasi.

**FR-07: Ambang Keyakinan & Klarifikasi**
The system SHALL menerapkan ambang keyakinan bertingkat.
*   `confidence` ≥ 0,65 MUST dijawab langsung.
*   `confidence` 0,40–0,65 SHALL memicu pertanyaan klarifikasi dengan maksimal tiga pilihan.
*   `confidence` < 0,40 MUST memicu tawaran eskalasi ke petugas.
*   Nilai ambang MUST dapat diubah admin tanpa deploy ulang.

**FR-08: Slot Filling Multi-Turn**
The system SHALL mengumpulkan field wajib satu per satu melalui percakapan.
*   Sistem MUST menanyakan hanya field yang belum terisi.
*   Warga SHALL dapat mengoreksi jawaban sebelumnya dengan perintah `ubah <nama_field>`.
*   Sistem MUST menyimpan progres slot filling sehingga percakapan dapat dilanjutkan setelah gangguan jaringan.
*   Sistem SHOULD mengelompokkan maksimal tiga field terkait dalam satu pertanyaan bila field tersebut pendek (mis. tempat dan tanggal lahir).

**FR-09: Validasi Data Pemohon**
The system SHALL memvalidasi seluruh data pemohon sebelum disimpan permanen.
*   NIK MUST tepat 16 digit numerik dan diawali `7304`.
*   Nomor KK, bila diisi, MUST tepat 16 digit numerik.
*   Tanggal lahir MUST berupa tanggal valid dan tidak boleh di masa depan.
*   Nomor HP MUST 10–15 digit dan dapat diawali `62` atau `0`.
*   Nilai `agama`, `status_perkawinan`, dan `dusun` MUST termasuk dalam enumerasi yang terdaftar.
*   Pesan kesalahan MUST menyebut field dan alasan spesifik, bukan pesan umum.

**FR-10: Jawaban Informasi Layanan**
The system SHALL menjawab pertanyaan persyaratan, prosedur, estimasi waktu, dan biaya berdasarkan data pada tabel `SERVICE`.
*   Jawaban MUST diambil dari basis data, bukan dari teks yang ditanam di kode.
*   Perubahan data layanan oleh admin SHALL langsung berlaku pada jawaban berikutnya.
*   Jawaban SHOULD menyertakan tombol atau perintah untuk memulai pengajuan.

**FR-11: FAQ & Informasi Operasional**
The system SHALL menjawab pertanyaan umum tentang jam layanan, lokasi kantor, daftar dusun, dan kontak.
*   FAQ MUST dikelola melalui panel admin.
*   Sistem MUST mengambil jam layanan dan alamat dari tabel `SETTING`, bukan konstanta.
*   Daftar dusun SHOULD mencakup Buntulu, Kalukuang, Monroloe, Pinyangkabung, dan Sepeka, serta dapat ditambah admin.

**FR-12: Pencatatan Pertanyaan Gagal**
The system SHALL menyimpan pertanyaan yang tidak terklasifikasi ke antrean *unanswered questions*.
*   Setiap entri MUST memuat teks asli, teks hasil preprocessing, kanal, `confidence` tertinggi, dan timestamp.
*   Admin MUST dapat melihat, memfilter, dan melabeli entri tersebut.
*   Entri yang sudah dilabeli SHALL masuk ke dataset pelatihan dengan sumber `chat_log`.

**FR-13: Eskalasi ke Petugas**
The system SHALL membuat tiket eskalasi ketika warga meminta bantuan manusia atau ketika intent gagal dikenali dua kali berturut-turut.
*   Tiket MUST memuat ringkasan percakapan dan status `MENUNGGU_PETUGAS`.
*   Warga MUST menerima estimasi waktu respons sesuai jam layanan.
*   Operator MUST melihat tiket eskalasi pada antrean terpisah di panel admin.

**FR-14: Pembuatan Tiket Pengajuan**
The system SHALL membuat tiket pengajuan dengan nomor unik berformat `APP-{YYYY}-{seq:6d}` dan status awal `DRAFT`.
*   Nomor tiket MUST unik dan tidak dapat diprediksi berurutan lintas tahun.
*   Tiket MUST terhubung ke `CITIZEN` dan `SERVICE`.
*   Pembuatan tiket MUST mencatat event `DRAFT` pada `APPLICATION_EVENT`.

**FR-15: Ringkasan & Konfirmasi**
The system SHALL menampilkan ringkasan seluruh data sebelum submit.
*   Ringkasan MUST memuat nama, NIK ter-mask sebagian, layanan, dan field khusus layanan.
*   Warga MUST dapat mengubah field sebelum menekan konfirmasi.
*   Submit MUST NOT terjadi tanpa konfirmasi eksplisit (`Ya` atau tombol setara).

**FR-16: Pencegahan Pengajuan Ganda**
The system SHALL membatasi maksimal tiga pengajuan aktif per NIK per 24 jam.
*   Pengajuan aktif didefinisikan sebagai status `DRAFT`, `MENUNGGU_VERIFIKASI`, atau `DIPROSES`.
*   Pengajuan keempat MUST ditolak dengan pesan yang menyebut nomor tiket yang masih aktif.
*   Batas SHOULD dapat dikonfigurasi admin.

**FR-17: Pelacakan Status**
The system SHALL menjawab perintah `status` dengan status pengajuan terakhir milik pengguna.
*   Balasan MUST memuat nomor tiket, nama layanan, status, dan tanggal pembaruan terakhir.
*   Bila status `DITOLAK`, balasan MUST menyertakan alasan penolakan.
*   Bila pengguna tidak memiliki pengajuan, sistem MUST menawarkan untuk memulai pengajuan baru.

**FR-18: Pembatalan Pengajuan**
The system SHALL memungkinkan warga membatalkan pengajuannya selama status belum `DIPROSES`.
*   Pembatalan MUST mengubah status menjadi `DIBATALKAN` dan mencatat event.
*   Nomor surat yang belum dialokasikan MUST tetap tersedia untuk pengajuan lain.
*   Pembatalan setelah dokumen terbit MUST ditolak dan diarahkan ke petugas.

**FR-19: Notifikasi Perubahan Status**
The system SHALL mengirim notifikasi ke kanal asal setiap kali status pengajuan berubah.
*   Notifikasi MUST dikirim maksimal satu kali per transisi status.
*   Kegagalan pengiriman MUST dicatat dan dicoba ulang maksimal tiga kali dengan backoff.
*   Notifikasi MUST NOT memuat NIK lengkap.

**FR-20: Pengiriman Dokumen ke Chat**
The system SHALL mengirim berkas PDF ke percakapan warga setelah dokumen berstatus `TERBIT`.
*   Pengiriman MUST terjadi dalam ≤ 10 detik setelah persetujuan.
*   Bila pengiriman gagal, sistem MUST menyimpan tautan unduhan bertoken yang berlaku 7 hari.
*   Sistem MUST mencatat waktu pengiriman pada `DOCUMENT`.

**FR-21: Survei Kepuasan**
The system SHALL meminta penilaian kepuasan setelah dokumen diterima.
*   Skor MUST berupa skala 1–5 dan disimpan pada `FEEDBACK_RESPONSE`.
*   Komentar bersifat opsional dan dibatasi 500 karakter.
*   Sistem SHOULD mengirim permintaan maksimal satu kali per pengajuan.

### 1.2. Dokumen & Verifikasi

**FR-22: Katalog Layanan Administrasi**
The system SHALL menyimpan katalog layanan yang dapat dikelola admin tanpa mengubah kode.
*   Setiap layanan MUST memiliki `kode`, `nama`, `deskripsi`, `persyaratan`, `alur`, `sla_hari`, `biaya`, dan status `aktif`.
*   Layanan nonaktif MUST NOT muncul pada menu chatbot maupun daftar publik.
*   Perubahan katalog MUST tercatat pada `AUDIT_LOG`.

**FR-23: Skema Field Dinamis**
The system SHALL menyimpan definisi field per layanan pada tabel `SERVICE_FIELD`.
*   Setiap field MUST memiliki `nama_field`, `label`, `tipe`, `wajib`, `urutan`, dan aturan validasi.
*   Tipe yang didukung MUST mencakup `text`, `number`, `date`, `enum`, `textarea`, dan `phone`.
*   Field `enum` MUST menyimpan daftar opsi pada kolom `opsi`.
*   Penambahan layanan baru MUST NOT memerlukan migrasi skema database.

**FR-24: Template Surat & Placeholder**
The system SHALL mengelola template surat berversi dengan placeholder.
*   Placeholder MUST menggunakan sintaks `{{nama_field}}` dan divalidasi terhadap skema field layanan.
*   Placeholder yang tidak dikenal MUST menghasilkan error saat pratinjau, bukan saat penerbitan.
*   Setiap perubahan template MUST membuat versi baru; versi lama MUST tetap tersimpan.
*   Hanya satu versi yang boleh berstatus aktif per layanan.

**FR-25: Alokasi Nomor Surat**
The system SHALL mengalokasikan nomor surat secara atomik dan unik.
*   Format nomor MUST `{seq:03d}/DKP/{bulan_romawi}/{tahun}` dan dapat dikonfigurasi.
*   Counter MUST terpisah per layanan per tahun.
*   Alokasi MUST menggunakan transaksi dan penguncian baris untuk mencegah duplikasi.
*   Override manual MUST memerlukan alasan dan hanya dapat dilakukan Sekdes, Kepala Desa, atau Admin Teknis.

**FR-26: Generate PDF Surat**
The system SHALL menghasilkan PDF A4 sesuai tata letak arsip desa.
*   PDF MUST memuat kop pemerintah kabupaten/kecamatan/desa, judul surat, nomor, isi, dan blok tanda tangan.
*   Font MUST Times New Roman atau metrik setara, ukuran 12 pt untuk isi.
*   Margin MUST 2,5–3 cm pada semua sisi.
*   PDF MUST dihasilkan dalam ≤ 5 detik p95.

**FR-27: QR Code Verifikasi**
The system SHALL menempelkan QR Code pada area tanda tangan.
*   QR MUST mengarah ke `https://{domain}/v/{qr_token}`.
*   `qr_token` MUST dihasilkan dari minimal 128 bit entropi dan tidak dapat diprediksi.
*   Ukuran QR MUST minimal 2,5 × 2,5 cm dan tidak menutupi teks.
*   QR MUST tetap dapat dipindai setelah PDF dicetak pada resolusi 300 dpi.

**FR-28: Hash & Arsip Dokumen**
The system SHALL menyimpan hash SHA-256 setiap dokumen yang dihasilkan.
*   Hash MUST dihitung dari berkas final, setelah QR dan tanda tangan ditempel.
*   Hash MUST ditampilkan pada halaman verifikasi.
*   Berkas PDF MUST diarsipkan minimal 5 tahun.

**FR-29: Watermark Draft**
The system SHALL menandai dokumen yang belum disetujui pejabat.
*   Watermark MUST berbunyi "DRAFT — BELUM SAH" dan ditempatkan diagonal dengan opasitas rendah.
*   Watermark MUST hilang sepenuhnya pada dokumen berstatus `TERBIT`.
*   Dokumen draft MUST NOT dapat diunduh melalui portal verifikasi publik.

**FR-30: Tanda Tangan Pejabat**
The system SHALL menempelkan scan tanda tangan pejabat aktif.
*   Pejabat MUST dipilih berdasarkan jabatan yang disyaratkan layanan dan tanggal penerbitan.
*   Sistem MUST menolak penerbitan bila tidak ada pejabat aktif atau masa berlaku habis.
*   Berkas tanda tangan MUST hanya dapat diunggah oleh Kepala Desa atau Admin Teknis.

**FR-31: Halaman Verifikasi Publik**
The system SHALL menyediakan halaman publik tanpa login pada `/v/{qr_token}`.
*   Halaman MUST menampilkan status (`SAH`, `DIBATALKAN`, `TIDAK DITEMUKAN`), jenis surat, nomor, tanggal terbit, nama ter-mask, NIK ter-mask, dan hash.
*   Halaman MUST NOT menampilkan NIK lengkap, alamat lengkap, atau berkas PDF.
*   Halaman MUST dapat diakses dalam ≤ 1 detik dan tetap terbaca pada layar 360 px.
*   Status `DIBATALKAN` MUST ditampilkan dengan peringatan visual yang jelas.

**FR-32: API Verifikasi Instansi**
The system SHALL menyediakan endpoint JSON verifikasi untuk instansi.
*   Endpoint MUST membatasi 60 permintaan per menit per IP.
*   Respons MUST memakai struktur yang sama dengan halaman verifikasi.
*   Endpoint MUST mencatat pemanggilan pada `VERIFICATION_SCAN`.

**FR-33: Log Pemindaian QR**
The system SHALL mencatat setiap pemindaian QR.
*   Log MUST memuat `document_id`, waktu, IP ter-hash, dan user agent.
*   IP MUST disimpan sebagai hash SHA-256 dengan salt, bukan teks asli.
*   Log MUST dapat difilter berdasarkan dokumen dan rentang tanggal pada panel admin.

### 1.3. Panel Admin

**FR-34: Autentikasi Admin & RBAC**
The system SHALL menyediakan login email dan password untuk akun admin.
*   Password MUST di-hash dengan Argon2id.
*   Sesi MUST menggunakan cookie `HttpOnly`, `Secure`, dan `SameSite=Lax` dengan masa berlaku 30 menit.
*   Akun MUST terkunci 15 menit setelah lima percobaan login gagal.
*   Setiap endpoint admin MUST memeriksa peran sesuai matriks RBAC pada PRD.

**FR-35: Dashboard Operasional**
The system SHALL menampilkan ringkasan operasional pada halaman utama admin.
*   Dashboard MUST menampilkan jumlah pengajuan hari ini, antrean `MENUNGGU_VERIFIKASI`, dokumen `TERBIT`, penolakan, dan akurasi model aktif.
*   Data MUST diperbarui paling lambat 5 detik setelah halaman dimuat ulang.
*   Dashboard SHOULD menampilkan tren tujuh hari terakhir.

**FR-36: Manajemen Pengajuan**
The system SHALL menyediakan daftar dan detail pengajuan.
*   Daftar MUST mendukung filter status, layanan, rentang tanggal, dan dusun, serta pencarian nomor tiket atau NIK.
*   Daftar MUST menggunakan pagination maksimal 25 baris per halaman.
*   Detail MUST menampilkan data pemohon, riwayat status, lampiran, dan aksi yang tersedia sesuai peran.

**FR-37: Koreksi Data & Audit Perubahan**
The system SHALL memungkinkan operator mengoreksi data pemohon sebelum dokumen terbit.
*   Setiap perubahan MUST mencatat nilai lama, nilai baru, aktor, dan waktu.
*   Koreksi MUST NOT dapat dilakukan setelah status `TERBIT`.
*   Field yang dikoreksi SHOULD ditandai pada tampilan detail.

**FR-38: Persetujuan & Penerbitan**
The system SHALL memungkinkan Sekdes atau Kepala Desa menyetujui pengajuan.
*   Persetujuan MUST memicu alokasi nomor, generate PDF, penempelan QR dan tanda tangan, serta pengiriman ke warga dalam satu alur.
*   Bila salah satu langkah gagal, status MUST tetap `DIPROSES` dan error MUST dicatat.
*   Persetujuan MUST mencatat aktor dan waktu pada `APPLICATION_EVENT`.

**FR-39: Penolakan dengan Alasan**
The system SHALL memungkinkan penolakan pengajuan dengan alasan wajib.
*   Alasan MUST minimal 10 karakter.
*   Status MUST berubah menjadi `DITOLAK` dan alasan MUST dikirim ke warga.
*   Pengajuan yang ditolak MUST dapat diajukan ulang sebagai tiket baru.

**FR-40: Manajemen Template Surat**
The system SHALL menyediakan editor template dengan pratinjau.
*   Editor MUST menampilkan daftar placeholder yang tersedia untuk layanan terkait.
*   Pratinjau MUST menghasilkan PDF contoh dengan data dummy.
*   Aktivasi versi baru MUST menonaktifkan versi sebelumnya secara otomatis.

**FR-41: Manajemen Pejabat & TTD**
The system SHALL mengelola data pejabat dan berkas tanda tangan.
*   Data MUST memuat nama, jabatan, NIP, berkas TTD, dan masa berlaku.
*   Sistem MUST mencegah lebih dari satu pejabat aktif untuk jabatan yang sama.
*   Unggahan TTD MUST dibatasi 2 MB dan hanya menerima PNG/JPG.

**FR-42: Manajemen Nomor Surat**
The system SHALL menampilkan dan mengelola counter nomor surat.
*   Halaman MUST menampilkan nomor terakhir per layanan per tahun.
*   Reset MUST memerlukan konfirmasi ganda dan alasan.
*   Override MUST menolak nomor yang sudah ada.

**FR-43: Manajemen Katalog & Field Layanan**
The system SHALL menyediakan CRUD layanan dan field-nya.
*   Penghapusan layanan MUST bersifat soft delete bila sudah memiliki pengajuan.
*   Urutan field MUST dapat diubah dan memengaruhi urutan pertanyaan chatbot.
*   Perubahan MUST langsung berlaku pada sesi percakapan baru.

**FR-44: Manajemen Basis Pengetahuan**
The system SHALL menyediakan CRUD FAQ dan materi jawaban.
*   Setiap FAQ MUST memiliki pertanyaan, jawaban, intent terkait, dan status aktif.
*   FAQ nonaktif MUST NOT digunakan chatbot.
*   Perubahan MUST tercatat pada `AUDIT_LOG`.

**FR-45: Manajemen Dataset & Pelabelan**
The system SHALL menyediakan antrean pelabelan dan impor dataset.
*   Admin MUST dapat melabeli pertanyaan gagal dengan intent yang tersedia.
*   Impor CSV MUST memvalidasi header `teks,intent` dan menolak baris tidak valid dengan laporan per baris.
*   Setiap sampel MUST mencatat sumber (`manual`, `chat_log`, `import`).

**FR-46: Pelatihan & Evaluasi Model**
The system SHALL menjalankan pelatihan dan menampilkan metrik model.
*   Pelatihan MUST memakai split 80/20 stratifikasi dan seed tetap.
*   Metrik MUST mencakup akurasi, macro F1, precision/recall per kelas, dan confusion matrix.
*   Model baru MUST berstatus `kandidat` sampai diaktifkan manual.
*   Sistem MUST menolak aktivasi model dengan akurasi < 85% kecuali disertai alasan tertulis.
*   Rollback ke model sebelumnya MUST tersedia dalam satu aksi.

**FR-47: Audit Log**
The system SHALL mencatat seluruh aksi admin dan transisi status.
*   Log MUST memuat aktor, aksi, entitas, ID entitas, perubahan, dan waktu.
*   Log MUST NOT dapat diubah atau dihapus melalui aplikasi.
*   Log MUST dapat difilter berdasarkan aktor, aksi, entitas, dan tanggal.

**FR-48: Manajemen Pengguna Admin**
The system SHALL menyediakan CRUD akun admin.
*   Setiap akun MUST memiliki tepat satu peran.
*   Sistem MUST menolak penghapusan atau penonaktifan akun aktif terakhir.
*   Reset password MUST dihasilkan sistem dan wajib diganti saat login berikutnya.

**FR-49: Pengaturan Sistem**
The system SHALL menyediakan pengaturan operasional.
*   Pengaturan MUST mencakup jam layanan, alamat, kontak, teks eskalasi, ambang keyakinan, batas pengajuan, dan versi kebijakan privasi.
*   Perubahan MUST berlaku tanpa restart aplikasi.
*   Nilai pengaturan SHOULD memiliki validasi tipe dan rentang.

**FR-50: Laporan & Ekspor**
The system SHALL menyediakan rekap bulanan.
*   Rekap MUST memuat jumlah pengajuan per layanan, per status, dan rata-rata waktu proses.
*   Ekspor CSV MUST menggunakan pemisah koma dan encoding UTF-8.
*   Laporan MUST dapat difilter berdasarkan bulan dan tahun.

## 2. Non-Functional Requirements

| Category | Requirement | Measurable Target |
|:---|:---|:---|
| Performance | Respons chat cepat | Respons chatbot p95 ≤ 2 detik; klasifikasi intent ≤ 50 ms; generate PDF p95 ≤ 5 detik |
| Performance | Throughput memadai | 50 pengguna concurrent; 1.000 pesan/hari tanpa antrean > 1 menit |
| Reliability | Ketersediaan layanan | Uptime ≥ 99% per bulan; RTO ≤ 4 jam; RPO ≤ 24 jam |
| Security | Integritas sistem | HTTPS wajib; Argon2id; proteksi OWASP Top 10; rate limit login 5/menit dan chat 20/menit per pengguna; audit log immutable |
| Privacy | Perlindungan data warga | Consent wajib; NIK di-mask pada tampilan publik; penyimpanan terenkripsi pada tingkat volume disk dan backup; retensi sesuai kebijakan desa |
| Usability | Mudah dipakai | Alur pengajuan ≤ 3 menit; task completion ≥ 80%; WCAG 2.1 AA; target sentuh ≥ 44 px |
| Compatibility | Dukungan perangkat | WhatsApp Android 8+/iOS 14+; empat browser utama dua versi terakhir; layout 360–1440 px |
| Maintainability | Mudah dirawat | Coverage ≥ 70%; `ruff` bersih; OpenAPI 3.1; deploy satu perintah |
| Observability | Mudah didiagnosis | Log JSON; error tracking; `/healthz`; uptime monitor eksternal |
| Localization | Konteks lokal | Bahasa Indonesia; `dd MMMM yyyy`; WITA (UTC+8) |

## 3. Technical Constraints

*   Sistem MUST berjalan pada satu VPS 2 vCPU / 2 GB RAM / 40 GB SSD tanpa layanan terkelola tambahan.
*   Sistem MUST NOT memanggil API LLM komersial untuk memproses pesan warga.
*   Model NLP MUST dilatih dari dataset lokal dan disimpan sebagai artefak versi.
*   Stack MUST Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL 16 (produksi), Jinja2, HTMX, Tailwind CSS, ReportLab, dan scikit-learn.
*   Panel admin MUST server-rendered; tidak ada SPA framework.
*   Antarmuka MUST berbahasa Indonesia.
*   Format nomor surat MUST mengikuti pola arsip desa dan disetujui Sekdes sebelum go-live.
*   Dokumen MUST A4 dengan margin 2,5–3 cm dan font Times New Roman atau metrik setara.
*   Data pribadi MUST NOT dikirim ke layanan pihak ketiga selain gateway pengiriman pesan.

## 4. Assumptions

*   Desa WILL menyediakan koneksi internet stabil minimal 8 jam/hari dan satu komputer operator.
*   Desa WILL menyediakan nomor WhatsApp yang dapat dihubungkan ke gateway pihak ketiga.
*   Desa WILL menyediakan data monografi (jumlah penduduk/KK) untuk perhitungan sampel Slovin.
*   Kepala Desa WILL menyetujui penggunaan scan tanda tangan digital.
*   Minimal 600 ujaran berlabel WILL tersedia sebelum pelatihan model final.
*   Sekdes WILL memvalidasi format dan isi template surat sebelum go-live.
*   Dua operator WILL mengikuti pelatihan penggunaan panel admin.
*   Domain dan sertifikat SSL WILL tersedia sebelum pengujian pengguna.
*   Pengujian kepuasan WILL menggunakan sampel sesuai rumus Slovin dengan `e = 10%`.
