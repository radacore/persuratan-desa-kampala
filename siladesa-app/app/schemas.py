"""Skema Pydantic untuk API JSON."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class SessionCreate(BaseModel):
    channel: Literal["web", "whatsapp", "telegram"] = "web"
    kontak: str = Field(default="web-anonim", max_length=60)
    nama: str | None = Field(default=None, max_length=120)


class SessionOut(BaseModel):
    session_id: str
    channel: str
    state: str
    balasan: list[str]
    pilihan: list[dict[str, str]] = []


class MessageIn(BaseModel):
    session_id: str = Field(min_length=6, max_length=40)
    pesan: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    session_id: str
    state: str
    balasan: list[str]
    intent: str | None = None
    confidence: float | None = None
    pilihan: list[dict[str, str]] = []
    tiket: str | None = None
    perlu_petugas: bool = False


class FeedbackIn(BaseModel):
    session_id: str
    rating: int = Field(ge=1, le=5)
    komentar: str | None = Field(default=None, max_length=1000)
    chat_message_id: int | None = None


# --------------------------------------------------------------------------- #
# Layanan
# --------------------------------------------------------------------------- #
class ServiceFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama_field: str
    label: str
    tipe: str
    wajib: bool
    urutan: int
    pilihan: list[str] | None = None
    placeholder: str | None = None
    bantuan: str | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kode: str
    nama: str
    deskripsi: str | None
    syarat: list[str] | None
    estimasi_hari: int
    aktif: bool
    fields: list[ServiceFieldOut] = []


# --------------------------------------------------------------------------- #
# Pengajuan
# --------------------------------------------------------------------------- #
class CitizenIn(BaseModel):
    nik: str = Field(pattern=r"^\d{16}$")
    nama_lengkap: str = Field(min_length=2, max_length=120)
    jenis_kelamin: Literal["Laki-Laki", "Perempuan"] | None = None
    tempat_lahir: str | None = None
    tanggal_lahir: date | None = None
    agama: str | None = None
    status_perkawinan: str | None = None
    pekerjaan: str | None = None
    alamat: str | None = None
    dusun: str | None = None
    rt: str | None = None
    rw: str | None = None
    no_hp: str | None = None
    email: str | None = None

    @field_validator("nik")
    @classmethod
    def _cek_prefix(cls, v: str) -> str:
        if not v.startswith("7304"):
            raise ValueError("NIK bukan wilayah Kabupaten Jeneponto (harus diawali 7304).")
        return v


class ApplicationCreate(BaseModel):
    service_kode: str
    citizen: CitizenIn
    form_data: dict[str, Any] = {}
    channel: Literal["web", "whatsapp", "telegram"] = "web"
    session_id: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_no: str
    status: str
    channel: str
    created_at: datetime
    submitted_at: datetime | None = None
    issued_at: datetime | None = None
    service_kode: str | None = None
    service_nama: str | None = None


class TrackingOut(BaseModel):
    ticket_no: str
    status: str
    service_nama: str
    pemohon: str
    dibuat: datetime
    diperbarui: datetime
    nomor_surat: str | None = None
    nomor_surat_dicabut: str | None = None
    dokumen_terbit: bool = False
    unduh_url: str | None = None
    catatan: str | None = None
    riwayat: list[dict[str, Any]] = []


class StatusChangeIn(BaseModel):
    status: Literal["MENUNGGU_VERIFIKASI", "DIPROSES", "TERBIT", "DITOLAK", "DIBATALKAN"]
    catatan: str | None = Field(default=None, max_length=1000)
    nomor_surat: str | None = None


# --------------------------------------------------------------------------- #
# Verifikasi dokumen
# --------------------------------------------------------------------------- #
class VerifyOut(BaseModel):
    valid: bool
    hasil: Literal["VALID", "DIBATALKAN", "TIDAK_DITEMUKAN"]
    nomor_surat: str | None = None
    jenis_surat: str | None = None
    nama_pemohon: str | None = None
    nik_masked: str | None = None
    tanggal_terbit: datetime | None = None
    sha256: str | None = None
    berkas_utuh: bool = True
    pesan: str


# --------------------------------------------------------------------------- #
# Admin / konten
# --------------------------------------------------------------------------- #
class FaqIn(BaseModel):
    pertanyaan: str = Field(min_length=5)
    jawaban: str = Field(min_length=5)
    intent_kode: str | None = None
    kata_kunci: list[str] = []
    aktif: bool = True
    urutan: int = 0


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pertanyaan: str
    jawaban: str
    kata_kunci: list[str] | None
    aktif: bool
    urutan: int


class AdminUserIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    nama_lengkap: str = Field(min_length=2, max_length=120)
    role: Literal["operator", "sekdes", "kepala_desa", "admin_teknis"]
    password: str = Field(min_length=10, max_length=128)


class TrainIn(BaseModel):
    catatan: str | None = None
    aktifkan: bool = True


class PredictIn(BaseModel):
    teks: str = Field(min_length=1, max_length=1000)


class PredictOut(BaseModel):
    intent: str | None
    confidence: float
    keputusan: Literal["jawab", "klarifikasi", "eskalasi"]
    alternatif: list[dict[str, Any]] = []
