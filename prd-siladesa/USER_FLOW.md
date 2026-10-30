# USER_FLOW.md: SILADESA

## Daftar Alur

| # | Alur | Aktor | Kanal | FR terkait |
|:--|:---|:---|:---|:---|
| UF-01 | Menanyakan informasi layanan | Warga | WhatsApp/TG/Web | FR-05, FR-07, FR-10 |
| UF-02 | Mengajukan surat | Warga | WhatsApp/TG/Web | FR-08, FR-09, FR-14, FR-15 |
| UF-03 | Melacak status pengajuan | Warga | WhatsApp/TG/Web | FR-17 |
| UF-04 | Menerima & memverifikasi dokumen | Warga | WhatsApp/TG/Web | FR-20, FR-27 |
| UF-05 | Membatalkan pengajuan | Warga | WhatsApp/TG/Web | FR-18 |
| UF-06 | Meminta bantuan petugas | Warga | WhatsApp/TG/Web | FR-13 |
| UF-07 | Memverifikasi keaslian dokumen | Verifikator eksternal | Browser | FR-31, FR-32 |
| UF-08 | Meninjau & mengoreksi pengajuan | Operator | Panel admin | FR-36, FR-37 |
| UF-09 | Menyetujui & menerbitkan dokumen | Sekdes/Kepala Desa | Panel admin | FR-38 |
| UF-10 | Mengelola template & nomor surat | Sekdes | Panel admin | FR-40, FR-42 |
| UF-11 | Melabeli pertanyaan gagal & melatih model | Admin Teknis | Panel admin | FR-45, FR-46 |
| UF-12 | Mengaudit & menyusun laporan | Sekdes | Panel admin | FR-47, FR-50 |

---

## UF-01 — Menanyakan Informasi Layanan

**Aktor:** Warga
**Tujuan:** mengetahui persyaratan, prosedur, biaya, dan estimasi waktu sebelum datang atau mengajukan.
**Prasyarat:** tidak ada.

```mermaid
flowchart TD
    A[Warga kirim pesan] --> B{Sesi aktif?}
    B -- Tidak --> C[Buat sesi + kirim menu]
    B -- Ya --> D[Preprocessing teks]
    C --> D
    D --> E[Klasifikasi intent]
    E --> F{Confidence}
    F -- ">= 0,65" --> G[Ambil data SERVICE]
    G --> H[Kirim jawaban + tombol ajukan]
    F -- "0,40 - 0,65" --> I[Kirim 3 pilihan klarifikasi]
    I --> A
    F -- "< 0,40" --> J[Simpan pertanyaan gagal]
    J --> K[Tawarkan eskalasi petugas]
    K --> L{Warga pilih?}
    L -- Ya --> M[UF-06]
    L -- Tidak --> N[Kirim menu utama]
```

| Langkah | Sistem | Warga melihat |
|:--|:---|:---|
| 1 | Terima pesan, buat/lanjutkan sesi | — |
| 2 | Normalisasi + klasifikasi | "Sedang mengetik…" (maks 2 detik) |
| 3 | Ambil `SERVICE.persyaratan`, `alur`, `sla_hari`, `biaya` | — |
| 4 | Susun balasan dari data, bukan teks statis | Daftar persyaratan bernomor + tombol "Buatkan sekarang" |
| 5 | Simpan `chat_message` masuk dan keluar | — |

**Contoh pertukaran:**

```text
Warga : syarat bikin surat usaha apa aja?
Bot   : Untuk Surat Keterangan Usaha, Bapak/Ibu perlu menyiapkan:
        1. Fotokopi KTP
        2. Fotokopi KK
        3. Surat pengantar dari kepala dusun
        Estimasi selesai 1 hari kerja, tanpa biaya.
        Apakah ingin saya bantu buatkan sekarang?
        [Ya, buatkan]  [Lihat layanan lain]
```

**Jalur alternatif:**

| Kondisi | Perilaku |
|:---|:---|
| Pertanyaan di luar cakupan ("berapa harga cabai?") | Confidence rendah → eskalasi, bukan jawaban mengarang |
| Pertanyaan tentang layanan fase 2 ("surat keterangan kematian") | "Layanan tersebut belum tersedia melalui chatbot. Silakan hubungi petugas desa." |
| Warga mengirim pesan kosong atau stiker | "Maaf, saya belum bisa membaca pesan itu. Boleh diketik ulang?" |
| Warga mengirim 5 pesan dalam 10 detik | Rate limit → "Mohon tunggu sebentar, saya sedang memproses pesan sebelumnya." |

---

## UF-02 — Mengajukan Surat

**Aktor:** Warga
**Tujuan:** mendapatkan surat keterangan tanpa datang ke kantor desa.
**Prasyarat:** sesi aktif; pengajuan aktif < 3.

```mermaid
flowchart TD
    A[Pilih layanan] --> B[Tampilkan persyaratan + consent]
    B --> C{Setuju?}
    C -- Tidak --> D[Batalkan, tidak simpan PII]
    C -- Ya --> E[POST /applications -> tiket DRAFT]
    E --> F[Field berikutnya]
    F --> G[Warga jawab]
    G --> H[Validasi field]
    H -- Gagal --> I[Pesan error spesifik]
    I --> G
    H -- Lolos --> J{Masih ada field?}
    J -- Ya --> F
    J -- Tidak --> K[Tampilkan ringkasan]
    K --> L{Konfirmasi?}
    L -- "Ubah field" --> M[Pilih field -> G]
    L -- Ya --> N[Submit -> MENUNGGU_VERIFIKASI]
    N --> O[Kirim estimasi + nomor tiket]
```

| Langkah | Sistem | Warga melihat |
|:--|:---|:---|
| 1 | Tampilkan persyaratan dan teks persetujuan | "Sebelum lanjut, kami perlu menyimpan data Bapak/Ibu untuk membuat surat. Setuju?" |
| 2 | Simpan consent (`consent_at`, `consent_version`) | — |
| 3 | Buat tiket `APP-{YYYY}-{seq}` status `DRAFT` | "Baik, pengajuan dimulai. Nomor pengajuan: APP-2026-000128" |
| 4 | Tanyakan field sesuai `urutan` | "Boleh kami tahu NIK Bapak/Ibu?" |
| 5 | Validasi tiap jawaban | Jika salah: "NIK harus 16 angka. Bapak/Ibu memasukkan 12 angka." |
| 6 | Tampilkan ringkasan | Daftar field dengan NIK ter-mask + tombol "Ubah" per baris |
| 7 | Submit → `MENUNGGU_VERIFIKASI` | "Pengajuan sudah kami terima. Petugas akan memeriksa dalam 1 hari kerja." |

**Aturan pengalaman:**

*   Sistem **hanya** menanyakan field yang belum terisi.
*   Warga dapat mengetik `ubah nik` kapan saja untuk mengoreksi.
*   Progres ditampilkan: "Langkah 3 dari 9".
*   Bila warga berhenti > 30 menit, progres tetap tersimpan; saat kembali, sistem menawarkan melanjutkan.
*   Tidak ada field yang ditanyakan dua kali.

**Jalur alternatif:**

| Kondisi | Perilaku |
|:---|:---|
| 3 pengajuan aktif | Tampilkan nomor tiket yang masih aktif + saran membatalkan atau menunggu |
| Warga membatalkan di tengah | Status `DIBATALKAN`; data tetap tersimpan untuk audit tetapi tidak diproses |
| Warga mengirim foto KTP | "Untuk tahap ini cukup diketik. Foto KTP dibawa saat pengambilan bila diminta petugas." (fase 2: unggah lampiran) |
| Data tidak konsisten (NIK ≠ tanggal lahir) | Operator akan memverifikasi; warga diberi tahu bahwa data akan diperiksa |

---

## UF-03 — Melacak Status Pengajuan

**Aktor:** Warga
**Tujuan:** mengetahui posisi pengajuannya tanpa menelepon kantor.

```mermaid
flowchart TD
    A["Warga ketik: status"] --> B{Sesi punya tiket?}
    B -- Ya --> C[Ambil pengajuan terakhir]
    C --> D[Tampilkan status + timeline]
    B -- Tidak --> E[Tanya nomor tiket]
    E --> F{Tiket cocok dengan sesi?}
    F -- Ya --> D
    F -- Tidak --> G[Tolak: bukan pemilik]
    D --> H{Status?}
    H -- DITOLAK --> I[Tampilkan alasan + cara ajukan ulang]
    H -- TERBIT --> J[Tampilkan tautan unduh]
    H -- Lain --> K[Tampilkan estimasi]
```

| Status | Pesan ke warga |
|:---|:---|
| `DRAFT` | "Pengajuan belum dikirim. Ingin lanjutkan sekarang?" |
| `MENUNGGU_VERIFIKASI` | "Sedang menunggu pemeriksaan petugas. Estimasi 1 hari kerja." |
| `DIPROSES` | "Sedang diproses dan ditandatangani Kepala Desa." |
| `TERBIT` | "Surat sudah terbit. Nomor: 128/DKP/XI/2026. [Unduh PDF]" |
| `DITOLAK` | "Pengajuan belum bisa diproses karena: <alasan>. Silakan ajukan ulang setelah dilengkapi." |
| `DIBATALKAN` | "Pengajuan ini sudah dibatalkan." |

**Keamanan:** warga hanya dapat melihat pengajuan yang dibuat dari sesi/kanal yang sama. Mencoba nomor tiket milik orang lain menghasilkan "Nomor pengajuan tidak ditemukan pada percakapan ini."

---

## UF-04 — Menerima & Memverifikasi Dokumen

**Aktor:** Warga
**Tujuan:** mendapatkan PDF sah dan memahami cara memverifikasinya.

```mermaid
sequenceDiagram
    participant S as Sistem
    participant W as Warga
    participant Q as QR

    S->>W: "Surat sudah terbit" + lampiran PDF
    W->>W: Buka PDF
    W->>Q: Pindai QR di area TTD
    Q->>S: GET /v/{qr_token}
    S-->>W: Halaman "Dokumen Sah" + metadata
    S->>W: "Apakah layanan ini membantu?" 1-5
```

| Langkah | Detail |
|:--|:---|
| 1 | PDF dikirim ke kanal asal dalam ≤ 10 detik setelah persetujuan |
| 2 | Bila pengiriman gagal, dikirim tautan `/d/{token}` berlaku 7 hari |
| 3 | PDF memuat QR 2,5 × 2,5 cm di dekat tanda tangan |
| 4 | Warga memindai → halaman verifikasi menampilkan status `SAH` |
| 5 | Sistem meminta penilaian 1–5 (sekali per pengajuan) |

**Yang dilihat pada halaman verifikasi:**

```text
┌────────────────────────────────────────┐
│              ✓  DOKUMEN SAH            │
│                                        │
│  Surat Keterangan Tidak Mampu          │
│  Nomor: 128/DKP/XI/2026                │
│  Terbit: 3 November 2026               │
│                                        │
│  Nama  : Ahmad F***                    │
│  NIK   : ************0001              │
│  Dusun : Buntulu                       │
│  TTD   : Hj. Rosmiati, Kepala Desa     │
│                                        │
│  Sidik: 9f2c1e7b4a8d3f60…              │
│                                        │
│  [Laporkan kejanggalan]                │
└────────────────────────────────────────┘
```

---

## UF-05 — Membatalkan Pengajuan

**Aktor:** Warga
**Prasyarat:** status `DRAFT` atau `MENUNGGU_VERIFIKASI`.

```mermaid
flowchart LR
    A["Warga: batalkan"] --> B{Status?}
    B -- "DRAFT / MENUNGGU" --> C[Konfirmasi]
    C -- Ya --> D[Status DIBATALKAN + event]
    D --> E[Notifikasi ke warga]
    B -- "DIPROSES / TERBIT" --> F[Tolak + arahkan ke petugas]
```

| Kondisi | Perilaku |
|:---|:---|
| `DRAFT` | Langsung dapat dibatalkan |
| `MENUNGGU_VERIFIKASI` | Dapat dibatalkan; operator melihat status berubah |
| `DIPROSES` | Tidak dapat dibatalkan sendiri; harus menghubungi petugas |
| `TERBIT` | Tidak dapat dibatalkan; bila bermasalah, dokumen dicabut oleh Kepala Desa |

---

## UF-06 — Meminta Bantuan Petugas

**Aktor:** Warga
**Pemicu:** warga mengetik "bicara dengan petugas", atau dua kali gagal dikenali, atau memilih tombol eskalasi.

```mermaid
flowchart TD
    A[Pemicu eskalasi] --> B[Buat tiket eskalasi]
    B --> C[Ringkas percakapan]
    C --> D[Tampilkan estimasi respons]
    D --> E[Operator buka antrean eskalasi]
    E --> F{Perlu balas?}
    F -- Ya --> G[Operator kirim pesan ke kanal warga]
    F -- Tidak --> H[Tandai selesai]
    G --> H
```

| Langkah | Detail |
|:--|:---|
| 1 | Tiket memuat 5 pesan terakhir sebagai konteks |
| 2 | Warga menerima: "Permintaan Bapak/Ibu sudah kami teruskan. Petugas akan membalas pada jam layanan (Senin–Jumat, 08.00–15.00 WITA)." |
| 3 | Di luar jam layanan, ditambahkan: "Pesan akan dibalas pada hari kerja berikutnya." |
| 4 | Operator membalas dari panel admin; pesan terkirim ke kanal asal warga |
| 5 | Tiket ditandai selesai setelah operator menutupnya |

---

## UF-07 — Memverifikasi Keaslian Dokumen

**Aktor:** Verifikator eksternal (bank, sekolah, dinas, perusahaan)
**Prasyarat:** memiliki dokumen cetak atau PDF.

```mermaid
flowchart TD
    A[Pindai QR / buka URL] --> B{Token ada?}
    B -- Tidak --> C[Halaman: Dokumen Tidak Ditemukan]
    B -- Ya --> D{Status dokumen}
    D -- TERBIT --> E[Halaman: Dokumen Sah]
    D -- DIBATALKAN --> F[Halaman: Dokumen Dicabut + alasan]
    D -- DRAFT --> G[Halaman: Belum Sah]
    E --> H[Catat verification_scan]
    F --> H
    G --> H
```

| Yang ditampilkan | Yang **tidak** ditampilkan |
|:---|:---|
| Status keabsahan | NIK lengkap |
| Jenis dan nomor surat | Alamat lengkap |
| Tanggal terbit | Berkas PDF |
| Nama ter-mask | Data keluarga |
| Nama dan jabatan penandatangan | Nomor HP warga |
| Hash SHA-256 | — |

**Untuk sistem instansi:** `GET /api/v1/verify/{qr_token}` mengembalikan JSON yang sama, dibatasi 60 permintaan/menit/IP.

**Jalur alternatif:**

| Kondisi | Perilaku |
|:---|:---|
| QR rusak/tidak terbaca | Halaman menyediakan form input nomor surat manual |
| Nomor surat ditemukan tetapi token berbeda | Tetap tampilkan status berdasarkan nomor; catat anomali |
| Dokumen palsu dengan QR mengarah ke domain lain | Halaman resmi mencantumkan domain yang benar agar dapat dibandingkan |
| Pemindaian berulang 20 kali dalam 1 menit | Rate limit + catat sebagai anomali |

---

## UF-08 — Meninjau & Mengoreksi Pengajuan

**Aktor:** Operator
**Prasyarat:** login dengan peran `operator`.

```mermaid
flowchart TD
    A[Login] --> B[Dashboard]
    B --> C[Antrean MENUNGGU_VERIFIKASI]
    C --> D[Buka detail]
    D --> E{Data lengkap & sesuai?}
    E -- Tidak --> F[Koreksi field]
    F --> G[Simpan + audit log]
    G --> H[Kirim pesan ke warga bila perlu]
    H --> E
    E -- Ya --> I[Teruskan ke approver]
    I --> J[Status DIPROSES]
    E -- Tidak dapat diperbaiki --> K[Tolak + alasan wajib]
    K --> L[Status DITOLAK + notifikasi]
```

| Langkah | Detail |
|:--|:---|
| 1 | Daftar menampilkan lama menunggu (jam) agar prioritas jelas |
| 2 | Detail menampilkan data pemohon, form_data, lampiran, timeline |
| 3 | Koreksi mencatat nilai lama → nilai baru pada audit log |
| 4 | Bila berkas kurang, operator mengirim pesan langsung ke kanal warga |
| 5 | Penolakan memerlukan alasan ≥ 10 karakter yang diteruskan ke warga |
| 6 | Setelah diteruskan, status menjadi `DIPROSES` dan masuk antrean approver |

**Batas peran:** operator **tidak dapat** menerbitkan dokumen. Hanya `sekdes` dan `kepala_desa` yang dapat menyetujui.

---

## UF-09 — Menyetujui & Menerbitkan Dokumen

**Aktor:** Sekdes atau Kepala Desa

```mermaid
flowchart TD
    A[Antrean DIPROSES] --> B[Buka detail]
    B --> C[Pilih pejabat penandatangan]
    C --> D{Pejabat aktif & TTD ada?}
    D -- Tidak --> E[Tolak terbit + pesan error]
    D -- Ya --> F[Approve]
    F --> G[Alokasi nomor atomik]
    G --> H[Render PDF + QR + TTD]
    H --> I{Berhasil?}
    I -- Ya --> J[Status TERBIT + hash]
    J --> K[Kirim PDF ke warga]
    K --> L[Catat sent_at + audit]
    I -- Tidak --> M[Rollback nomor, status tetap DIPROSES]
    M --> N[Tampilkan langkah gagal ke approver]
```

| Langkah | Detail |
|:--|:---|
| 1 | Approver melihat pratinjau PDF sebelum menyetujui |
| 2 | Pejabat dipilih otomatis berdasarkan jabatan dan tanggal, dapat diubah |
| 3 | Nomor dialokasikan dalam transaksi yang sama dengan pembuatan dokumen |
| 4 | QR dan TTD ditempel sebelum hash dihitung |
| 5 | PDF dikirim ke kanal warga; `sent_at` dicatat |
| 6 | Bila pengiriman gagal, tautan unduhan 7 hari dibuat |

**Jalur alternatif:**

| Kondisi | Perilaku |
|:---|:---|
| Tidak ada pejabat aktif | Tombol setujui nonaktif + "Tidak ada pejabat aktif untuk jabatan ini" |
| TTD pejabat tidak ada | Penerbitan ditolak; arahkan ke pengaturan pejabat |
| Placeholder template tidak cocok | Penerbitan gagal dengan pesan spesifik; nomor dikembalikan |
| Dua approver menekan setujui bersamaan | Satu berhasil, satu menerima `409 INVALID_TRANSITION` |

---

## UF-10 — Mengelola Template & Nomor Surat

**Aktor:** Sekdes

```mermaid
flowchart LR
    A[Pilih layanan] --> B[Editor template]
    B --> C[Pratinjau PDF dummy]
    C --> D{Placeholder valid?}
    D -- Tidak --> E[Tampilkan placeholder bermasalah]
    E --> B
    D -- Ya --> F[Simpan versi baru]
    F --> G[Aktivasi]
    G --> H[Versi lama nonaktif otomatis]
    H --> I[Audit log]
```

| Tugas | Langkah |
|:---|:---|
| Ubah redaksi surat | Edit template → pratinjau → simpan versi baru → aktivasi |
| Tambah layanan baru | Buat layanan → definisikan field → buat template → aktifkan |
| Perbaiki nomor surat | Lihat counter → override dengan alasan → verifikasi tidak duplikat |
| Reset counter tahun baru | Reset dengan konfirmasi ganda → counter mulai dari 0 |

**Aturan:** perubahan template tidak memengaruhi dokumen yang sudah terbit. Dokumen lama tetap merujuk versi yang dipakai saat diterbitkan.

---

## UF-11 — Melabeli Pertanyaan Gagal & Melatih Model

**Aktor:** Admin Teknis

```mermaid
flowchart TD
    A[Antrean pertanyaan gagal] --> B[Pilih pertanyaan]
    B --> C[Pilih intent yang benar]
    C --> D[Sampel masuk dataset]
    D --> E{Cukup 20+ sampel baru?}
    E -- Belum --> A
    E -- Ya --> F[Latih model]
    F --> G[Lihat akurasi & macro F1]
    G --> H{Akurasi >= 85%?}
    H -- Ya --> I[Aktivasi model]
    H -- Tidak --> J[Tinjau confusion matrix]
    J --> K[Tambah sampel kelas lemah]
    K --> F
```

| Langkah | Detail |
|:--|:---|
| 1 | Antrean menampilkan teks, confidence, kanal, dan tanggal |
| 2 | Pelabelan satu klik per pertanyaan; dapat menandai "di luar cakupan" |
| 3 | Pelatihan memakai split 80/20 stratifikasi dengan seed tetap |
| 4 | Metrik ditampilkan per kelas beserta confusion matrix |
| 5 | Aktivasi ditolak bila akurasi < 85% tanpa catatan alasan |
| 6 | Rollback ke model sebelumnya tersedia dalam satu aksi |

**Ritme:** minimal sekali sebulan, atau segera setelah 50 pertanyaan gagal terkumpul.

---

## UF-12 — Mengaudit & Menyusun Laporan

**Aktor:** Sekdes

```mermaid
flowchart LR
    A[Audit log] --> B[Filter aktor/aksi/tanggal]
    B --> C[Tinjau anomali]
    C --> D[Tindak lanjut bila perlu]
    A --> E[Laporan bulanan]
    E --> F[Ringkasan per layanan & status]
    F --> G[Ekspor CSV]
    G --> H[Bahan rapat desa / Bab IV]
```

| Yang diperiksa | Frekuensi | Indikator anomali |
|:---|:---|:---|
| Penerbitan di luar jam kerja | Mingguan | Penerbitan pukul 02.00 |
| Penolakan dengan alasan seragam | Bulanan | Satu alasan dipakai > 10 kali |
| Override nomor surat | Setiap kejadian | Lebih dari 2 kali sebulan |
| Akses akun dari IP baru | Mingguan | Login dari luar Indonesia |
| Pemindaian QR berlebihan | Bulanan | Satu dokumen dipindai > 100 kali |

**Keluaran laporan bulanan:** jumlah pengajuan per layanan, per status, rata-rata waktu proses, tingkat penolakan beserta alasan terbanyak, skor kepuasan, dan akurasi model aktif.

---

## Matriks Transisi Status

| Dari | Aksi | Ke | Aktor yang berhak |
|:---|:---|:---|:---|
| — | Buat pengajuan | `DRAFT` | Warga |
| `DRAFT` | Submit | `MENUNGGU_VERIFIKASI` | Warga |
| `DRAFT` | Batalkan | `DIBATALKAN` | Warga |
| `MENUNGGU_VERIFIKASI` | Teruskan | `DIPROSES` | Operator |
| `MENUNGGU_VERIFIKASI` | Tolak | `DITOLAK` | Operator |
| `MENUNGGU_VERIFIKASI` | Batalkan | `DIBATALKAN` | Warga |
| `DIPROSES` | Setujui & terbitkan | `TERBIT` | Sekdes, Kepala Desa |
| `DIPROSES` | Tolak | `DITOLAK` | Operator, Sekdes |
| `DIPROSES` | Batalkan | `DIBATALKAN` | Sekdes |
| `TERBIT` | Cabut dokumen | `DIBATALKAN` (dokumen) | Kepala Desa |

Transisi di luar tabel ini ditolak dengan `409 INVALID_TRANSITION`.
