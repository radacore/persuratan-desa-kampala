"""Orkestrator percakapan: klasifikasi intent → jawab / isi formulir / eskalasi.

Satu orkestrator melayani ketiga kanal (web, WhatsApp, Telegram) supaya aturan
bisnis dan teks balasan konsisten.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import constants as C
from app.config import settings
from app.models import (
    Application,
    ChatMessage,
    Citizen,
    ConversationSession,
    Faq,
    Intent,
    Service,
    ServiceField,
    Setting,
)
from app.services import applications as appsvc
from app.services.nlp import cocokkan_faq, nlp

TIKET_RE = re.compile(r"APP-\d{4}-\d{6}", re.IGNORECASE)
NIK_RE = re.compile(r"\b\d{16}\b")
YA = {"ya", "y", "yes", "boleh", "lanjut", "ok", "oke", "okey", "betul", "benar", "sudah", "siap", "setuju"}
TIDAK = {"tidak", "tdk", "gak", "gk", "engga", "batal", "jangan", "belum", "no", "salah", "ganti"}
BATAL = {"batal", "cancel", "batalkan", "urungkan", "stop", "keluar"}
MENU = {"menu", "mulai", "start", "/start", "home", "bantuan", "help"}

SESI_KEDALUWARSA_MENIT = 45

INTENT_LAYANAN = {
    "AJUKAN_DOMISILI": "DOM",
    "AJUKAN_SKTM": "SKTM",
    "AJUKAN_USAHA": "USH",
    "AJUKAN_PENGANTAR": "PGG",
}

INFO_LAYANAN = {
    "INFO_SYARAT_DOMISILI": "DOM",
    "INFO_SYARAT_SKTM": "SKTM",
    "INFO_SYARAT_USAHA": "USH",
    "INFO_SYARAT_PENGANTAR": "PGG",
}

PILIHAN_MENU = [
    {"label": "Surat Keterangan Domisili", "value": "1"},
    {"label": "Surat Keterangan Tidak Mampu", "value": "2"},
    {"label": "Surat Keterangan Usaha", "value": "3"},
    {"label": "Surat Pengantar", "value": "4"},
    {"label": "Cek status pengajuan", "value": "5"},
    {"label": "Bicara dengan petugas", "value": "6"},
]

PILIHAN_KONFIRMASI_WARGA = [
    {"label": "Ya, pakai data ini", "value": "1"},
    {"label": "Perbaiki data", "value": "2"},
    {"label": "Batal", "value": "3"},
]

_URUTAN_MENU = ["DOM", "SKTM", "USH", "PGG"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ekstrak_nik(pesan: str) -> str | None:
    """Ambil NIK 16 digit dari pesan, bila ada."""
    cocok = NIK_RE.search(pesan or "")
    return cocok.group(0) if cocok else None


def _setting(db: Session, kunci: str, bawaan: str) -> str:
    row = db.execute(select(Setting).where(Setting.kunci == kunci)).scalar_one_or_none()
    return row.nilai if row else bawaan


def _ambang(db: Session) -> tuple[float, float]:
    try:
        tinggi = float(_setting(db, "confidence_tinggi", str(settings.confidence_tinggi)))
    except ValueError:
        tinggi = settings.confidence_tinggi
    try:
        rendah = float(_setting(db, "confidence_rendah", str(settings.confidence_rendah)))
    except ValueError:
        rendah = settings.confidence_rendah
    return tinggi, rendah


# --------------------------------------------------------------------------- #
# Sesi
# --------------------------------------------------------------------------- #
def sesi_baru(db: Session, channel: str, kontak: str) -> ConversationSession:
    sesi = ConversationSession(
        id=secrets.token_urlsafe(16),
        channel=channel,
        kontak=kontak[:60],
        state=C.ChatState.IDLE.value,
        slot_data={},
    )
    db.add(sesi)
    db.flush()
    return sesi


def buka_sesi(db: Session, channel: str, kontak: str) -> tuple[ConversationSession, list[str]]:
    """Buat sesi baru dan catat sapaan menu sebagai pesan keluar.

    Dipakai router API agar tidak perlu memanggil fungsi privat modul ini.
    """
    sesi = sesi_baru(db, channel, kontak)
    sapaan = _menu_text(db)
    for baris in sapaan:
        _catat(db, sesi, "out", baris)
    return sesi, sapaan


def ambil_sesi(db: Session, session_id: str) -> ConversationSession | None:
    sesi = db.get(ConversationSession, session_id)
    if sesi is None:
        return None
    if sesi.last_activity_at and sesi.last_activity_at.tzinfo is None:
        sesi.last_activity_at = sesi.last_activity_at.replace(tzinfo=timezone.utc)
    if sesi.last_activity_at and _now() - sesi.last_activity_at > timedelta(
        minutes=SESI_KEDALUWARSA_MENIT
    ):
        _reset(sesi)
    return sesi


def _reset(sesi: ConversationSession) -> None:
    sesi.state = C.ChatState.IDLE.value
    sesi.intent_kode = None
    sesi.service_id = None
    sesi.application_id = None
    sesi.slot_data = {}
    sesi.field_index = 0


def _catat(
    db: Session,
    sesi: ConversationSession,
    arah: str,
    isi: str,
    *,
    intent: str | None = None,
    confidence: float | None = None,
    faq_id: int | None = None,
) -> ChatMessage:
    pesan = ChatMessage(
        session_id=sesi.id,
        arah=arah,
        isi=isi,
        intent_kode=intent,
        confidence=confidence,
        faq_id=faq_id,
    )
    db.add(pesan)
    sesi.last_activity_at = _now()
    return pesan


def kirim_pesan_keluar(db: Session, application_id: int, isi: str) -> bool:
    """Sisipkan pesan keluar ke sesi percakapan asal pengajuan (FR-20).

    Dipakai setelah surat terbit supaya tautan unduhan muncul langsung di
    percakapan warga, bukan hanya di kanal push WhatsApp/Telegram. Relasi
    disimpan di `Application.session_id` karena sesi chat sudah di-reset
    (application_id dikosongkan) begitu pengajuan dikirim.
    """
    pengajuan = db.get(Application, application_id)
    if pengajuan is None or not pengajuan.session_id:
        return False
    sesi = db.get(ConversationSession, pengajuan.session_id)
    if sesi is None:
        return False
    _catat(db, sesi, "out", isi)
    return True


# --------------------------------------------------------------------------- #
# Teks bantuan
# --------------------------------------------------------------------------- #
def _menu_text(db: Session) -> list[str]:
    sapaan = _setting(db, "sapaan", "Selamat datang di layanan mandiri Desa Kampala.")
    return [
        sapaan,
        "Silakan pilih layanan dengan mengetik angka, atau tanyakan langsung kebutuhan Anda:",
        "1. Surat Keterangan Domisili\n"
        "2. Surat Keterangan Tidak Mampu\n"
        "3. Surat Keterangan Usaha\n"
        "4. Surat Pengantar\n"
        "5. Cek status pengajuan\n"
        "6. Bicara dengan petugas",
    ]


def _syarat_text(service: Service) -> str:
    syarat = service.syarat or []
    daftar = "\n".join(f"- {s}" for s in syarat) if syarat else "- Tidak ada berkas tambahan"
    field_wajib = [f.label for f in service.fields if f.wajib]
    return (
        f"Syarat {service.nama}:\n{daftar}\n\n"
        f"Data yang perlu diisi: {', '.join(field_wajib)}.\n"
        f"Estimasi selesai {service.estimasi_hari} hari kerja. Layanan ini gratis."
    )


def _ringkasan(app: Application) -> str:
    data = app.form_data or {}
    baris = [
        f"• {f.label}: {data.get(f.nama_field, '-')}" for f in app.service.fields
    ]
    return (
        f"Ringkasan pengajuan {app.service.nama}:\n" + "\n".join(baris) + "\n\n"
        "Ketik *ya* untuk mengirim, atau *batal* untuk membatalkan."
    )


def _prompt_field(field: ServiceField) -> tuple[str, list[dict[str, str]]]:
    teks = f"{field.label}"
    if field.bantuan:
        teks += f" ({field.bantuan})"
    if field.placeholder:
        # Placeholder bawaan seed sudah berawalan "Contoh: " — jangan digandakan.
        contoh = field.placeholder.strip()
        if contoh.lower().startswith("contoh:"):
            teks += f"\n{contoh}"
        else:
            teks += f"\nContoh: {contoh}"
    pilihan: list[dict[str, str]] = []
    if field.tipe == "select" and field.pilihan:
        pilihan = [{"label": p, "value": p} for p in field.pilihan]
        teks += "\n" + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(field.pilihan))
    elif field.tipe == "date" and "yyyy-mm-dd" not in teks.lower():
        teks += "\nFormat: YYYY-MM-DD"
    return teks, pilihan


# --------------------------------------------------------------------------- #
# Pencarian data pendukung
# --------------------------------------------------------------------------- #
def _layanan(db: Session, kode: str) -> Service | None:
    return db.execute(
        select(Service).where(Service.kode == kode, Service.aktif.is_(True))
    ).scalar_one_or_none()


def _faq_untuk(db: Session, intent_kode: str) -> Faq | None:
    return db.execute(
        select(Faq)
        .join(Intent, Faq.intent_id == Intent.id)
        .where(Intent.kode == intent_kode, Faq.aktif.is_(True))
        .order_by(Faq.urutan)
    ).scalars().first()


def _semua_faq(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(Faq).where(Faq.aktif.is_(True))).scalars().all()
    return [
        {
            "id": f.id,
            "pertanyaan": f.pertanyaan,
            "jawaban": f.jawaban,
            "kata_kunci": f.kata_kunci or [],
            "intent": f.intent.kode if f.intent else None,
        }
        for f in rows
    ]


# --------------------------------------------------------------------------- #
# Pengisian formulir
# --------------------------------------------------------------------------- #
def _fields_service(service: Service) -> list[ServiceField]:
    return sorted(service.fields, key=lambda f: f.urutan)



# --------------------------------------------------------------------------- #
# Data warga (master)
# --------------------------------------------------------------------------- #
def _nilai_identitas(citizen: Citizen, fields: list[ServiceField]) -> dict[str, str]:
    """Nilai identitas warga yang sah untuk field layanan ini.

    Nilai yang tidak lolos validasi field (mis. pilihan dusun sudah berubah)
    dilewati supaya warga ditanya ulang, bukan terjebak di ringkasan.
    """
    hasil: dict[str, str] = {}
    for field in fields:
        nama = field.nama_field
        if nama not in appsvc.CITIZEN_FIELDS or nama == "nik":
            continue
        nilai = getattr(citizen, nama, None)
        if nilai is None:
            continue
        if isinstance(nilai, date):
            nilai = nilai.isoformat()
        teks = str(nilai).strip()
        if not teks or appsvc.validasi_nilai(field, teks) is not None:
            continue
        hasil[nama] = teks
    return hasil


def _kartu_warga(citizen: Citizen, fields: list[ServiceField]) -> str:
    """Ringkasan data warga untuk dikonfirmasi sebelum dipakai pada surat."""
    data = _nilai_identitas(citizen, fields)
    tanggal = data.get("tanggal_lahir")
    if tanggal:
        try:
            tanggal = date.fromisoformat(tanggal).strftime("%d-%m-%Y")
        except ValueError:
            pass
    ttl = ", ".join(
        v for v in (data.get("tempat_lahir"), tanggal) if v
    ) or "-"
    alamat = data.get("alamat") or "-"
    rt, rw = data.get("rt"), data.get("rw")
    if rt or rw:
        alamat += f" RT {rt or '-'}/RW {rw or '-'}"

    baris = [
        f"NIK: {citizen.nik}",
        f"Nama: {data.get('nama_lengkap') or citizen.nama_lengkap}",
        f"TTL: {ttl}",
        f"Alamat: {alamat}",
    ]
    if data.get("no_hp"):
        baris.append(f"No HP: {data['no_hp']}")

    return (
        "Data warga ditemukan:\n"
        + "\n".join(f"• {b}" for b in baris)
        + "\n\nGunakan data ini untuk surat?\n"
        "1. Ya, pakai data ini\n"
        "2. Perbaiki data\n"
        "3. Batal"
    )


def _tanya_field_berikut(
    db: Session, sesi: ConversationSession, fields: list[ServiceField]
) -> tuple[list[str], list[dict[str, str]]]:
    """Ajukan field pertama yang belum terisi, atau masuk ringkasan."""
    sesi.state = C.ChatState.SLOT_FILLING.value
    slot = sesi.slot_data or {}
    sesi.field_index = next(
        (
            i
            for i, f in enumerate(fields)
            if not str(slot.get(f.nama_field, "")).strip()
        ),
        len(fields),
    )

    draft = db.get(Application, sesi.application_id) if sesi.application_id else None
    if sesi.field_index >= len(fields):
        if draft is None:
            _reset(sesi)
            return ["Draft pengajuan hilang. Silakan mulai lagi."], []
        return _konfirmasi(db, sesi, draft)

    field = fields[sesi.field_index]
    pertanyaan, pilihan = _prompt_field(field)
    return [
        f"Data {sesi.field_index + 1} dari {len(fields)}.\n{pertanyaan}"
    ], pilihan


def _jawab_konfirmasi_warga(
    db: Session, sesi: ConversationSession, pesan: str
) -> tuple[list[str], list[dict[str, str]]]:
    """Tangani jawaban atas kartu data warga (pakai / perbaiki / batal)."""
    service = db.get(Service, sesi.service_id) if sesi.service_id else None
    if service is None:
        _reset(sesi)
        return ["Sesi pengajuan tidak ditemukan. Silakan mulai lagi dari menu."], []

    fields = _fields_service(service)
    teks = pesan.strip().lower()

    if teks in {"1"} | YA:
        return _tanya_field_berikut(db, sesi, fields)

    if teks in {"2", "perbaiki", "ubah", "revisi", "koreksi"}:
        # Pertahankan NIK, kosongkan identitas lain supaya ditanya ulang.
        sesi.slot_data = {
            k: v
            for k, v in (sesi.slot_data or {}).items()
            if k not in appsvc.CITIZEN_FIELDS or k == "nik"
        }
        return _tanya_field_berikut(db, sesi, fields)

    return [
        "Mohon pilih:\n1. Ya, pakai data ini\n2. Perbaiki data\n3. Batal"
    ], PILIHAN_KONFIRMASI_WARGA


def _mulai_pengisian(
    db: Session, sesi: ConversationSession, service: Service
) -> tuple[list[str], list[dict[str, str]]]:
    """Buat draft dan ajukan pertanyaan pertama."""
    sesi.state = C.ChatState.SLOT_FILLING.value
    sesi.service_id = service.id
    sesi.field_index = 0

    draft = None
    if sesi.application_id:
        draft = db.get(Application, sesi.application_id)
        if draft is not None and draft.status != C.Status.DRAFT.value:
            draft = None
    if draft is None:
        draft = appsvc.buat_draft(
            db, service=service, form_data=sesi.slot_data or {}, channel=sesi.channel,
            session_id=sesi.id,
        )
        sesi.application_id = draft.id

    fields = _fields_service(service)
    # Lewati field yang sudah terisi (mis. warga lama yang datanya tersimpan).
    while sesi.field_index < len(fields) and str(
        (sesi.slot_data or {}).get(fields[sesi.field_index].nama_field, "")
    ).strip():
        sesi.field_index += 1

    if sesi.field_index >= len(fields):
        return _konfirmasi(db, sesi, draft)

    field = fields[sesi.field_index]
    pertanyaan, pilihan = _prompt_field(field)
    total = len(fields)
    return [
        f"Data {sesi.field_index + 1} dari {total}.\n{pertanyaan}",
    ], pilihan


def _konfirmasi(
    db: Session, sesi: ConversationSession, draft: Application
) -> tuple[list[str], list[dict[str, str]]]:
    sesi.state = C.ChatState.KONFIRMASI.value
    draft.form_data = dict(sesi.slot_data or {})
    errors = appsvc.validasi_form(draft.service, draft.form_data)
    if errors:
        sesi.state = C.ChatState.SLOT_FILLING.value
        return ["Ada data yang belum lengkap: " + " ".join(errors)], []
    db.flush()
    return [_ringkasan(draft)], [
        {"label": "Ya, kirim", "value": "ya"},
        {"label": "Batal", "value": "batal"},
    ]


def _simpan_jawaban_field(
    db: Session, sesi: ConversationSession, pesan: str
) -> tuple[list[str], list[dict[str, str]]]:
    service = db.get(Service, sesi.service_id) if sesi.service_id else None
    if service is None:
        _reset(sesi)
        return ["Sesi pengajuan tidak ditemukan. Silakan mulai lagi dari menu."], []

    fields = _fields_service(service)
    if sesi.field_index >= len(fields):
        draft = db.get(Application, sesi.application_id) if sesi.application_id else None
        if draft is None:
            _reset(sesi)
            return ["Draft pengajuan hilang. Silakan mulai lagi."], []
        return _konfirmasi(db, sesi, draft)

    field = fields[sesi.field_index]
    nilai = pesan.strip()

    if field.tipe == "select" and field.pilihan:
        if nilai.isdigit() and 1 <= int(nilai) <= len(field.pilihan):
            nilai = field.pilihan[int(nilai) - 1]
        else:
            cocok = [p for p in field.pilihan if p.lower() == nilai.lower()]
            if cocok:
                nilai = cocok[0]

    if field.tipe == "nik":
        nilai = "".join(ch for ch in nilai if ch.isdigit())
    if field.tipe == "phone":
        nilai = "".join(ch for ch in nilai if ch.isdigit() or ch == "+")

    percobaan = dict(sesi.slot_data or {})
    percobaan[field.nama_field] = nilai
    pesan_error = appsvc.validasi_nilai(field, nilai)
    if pesan_error:
        pertanyaan, pilihan = _prompt_field(field)
        return [f"⚠️ {pesan_error}\n\n{pertanyaan}"], pilihan

    if field.tipe == "nik":
        warga = appsvc.cari_citizen(db, nilai)
        if warga is not None and not warga.aktif:
            pertanyaan, pilihan = _prompt_field(field)
            return [
                "⚠️ NIK ini tercatat nonaktif. Hubungi kantor desa untuk "
                f"mengaktifkan kembali.\n\n{pertanyaan}"
            ], pilihan
        if warga is not None:
            # Identitas dari data warga mengisi field lain; warga hanya perlu
            # mengonfirmasi lalu menjawab field khusus layanan.
            sesi.slot_data = {**percobaan, **_nilai_identitas(warga, fields)}
            sesi.state = C.ChatState.KONFIRMASI_WARGA.value
            return [_kartu_warga(warga, fields)], PILIHAN_KONFIRMASI_WARGA

    sesi.slot_data = percobaan
    sesi.field_index += 1

    draft = db.get(Application, sesi.application_id) if sesi.application_id else None
    if draft is not None:
        draft.form_data = dict(percobaan)
        db.flush()

    while sesi.field_index < len(fields) and str(
        (sesi.slot_data or {}).get(fields[sesi.field_index].nama_field, "")
    ).strip():
        sesi.field_index += 1

    if sesi.field_index >= len(fields):
        if draft is None:
            _reset(sesi)
            return ["Draft pengajuan hilang. Silakan mulai lagi."], []
        return _konfirmasi(db, sesi, draft)

    berikut = fields[sesi.field_index]
    pertanyaan, pilihan = _prompt_field(berikut)
    return [f"Data {sesi.field_index + 1} dari {len(fields)}.\n{pertanyaan}"], pilihan


# --------------------------------------------------------------------------- #
# Penanganan pesan
# --------------------------------------------------------------------------- #
def _jawab_info(db: Session, sesi: ConversationSession, intent: str) -> list[str]:
    if intent in INFO_LAYANAN:
        service = _layanan(db, INFO_LAYANAN[intent])
        if service:
            return [_syarat_text(service)]
    faq = _faq_untuk(db, intent)
    if faq:
        return [faq.jawaban]
    return ["Informasi tersebut belum tersedia. Silakan hubungi petugas desa."]


def _jawab_faq_bebas(db: Session, teks: str) -> tuple[list[str], int | None] | None:
    hasil = cocokkan_faq(teks, _semua_faq(db))
    if hasil is None:
        return None
    faq, _skor = hasil
    return [faq["jawaban"]], faq["id"]


def _jawab_status(db: Session, sesi: ConversationSession, pesan: str) -> tuple[list[str], list[dict[str, str]], str | None]:
    """Lacak status pengajuan. NIK wajib karena nomor tiket berurutan.

    Nomor tiket berbentuk `APP-{tahun}-{id urut}` sehingga mudah ditebak.
    Tanpa NIK, siapa pun bisa membaca status dan tautan unduh surat orang
    lain. Karena itu tiket saja hanya membuka permintaan NIK.
    """
    cocok = TIKET_RE.search(pesan)
    nik = _ekstrak_nik(pesan)
    tiket = cocok.group(0).upper() if cocok else (sesi.slot_data or {}).get("_tiket")

    if not tiket:
        sesi.state = C.ChatState.TRACKING.value
        return (
            [
                "Silakan kirim nomor tiket pengajuan Anda.\n"
                "Contoh: APP-2026-000123. Nomor tiket dikirim saat pengajuan diterima."
            ],
            [],
            None,
        )

    if not nik:
        sesi.state = C.ChatState.TRACKING.value
        sesi.slot_data = {**(sesi.slot_data or {}), "_tiket": tiket}
        return (
            [
                f"Tiket {tiket}.\n"
                "Untuk membuka status, kirim NIK pemohon (16 digit) pada pesan yang sama "
                "atau pesan berikutnya."
            ],
            [],
            None,
        )

    app = appsvc.lacak(db, tiket, nik)
    sesi.slot_data = {k: v for k, v in (sesi.slot_data or {}).items() if k != "_tiket"}
    sesi.state = C.ChatState.IDLE.value
    if app is None:
        # Pesan disamakan untuk tiket tidak ada dan NIK salah agar tidak bisa
        # dipakai menebak tiket mana yang benar-benar terdaftar.
        return (
            [
                f"Tiket {tiket} dengan NIK tersebut tidak ditemukan. "
                "Periksa kembali nomor tiket dan NIK Anda."
            ],
            [],
            None,
        )

    label = {
        C.Status.DRAFT.value: "masih draf (belum dikirim)",
        C.Status.MENUNGGU_VERIFIKASI.value: "menunggu verifikasi petugas",
        C.Status.DIPROSES.value: "sedang diproses",
        C.Status.TERBIT.value: "sudah terbit",
        C.Status.DITOLAK.value: "ditolak",
        C.Status.DIBATALKAN.value: "dibatalkan",
    }.get(app.status, app.status)

    balasan = [f"Tiket {app.ticket_no} — {app.service.nama}\nStatus: {label}."]
    dokumen = app.documents[-1] if app.documents else None
    if app.status == C.Status.TERBIT.value and dokumen is not None:
        if dokumen.status == "TERBIT":
            from app.security import sign_download

            balasan.append(
                f"Nomor surat: {dokumen.nomor_surat}\n"
                f"Unduh: {settings.app_url.rstrip('/')}/d/{sign_download(dokumen.id)}\n"
                "Tautan unduh berlaku 7 hari."
            )
        else:
            balasan.append(
                f"Nomor surat: {dokumen.nomor_surat}\n"
                "Surat ini telah dicabut oleh desa dan tidak dapat diunduh."
            )
    elif app.alasan_penolakan:
        balasan.append(f"Alasan: {app.alasan_penolakan}")
    elif app.status in {C.Status.MENUNGGU_VERIFIKASI.value, C.Status.DIPROSES.value}:
        balasan.append("Kami akan mengabari lagi setelah status berubah.")
    return balasan, [], app.ticket_no


def _tawarkan_eskalasi(sesi: ConversationSession) -> list[str]:
    sesi.state = C.ChatState.IDLE.value
    return [
        "Maaf, saya belum yakin memahami pertanyaan Anda.",
        "Pertanyaan Anda sudah dicatat untuk ditinjau petugas desa.",
        "Anda bisa memilih menu di bawah, atau ketik *petugas* untuk dihubungkan dengan petugas.",
    ]


def tangani(db: Session, sesi: ConversationSession, pesan: str) -> dict[str, Any]:
    """Proses satu pesan masuk dan kembalikan balasan terstruktur."""
    pesan = (pesan or "").strip()
    if not pesan:
        return {
            "session_id": sesi.id, "state": sesi.state,
            "balasan": ["Silakan ketik pesan Anda."], "pilihan": [],
        }

    _catat(db, sesi, "in", pesan)
    teks = pesan.lower()
    balasan: list[str] = []
    pilihan: list[dict[str, str]] = []
    intent: str | None = None
    confidence: float | None = None
    tiket: str | None = None
    perlu_petugas = False
    faq_id: int | None = None

    # --- perintah global -------------------------------------------------- #
    if teks in BATAL or (
        sesi.state == C.ChatState.KONFIRMASI_WARGA.value and teks == "3"
    ):
        draft = db.get(Application, sesi.application_id) if sesi.application_id else None
        if draft is not None and draft.status == C.Status.DRAFT.value:
            appsvc.transisi(
                db, draft, C.Status.DIBATALKAN.value, aktor=None,
                aktor_label="warga", catatan="Dibatalkan oleh warga melalui chat.",
            )
        _reset(sesi)
        balasan = ["Pengajuan dibatalkan. Ada yang bisa saya bantu lagi?"]
        pilihan = PILIHAN_MENU
        intent = "SISTEM_BATAL"

    elif teks in MENU:
        sesi.state = C.ChatState.MENU.value
        balasan = _menu_text(db)
        pilihan = PILIHAN_MENU
        intent = "SISTEM_MENU"

    # --- alur stateful ---------------------------------------------------- #
    elif sesi.state == C.ChatState.CONSENT.value:
        if teks in YA:
            service = db.get(Service, sesi.service_id) if sesi.service_id else None
            if service is None:
                _reset(sesi)
                balasan = ["Layanan tidak ditemukan. Silakan pilih dari menu."]
                pilihan = PILIHAN_MENU
            else:
                balasan, pilihan = _mulai_pengisian(db, sesi, service)
                intent = sesi.intent_kode
        elif teks in TIDAK:
            _reset(sesi)
            balasan = ["Baik, pengajuan tidak dilanjutkan. Ada yang bisa saya bantu?"]
            pilihan = PILIHAN_MENU
        else:
            balasan = ["Mohon jawab *ya* untuk melanjutkan atau *tidak* untuk membatalkan."]
            pilihan = [{"label": "Ya", "value": "ya"}, {"label": "Tidak", "value": "tidak"}]

    elif sesi.state == C.ChatState.SLOT_FILLING.value:
        balasan, pilihan = _simpan_jawaban_field(db, sesi, pesan)
        intent = sesi.intent_kode

    elif sesi.state == C.ChatState.KONFIRMASI_WARGA.value:
        balasan, pilihan = _jawab_konfirmasi_warga(db, sesi, pesan)
        intent = sesi.intent_kode

    elif sesi.state == C.ChatState.KONFIRMASI.value:
        draft = db.get(Application, sesi.application_id) if sesi.application_id else None
        if teks in YA and draft is not None:
            draft.form_data = dict(sesi.slot_data or {})
            try:
                appsvc.kirim_pengajuan(db, draft)
            except appsvc.KesalahanPengajuan as exc:
                balasan = [f"⚠️ {exc}", "Silakan periksa kembali data Anda atau hubungi petugas."]
                sesi.state = C.ChatState.SLOT_FILLING.value
                sesi.field_index = 0
            else:
                tiket = draft.ticket_no
                balasan = [
                    f"✅ Pengajuan diterima.\nNomor tiket: {draft.ticket_no}\n"
                    f"Status: menunggu verifikasi petugas.\n"
                    f"Simpan nomor ini untuk mengecek status."
                ]
                pilihan = [
                    {"label": "Cek status", "value": f"cek {draft.ticket_no}"},
                    {"label": "Selesai", "value": "terima kasih"},
                ]
                _reset(sesi)
                sesi.state = C.ChatState.IDLE.value
        elif teks in TIDAK:
            balasan = [
                "Baik, pengajuan belum dikirim. Ketik *ubah* untuk memperbaiki data, "
                "atau *batal* untuk membatalkan."
            ]
        elif teks in {"ubah", "edit", "revisi"}:
            sesi.state = C.ChatState.SLOT_FILLING.value
            sesi.field_index = 0
            service = db.get(Service, sesi.service_id) if sesi.service_id else None
            if service is None:
                _reset(sesi)
                balasan = ["Sesi pengajuan tidak ditemukan. Silakan mulai dari menu."]
                pilihan = PILIHAN_MENU
            else:
                field = _fields_service(service)[0]
                pertanyaan, pilihan = _prompt_field(field)
                balasan = [f"Data 1 dari {len(service.fields)}.\n{pertanyaan}"]
        else:
            balasan = ["Ketik *ya* untuk mengirim atau *batal* untuk membatalkan."]
            pilihan = [{"label": "Ya, kirim", "value": "ya"}, {"label": "Batal", "value": "batal"}]

    elif sesi.state == C.ChatState.TRACKING.value:
        balasan, pilihan, tiket = _jawab_status(db, sesi, pesan)
        intent = "CEK_STATUS"

    # --- nomor tiket dikirim langsung ------------------------------------- #
    elif TIKET_RE.search(pesan) and sesi.state in {C.ChatState.IDLE.value, C.ChatState.MENU.value}:
        balasan, pilihan, tiket = _jawab_status(db, sesi, pesan)
        intent = "CEK_STATUS"
        confidence = 1.0

    # --- klasifikasi ------------------------------------------------------ #
    else:
        hasil = nlp.prediksi(pesan)
        intent = hasil.intent
        confidence = hasil.confidence
        tinggi, rendah = _ambang(db)

        # Nomor menu lebih diutamakan bila sesi baru dibuka.
        if teks in {"1", "2", "3", "4"}:
            kode = _URUTAN_MENU[int(teks) - 1]
            service = _layanan(db, kode)
            if service:
                sesi.service_id = service.id
                sesi.intent_kode = f"AJUKAN_{kode}"
                sesi.state = C.ChatState.CONSENT.value
                balasan = [
                    f"Anda akan mengajukan {service.nama}.\n"
                    f"Syarat: {', '.join(service.syarat or ['tidak ada berkas tambahan'])}.\n\n"
                    "Data yang Anda isi hanya dipakai untuk pembuatan surat ini. "
                    "Lanjutkan pengisian data? (ya/tidak)"
                ]
                pilihan = [{"label": "Ya", "value": "ya"}, {"label": "Tidak", "value": "tidak"}]
                intent = f"AJUKAN_{kode}"
                confidence = 1.0
        elif teks in {"5"}:
            balasan, pilihan, tiket = _jawab_status(db, sesi, pesan)
            intent = "CEK_STATUS"
            confidence = 1.0
        elif teks in {"6"}:
            sesi.state = C.ChatState.ESKALASI.value
            balasan = [
                "Permintaan Anda diteruskan ke petugas desa. Petugas akan membalas pada "
                "jam kerja (Senin–Kamis 08.00–15.00, Jumat 08.00–11.00 WITA)."
            ]
            perlu_petugas = True
            intent = "BICARA_PETUGAS"
            confidence = 1.0
        elif intent is not None and confidence is not None and confidence >= tinggi:
            if intent in INTENT_LAYANAN:
                kode = INTENT_LAYANAN[intent]
                service = _layanan(db, kode)
                if service is None:
                    balasan = [f"Layanan {kode} sedang tidak tersedia."]
                else:
                    sesi.service_id = service.id
                    sesi.intent_kode = intent
                    sesi.state = C.ChatState.CONSENT.value
                    balasan = [
                        f"Anda akan mengajukan {service.nama}.\n"
                        f"Syarat: {', '.join(service.syarat or ['tidak ada berkas tambahan'])}.\n\n"
                        "Data yang Anda isi hanya dipakai untuk pembuatan surat ini. "
                        "Lanjutkan pengisian data? (ya/tidak)"
                    ]
                    pilihan = [
                        {"label": "Ya", "value": "ya"},
                        {"label": "Tidak", "value": "tidak"},
                    ]
            elif intent == "CEK_STATUS":
                balasan, pilihan, tiket = _jawab_status(db, sesi, pesan)
            elif intent == "BICARA_PETUGAS":
                sesi.state = C.ChatState.ESKALASI.value
                balasan = [
                    "Permintaan Anda diteruskan ke petugas desa. Petugas akan membalas pada "
                    "jam kerja (Senin–Kamis 08.00–15.00, Jumat 08.00–11.00 WITA)."
                ]
                perlu_petugas = True
            elif intent in {"SAPA", "TERIMA_KASIH"}:
                if intent == "SAPA":
                    balasan = _menu_text(db)
                    pilihan = PILIHAN_MENU
                    sesi.state = C.ChatState.MENU.value
                else:
                    balasan = [
                        "Sama-sama. Semoga bermanfaat. Layanan Desa Kampala siap membantu "
                        "pada jam kerja."
                    ]
            elif intent == "KOMPLAIN":
                faq = _faq_untuk(db, intent)
                balasan = [faq.jawaban if faq else "Keluhan Anda kami catat."]
                perlu_petugas = True
                sesi.state = C.ChatState.ESKALASI.value
            elif intent.startswith("INFO_"):
                balasan = _jawab_info(db, sesi, intent)
                faq = _faq_untuk(db, intent)
                faq_id = faq.id if faq else None
            else:
                balasan = _menu_text(db)
                pilihan = PILIHAN_MENU
        else:
            # Keyakinan sedang: coba cocokkan FAQ secara fuzzy sebelum menyerah.
            fuzzy = _jawab_faq_bebas(db, pesan) if (confidence or 0) >= rendah else None
            if fuzzy is not None:
                balasan, faq_id = fuzzy
                if intent is None:
                    intent = "FAQ_DEKAT"
            elif intent == "LAINNYA" or (confidence or 0) < rendah:
                balasan = _tawarkan_eskalasi(sesi)
                pilihan = PILIHAN_MENU
                perlu_petugas = True
            else:
                alternatif = hasil.peringkat
                tebakan = [k for k, _ in alternatif[:2] if k]
                balasan = [
                    "Maaf, saya belum sepenuhnya paham maksud Anda.",
                    "Mungkin yang Anda maksud: " + " atau ".join(tebakan) + "?"
                    if tebakan
                    else "Silakan pilih menu di bawah.",
                ]
                pilihan = PILIHAN_MENU
                sesi.state = C.ChatState.MENU.value

    for baris in balasan:
        _catat(db, sesi, "out", baris, intent=intent, confidence=confidence, faq_id=faq_id)
    db.flush()

    return {
        "session_id": sesi.id,
        "state": sesi.state,
        "balasan": balasan,
        "intent": intent,
        "confidence": confidence,
        "pilihan": pilihan,
        "tiket": tiket,
        "perlu_petugas": perlu_petugas,
    }
