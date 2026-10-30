# Checklist Uji Black-Box WhatsApp (Fonnte) — SILADESA

Dipakai manual dari HP setelah nomor WA desa aktif di Fonnte.
Prasyarat: `FONNTE_TOKEN` + `FONNTE_WEBHOOK_TOKEN` terisi di `.env`,
webhook Fonnte mengarah ke `https://<domain>/webhooks/whatsapp/<secret>`,
server produksi berjalan dan dapat dijangkau internet.

Hasil tiap kasus: tulis Lulus/Gagal + tanggal + nama penguji.

## A. Koneksi dasar

| Kode | Skenario | Langkah | Hasil yang diharapkan |
|---|---|---|---|
| WA-01 | Sapaan awal | Kirim `Halo` ke nomor WA desa | Balasan menu layanan (bukan diam/error) |
| WA-02 | Menu angka | Balas `1` | Sistem masuk tahap persetujuan pengajuan surat |
| WA-03 | Tanya syarat | Kirim `syarat surat keterangan domisili apa saja` | Jawaban memuat KTP, KK, nomor HP |

## B. Pengajuan sampai tiket

| Kode | Skenario | Langkah | Hasil yang diharapkan |
|---|---|---|---|
| WA-04 | Pengisian data | Setujui (`ya`), isi 14 kolom dengan data valid | Menerima nomor tiket format `APP-{tahun}-{6 digit}` |
| WA-05 | Validasi NIK | Saat diminta NIK, kirim `123` | Ditolak, diminta NIK 16 digit |
| WA-06 | Pembatalan | Ketik `batal` saat pengisian | Sesi direset, pengajuan dibatalkan |

## C. Pelacakan dan unduh (perlu tiket dari WA-04 + NIK pemohon)

| Kode | Skenario | Langkah | Hasil yang diharapkan |
|---|---|---|---|
| WA-07 | Lacak tanpa NIK | Kirim `cek APP-...` (tiket saja) | Sistem meminta NIK, TIDAK menampilkan tautan unduh |
| WA-08 | Lacak dengan NIK benar | Kirim NIK 16 digit | Status pengajuan ditampilkan |
| WA-09 | Unduh PDF (setelah sekdes menerbitkan) | Kirim `cek` + NIK lagi setelah status TERBIT | Menerima pesan berisi tautan `/d/...`; tautan bisa dibuka dan PDF terbaca |

## D. Notifikasi proaktif (perlu peran operator di panel)

| Kode | Skenario | Langkah | Hasil yang diharapkan |
|---|---|---|---|
| WA-10 | Status diproses | Operator verifikasi pengajuan di panel | WA menerima pesan "sedang diproses petugas" |
| WA-11 | Surat terbit | Sekdes terbitkan surat di panel | WA menerima pesan + tautan unduh (dan/atau lampiran PDF) |

## E. Batasan yang diverifikasi

| Kode | Skenario | Langkah | Hasil yang diharapkan |
|---|---|---|---|
| WA-12 | Token salah | Ubah `{secret}` di URL webhook jadi nilai acak | Fonnte menerima 403; tidak ada balasan ke pengirim |
| WA-13 | Spam bertubi | Kirim 10 pesan cepat berturut-turut | Semua dibalas atau dibatasi sopan; server tidak error |
| WA-14 | Pesan grup | Jika memungkinkan, uji dari grup WA | Pesan grup diabaikan (tidak dibalas) |

## Catatan penguji

- Jam layanan yang dijanjikan bot: Senin–Kamis 08.00–15.00, Jumat 08.00–11.00 WITA.
- Jangan pakai nomor ini untuk broadcast massal (risiko blokir Meta).
- Simpan tangkapan layar tiap WA-01–WA-11 sebagai bukti Bab IV bila diperlukan.
