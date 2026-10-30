"""Katalog awal: intent, layanan, template surat, FAQ, pejabat, dan pengaturan.

Semua isi di sini diturunkan dari dokumen asli Kantor Desa Kampala
(`Format surat/`) dan batasan masalah pada skripsi.
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# 18 intent
# --------------------------------------------------------------------------- #
INTENTS: list[dict[str, Any]] = [
    {"kode": "SAPA", "nama": "Sapaan", "jenis": "sistem",
     "deskripsi": "Warga menyapa atau membuka percakapan."},
    {"kode": "INFO_SYARAT_DOMISILI", "nama": "Info syarat domisili", "jenis": "info",
     "deskripsi": "Menanyakan syarat surat keterangan domisili."},
    {"kode": "AJUKAN_DOMISILI", "nama": "Ajukan domisili", "jenis": "ajukan",
     "deskripsi": "Ingin mengajukan surat keterangan domisili."},
    {"kode": "INFO_SYARAT_SKTM", "nama": "Info syarat SKTM", "jenis": "info",
     "deskripsi": "Menanyakan syarat surat keterangan tidak mampu."},
    {"kode": "AJUKAN_SKTM", "nama": "Ajukan SKTM", "jenis": "ajukan",
     "deskripsi": "Ingin mengajukan surat keterangan tidak mampu."},
    {"kode": "INFO_SYARAT_USAHA", "nama": "Info syarat usaha", "jenis": "info",
     "deskripsi": "Menanyakan syarat surat keterangan usaha."},
    {"kode": "AJUKAN_USAHA", "nama": "Ajukan usaha", "jenis": "ajukan",
     "deskripsi": "Ingin mengajukan surat keterangan usaha."},
    {"kode": "INFO_SYARAT_PENGANTAR", "nama": "Info syarat pengantar", "jenis": "info",
     "deskripsi": "Menanyakan syarat surat pengantar."},
    {"kode": "AJUKAN_PENGANTAR", "nama": "Ajukan pengantar", "jenis": "ajukan",
     "deskripsi": "Ingin mengajukan surat pengantar."},
    {"kode": "CEK_STATUS", "nama": "Cek status", "jenis": "sistem",
     "deskripsi": "Menanyakan status pengajuan yang sudah dibuat."},
    {"kode": "INFO_JAM_LAYANAN", "nama": "Jam layanan", "jenis": "faq",
     "deskripsi": "Menanyakan jam operasional kantor desa."},
    {"kode": "INFO_BIAYA", "nama": "Biaya layanan", "jenis": "faq",
     "deskripsi": "Menanyakan biaya pembuatan surat."},
    {"kode": "INFO_LAMA_PROSES", "nama": "Lama proses", "jenis": "faq",
     "deskripsi": "Menanyakan berapa lama surat selesai."},
    {"kode": "INFO_SYARAT_UMUM", "nama": "Syarat umum", "jenis": "info",
     "deskripsi": "Menanyakan dokumen persyaratan secara umum."},
    {"kode": "KOMPLAIN", "nama": "Keluhan", "jenis": "faq",
     "deskripsi": "Menyampaikan keluhan atas layanan."},
    {"kode": "BICARA_PETUGAS", "nama": "Minta petugas", "jenis": "sistem",
     "deskripsi": "Ingin dihubungkan dengan petugas desa."},
    {"kode": "TERIMA_KASIH", "nama": "Ucapan terima kasih", "jenis": "sistem",
     "deskripsi": "Warga berterima kasih atau menutup percakapan."},
    {"kode": "LAINNYA", "nama": "Di luar cakupan", "jenis": "sistem",
     "deskripsi": "Pertanyaan di luar 18 intent yang dikenali."},
]

# --------------------------------------------------------------------------- #
# Layanan MVP
# --------------------------------------------------------------------------- #
IDENTITAS = [
    ("nik", "NIK", "nik", "16 digit sesuai KTP", "Contoh: 7304091201900001"),
    ("nama_lengkap", "Nama Lengkap", "text", "Sesuai KTP", "Contoh: RESKI ADITYA"),
    ("tempat_lahir", "Tempat Lahir", "text", "Sesuai KTP", "Contoh: Jeneponto"),
    ("tanggal_lahir", "Tanggal Lahir", "date", "Format YYYY-MM-DD", "Contoh: 1990-01-12"),
    ("jenis_kelamin", "Jenis Kelamin", "select", "Laki-Laki atau Perempuan", None),
    ("status_perkawinan", "Status Perkawinan", "select", "Belum Kawin / Kawin / Cerai", None),
    ("agama", "Agama", "select", "Agama yang tercatat", None),
    ("pekerjaan", "Pekerjaan", "text", "Sesuai KTP", "Contoh: Petani/Pekebun"),
    ("alamat", "Alamat", "textarea", "Nama jalan/dusun", "Contoh: Dusun Kalukuang"),
    ("dusun", "Dusun", "select", "Pilih dusun domisili", None),
    ("rt", "RT", "text", "Nomor RT", "Contoh: 002"),
    ("rw", "RW", "text", "Nomor RW", "Contoh: 001"),
    ("no_hp", "Nomor HP/WhatsApp", "phone", "Untuk notifikasi status", "Contoh: 081234567890"),
]

_PILIHAN = {
    "jenis_kelamin": ["Laki-Laki", "Perempuan"],
    "status_perkawinan": ["Belum Kawin", "Kawin", "Cerai Hidup", "Cerai Mati"],
    "agama": ["Islam", "Kristen", "Katolik", "Hindu", "Buddha", "Konghucu"],
    "dusun": ["Buntulu", "Kalukuang", "Monroloe", "Pinyangkabung", "Sepeka"],
    "bentuk_usaha": ["Milik Sendiri", "Sewa", "Lainnya"],
}


def _fields(extra: list[tuple[str, str, str, str | None, str | None]]) -> list[dict[str, Any]]:
    hasil: list[dict[str, Any]] = []
    urutan = 0
    for nama, label, tipe, bantuan, placeholder in IDENTITAS + extra:
        hasil.append(
            {
                "nama_field": nama,
                "label": label,
                "tipe": tipe,
                "wajib": True,
                "urutan": urutan,
                "pilihan": _PILIHAN.get(nama),
                "placeholder": placeholder,
                "bantuan": bantuan,
            }
        )
        urutan += 1
    return hasil


SERVICES: list[dict[str, Any]] = [
    {
        "kode": "DOM",
        "nama": "Surat Keterangan Domisili",
        "deskripsi": "Menerangkan bahwa seseorang benar berdomisili di Desa Kampala.",
        "syarat": ["KTP asli", "Kartu Keluarga", "Nomor HP aktif"],
        "estimasi_hari": 1,
        "urutan": 1,
        "fields": _fields(
            [("keperluan", "Keperluan Surat", "textarea", "Untuk apa surat dipakai", "Contoh: pendaftaran sekolah")]
        ),
    },
    {
        "kode": "SKTM",
        "nama": "Surat Keterangan Tidak Mampu",
        "deskripsi": "Keterangan ekonomi untuk keringanan biaya pendidikan atau kesehatan.",
        "syarat": ["KTP asli", "Kartu Keluarga", "Surat permohonan"],
        "estimasi_hari": 1,
        "urutan": 2,
        "fields": _fields(
            [
                ("penghasilan_bulanan", "Penghasilan per Bulan (Rp)", "number", "Perkiraan penghasilan", "Contoh: 1500000"),
                ("jumlah_tanggungan", "Jumlah Tanggungan", "number", "Jumlah anggota keluarga yang ditanggung", "Contoh: 4"),
                ("keperluan", "Keperluan Surat", "textarea", "Untuk apa surat dipakai", "Contoh: beasiswa sekolah"),
            ]
        ),
    },
    {
        "kode": "USH",
        "nama": "Surat Keterangan Usaha",
        "deskripsi": "Menerangkan kepemilikan dan lokasi usaha warga.",
        "syarat": ["KTP asli", "Kartu Keluarga", "Foto lokasi usaha"],
        "estimasi_hari": 2,
        "urutan": 3,
        "fields": _fields(
            [
                ("nama_usaha", "Nama Usaha", "text", "Nama usaha yang dijalankan", "Contoh: UD. KARSUT"),
                ("jenis_usaha", "Jenis Usaha", "text", "Bidang usaha", "Contoh: Peternakan Ayam"),
                ("alamat_usaha", "Alamat Usaha", "textarea", "Lokasi usaha", "Contoh: Dusun Sepeka"),
                ("bentuk_usaha", "Bentuk Usaha", "select", "Status tempat usaha", None),
                ("modal_usaha", "Modal Usaha (Rp)", "number", "Perkiraan modal", "Contoh: 5000000"),
                ("tahun_mulai", "Usaha Sejak Tahun", "number", "Tahun mulai berusaha", "Contoh: 2020"),
            ]
        ),
    },
    {
        "kode": "PGG",
        "nama": "Surat Pengantar",
        "deskripsi": "Pengantar kepada instansi lain (kelurahan, kepolisian, dinas, dan sebagainya).",
        "syarat": ["KTP asli", "Kartu Keluarga"],
        "estimasi_hari": 1,
        "urutan": 4,
        "fields": _fields(
            [
                ("tujuan_instansi", "Tujuan Instansi", "text", "Instansi yang dituju", "Contoh: Polres Jeneponto"),
                ("keperluan", "Keperluan Surat", "textarea", "Untuk apa surat dipakai", "Contoh: pengurusan SKCK"),
            ]
        ),
    },
]

# --------------------------------------------------------------------------- #
# Template surat
# --------------------------------------------------------------------------- #
TEMPLATES: dict[str, str] = {
    "DOM": "\n".join(
        [
            "#JUDUL# SURAT KETERANGAN DOMISILI",
            "",
            "Yang bertanda tangan di bawah ini :",
            "",
            "| Nama | {pejabat_nama}",
            "| Jabatan | {pejabat_jabatan}",
            "",
            "Dengan ini menerangkan bahwa :",
            "",
            "| Nama | {nama_lengkap}",
            "| NIK | {nik}",
            "| Tempat / Tgl Lahir | {tempat_lahir}, {tanggal_lahir_panjang}",
            "| Jenis Kelamin | {jenis_kelamin}",
            "| Status | {status_perkawinan}",
            "| Agama | {agama}",
            "| Pekerjaan | {pekerjaan}",
            "| Alamat | {alamat_penuh}",
            "",
            "Bahwa nama tersebut adalah benar warga kami yang bertempat tinggal di "
            "Dusun {dusun} Desa Kampala Kecamatan Arungkeke Kabupaten Jeneponto.",
            "",
            "Surat keterangan ini diberikan untuk keperluan {keperluan}.",
            "",
            "Demikian surat keterangan Domisili ini kami berikan kepada yang bersangkutan "
            "untuk dipergunakan sebagaimana mestinya.",
        ]
    ),
    "SKTM": "\n".join(
        [
            "#JUDUL# SURAT KETERANGAN TIDAK MAMPU",
            "",
            "Yang bertanda tangan di bawah ini :",
            "",
            "| Nama | {pejabat_nama}",
            "| Jabatan | {pejabat_jabatan}",
            "",
            "Dengan ini menerangkan bahwa :",
            "",
            "| Nama | {nama_lengkap}",
            "| NIK | {nik}",
            "| Tempat / Tgl Lahir | {tempat_lahir}, {tanggal_lahir_panjang}",
            "| Jenis Kelamin | {jenis_kelamin}",
            "| Status | {status_perkawinan}",
            "| Agama | {agama}",
            "| Pekerjaan | {pekerjaan}",
            "| Alamat | {alamat_penuh}",
            "| Penghasilan / Bulan | Rp {penghasilan_bulanan}",
            "| Jumlah Tanggungan | {jumlah_tanggungan} orang",
            "| Keterangan | Nama dan keluarga tersebut di atas adalah benar-benar "
            "berdomisili di Dusun {dusun} Desa Kampala Kecamatan Arungkeke Kabupaten "
            "Jeneponto berdasarkan pengamatan kami di lapangan, dan yang bersangkutan "
            "benar-benar keluarga yang tidak mampu/miskin.",
            "| Keperluan | {keperluan}",
            "",
            "Demikian surat keterangan ini kami buat dengan sebenar-benarnya dan diberikan "
            "kepada yang bersangkutan untuk dipergunakan sebagaimana mestinya.",
        ]
    ),
    "USH": "\n".join(
        [
            "#JUDUL# SURAT KETERANGAN USAHA",
            "#PEMEGANG#",
            "",
            "Yang bertanda tangan di bawah ini :",
            "",
            "| Nama | {pejabat_nama}",
            "| Jabatan | {pejabat_jabatan}",
            "",
            "Dengan ini menerangkan bahwa :",
            "",
            "| Nama | {nama_lengkap}",
            "| NIK | {nik}",
            "| Tempat / Tgl Lahir | {tempat_lahir}, {tanggal_lahir_panjang}",
            "| Jenis Kelamin | {jenis_kelamin}",
            "| Status | {status_perkawinan}",
            "| Agama | {agama}",
            "| Pekerjaan | {pekerjaan}",
            "| Alamat | {alamat_penuh}",
            "",
            "Bahwa orang tersebut adalah benar-benar warga kami yang memiliki usaha "
            "dengan identitas :",
            "",
            "| Nama Usaha | {nama_usaha}",
            "| Jenis Usaha | {jenis_usaha}",
            "| Alamat Usaha | {alamat_usaha}",
            "| Bentuk Usaha | {bentuk_usaha}",
            "| Modal Usaha | Rp {modal_usaha}",
            "| Usaha Sejak Tahun | {tahun_mulai}",
            "",
            "Demikian surat keterangan Usaha ini kami berikan kepada yang bersangkutan "
            "untuk dipergunakan sebagaimana mestinya.",
        ]
    ),
    "PGG": "\n".join(
        [
            "#JUDUL# SURAT PENGANTAR",
            "",
            "Yang bertanda tangan di bawah ini :",
            "",
            "| Nama | {pejabat_nama}",
            "| Jabatan | {pejabat_jabatan}",
            "",
            "Dengan ini menerangkan bahwa :",
            "",
            "| Nama | {nama_lengkap}",
            "| NIK | {nik}",
            "| Tempat / Tgl Lahir | {tempat_lahir}, {tanggal_lahir_panjang}",
            "| Jenis Kelamin | {jenis_kelamin}",
            "| Status | {status_perkawinan}",
            "| Agama | {agama}",
            "| Pekerjaan | {pekerjaan}",
            "| Alamat | {alamat_penuh}",
            "",
            "Adalah benar warga Desa Kampala Kecamatan Arungkeke Kabupaten Jeneponto. "
            "Yang bersangkutan memohon pengantar kepada {tujuan_instansi} untuk keperluan "
            "{keperluan}.",
            "",
            "Demikian surat pengantar ini kami berikan untuk dipergunakan sebagaimana mestinya.",
        ]
    ),
}

#: Jabatan penanda tangan tiap layanan (dicocokkan ke tabel OFFICIAL).
PENANDATANGAN = {
    "DOM": "Sekretaris Desa",
    "SKTM": "Kepala Desa",
    "USH": "Sekretaris Desa",
    "PGG": "Sekretaris Desa",
}

#: Saksi tambahan (kolom kiri blok tanda tangan), bila ada.
SAKSI = {"DOM": "Kapolsek Arungkeke", "SKTM": "Kapolsek Arungkeke", "PGG": "Kapolsek Arungkeke"}

# --------------------------------------------------------------------------- #
# FAQ awal
# --------------------------------------------------------------------------- #
FAQS: list[dict[str, Any]] = [
    {
        "intent_kode": "INFO_JAM_LAYANAN",
        "pertanyaan": "Jam berapa kantor desa buka?",
        "jawaban": (
            "Kantor Desa Kampala melayani Senin–Kamis pukul 08.00–15.00 WITA, "
            "Jumat pukul 08.00–11.00 WITA. Sabtu, Minggu, dan hari libur nasional tutup."
        ),
        "kata_kunci": ["jam", "buka", "layanan", "operasional", "hari apa", "tutup"],
    },
    {
        "intent_kode": "INFO_BIAYA",
        "pertanyaan": "Apakah pembuatan surat dikenakan biaya?",
        "jawaban": (
            "Tidak. Seluruh layanan administrasi Desa Kampala gratis, tidak dipungut biaya "
            "dalam bentuk apa pun. Bila ada permintaan pembayaran, laporkan ke petugas desa."
        ),
        "kata_kunci": ["biaya", "bayar", "gratis", "tarif", "pungli", "uang"],
    },
    {
        "intent_kode": "INFO_LAMA_PROSES",
        "pertanyaan": "Berapa lama surat selesai?",
        "jawaban": (
            "Rata-rata 1 hari kerja setelah berkas lengkap dan diverifikasi. "
            "Surat keterangan usaha 2 hari kerja karena perlu pengecekan lokasi usaha."
        ),
        "kata_kunci": ["lama", "berapa hari", "cepat", "selesai", "jadi"],
    },
    {
        "intent_kode": "INFO_SYARAT_UMUM",
        "pertanyaan": "Dokumen apa saja yang harus disiapkan?",
        "jawaban": (
            "Secara umum: KTP asli, Kartu Keluarga, dan nomor HP aktif. "
            "Persyaratan tambahan berbeda per layanan, silakan tanyakan jenis suratnya."
        ),
        "kata_kunci": ["syarat", "dokumen", "berkas", "persyaratan", "apa saja"],
    },
    {
        "intent_kode": "CEK_STATUS",
        "pertanyaan": "Bagaimana cara cek status pengajuan?",
        "jawaban": (
            "Kirim nomor tiket Anda (format APP-2026-000123) di chat ini, atau buka "
            "halaman Lacak di situs desa. Status akan diperbarui setiap kali petugas "
            "memproses pengajuan."
        ),
        "kata_kunci": ["cek status", "tiket", "sudah jadi", "progres", "lacak"],
    },
    {
        "intent_kode": "KOMPLAIN",
        "pertanyaan": "Saya ingin menyampaikan keluhan.",
        "jawaban": (
            "Mohon maaf atas ketidaknyamanannya. Silakan tuliskan keluhan Anda, "
            "kami teruskan ke petugas desa untuk ditindaklanjuti pada hari kerja berikutnya."
        ),
        "kata_kunci": ["keluhan", "komplain", "kecewa", "lambat", "tidak puas"],
    },
]

# --------------------------------------------------------------------------- #
# Pejabat
# --------------------------------------------------------------------------- #
OFFICIALS: list[dict[str, Any]] = [
    {"nama": "Hj. ROSMIATI", "jabatan": "Kepala Desa", "pangkat": None, "urutan": 1},
    {"nama": "BAHTIAR.B", "jabatan": "Sekretaris Desa", "pangkat": None, "urutan": 2},
    {"nama": "SALMAN SALAM SH.", "jabatan": "Kapolsek Arungkeke", "pangkat": None, "urutan": 3},
]

# --------------------------------------------------------------------------- #
# Pengaturan awal
# --------------------------------------------------------------------------- #
SETTINGS: list[dict[str, str]] = [
    {"kunci": "nama_desa", "nilai": "Kampala", "tipe": "string",
     "deskripsi": "Nama desa pada kop surat."},
    {"kunci": "nama_kecamatan", "nilai": "Arungkeke", "tipe": "string",
     "deskripsi": "Nama kecamatan."},
    {"kunci": "nama_kabupaten", "nilai": "Jeneponto", "tipe": "string",
     "deskripsi": "Nama kabupaten."},
    {"kunci": "alamat_kantor", "nilai": "Jl. Poros Dusun Buntulu Desa Kampala Kec. Arungkeke",
     "tipe": "string", "deskripsi": "Alamat pada kop surat."},
    {"kunci": "logo_kop", "nilai": "", "tipe": "string",
     "deskripsi": "Berkas logo kop surat. Kosongkan untuk memakai logo kabupaten bawaan."},
    {"kunci": "telepon_kantor", "nilai": "-", "tipe": "string",
     "deskripsi": "Nomor telepon kantor desa."},
    {"kunci": "confidence_tinggi", "nilai": "0.65", "tipe": "float",
     "deskripsi": "Ambang bawah untuk menjawab langsung."},
    {"kunci": "confidence_rendah", "nilai": "0.40", "tipe": "float",
     "deskripsi": "Ambang bawah untuk meminta klarifikasi."},
    {"kunci": "batas_pengajuan_aktif", "nilai": "3", "tipe": "int",
     "deskripsi": "Jumlah maksimum pengajuan aktif per NIK."},
    {"kunci": "sapaan", "nilai": "Selamat datang di layanan mandiri Desa Kampala.",
     "tipe": "string", "deskripsi": "Kalimat pembuka chat."},
]

for _kode in ("DOM", "SKTM", "USH", "PGG"):
    SETTINGS.append(
        {
            "kunci": f"penandatangan_{_kode}",
            "nilai": PENANDATANGAN[_kode],
            "tipe": "string",
            "deskripsi": f"Jabatan penanda tangan surat {_kode}.",
        }
    )
    if _kode in SAKSI:
        SETTINGS.append(
            {
                "kunci": f"saksi_{_kode}",
                "nilai": SAKSI[_kode],
                "tipe": "string",
                "deskripsi": f"Jabatan saksi surat {_kode}.",
            }
        )


def pilihan_untuk(nama_field: str) -> list[str] | None:
    return _PILIHAN.get(nama_field)
