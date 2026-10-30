"""Model ORM SILADESA — 22 tabel sesuai `prd-siladesa/DATABASE.md`.

Konvensi:
- Nama tabel tunggal, huruf kecil, snake_case.
- Status/role disimpan sebagai VARCHAR dengan CHECK, bukan tipe ENUM native,
  agar portabel antara SQLite (dev) dan PostgreSQL (produksi).
- `application.form_data` adalah snapshot JSON: perubahan data warga setelah
  surat terbit tidak boleh mengubah isi dokumen yang sudah diterbitkan.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


# --------------------------------------------------------------------------- #
# 1. admin_user
# --------------------------------------------------------------------------- #
class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    nama_lengkap: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "role IN ('operator','sekdes','kepala_desa','admin_teknis')",
            name="ck_admin_user_role",
        ),
    )


# --------------------------------------------------------------------------- #
# 2. citizen
# --------------------------------------------------------------------------- #
class Citizen(TimestampMixin, Base):
    __tablename__ = "citizen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nik: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    nama_lengkap: Mapped[str] = mapped_column(String(120), nullable=False)
    jenis_kelamin: Mapped[str | None] = mapped_column(String(12))
    tempat_lahir: Mapped[str | None] = mapped_column(String(80))
    tanggal_lahir: Mapped[date | None] = mapped_column(Date)
    agama: Mapped[str | None] = mapped_column(String(20))
    status_perkawinan: Mapped[str | None] = mapped_column(String(20))
    pekerjaan: Mapped[str | None] = mapped_column(String(80))
    alamat: Mapped[str | None] = mapped_column(Text)
    dusun: Mapped[str | None] = mapped_column(String(40))
    rt: Mapped[str | None] = mapped_column(String(5))
    rw: Mapped[str | None] = mapped_column(String(5))
    no_hp: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    applications: Mapped[list["Application"]] = relationship(back_populates="citizen")

    __table_args__ = (
        CheckConstraint("length(nik) = 16", name="ck_citizen_nik_panjang"),
        CheckConstraint(
            "jenis_kelamin IS NULL OR jenis_kelamin IN ('Laki-Laki','Perempuan')",
            name="ck_citizen_jk",
        ),
        Index("ix_citizen_nama", "nama_lengkap"),
    )


# --------------------------------------------------------------------------- #
# 3. service
# --------------------------------------------------------------------------- #
class Service(TimestampMixin, Base):
    __tablename__ = "service"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    deskripsi: Mapped[str | None] = mapped_column(Text)
    syarat: Mapped[list | None] = mapped_column(JSONType, default=list)
    estimasi_hari: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    fields: Mapped[list["ServiceField"]] = relationship(
        back_populates="service", cascade="all, delete-orphan", order_by="ServiceField.urutan"
    )
    templates: Mapped[list["LetterTemplate"]] = relationship(back_populates="service")
    applications: Mapped[list["Application"]] = relationship(back_populates="service")


# --------------------------------------------------------------------------- #
# 4. service_field
# --------------------------------------------------------------------------- #
class ServiceField(Base):
    __tablename__ = "service_field"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nama_field: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    tipe: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    wajib: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pilihan: Mapped[list | None] = mapped_column(JSONType)
    validator: Mapped[str | None] = mapped_column(String(40))
    placeholder: Mapped[str | None] = mapped_column(String(160))
    bantuan: Mapped[str | None] = mapped_column(String(255))

    service: Mapped[Service] = relationship(back_populates="fields")

    __table_args__ = (
        UniqueConstraint("service_id", "nama_field", name="uq_service_field"),
        CheckConstraint(
            "tipe IN ('text','textarea','date','select','number','phone','nik','email')",
            name="ck_service_field_tipe",
        ),
    )


# --------------------------------------------------------------------------- #
# 5. letter_template
# --------------------------------------------------------------------------- #
class LetterTemplate(TimestampMixin, Base):
    __tablename__ = "letter_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    versi: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    konten_html: Mapped[str] = mapped_column(Text, nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"))

    service: Mapped[Service] = relationship(back_populates="templates")

    __table_args__ = (
        # Satu template aktif per layanan.
        Index(
            "uq_letter_template_aktif",
            "service_id",
            unique=True,
            sqlite_where=(aktif == True),  # noqa: E712
            postgresql_where=(aktif == True),  # noqa: E712
        ),
    )


# --------------------------------------------------------------------------- #
# 6. application
# --------------------------------------------------------------------------- #
class Application(TimestampMixin, Base):
    __tablename__ = "application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id"), nullable=False, index=True)
    # Nullable selama status DRAFT: warga belum tentu sudah mengisi NIK.
    citizen_id: Mapped[int | None] = mapped_column(ForeignKey("citizen.id"), index=True)
    status: Mapped[str] = mapped_column(String(25), default="DRAFT", nullable=False, index=True)
    form_data: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    catatan_operator: Mapped[str | None] = mapped_column(Text)
    alasan_penolakan: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(15), default="web", nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(40), index=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    service: Mapped[Service] = relationship(back_populates="applications")
    citizen: Mapped[Citizen | None] = relationship(back_populates="applications")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.created_at",
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','MENUNGGU_VERIFIKASI','DIPROSES','TERBIT','DITOLAK','DIBATALKAN')",
            name="ck_application_status",
        ),
        CheckConstraint("channel IN ('web','whatsapp','telegram')", name="ck_application_channel"),
        Index("ix_application_status_created", "status", "created_at"),
    )


# --------------------------------------------------------------------------- #
# 7. application_event
# --------------------------------------------------------------------------- #
class ApplicationEvent(Base):
    __tablename__ = "application_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dari_status: Mapped[str | None] = mapped_column(String(25))
    ke_status: Mapped[str] = mapped_column(String(25), nullable=False)
    aktor_id: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"))
    aktor_label: Mapped[str] = mapped_column(String(120), nullable=False)
    catatan: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )

    application: Mapped[Application] = relationship(back_populates="events")


# --------------------------------------------------------------------------- #
# 8. document
# --------------------------------------------------------------------------- #
class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[int | None] = mapped_column(ForeignKey("letter_template.id", ondelete="SET NULL"))
    nomor_surat: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qr_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(15), default="DRAFT", nullable=False)
    issued_by: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: FR-20: waktu dokumen benar-benar terkirim ke percakapan warga.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    application: Mapped[Application] = relationship(back_populates="documents")
    scans: Mapped[list["VerificationScan"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','TERBIT','DIBATALKAN')", name="ck_document_status"),
        # Satu pengajuan menghasilkan tepat satu surat. Invarian ini menahan
        # penerbitan ganda (dua klik / dua operator) yang akan memakai dua
        # nomor surat untuk satu berkas.
        UniqueConstraint("application_id", name="uq_document_application"),
    )


# --------------------------------------------------------------------------- #
# 9. official
# --------------------------------------------------------------------------- #
class Official(TimestampMixin, Base):
    __tablename__ = "official"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    nip: Mapped[str | None] = mapped_column(String(30))
    jabatan: Mapped[str] = mapped_column(String(80), nullable=False)
    pangkat: Mapped[str | None] = mapped_column(String(80))
    ttd_path: Mapped[str | None] = mapped_column(String(255))
    #: Tanggal terakhir pejabat boleh menandatangani; NULL berarti tanpa batas.
    berlaku_sampai: Mapped[date | None] = mapped_column(Date)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        # Satu pejabat aktif per jabatan.
        Index(
            "uq_official_aktif",
            "jabatan",
            unique=True,
            sqlite_where=(aktif == True),  # noqa: E712
            postgresql_where=(aktif == True),  # noqa: E712
        ),
    )


# --------------------------------------------------------------------------- #
# 10. verification_scan
# --------------------------------------------------------------------------- #
class VerificationScan(Base):
    __tablename__ = "verification_scan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("document.id", ondelete="SET NULL"), index=True
    )
    qr_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    hasil: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )

    document: Mapped[Document | None] = relationship(back_populates="scans")

    __table_args__ = (
        CheckConstraint(
            "hasil IN ('VALID','DIBATALKAN','TIDAK_DITEMUKAN')", name="ck_scan_hasil"
        ),
    )


# --------------------------------------------------------------------------- #
# 11. audit_log
# --------------------------------------------------------------------------- #
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(String(160))
    aksi: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entitas: Mapped[str] = mapped_column(String(40), nullable=False)
    entitas_id: Mapped[str | None] = mapped_column(String(40))
    detail: Mapped[dict | None] = mapped_column(JSONType)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )


# --------------------------------------------------------------------------- #
# 12. intent
# --------------------------------------------------------------------------- #
class Intent(TimestampMixin, Base):
    __tablename__ = "intent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    jenis: Mapped[str] = mapped_column(String(10), nullable=False)
    deskripsi: Mapped[str | None] = mapped_column(Text)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("jenis IN ('info','ajukan','faq','sistem')", name="ck_intent_jenis"),
    )


# --------------------------------------------------------------------------- #
# 13. faq
# --------------------------------------------------------------------------- #
class Faq(TimestampMixin, Base):
    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_id: Mapped[int | None] = mapped_column(ForeignKey("intent.id", ondelete="SET NULL"))
    pertanyaan: Mapped[str] = mapped_column(Text, nullable=False)
    jawaban: Mapped[str] = mapped_column(Text, nullable=False)
    kata_kunci: Mapped[list | None] = mapped_column(JSONType, default=list)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    intent: Mapped[Intent | None] = relationship()


# --------------------------------------------------------------------------- #
# 14. training_sample
# --------------------------------------------------------------------------- #
class TrainingSample(Base):
    __tablename__ = "training_sample"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_kode: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    teks: Mapped[str] = mapped_column(Text, nullable=False)
    sumber: Mapped[str] = mapped_column(String(20), default="seed", nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        CheckConstraint("sumber IN ('seed','koreksi','manual')", name="ck_sample_sumber"),
    )


# --------------------------------------------------------------------------- #
# 15. nlp_model
# --------------------------------------------------------------------------- #
class NlpModel(Base):
    __tablename__ = "nlp_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    versi: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    akurasi: Mapped[float | None] = mapped_column()
    macro_f1: Mapped[float | None] = mapped_column()
    jumlah_sampel: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jumlah_intent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dilatih_oleh: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"))
    catatan: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    metrics: Mapped[list["ModelMetric"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Hanya satu model aktif.
        Index(
            "uq_nlp_model_aktif",
            "aktif",
            unique=True,
            sqlite_where=(aktif == True),  # noqa: E712
            postgresql_where=(aktif == True),  # noqa: E712
        ),
    )


# --------------------------------------------------------------------------- #
# 16. model_metric
# --------------------------------------------------------------------------- #
class ModelMetric(Base):
    __tablename__ = "model_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("nlp_model.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    precision: Mapped[float] = mapped_column(nullable=False)
    recall: Mapped[float] = mapped_column(nullable=False)
    f1: Mapped[float] = mapped_column(nullable=False)
    support: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    model: Mapped[NlpModel] = relationship(back_populates="metrics")


# --------------------------------------------------------------------------- #
# 17. conversation_session
# --------------------------------------------------------------------------- #
class ConversationSession(Base):
    __tablename__ = "conversation_session"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    channel: Mapped[str] = mapped_column(String(15), nullable=False)
    kontak: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), default="IDLE", nullable=False)
    intent_kode: Mapped[str | None] = mapped_column(String(40))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("service.id", ondelete="SET NULL"))
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("application.id", ondelete="SET NULL")
    )
    slot_data: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    field_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    __table_args__ = (
        CheckConstraint("channel IN ('web','whatsapp','telegram')", name="ck_session_channel"),
    )


# --------------------------------------------------------------------------- #
# 18. chat_message
# --------------------------------------------------------------------------- #
class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    arah: Mapped[str] = mapped_column(String(3), nullable=False)
    isi: Mapped[str] = mapped_column(Text, nullable=False)
    intent_kode: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column()
    faq_id: Mapped[int | None] = mapped_column(ForeignKey("faq.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )

    session: Mapped[ConversationSession] = relationship(back_populates="messages")

    __table_args__ = (CheckConstraint("arah IN ('in','out')", name="ck_message_arah"),)


# --------------------------------------------------------------------------- #
# 19. feedback_response
# --------------------------------------------------------------------------- #
class FeedbackResponse(Base):
    __tablename__ = "feedback_response"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_message.id", ondelete="SET NULL")
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    komentar: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),)


# --------------------------------------------------------------------------- #
# 20. attachment
# --------------------------------------------------------------------------- #
class Attachment(Base):
    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nama_file: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    ukuran: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(20), default="warga", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    application: Mapped[Application] = relationship(back_populates="attachments")


# --------------------------------------------------------------------------- #
# 21. letter_number_counter
# --------------------------------------------------------------------------- #
class LetterNumberCounter(Base):
    __tablename__ = "letter_number_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode: Mapped[str] = mapped_column(String(10), default="DKP", nullable=False)
    tahun: Mapped[int] = mapped_column(Integer, nullable=False)
    bulan: Mapped[int] = mapped_column(Integer, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("kode", "tahun", "bulan", name="uq_counter_periode"),
        CheckConstraint("bulan BETWEEN 1 AND 12", name="ck_counter_bulan"),
    )


# --------------------------------------------------------------------------- #
# 22. setting
# --------------------------------------------------------------------------- #
class Setting(Base):
    __tablename__ = "setting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kunci: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    nilai: Mapped[str] = mapped_column(Text, nullable=False)
    tipe: Mapped[str] = mapped_column(String(10), default="string", nullable=False)
    deskripsi: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


__all__ = [
    "AdminUser",
    "Application",
    "ApplicationEvent",
    "Attachment",
    "AuditLog",
    "ChatMessage",
    "Citizen",
    "ConversationSession",
    "Document",
    "Faq",
    "FeedbackResponse",
    "Intent",
    "LetterNumberCounter",
    "LetterTemplate",
    "ModelMetric",
    "NlpModel",
    "Official",
    "Service",
    "ServiceField",
    "Setting",
    "TrainingSample",
    "VerificationScan",
]
