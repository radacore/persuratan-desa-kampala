"""Konstanta domain SILADESA.

Semua nilai yang dipakai bersama oleh model, service, dan router diletakkan
di sini agar tidak ada string ajaib yang tersebar.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OPERATOR = "operator"
    SEKDES = "sekdes"
    KEPALA_DESA = "kepala_desa"
    ADMIN_TEKNIS = "admin_teknis"


class Status(StrEnum):
    DRAFT = "DRAFT"
    MENUNGGU_VERIFIKASI = "MENUNGGU_VERIFIKASI"
    DIPROSES = "DIPROSES"
    TERBIT = "TERBIT"
    DITOLAK = "DITOLAK"
    DIBATALKAN = "DIBATALKAN"


#: Status yang dianggap masih berjalan (dipakai untuk batas pengajuan aktif).
#: DRAFT ikut di sini secara konsep, tetapi dalam praktik belum terhitung karena
#: `application.citizen_id` baru diisi saat pengajuan dikirim.
STATUS_AKTIF = (
    Status.DRAFT,
    Status.MENUNGGU_VERIFIKASI,
    Status.DIPROSES,
)

#: Transisi status yang sah: (dari, ke) -> peran yang berhak.
TRANSISI = {
    (Status.DRAFT, Status.MENUNGGU_VERIFIKASI): {
        Role.OPERATOR,
        Role.SEKDES,
        Role.KEPALA_DESA,
        Role.ADMIN_TEKNIS,
    },
    (Status.DRAFT, Status.DIBATALKAN): {
        Role.OPERATOR,
        Role.SEKDES,
        Role.KEPALA_DESA,
        Role.ADMIN_TEKNIS,
    },
    (Status.MENUNGGU_VERIFIKASI, Status.DIPROSES): {
        Role.OPERATOR,
        Role.SEKDES,
        Role.KEPALA_DESA,
    },
    (Status.MENUNGGU_VERIFIKASI, Status.DITOLAK): {
        Role.OPERATOR,
        Role.SEKDES,
        Role.KEPALA_DESA,
    },
    (Status.MENUNGGU_VERIFIKASI, Status.DIBATALKAN): {
        Role.OPERATOR,
        Role.SEKDES,
        Role.KEPALA_DESA,
        Role.ADMIN_TEKNIS,
    },
    (Status.DIPROSES, Status.TERBIT): {Role.SEKDES, Role.KEPALA_DESA},
    (Status.DIPROSES, Status.DITOLAK): {
        Role.OPERATOR,
        Role.SEKDES,
        Role.KEPALA_DESA,
    },
    (Status.DIPROSES, Status.DIBATALKAN): {Role.SEKDES, Role.KEPALA_DESA},
}

#: Peran yang boleh menerbitkan dokumen: lihat `TRANSISI` (DIPROSES → TERBIT).

class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class ChatState(StrEnum):
    IDLE = "IDLE"
    MENU = "MENU"
    INFO = "INFO"
    CONSENT = "CONSENT"
    SLOT_FILLING = "SLOT_FILLING"
    KONFIRMASI_NIK = "KONFIRMASI_NIK"
    KONFIRMASI_WARGA = "KONFIRMASI_WARGA"
    KONFIRMASI = "KONFIRMASI"
    TRACKING = "TRACKING"
    ESKALASI = "ESKALASI"


#: Kode wilayah NIK Kabupaten Jeneponto.
NIK_PREFIX = "7304"

#: Ambang keyakinan bawaan; dapat ditimpa lewat tabel SETTING.
CONFIDENCE_TINGGI = 0.65
CONFIDENCE_RENDAH = 0.40

#: Batas pengajuan aktif per NIK.
BATAS_PENGAJUAN_AKTIF = 3

BULAN_ROMAWI = (
    "",
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
)

MASK_NIK = "************"

#: Peran yang boleh melakukan aksi tertentu pada panel admin.
PERMISSIONS = {
    Role.OPERATOR: {
        "application.read",
        "application.review",
        "application.reject",
        "citizen.read",
        "citizen.manage",
        "faq.manage",
        "report.read",
    },
    Role.SEKDES: {
        "application.read",
        "application.review",
        "application.reject",
        "application.approve",
        "service.manage",
        "template.manage",
        "number.manage",
        "official.manage",
        "citizen.read",
        "citizen.manage",
        "faq.manage",
        "audit.read",
        "report.read",
    },
    Role.KEPALA_DESA: {
        "application.read",
        "application.review",
        "application.reject",
        "application.approve",
        "application.revoke",
        "service.manage",
        "template.manage",
        "number.manage",
        "official.manage",
        "citizen.read",
        "faq.manage",
        "audit.read",
        "report.read",
    },
    Role.ADMIN_TEKNIS: {
        "application.read",
        "service.manage",
        "template.manage",
        "number.manage",
        "official.manage",
        "citizen.read",
        "citizen.manage",
        "faq.manage",
        "model.manage",
        "dataset.manage",
        "user.manage",
        "setting.manage",
        "audit.read",
        "report.read",
    },
}


def boleh(role: str, permission: str) -> bool:
    """True bila peran memiliki izin tertentu."""
    try:
        return permission in PERMISSIONS[Role(role)]
    except (KeyError, ValueError):
        return False
