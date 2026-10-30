# DESIGN_SYSTEM.md: SILADESA

## Design Principles

1. **Tenang dan formal, bukan ramai.** Ini layanan pemerintah desa. Warna netral mendominasi; warna aksen hanya menandai status dan aksi utama.
2. **Terbaca di HP murah dan layar retak.** Ukuran teks minimal 15 px, kontras tinggi, target sentuh 44 px, tanpa efek visual yang bergantung pada GPU.
3. **Satu jalur yang jelas per layar.** Setiap halaman punya satu aksi utama yang terlihat; aksi sekunder diredupkan.
4. **Status harus terbaca dalam satu pandangan.** Warga dan operator harus tahu "di mana dokumen saya" tanpa membaca kalimat panjang.
5. **Tidak menakutkan.** Bahasa manusia, bukan bahasa formulir. Kesalahan dijelaskan beserta cara memperbaikinya.

## Brand Identity

**Nama:** SILADESA — Sistem Layanan Administrasi Desa.

**Positioning:** Infrastruktur layanan desa yang bekerja diam-diam. Bukan startup, bukan aplikasi konsumen. Nada visual: **institusional tetapi hangat**.

**Logo:** mark sederhana berupa siluet atap rumah desa yang dibentuk dari dua garis yang bertemu, di dalam lingkaran penuh. Dua warna: hijau tua dan emas. Tanpa gradien, tanpa bayangan.

| Elemen | Aturan |
|:---|:---|
| Logo utama | Mark + wordmark "SILADESA" dalam Plus Jakarta Sans Bold |
| Logo sekunder | Mark saja, untuk favicon dan header sempit |
| Ukuran minimum | 24 px (mark), 120 px (mark + wordmark) |
| Ruang kosong | Minimal setinggi huruf "S" di semua sisi |
| Warna di atas foto | Versi putih penuh, tidak boleh ada outline |
| Larangan | Jangan memiringkan, memberi gradien, atau menambahkan bayangan |

## Color System

Palet dibangun dari satu warna institusional (hijau desa) dan satu aksen hangat (emas), dengan netral yang cukup untuk tabel data padat.

### Primitive tokens

| Token | Hex | HSL | Penggunaan |
|:---|:---|:---|:---|
| `green-50` | `#F1FAF6` | 156 47% 96% | Latar section sukses |
| `green-100` | `#D9F0E7` | 156 44% 89% | Latar badge, hover halus |
| `green-300` | `#7FC7AC` | 158 39% 64% | Border fokus sekunder |
| `green-500` | `#14855F` | 160 74% 30% | Ikon aktif |
| `green-600` | `#0E6B4F` | 160 77% 24% | **Primary** — tombol utama, header |
| `green-700` | `#0A5640` | 161 79% 19% | Hover/active tombol utama |
| `gold-100` | `#FBF3D9` | 45 73% 92% | Latar peringatan ringan |
| `gold-600` | `#A67C00` | 44 100% 33% | Aksen, garis kop surat di UI |
| `slate-900` | `#0F172A` | 222 47% 11% | Teks utama |
| `slate-700` | `#334155` | 215 25% 27% | Teks sekunder kuat |
| `slate-500` | `#64748B` | 215 16% 47% | Teks tersier, placeholder |
| `slate-300` | `#CBD5E1` | 213 27% 84% | Border input |
| `slate-200` | `#E2E8F0` | 214 32% 91% | Border kartu, pemisah |
| `slate-100` | `#F1F5F9` | 210 40% 96% | Latar halaman |
| `white` | `#FFFFFF` | — | Permukaan kartu |
| `red-600` | `#B42318` | 4 74% 40% | Bahaya, tolak |
| `red-50` | `#FEF3F2` | 6 86% 97% | Latar error |
| `blue-600` | `#1D4ED8` | 224 76% 48% | Info, tautan |
| `amber-600` | `#B45309` | 32 95% 30% | Menunggu |

### Semantic tokens

| Token | Nilai | Penggunaan |
|:---|:---|:---|
| `--color-primary` | `green-600` | Tombol utama, header admin, tautan aktif |
| `--color-primary-hover` | `green-700` | Hover/active |
| `--color-on-primary` | `white` | Teks di atas primary |
| `--color-surface` | `white` | Kartu, panel |
| `--color-canvas` | `slate-100` | Latar halaman admin |
| `--color-border` | `slate-200` | Pemisah, border kartu |
| `--color-border-strong` | `slate-300` | Border input |
| `--color-text` | `slate-900` | Teks utama |
| `--color-text-muted` | `slate-500` | Teks pendukung |
| `--color-focus` | `green-500` | Ring fokus |
| `--color-success` | `#1B7F4B` | Status `TERBIT`, verifikasi `SAH` |
| `--color-warning` | `amber-600` | Status `MENUNGGU_VERIFIKASI` |
| `--color-info` | `blue-600` | Status `DIPROSES` |
| `--color-danger` | `red-600` | Status `DITOLAK`, aksi hapus |

### Warna status pengajuan

| Status | Latar | Teks | Ikon |
|:---|:---|:---|:---|
| `DRAFT` | `slate-100` | `slate-700` | `pencil` |
| `MENUNGGU_VERIFIKASI` | `#FEF6E7` | `#92400E` | `clock` |
| `DIPROSES` | `#EFF6FF` | `#1E40AF` | `loader` |
| `TERBIT` | `#ECFDF5` | `#065F46` | `check-circle` |
| `DITOLAK` | `red-50` | `#912018` | `x-circle` |
| `DIBATALKAN` | `slate-100` | `slate-500` | `slash` |

Semua kombinasi di atas memiliki rasio kontras ≥ 4,5:1 untuk teks normal (diverifikasi dengan perhitungan luminans relatif).

## Typography

**Keluarga font:**

| Peran | Font | Fallback |
|:---|:---|:---|
| UI & teks | **Plus Jakarta Sans** | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` |
| Angka tabel | Plus Jakarta Sans, `font-variant-numeric: tabular-nums` | — |
| Pratinjau dokumen | Liberation Serif | `"Times New Roman", serif` |
| Kode & token | JetBrains Mono | `ui-monospace, monospace` |

Plus Jakarta Sans dipilih karena dirancang untuk konteks Indonesia, memiliki bobot yang cukup untuk hierarki tanpa terlihat dekoratif, dan tersedia gratis.

**Skala tipe (rem, basis 16 px):**

| Token | Size | Line-height | Weight | Penggunaan |
|:---|:---|:---|:---|:---|
| `display` | 2.25 rem / 36 px | 1.15 | 700 | Judul halaman verifikasi |
| `h1` | 1.75 rem / 28 px | 1.2 | 700 | Judul halaman admin |
| `h2` | 1.375 rem / 22 px | 1.3 | 600 | Judul seksi |
| `h3` | 1.125 rem / 18 px | 1.4 | 600 | Judul kartu |
| `body` | 1 rem / 16 px | 1.6 | 400 | Teks utama |
| `body-sm` | 0.9375 rem / 15 px | 1.55 | 400 | Teks tabel, bantuan |
| `caption` | 0.8125 rem / 13 px | 1.45 | 500 | Label, metadata |
| `mono` | 0.875 rem / 14 px | 1.5 | 400 | Hash, nomor surat, token |

**Aturan:** lebar baris maksimal 72 karakter untuk teks paragraf; tidak pernah memakai lebih dari tiga ukuran berbeda dalam satu kartu.

## Spacing & Layout

**Skala spasi (basis 4 px):** `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

| Token | Nilai | Penggunaan |
|:---|:---|:---|
| `space-1` | 4 px | Jarak ikon–teks |
| `space-2` | 8 px | Padding badge |
| `space-3` | 12 px | Gap antar-field |
| `space-4` | 16 px | Padding kartu (mobile) |
| `space-6` | 24 px | Padding kartu (desktop), jarak antar-kartu |
| `space-8` | 32 px | Jarak antar-seksi |
| `space-12` | 48 px | Jarak header–konten |

**Grid & container:**

| Breakpoint | Lebar | Layout |
|:---|:---|:---|
| `< 640 px` | 100% | Satu kolom, sidebar jadi bottom sheet |
| `640–1023 px` | 100% | Satu kolom, tabel dapat di-scroll horizontal |
| `≥ 1024 px` | maks 1280 px | Sidebar 240 px + konten cair |

**Radius:** `6 px` input & badge, `10 px` tombol & kartu, `14 px` modal & panel besar, `999 px` pill.

**Elevation:** hanya tiga tingkat — `0` (datar), `1` (`0 1px 2px rgba(15,23,42,.06)`), `2` (`0 8px 24px rgba(15,23,42,.10)` untuk modal). Tidak ada bayangan berlapis.

## Component Specifications

### Tombol

| Varian | Latar | Teks | Border | Penggunaan |
|:---|:---|:---|:---|:---|
| Primary | `green-600` | white | — | Aksi utama per layar |
| Secondary | white | `slate-900` | `slate-300` | Aksi pendukung |
| Ghost | transparan | `slate-700` | — | Aksi dalam tabel |
| Danger | `red-600` | white | — | Tolak, hapus |

**Ukuran:** `sm` 32 px (tabel), `md` 40 px (default), `lg` 48 px (chat widget & verifikasi). Padding horizontal 16 px (`md`), 12 px (`sm`).

**State:** hover menggelapkan 8%, active 12%, focus ring `2 px solid green-500` dengan `offset 2 px`, disabled `opacity .5` + `cursor: not-allowed`, loading menampilkan spinner dan menonaktifkan klik.

**Aturan:** maksimal satu tombol primary per layar. Tombol destruktif selalu meminta konfirmasi.

### Input & Form

*   Tinggi 44 px (mobile) / 40 px (desktop), padding horizontal 12 px, radius 6 px, border `slate-300`.
*   Label **selalu** di atas input, 13 px, weight 500. Tidak memakai placeholder sebagai label.
*   Teks bantuan 13 px `slate-500`, maksimal satu baris.
*   Error: border `red-600`, ikon `alert-circle`, teks 13 px `red-600` di bawah input, `aria-describedby` menunjuk ke teks error.
*   Field wajib ditandai dengan teks "(wajib)", bukan hanya asterisk.
*   Fokus: border `green-500` + ring `green-100` 3 px.

### Kartu Pengajuan

```text
┌─────────────────────────────────────────────┐
│ APP-2026-000128            [MENUNGGU VERIFIKASI] │
│ Ahmad Fauzi · ************0001               │
│ Surat Keterangan Tidak Mampu · Buntulu       │
│ Diajukan 3 Nov 2026, 09.22 · 26 jam lalu     │
│                                   [Tinjau →] │
└─────────────────────────────────────────────┘
```

*   Nomor tiket memakai `mono` 14 px agar mudah dibacakan lewat telepon.
*   Badge status selalu di kanan atas, tidak pernah di tengah.
*   Tinggi kartu tetap 104 px di mobile agar daftar terasa konsisten.

### Tabel Data

*   Header: 13 px, weight 600, `slate-500`, uppercase **tidak** dipakai (sulit dibaca).
*   Baris: 15 px, tinggi 48 px, garis pemisah `slate-200` hanya di bawah.
*   Kolom angka rata kanan dengan `tabular-nums`.
*   Di bawah 768 px, tabel berubah menjadi daftar kartu — bukan scroll horizontal untuk kolom kunci.
*   Pagination: "Menampilkan 1–25 dari 132" + tombol Sebelumnya/Berikutnya, tanpa nomor halaman panjang.

### Chat Bubble (Web Widget)

| Elemen | Spesifikasi |
|:---|:---|
| Bubble bot | Latar `slate-100`, teks `slate-900`, radius 14 px dengan sudut kiri bawah 4 px |
| Bubble warga | Latar `green-600`, teks white, radius 14 px dengan sudut kanan bawah 4 px |
| Lebar maksimal | 80% lebar panel |
| Metadata waktu | 11 px `slate-500`, di bawah bubble |
| Indikator mengetik | Tiga titik animasi 1,2 detik, `prefers-reduced-motion` → teks "Sedang mengetik…" |
| Quick reply | Pill putih, border `green-300`, teks `green-700`, tinggi 36 px, dapat di-scroll horizontal |
| Panel | 380 × 600 px di desktop, full-screen di mobile, header 56 px dengan nama desa + status |

### Badge Verifikasi (Halaman Publik)

| Status | Tampilan |
|:---|:---|
| `SAH` | Blok hijau besar, ikon centang 48 px, teks "Dokumen Sah" 28 px, subteks nomor surat |
| `DIBATALKAN` | Blok merah, ikon silang, teks "Dokumen Telah Dicabut", alasan pencabutan, tanggal |
| `TIDAK DITEMUKAN` | Blok netral, ikon tanda tanya, teks "Dokumen Tidak Ditemukan", panduan memindai ulang, kontak desa |

Halaman ini harus terbaca penuh dalam satu layar 360 × 640 px tanpa scroll.

### Modal & Konfirmasi

*   Lebar maks 480 px, radius 14 px, padding 24 px.
*   Judul 18 px, deskripsi 15 px, dua tombol di kanan bawah (Batal = ghost, Aksi = primary/danger).
*   Fokus terkunci di dalam modal (`focus trap`), `Esc` menutup, klik latar menutup hanya untuk modal non-destruktif.
*   Konfirmasi destruktif menyebut objek secara eksplisit: "Tolak pengajuan APP-2026-000128?"

### Toast

Pojok kanan atas, lebar maks 360 px, durasi 5 detik, `role="status"`. Hanya untuk hasil aksi, bukan untuk error validasi (error validasi tampil inline).

## Iconography

*   Set: **Lucide** (outline, 1,5 px stroke), disalin sebagai SVG inline agar tidak menambah request.
*   Ukuran: 16 px (dalam teks), 20 px (tombol), 24 px (navigasi), 48 px (status besar).
*   Warna mengikuti `currentColor`.
*   Ikon selalu berpasangan dengan teks kecuali pada tombol ikon yang memiliki `aria-label`.
*   Tidak memakai emoji di antarmuka admin. Di chat, emoji dibatasi pada satu salam pembuka.

## Motion

| Interaksi | Durasi | Easing |
|:---|:---|:---|
| Hover tombol | 120 ms | `ease-out` |
| Buka/tutup modal | 180 ms | `cubic-bezier(.2,.8,.2,1)` |
| Transisi halaman (HTMX) | 150 ms fade | `ease-out` |
| Munculnya bubble chat | 200 ms slide-up 8 px | `ease-out` |
| Indikator mengetik | 1.200 ms loop | `ease-in-out` |

**Aturan:** semua animasi dimatikan pada `@media (prefers-reduced-motion: reduce)`. Tidak ada animasi yang menunda aksi pengguna lebih dari 200 ms. Tidak ada parallax atau animasi dekoratif.

## Accessibility

| Kriteria | Target | Implementasi |
|:---|:---|:---|
| Kontras teks | WCAG 2.1 AA (≥ 4,5:1) | Semua pasangan token diuji; teks besar ≥ 3:1 |
| Fokus keyboard | Terlihat jelas | Ring 2 px `green-500`, offset 2 px, tidak pernah `outline: none` tanpa pengganti |
| Target sentuh | ≥ 44 × 44 px | Tombol chat, quick reply, dan navigasi mobile |
| Struktur | Landmark & heading berurutan | `header`, `nav`, `main`, `footer`; satu `h1` per halaman |
| Formulir | Label eksplisit | `<label for>`, `aria-describedby` untuk bantuan/error, `aria-invalid` |
| Status dinamis | Diumumkan | `aria-live="polite"` pada area balasan chat dan toast |
| Gambar | Teks alternatif | QR memiliki `alt` berisi nomor surat, bukan token |
| Zoom | 200% tanpa kehilangan konten | Layout berbasis `rem`, tanpa tinggi tetap pada teks |
| Bahasa | Diumumkan | `<html lang="id">` |
| Waktu | Tidak ada batas waktu mendadak | Sesi chat 30 menit dengan peringatan 2 menit sebelum berakhir |

## Copy & Tone of Voice

**Prinsip:** sopan, langsung, tanpa jargon birokrasi.

| Konteks | Contoh benar | Hindari |
|:---|:---|:---|
| Salam | "Selamat datang di layanan Desa Kampala. Ada yang bisa kami bantu?" | "Silakan pilih menu yang tersedia di bawah ini." |
| Minta data | "Boleh kami tahu NIK Bapak/Ibu?" | "Input NIK:" |
| Error | "NIK harus 16 angka. Bapak/Ibu memasukkan 12 angka." | "Format tidak valid." |
| Menunggu | "Pengajuan sudah kami terima. Petugas akan memeriksa dalam 1 hari kerja." | "Status: PENDING." |
| Ditolak | "Pengajuan belum bisa kami proses karena surat pengantar dusun belum dilampirkan." | "Ditolak." |
| Verifikasi sah | "Dokumen ini sah dan diterbitkan oleh Desa Kampala." | "VALID." |

**Aturan penulisan:**

*   Sapa dengan "Bapak/Ibu", bukan "Anda" berulang kali.
*   Angka penting ditulis dengan format Indonesia: `1.500.000`, `3 Nov 2026`.
*   Jam memakai format 24 jam dengan zona WITA.
*   Tidak memakai huruf kapital semua untuk penekanan.
*   Setiap pesan error menyebut **apa yang salah** dan **apa yang harus dilakukan**.
*   Tidak menjanjikan waktu yang tidak dapat dipenuhi sistem.

## Screen Priorities

| Prioritas | Layar | Alasan |
|:---|:---|:---|
| P0 | Chat widget & WhatsApp flow | Titik sentuh utama warga |
| P0 | Halaman verifikasi `/v/{token}` | Membangun kepercayaan pada dokumen |
| P0 | Daftar & detail pengajuan admin | Inti pekerjaan operator |
| P0 | Form login admin | Gerbang keamanan |
| P1 | Dashboard | Orientasi kerja harian |
| P1 | Editor template + pratinjau PDF | Menjaga kesesuaian format surat |
| P1 | Manajemen nomor surat | Mencegah duplikasi |
| P1 | Antrean pertanyaan gagal & pelabelan | Menjaga kualitas NLP |
| P2 | Halaman model & metrik | Kebutuhan akademik dan pemeliharaan |
| P2 | Laporan & ekspor | Kebutuhan bulanan |
| P2 | Manajemen pengguna & pengaturan | Jarang diakses |

## Design Tokens (CSS)

```css
:root {
  /* Warna */
  --green-50:  #F1FAF6;
  --green-100: #D9F0E7;
  --green-300: #7FC7AC;
  --green-500: #14855F;
  --green-600: #0E6B4F;
  --green-700: #0A5640;

  --gold-100:  #FBF3D9;
  --gold-600:  #A67C00;

  --slate-900: #0F172A;
  --slate-700: #334155;
  --slate-500: #64748B;
  --slate-300: #CBD5E1;
  --slate-200: #E2E8F0;
  --slate-100: #F1F5F9;

  --red-50:    #FEF3F2;
  --red-600:   #B42318;
  --blue-600:  #1D4ED8;
  --amber-600: #B45309;

  /* Semantik */
  --color-primary:        var(--green-600);
  --color-primary-hover:  var(--green-700);
  --color-on-primary:     #FFFFFF;
  --color-surface:        #FFFFFF;
  --color-canvas:         var(--slate-100);
  --color-border:         var(--slate-200);
  --color-border-strong:  var(--slate-300);
  --color-text:           var(--slate-900);
  --color-text-muted:     var(--slate-500);
  --color-focus:          var(--green-500);
  --color-success:        #1B7F4B;
  --color-warning:        var(--amber-600);
  --color-info:           var(--blue-600);
  --color-danger:         var(--red-600);

  /* Tipografi */
  --font-sans: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-serif: "Liberation Serif", "Times New Roman", serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  --text-display: 2.25rem;
  --text-h1: 1.75rem;
  --text-h2: 1.375rem;
  --text-h3: 1.125rem;
  --text-body: 1rem;
  --text-sm: 0.9375rem;
  --text-caption: 0.8125rem;
  --text-mono: 0.875rem;

  /* Spasi */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;

  /* Bentuk */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-pill: 999px;

  /* Elevasi */
  --shadow-1: 0 1px 2px rgba(15, 23, 42, .06);
  --shadow-2: 0 8px 24px rgba(15, 23, 42, .10);

  /* Gerak */
  --motion-fast: 120ms;
  --motion-base: 180ms;
  --motion-ease: cubic-bezier(.2, .8, .2, 1);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Tailwind Configuration

```js
// tailwind.config.js
module.exports = {
  content: ["./app/templates/**/*.html", "./app/static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  "#F1FAF6",
          100: "#D9F0E7",
          300: "#7FC7AC",
          500: "#14855F",
          600: "#0E6B4F",
          700: "#0A5640",
        },
        accent: { 100: "#FBF3D9", 600: "#A67C00" },
        success: "#1B7F4B",
        warning: "#B45309",
        info: "#1D4ED8",
        danger: { 50: "#FEF3F2", 600: "#B42318" },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        serif: ['"Liberation Serif"', '"Times New Roman"', "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { sm: "6px", md: "10px", lg: "14px" },
      boxShadow: {
        1: "0 1px 2px rgba(15,23,42,.06)",
        2: "0 8px 24px rgba(15,23,42,.10)",
      },
      maxWidth: { content: "1280px" },
    },
  },
  plugins: [],
};
```

## Empty, Loading & Error States

| Keadaan | Tampilan | Teks |
|:---|:---|:---|
| Daftar kosong (admin) | Ikon dokumen + teks | "Belum ada pengajuan pada filter ini." + tombol "Hapus filter" |
| Antrean kosong | Ikon centang | "Semua pengajuan sudah ditangani." |
| Model belum ada | Ikon otak + peringatan | "Belum ada model aktif. Chatbot tidak dapat menjawab." + tombol "Latih model" |
| Memuat tabel | Skeleton 5 baris | Tanpa spinner penuh halaman |
| Gagal memuat | Blok error | "Data gagal dimuat. Periksa koneksi lalu coba lagi." + tombol "Coba lagi" |
| Verifikasi tidak ditemukan | Blok netral | "Dokumen tidak ditemukan. Pastikan QR dipindai dengan benar." + kontak desa |
| Chat: bot ragu | Quick reply | "Maaf, saya belum yakin maksudnya. Mungkin salah satu dari ini?" |

## Do & Don't

| Lakukan | Jangan |
|:---|:---|
| Gunakan satu tombol primary per layar | Menaruh tiga tombol hijau bersaing |
| Tampilkan nomor tiket dengan font mono | Menyembunyikan nomor tiket di balik ikon |
| Jelaskan error beserta cara memperbaiki | Menampilkan "Terjadi kesalahan" tanpa konteks |
| Pertahankan jarak 24 px antar-kartu | Menumpuk kartu hingga sulit dibedakan |
| Pakai ikon Lucide 20 px | Mencampur tiga set ikon berbeda |
| Uji di layar 360 px | Mendesain hanya untuk laptop 1440 px |
| Tulis "Bapak/Ibu" | Menulis "USER" atau "Anda" berulang |
