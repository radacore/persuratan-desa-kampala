# API.md: SILADESA

## Authentication & Authorization

SILADESA memakai **session cookie** untuk panel admin dan **session percakapan** untuk warga. Tidak ada JWT dan tidak ada token di `localStorage`.

**Cookie admin:**

```
Set-Cookie: siladesa_session=<signed-session-id>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=1800
```

**Header wajib untuk endpoint admin yang mengubah data:**

```
X-CSRF-Token: <token-dari-meta-tag-atau-response-login>
```

**Header wajib untuk endpoint warga pada kanal web:**

```
X-Chat-Session: <session_id-dari-response-pertama>
```

**Authorization Levels:**

| Level | Keterangan |
|:---|:---|
| **Public** | Tanpa autentikasi. Hanya endpoint baca dan pembuatan pengajuan. |
| **Session** | Memerlukan `X-Chat-Session` valid yang cocok dengan pemilik `ticket_no`. |
| **Operator** | Peran `operator`, `sekdes`, `kepala_desa`, `admin_teknis`. |
| **Approver** | Peran `sekdes`, `kepala_desa`. |
| **Admin** | Peran `admin_teknis` (pengguna & sistem) atau `sekdes` (katalog & template). |
| **Signer** | Peran `kepala_desa` atau `admin_teknis` untuk berkas tanda tangan. |

Matriks izin lengkap ada pada PRD § System Scope & User Roles.

## Standard Response & Pagination Formats

**Success Response (200 OK):**

```json
{
  "success": true,
  "data": { },
  "message": "Operasi berhasil"
}
```

**Error Response (4xx/5xx):**

```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "message": "Data pemohon tidak valid",
  "details": [
    { "field": "nik", "message": "NIK harus 16 digit dan diawali 7304" }
  ]
}
```

**Error codes:**

| Code | HTTP | Keterangan |
|:---|:---|:---|
| `VALIDATION_ERROR` | 422 | Input tidak lolos validasi |
| `UNAUTHORIZED` | 401 | Sesi tidak ada atau kedaluwarsa |
| `FORBIDDEN` | 403 | Peran tidak mencukupi |
| `NOT_FOUND` | 404 | Resource tidak ditemukan |
| `CONFLICT` | 409 | Duplikasi atau transisi status tidak sah |
| `INVALID_TRANSITION` | 409 | Perubahan status tidak diizinkan |
| `RATE_LIMITED` | 429 | Melewati batas permintaan |
| `SERVICE_UNAVAILABLE` | 503 | Model NLP belum aktif atau dependensi gagal |
| `INTERNAL_ERROR` | 500 | Kesalahan tak terduga |

**Pagination Format:**

```json
{
  "success": true,
  "data": [],
  "meta": {
    "page": 1,
    "per_page": 25,
    "total": 132,
    "total_pages": 6
  }
}
```

**Rate limits:**

| Endpoint | Limit |
|:---|:---|
| `POST /api/v1/chat/messages` | 20/menit per sesi |
| `POST /api/v1/admin/auth/login` | 5/menit per IP |
| `GET /api/v1/verify/{qr_token}` | 60/menit per IP |
| Endpoint admin lain | 120/menit per sesi |

## Public API Endpoints

### Chat — Web Widget

#### Kirim Pesan Chat

Memproses satu pesan dari web widget melalui pipeline NLP dan mengembalikan balasan bot.

```
POST /api/v1/chat/messages
```

**Auth:** Public

**Request:**

```json
{
  "channel": "web",
  "external_user_id": "b7f3c1a2e8d94f0b",
  "message": "syarat bikin surat keterangan usaha apa aja?",
  "message_id": "msg_01J9F2K3M4"
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "session_id": 4821,
    "reply": "Untuk Surat Keterangan Usaha, Bapak/Ibu perlu menyiapkan:\n1. Fotokopi KTP\n2. Fotokopi KK\n3. Surat pengantar dari dusun\n\nApakah ingin saya bantu buatkan sekarang?",
    "intent": "INFO_USAHA",
    "confidence": 0.9123,
    "state": "INFO",
    "quick_replies": [
      { "label": "Ya, buatkan", "value": "ajukan usaha" },
      { "label": "Lihat layanan lain", "value": "menu" }
    ],
    "needs_clarification": false
  },
  "message": "Pesan diproses"
}
```

**Response (200 OK — perlu klarifikasi, `confidence` 0,40–0,65):**

```json
{
  "success": true,
  "data": {
    "session_id": 4821,
    "reply": "Maaf, saya belum yakin maksudnya. Mungkin salah satu dari ini?",
    "intent": null,
    "confidence": 0.5231,
    "state": "MENU",
    "quick_replies": [
      { "label": "Surat Keterangan Domisili", "value": "domisili" },
      { "label": "Surat Keterangan Tidak Mampu", "value": "sktm" },
      { "label": "Surat Keterangan Usaha", "value": "usaha" }
    ],
    "needs_clarification": true
  },
  "message": "Perlu klarifikasi"
}
```

**Errors:** `422 VALIDATION_ERROR` (pesan kosong atau > 1.000 karakter), `429 RATE_LIMITED`, `503 SERVICE_UNAVAILABLE` (model belum aktif).

#### Riwayat Chat

```
GET /api/v1/chat/history?session_id=4821&limit=50
```

**Auth:** Public (session cookie `X-Chat-Session` wajib cocok dengan `session_id`)

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    { "arah": "in", "isi": "halo", "created_at": "2026-11-03T09:12:44+08:00" },
    { "arah": "out", "isi": "Selamat datang di layanan Desa Kampala...", "created_at": "2026-11-03T09:12:45+08:00" }
  ],
  "message": "Riwayat percakapan"
}
```

### Layanan & FAQ

#### Daftar Layanan

```
GET /api/v1/services?fase=1
```

**Auth:** Public

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "kode": "DOM",
      "nama": "Surat Keterangan Domisili",
      "deskripsi": "Surat keterangan tempat tinggal/domisili warga Desa Kampala.",
      "sla_hari": 1,
      "biaya": 0,
      "urutan": 1,
      "persyaratan": [
        "Fotokopi KTP",
        "Fotokopi KK",
        "Surat pengantar dari kepala dusun"
      ]
    },
    {
      "kode": "SKTM",
      "nama": "Surat Keterangan Tidak Mampu",
      "deskripsi": "Surat keterangan untuk keperluan bantuan sosial, beasiswa, atau keringanan biaya.",
      "sla_hari": 1,
      "biaya": 0,
      "urutan": 2,
      "persyaratan": [
        "Fotokopi KTP",
        "Fotokopi KK",
        "Surat pengantar dari kepala dusun"
      ]
    }
  ],
  "message": "Daftar layanan aktif"
}
```

#### Detail Layanan

```
GET /api/v1/services/{kode}
```

**Auth:** Public

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "kode": "USH",
    "nama": "Surat Keterangan Usaha",
    "deskripsi": "Surat keterangan kepemilikan usaha bagi warga Desa Kampala.",
    "persyaratan": "1. Fotokopi KTP\n2. Fotokopi KK\n3. Surat pengantar dari kepala dusun",
    "alur": "Ajukan via chatbot → verifikasi operator → tanda tangan Kepala Desa → dokumen dikirim",
    "sla_hari": 1,
    "biaya": 0,
    "fields": [
      { "nama_field": "nama_usaha", "label": "Nama usaha", "tipe": "text", "wajib": true, "urutan": 1 },
      { "nama_field": "jenis_usaha", "label": "Jenis usaha", "tipe": "enum", "wajib": true, "urutan": 2, "opsi": ["Perdagangan", "Jasa", "Pertanian", "Peternakan", "Perikanan", "Lainnya"] },
      { "nama_field": "alamat_usaha", "label": "Alamat usaha", "tipe": "textarea", "wajib": true, "urutan": 3 },
      { "nama_field": "lama_usaha", "label": "Lama usaha berjalan (tahun)", "tipe": "number", "wajib": true, "urutan": 4 }
    ]
  },
  "message": "Detail layanan"
}
```

**Errors:** `404 NOT_FOUND`

#### Daftar FAQ

```
GET /api/v1/faqs
```

**Auth:** Public

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    { "id": 3, "pertanyaan": "Jam layanan kantor desa?", "jawaban": "Senin–Jumat, 08.00–15.00 WITA." },
    { "id": 7, "pertanyaan": "Berapa biaya surat?", "jawaban": "Seluruh layanan administrasi Desa Kampala tidak dipungut biaya." }
  ],
  "message": "Daftar FAQ aktif"
}
```

### Pengajuan Surat

#### Mulai Pengajuan

Membuat tiket `DRAFT` dan mengembalikan field pertama yang harus diisi.

```
POST /api/v1/applications
```

**Auth:** Public (wajib menyertakan `X-Chat-Session`)

**Request:**

```json
{
  "service_kode": "SKTM",
  "session_id": 4821,
  "consent": true,
  "consent_version": "2026-10-01"
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": {
    "ticket_no": "APP-2026-000128",
    "status": "DRAFT",
    "service": { "kode": "SKTM", "nama": "Surat Keterangan Tidak Mampu" },
    "next_field": {
      "nama_field": "nik",
      "label": "Nomor Induk Kependudukan (NIK)",
      "tipe": "text",
      "wajib": true,
      "urutan": 1
    },
    "progress": { "terisi": 0, "total": 9 }
  },
  "message": "Pengajuan dibuat"
}
```

**Errors:** `403 FORBIDDEN` (consent belum diberikan), `409 CONFLICT` (lebih dari tiga pengajuan aktif), `422 VALIDATION_ERROR`.

**Response (409 CONFLICT):**

```json
{
  "success": false,
  "error": "CONFLICT",
  "message": "Bapak/Ibu masih memiliki 3 pengajuan aktif",
  "details": [
    { "ticket_no": "APP-2026-000121", "status": "MENUNGGU_VERIFIKASI" },
    { "ticket_no": "APP-2026-000124", "status": "DIPROSES" },
    { "ticket_no": "APP-2026-000126", "status": "DRAFT" }
  ]
}
```

#### Isi / Ubah Field Pengajuan

```
PATCH /api/v1/applications/{ticket_no}
```

**Auth:** Session

**Request:**

```json
{
  "field": "nik",
  "value": "7304091203940001"
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "ticket_no": "APP-2026-000128",
    "status": "DRAFT",
    "accepted": { "field": "nik", "value": "7304091203940001" },
    "next_field": {
      "nama_field": "nama_lengkap",
      "label": "Nama lengkap sesuai KTP",
      "tipe": "text",
      "wajib": true,
      "urutan": 2
    },
    "progress": { "terisi": 1, "total": 9 }
  },
  "message": "Data diterima"
}
```

**Response (422 VALIDATION_ERROR):**

```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "message": "NIK tidak valid",
  "details": [
    { "field": "nik", "message": "NIK harus 16 digit dan diawali 7304" }
  ]
}
```

#### Ringkasan Sebelum Submit

```
GET /api/v1/applications/{ticket_no}/summary
```

**Auth:** Session

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "ticket_no": "APP-2026-000128",
    "service": "Surat Keterangan Tidak Mampu",
    "fields": [
      { "label": "NIK", "value": "************0001", "nama_field": "nik" },
      { "label": "Nama lengkap", "value": "Ahmad Fauzi", "nama_field": "nama_lengkap" },
      { "label": "Dusun", "value": "Buntulu", "nama_field": "dusun" },
      { "label": "Keperluan", "value": "Pengajuan beasiswa anak", "nama_field": "keperluan" }
    ],
    "lengkap": true,
    "field_kurang": []
  },
  "message": "Ringkasan pengajuan"
}
```

#### Submit Pengajuan

```
POST /api/v1/applications/{ticket_no}/submit
```

**Auth:** Session

**Request:**

```json
{ "confirm": true }
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "ticket_no": "APP-2026-000128",
    "status": "MENUNGGU_VERIFIKASI",
    "estimasi": "1 hari kerja",
    "pesan": "Pengajuan Bapak/Ibu sudah kami terima dan akan diverifikasi petugas."
  },
  "message": "Pengajuan terkirim"
}
```

**Errors:** `409 INVALID_TRANSITION` (status bukan `DRAFT`), `422 VALIDATION_ERROR` (masih ada field wajib kosong).

#### Lacak Status

```
GET /api/v1/applications/{ticket_no}
```

**Auth:** Session

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "ticket_no": "APP-2026-000128",
    "service": { "kode": "SKTM", "nama": "Surat Keterangan Tidak Mampu" },
    "status": "TERBIT",
    "rejected_reason": null,
    "created_at": "2026-11-03T09:20:11+08:00",
    "updated_at": "2026-11-03T13:41:02+08:00",
    "document": {
      "nomor_surat": "128/DKP/XI/2026",
      "issued_at": "2026-11-03T13:41:02+08:00",
      "download_url": "/d/eyJ0aWNrZXQiOiJBUFAtMjAyNi0wMDAxMjgifQ.7f3a1c"
    },
    "timeline": [
      { "ke_status": "DRAFT", "aktor_role": "warga", "created_at": "2026-11-03T09:20:11+08:00" },
      { "ke_status": "MENUNGGU_VERIFIKASI", "aktor_role": "warga", "created_at": "2026-11-03T09:22:35+08:00" },
      { "ke_status": "DIPROSES", "aktor_role": "operator", "created_at": "2026-11-03T10:02:19+08:00" },
      { "ke_status": "TERBIT", "aktor_role": "kepala_desa", "created_at": "2026-11-03T13:41:02+08:00" }
    ]
  },
  "message": "Status pengajuan"
}
```

#### Batalkan Pengajuan

```
POST /api/v1/applications/{ticket_no}/cancel
```

**Auth:** Session

**Request:**

```json
{ "alasan": "Salah pilih jenis surat" }
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": { "ticket_no": "APP-2026-000128", "status": "DIBATALKAN" },
  "message": "Pengajuan dibatalkan"
}
```

**Errors:** `409 INVALID_TRANSITION` (status sudah `DIPROSES` atau `TERBIT`).

#### Unduh Dokumen

```
GET /d/{signed_token}
```

**Auth:** Public (token bertanda tangan, berlaku 7 hari)

**Response (200 OK):** `application/pdf` dengan `Content-Disposition: attachment; filename="SKTM-128-DKP-XI-2026.pdf"`

**Errors:** `403 FORBIDDEN` (token kedaluwarsa atau tanda tangan tidak cocok), `404 NOT_FOUND` (dokumen belum terbit atau dicabut).

### Verifikasi Dokumen

#### Verifikasi via QR (JSON)

```
GET /api/v1/verify/{qr_token}
```

**Auth:** Public

**Response (200 OK — sah):**

```json
{
  "success": true,
  "data": {
    "status": "SAH",
    "jenis_surat": "Surat Keterangan Tidak Mampu",
    "nomor_surat": "128/DKP/XI/2026",
    "tanggal_terbit": "2026-11-03",
    "nama": "Ahmad F***",
    "nik": "************0001",
    "dusun": "Buntulu",
    "penandatangan": "Hj. Rosmiati",
    "jabatan": "Kepala Desa Kampala",
    "sha256": "9f2c1e7b4a8d3f6051c2b9e4d7a8f1c3b6e9d2a5f8c1b4e7d0a3f6c9b2e5d8a1",
    "diverifikasi_pada": "2026-11-04T08:15:22+08:00"
  },
  "message": "Dokumen sah"
}
```

**Response (200 OK — dicabut):**

```json
{
  "success": true,
  "data": {
    "status": "DIBATALKAN",
    "jenis_surat": "Surat Keterangan Usaha",
    "nomor_surat": "119/DKP/XI/2026",
    "tanggal_terbit": "2026-11-01",
    "alasan_pencabutan": "Data usaha tidak sesuai hasil verifikasi lapangan",
    "dicabut_pada": "2026-11-05T11:00:00+08:00"
  },
  "message": "Dokumen telah dicabut"
}
```

**Response (404 NOT_FOUND):**

```json
{
  "success": false,
  "error": "NOT_FOUND",
  "message": "Dokumen tidak ditemukan. Pastikan QR Code dipindai dengan benar."
}
```

**Catatan:** endpoint ini **tidak pernah** mengembalikan NIK lengkap, alamat lengkap, atau berkas PDF (FR-31).

#### Halaman Verifikasi (HTML)

```
GET /v/{qr_token}
```

**Auth:** Public — mengembalikan halaman HTML server-rendered dengan data yang sama seperti endpoint JSON di atas, ditambah tombol "Laporkan kejanggalan" yang membuka tautan WhatsApp desa.

### Umpan Balik

#### Kirim Penilaian

```
POST /api/v1/feedback
```

**Auth:** Public

**Request:**

```json
{
  "ticket_no": "APP-2026-000128",
  "instrumen": "likert",
  "skor": 5,
  "komentar": "Cepat dan mudah, tidak perlu datang ke kantor."
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 87, "skor": 5 },
  "message": "Terima kasih atas penilaiannya"
}
```

### Webhook Kanal

#### Webhook Telegram

```
POST /webhooks/telegram
```

**Auth:** Header `X-Telegram-Bot-Api-Secret-Token` harus cocok dengan nilai konfigurasi.

**Response (200 OK):** `{"ok": true}` — selalu 200 agar Telegram tidak mengulang pengiriman; kesalahan dicatat ke log.

#### Webhook WhatsApp (Fonnte)

```
POST /webhooks/fonnte
```

**Auth:** Verifikasi nilai `token` pada body terhadap `FONNTE_WEBHOOK_TOKEN`.

**Request (contoh payload gateway):**

```json
{
  "device": "6281234567890",
  "sender": "6285212345678",
  "message": "mau bikin sktm",
  "name": "Ahmad",
  "token": "<token>"
}
```

**Response (200 OK):** `{"status": true}`

### Kesehatan Sistem

```
GET /healthz
```

**Auth:** Public

**Response (200 OK):**

```json
{
  "status": "ok",
  "database": "ok",
  "model": "2026.11.1",
  "version": "1.0.0",
  "time": "2026-11-04T08:00:00+08:00"
}
```

**Response (503 Service Unavailable):** salah satu komponen `"error"`.

## Admin API Endpoints

### Authentication

#### Login Admin

```
POST /api/v1/admin/auth/login
```

**Auth:** Public

**Request:**

```json
{ "email": "operator@desakampala.id", "password": "••••••••" }
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 4,
    "nama": "Bahtiar B.",
    "email": "operator@desakampala.id",
    "role": "operator",
    "must_change_password": false,
    "csrf_token": "Q2hhbmdlVGhpc1Rva2Vu"
  },
  "message": "Login berhasil"
}
```

**Errors:** `401 UNAUTHORIZED`, `429 RATE_LIMITED` (akun terkunci 15 menit setelah 5 kegagalan).

#### Logout

```
POST /api/v1/admin/auth/logout
```

**Auth:** Any admin

**Response (200 OK):** `{"success": true, "data": null, "message": "Logout berhasil"}`

#### Profil Admin Aktif

```
GET /api/v1/admin/auth/me
```

**Auth:** Any admin

**Response (200 OK):**

```json
{
  "success": true,
  "data": { "id": 4, "nama": "Bahtiar B.", "role": "operator", "permissions": ["application.read", "application.review", "faq.manage"] },
  "message": "Profil admin"
}
```

### Dashboard

#### Ringkasan Operasional

```
GET /api/v1/admin/dashboard
```

**Auth:** Any admin

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "hari_ini": { "pengajuan_baru": 6, "terbit": 4, "ditolak": 1 },
    "antrean": { "menunggu_verifikasi": 9, "diproses": 3, "eskalasi": 2 },
    "model": { "versi": "2026.11.1", "akurasi": 0.8734, "macro_f1": 0.8412, "aktif_sejak": "2026-11-01" },
    "tren_7_hari": [
      { "tanggal": "2026-10-29", "pengajuan": 3, "terbit": 2 },
      { "tanggal": "2026-10-30", "pengajuan": 5, "terbit": 4 }
    ]
  },
  "message": "Ringkasan dashboard"
}
```

### Manajemen Pengajuan

#### Daftar Pengajuan

```
GET /api/v1/admin/applications?status=MENUNGGU_VERIFIKASI&service=SKTM&dusun=Buntulu&from=2026-11-01&to=2026-11-30&q=APP-2026&page=1&per_page=25
```

**Auth:** Operator+

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "id": 128,
      "ticket_no": "APP-2026-000128",
      "nama_pemohon": "Ahmad Fauzi",
      "nik_masked": "************0001",
      "dusun": "Buntulu",
      "service": "Surat Keterangan Tidak Mampu",
      "status": "MENUNGGU_VERIFIKASI",
      "created_at": "2026-11-03T09:22:35+08:00",
      "menunggu_jam": 26
    }
  ],
  "meta": { "page": 1, "per_page": 25, "total": 9, "total_pages": 1 }
}
```

#### Detail Pengajuan

```
GET /api/v1/admin/applications/{id}
```

**Auth:** Operator+

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 128,
    "ticket_no": "APP-2026-000128",
    "status": "MENUNGGU_VERIFIKASI",
    "service": { "id": 2, "kode": "SKTM", "nama": "Surat Keterangan Tidak Mampu" },
    "citizen": {
      "nik": "7304091203940001",
      "nama_lengkap": "Ahmad Fauzi",
      "tempat_lahir": "Jeneponto",
      "tanggal_lahir": "1994-03-12",
      "jenis_kelamin": "Laki-Laki",
      "agama": "Islam",
      "status_perkawinan": "Kawin",
      "pekerjaan": "Petani",
      "alamat": "Dusun Buntulu, RT 002/RW 001",
      "dusun": "Buntulu",
      "no_hp": "085212345678"
    },
    "form_data": { "keperluan": "Pengajuan beasiswa anak", "penghasilan_per_bulan": 1500000 },
    "attachments": [
      { "id": 41, "original_filename": "ktp.jpg", "mime_type": "image/jpeg", "file_size": 284112 }
    ],
    "timeline": [
      { "dari_status": null, "ke_status": "DRAFT", "aktor_role": "warga", "created_at": "2026-11-03T09:20:11+08:00" },
      { "dari_status": "DRAFT", "ke_status": "MENUNGGU_VERIFIKASI", "aktor_role": "warga", "created_at": "2026-11-03T09:22:35+08:00" }
    ],
    "catatan_operator": null
  },
  "message": "Detail pengajuan"
}
```

#### Koreksi Data Pengajuan

```
PATCH /api/v1/admin/applications/{id}
```

**Auth:** Operator+

**Request:**

```json
{
  "form_data": { "penghasilan_per_bulan": 1200000 },
  "catatan_operator": "Dikonfirmasi ulang ke pemohon via telepon"
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 128,
    "status": "MENUNGGU_VERIFIKASI",
    "diubah": [
      { "field": "penghasilan_per_bulan", "lama": 1500000, "baru": 1200000 }
    ]
  },
  "message": "Data pengajuan diperbarui"
}
```

**Errors:** `409 INVALID_TRANSITION` (status sudah `TERBIT`), `422 VALIDATION_ERROR`.

#### Setujui & Terbitkan

```
POST /api/v1/admin/applications/{id}/approve
```

**Auth:** Approver

**Request:**

```json
{
  "official_id": 1,
  "catatan": "Berkas lengkap, data sesuai KTP"
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 128,
    "ticket_no": "APP-2026-000128",
    "status": "TERBIT",
    "document": {
      "id": 88,
      "nomor_surat": "128/DKP/XI/2026",
      "sha256": "9f2c1e7b4a8d3f6051c2b9e4d7a8f1c3b6e9d2a5f8c1b4e7d0a3f6c9b2e5d8a1",
      "qr_token": "V1StGXR8Z5jdHi6BmyT3na",
      "issued_at": "2026-11-03T13:41:02+08:00",
      "sent_at": "2026-11-03T13:41:06+08:00"
    }
  },
  "message": "Dokumen diterbitkan dan dikirim ke warga"
}
```

**Errors:** `403 FORBIDDEN` (bukan approver), `409 INVALID_TRANSITION` (status bukan `MENUNGGU_VERIFIKASI`/`DIPROSES`), `422 VALIDATION_ERROR` (pejabat tidak aktif).

**Catatan:** bila generate PDF atau pengiriman gagal, status tetap `DIPROSES` dan respons menjadi:

```json
{
  "success": false,
  "error": "INTERNAL_ERROR",
  "message": "Dokumen gagal dihasilkan; pengajuan tetap berstatus DIPROSES",
  "details": [{ "langkah": "pdf_generation", "pesan": "Template placeholder {{nama_usaha}} tidak ditemukan" }]
}
```

#### Tolak Pengajuan

```
POST /api/v1/admin/applications/{id}/reject
```

**Auth:** Operator+

**Request:**

```json
{ "alasan": "Surat pengantar dari kepala dusun belum dilampirkan" }
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": { "id": 128, "status": "DITOLAK", "rejected_reason": "Surat pengantar dari kepala dusun belum dilampirkan" },
  "message": "Pengajuan ditolak dan warga telah diberi tahu"
}
```

### Manajemen Katalog Layanan

#### Daftar & Buat Layanan

```
GET  /api/v1/admin/services
POST /api/v1/admin/services
```

**Auth:** Sekdes+

**Request (POST):**

```json
{
  "kode": "DOM",
  "nama": "Surat Keterangan Domisili",
  "deskripsi": "Surat keterangan tempat tinggal warga Desa Kampala.",
  "persyaratan": "1. Fotokopi KTP\n2. Fotokopi KK\n3. Surat pengantar dari kepala dusun",
  "alur": "Ajukan via chatbot → verifikasi operator → tanda tangan Kepala Desa → dokumen dikirim",
  "sla_hari": 1,
  "biaya": 0,
  "urutan": 1,
  "aktif": true,
  "fase": 1
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 1, "kode": "DOM", "nama": "Surat Keterangan Domisili", "aktif": true },
  "message": "Layanan dibuat"
}
```

**Errors:** `409 CONFLICT` (kode sudah dipakai).

#### Ubah & Nonaktifkan Layanan

```
PATCH  /api/v1/admin/services/{id}
DELETE /api/v1/admin/services/{id}
```

**Auth:** Sekdes+

**Catatan:** `DELETE` melakukan soft delete (`aktif = false`) bila layanan sudah memiliki pengajuan; hanya layanan tanpa pengajuan yang dihapus fisik.

#### Field Layanan

```
GET    /api/v1/admin/services/{id}/fields
POST   /api/v1/admin/services/{id}/fields
PATCH  /api/v1/admin/services/{id}/fields/{field_id}
DELETE /api/v1/admin/services/{id}/fields/{field_id}
```

**Auth:** Sekdes+

**Request (POST):**

```json
{
  "nama_field": "keperluan",
  "label": "Keperluan pengajuan",
  "tipe": "textarea",
  "wajib": true,
  "urutan": 8,
  "validasi": "max:300"
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 57, "nama_field": "keperluan", "urutan": 8 },
  "message": "Field ditambahkan"
}
```

### Manajemen FAQ

```
GET    /api/v1/admin/faqs?aktif=true&service_id=2
POST   /api/v1/admin/faqs
PATCH  /api/v1/admin/faqs/{id}
DELETE /api/v1/admin/faqs/{id}
```

**Auth:** Sekdes+ (FR-44)

**Request (POST):**

```json
{
  "service_id": null,
  "pertanyaan": "Jam layanan kantor desa?",
  "jawaban": "Senin–Jumat, 08.00–15.00 WITA. Sabtu, Minggu, dan hari libur nasional tutup.",
  "kategori": "operasional",
  "urutan": 1,
  "aktif": true
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": {
    "id": 3,
    "service_id": null,
    "pertanyaan": "Jam layanan kantor desa?",
    "kategori": "operasional",
    "urutan": 1,
    "aktif": true,
    "updated_by": 6
  },
  "message": "FAQ dibuat"
}
```

**Response (200 OK — ubah):** mengembalikan objek yang sama dengan `updated_at` baru.

**Errors:** `404 NOT_FOUND`, `409 CONFLICT` (pertanyaan identik sudah ada pada `service_id` yang sama), `422 VALIDATION_ERROR` (jawaban < 10 karakter).

**Catatan:** `DELETE` melakukan soft delete (`aktif = false`) agar intent `faq` yang merujuknya tidak menggantung. Menghapus FAQ tidak menghapus `intent` terkait; Admin Teknis yang menonaktifkannya secara terpisah.

### Manajemen Template Surat

```
GET  /api/v1/admin/templates?service_id=2
POST /api/v1/admin/templates
GET  /api/v1/admin/templates/{id}
POST /api/v1/admin/templates/{id}/activate
POST /api/v1/admin/templates/preview
```

**Auth:** Sekdes+

**Request (POST):**

```json
{
  "service_id": 2,
  "nama": "SKTM v1",
  "konten_html": "<h3>SURAT KETERANGAN TIDAK MAMPU</h3><p>Nomor: {{nomor_surat}}</p><p>Yang bertanda tangan di bawah ini...</p>"
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 5, "service_id": 2, "versi": 1, "aktif": false },
  "message": "Template dibuat sebagai versi 1 (belum aktif)"
}
```

**Response (422 VALIDATION_ERROR — placeholder tidak dikenal):**

```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "message": "Template memuat placeholder yang tidak dikenal",
  "details": [{ "placeholder": "{{nama_usaha}}", "message": "Tidak ada pada skema field layanan SKTM" }]
}
```

**Response (200 OK — pratinjau):** `application/pdf` dengan data dummy.

### Manajemen Pejabat & Tanda Tangan

```
GET   /api/v1/admin/officials
POST  /api/v1/admin/officials
PATCH /api/v1/admin/officials/{id}
POST  /api/v1/admin/officials/{id}/signature
```

**Auth:** Kepala Desa / Admin Teknis

**Request (POST):**

```json
{
  "nama": "Hj. Rosmiati",
  "jabatan": "kepala_desa",
  "nip": "197805122006042001",
  "berlaku_mulai": "2026-01-01",
  "berlaku_sampai": "2031-12-31",
  "aktif": true
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 1, "nama": "Hj. Rosmiati", "jabatan": "kepala_desa", "aktif": true },
  "message": "Pejabat dibuat"
}
```

**Unggah tanda tangan:** `multipart/form-data` dengan field `file` (PNG/JPG, maks 2 MB).

```json
{
  "success": true,
  "data": { "id": 1, "ttd_path": "storage/officials/ttd_1_2026.png", "ukuran": 48211 },
  "message": "Tanda tangan diunggah"
}
```

### Manajemen Nomor Surat

```
GET  /api/v1/admin/number-counters?tahun=2026
POST /api/v1/admin/number-counters/{id}/override
POST /api/v1/admin/number-counters/{id}/reset
```

**Auth:** Sekdes+

**Response (200 OK — daftar):**

```json
{
  "success": true,
  "data": [
    { "id": 1, "service_kode": "DOM", "tahun": 2026, "seq_terakhir": 41 },
    { "id": 2, "service_kode": "SKTM", "tahun": 2026, "seq_terakhir": 128 },
    { "id": 3, "service_kode": "USH", "tahun": 2026, "seq_terakhir": 17 },
    { "id": 4, "service_kode": "PGG", "tahun": 2026, "seq_terakhir": 63 }
  ],
  "message": "Counter nomor surat"
}
```

**Request (override):**

```json
{ "seq": 130, "alasan": "Melanjutkan penomoran manual bulan lalu" }
```

**Errors:** `409 CONFLICT` (nomor sudah terpakai), `422 VALIDATION_ERROR` (alasan < 10 karakter).

### Manajemen Intent & Dataset

```
GET   /api/v1/admin/intents
POST  /api/v1/admin/intents
PATCH /api/v1/admin/intents/{id}
GET   /api/v1/admin/training-samples?intent=INFO_USAHA&split=train
POST  /api/v1/admin/training-samples
POST  /api/v1/admin/training-samples/import
GET   /api/v1/admin/unanswered
```

**Auth:** Admin Teknis

**Request (tambah sampel):**

```json
{
  "intent_kode": "INFO_USAHA",
  "teks": "syarat surat usaha apa aja ya pak",
  "sumber": "manual",
  "split": "train"
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 912, "intent_kode": "INFO_USAHA", "split": "train" },
  "message": "Sampel ditambahkan"
}
```

**Impor CSV:** `multipart/form-data` field `file`. Header wajib `teks,intent`.

```json
{
  "success": true,
  "data": {
    "diterima": 240,
    "ditolak": 3,
    "errors": [
      { "baris": 17, "pesan": "Intent 'INFO_SUARAT' tidak dikenal" },
      { "baris": 88, "pesan": "Kolom teks kosong" }
    ]
  },
  "message": "Impor selesai dengan sebagian baris ditolak"
}
```

**Response (200 OK — antrean pertanyaan gagal):**

```json
{
  "success": true,
  "data": [
    { "id": 55, "teks": "kalau mau pindah domisili gimana", "confidence": 0.2811, "channel": "whatsapp", "created_at": "2026-11-03T10:11:00+08:00", "sudah_dilabeli": false }
  ],
  "meta": { "page": 1, "per_page": 25, "total": 14, "total_pages": 1 }
}
```

### Pelatihan & Aktivasi Model

#### Latih Model

```
POST /api/v1/admin/models/train
```

**Auth:** Admin Teknis

**Request:**

```json
{
  "algoritma": "tfidf_linearsvc",
  "test_size": 0.2,
  "seed": 42,
  "catatan": "Retrain dengan 240 sampel baru dari antrean gagal"
}
```

**Response (202 Accepted):**

```json
{
  "success": true,
  "data": { "job_id": "train-20261104-081500", "status": "berjalan" },
  "message": "Pelatihan dimulai"
}
```

**Response (200 OK — selesai):**

```json
{
  "success": true,
  "data": {
    "id": 7,
    "versi": "2026.11.2",
    "algoritma": "tfidf_linearsvc",
    "akurasi": 0.8842,
    "macro_f1": 0.8521,
    "jumlah_train": 742,
    "jumlah_test": 186,
    "status": "kandidat"
  },
  "message": "Model kandidat siap dievaluasi"
}
```

**Errors:** `422 VALIDATION_ERROR` (sampel < 40 per intent).

#### Daftar & Aktivasi Model

```
GET  /api/v1/admin/models
POST /api/v1/admin/models/{id}/activate
```

**Auth:** Admin Teknis

**Response (200 OK — aktivasi):**

```json
{
  "success": true,
  "data": {
    "id": 7,
    "versi": "2026.11.2",
    "status": "aktif",
    "model_sebelumnya": { "id": 6, "versi": "2026.11.1", "status": "arsip" }
  },
  "message": "Model diaktifkan"
}
```

**Errors:** `422 VALIDATION_ERROR` (akurasi < 0,85 tanpa `catatan`), `409 CONFLICT` (model sudah aktif).

#### Metrik Model

```
GET /api/v1/admin/models/{id}/metrics
```

**Auth:** Admin Teknis

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "versi": "2026.11.2",
    "akurasi": 0.8842,
    "macro_f1": 0.8521,
    "per_kelas": [
      { "intent_kode": "INFO_USAHA", "precision": 0.91, "recall": 0.88, "f1": 0.895, "support": 12 },
      { "intent_kode": "FALLBACK", "precision": 0.79, "recall": 0.81, "f1": 0.80, "support": 9 }
    ],
    "confusion_matrix_url": "/api/v1/admin/models/7/confusion-matrix.png"
  },
  "message": "Metrik model"
}
```

### Audit Log

```
GET /api/v1/admin/audit-logs?aksi=approve&entitas=application&from=2026-11-01&page=1
```

**Auth:** Sekdes+ / Admin Teknis

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "id": 9021,
      "admin": "Hj. Rosmiati",
      "role": "kepala_desa",
      "aksi": "approve",
      "entitas": "application",
      "entitas_id": 128,
      "perubahan": { "status": { "lama": "MENUNGGU_VERIFIKASI", "baru": "TERBIT" } },
      "created_at": "2026-11-03T13:41:02+08:00"
    }
  ],
  "meta": { "page": 1, "per_page": 25, "total": 1, "total_pages": 1 }
}
```

### Manajemen Pengguna Admin

```
GET    /api/v1/admin/users
POST   /api/v1/admin/users
PATCH  /api/v1/admin/users/{id}
DELETE /api/v1/admin/users/{id}
```

**Auth:** Admin Teknis

**Request (POST):**

```json
{ "nama": "Bahtiar B.", "email": "sekdes@desakampala.id", "role": "sekdes" }
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": { "id": 6, "email": "sekdes@desakampala.id", "role": "sekdes", "must_change_password": true },
  "message": "Akun dibuat; password awal dikirim ke email"
}
```

**Errors:** `409 CONFLICT` (menghapus akun aktif terakhir), `422 VALIDATION_ERROR`.

### Pengaturan Sistem

```
GET   /api/v1/admin/settings
PATCH /api/v1/admin/settings
```

**Auth:** Sekdes+ / Admin Teknis

**Request (PATCH):**

```json
{
  "settings": [
    { "key": "jam_layanan", "value": "Senin–Jumat, 08.00–15.00 WITA" },
    { "key": "confidence_tinggi", "value": "0.65" },
    { "key": "confidence_rendah", "value": "0.40" },
    { "key": "batas_pengajuan_aktif", "value": "3" }
  ]
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": { "diubah": 4 },
  "message": "Pengaturan disimpan"
}
```

**Errors:** `422 VALIDATION_ERROR` (nilai di luar rentang, mis. `confidence_tinggi` ≥ 1).

### Laporan

```
GET /api/v1/admin/reports/summary?bulan=2026-11
GET /api/v1/admin/reports/export?bulan=2026-11&format=csv
```

**Auth:** Sekdes+

**Response (200 OK — ringkasan):**

```json
{
  "success": true,
  "data": {
    "periode": "2026-11",
    "total_pengajuan": 87,
    "per_status": { "TERBIT": 71, "DITOLAK": 6, "DIBATALKAN": 4, "DIPROSES": 6 },
    "per_layanan": [
      { "kode": "DOM", "jumlah": 21 },
      { "kode": "SKTM", "jumlah": 38 },
      { "kode": "USH", "jumlah": 12 },
      { "kode": "PGG", "jumlah": 16 }
    ],
    "rata_rata_waktu_proses_jam": 6.4,
    "kepuasan": { "rata_rata": 4.5, "jumlah_responden": 33 }
  },
  "message": "Rekap bulanan"
}
```

**Response (200 OK — ekspor):** `text/csv; charset=utf-8` dengan header `Content-Disposition: attachment; filename="rekap-siladesa-2026-11.csv"`.
