"""Seed data awal: katalog, FAQ, pejabat, pengaturan, akun admin, dan model NLP.

Jalankan: `python -m app.seed` (idempoten — aman diulang).
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import select

from app import constants as C
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import (
    AdminUser,
    Faq,
    Intent,
    LetterTemplate,
    ModelMetric,
    NlpModel,
    Official,
    Service,
    ServiceField,
    Setting,
    TrainingSample,
)
from app.seed_data.dataset import sampel_berlabel
from app.seed_data.katalog import FAQS, INTENTS, OFFICIALS, SERVICES, SETTINGS, TEMPLATES
from app.security import hash_password
from app.services.nlp import nlp

log = logging.getLogger("siladesa.seed")


def seed_intents(db) -> dict[str, Intent]:
    hasil: dict[str, Intent] = {}
    for item in INTENTS:
        row = db.execute(select(Intent).where(Intent.kode == item["kode"])).scalar_one_or_none()
        if row is None:
            row = Intent(**item)
            db.add(row)
        # Baris yang sudah ada tidak ditimpa: deskripsi/nama intent bisa
        # disunting petugas dan tidak boleh kembali ke nilai seed.
        hasil[item["kode"]] = row
    db.flush()
    return hasil


def seed_services(db) -> dict[str, Service]:
    hasil: dict[str, Service] = {}
    for item in SERVICES:
        row = db.execute(select(Service).where(Service.kode == item["kode"])).scalar_one_or_none()
        data = {k: v for k, v in item.items() if k != "fields"}
        if row is None:
            row = Service(**data)
            db.add(row)
            db.flush()
        # Layanan yang sudah ada dianggap milik admin: nama, syarat, dan field
        # tidak dikembalikan ke nilai seed saat kontainer restart.
        db.flush()

        ada = {f.nama_field: f for f in row.fields}
        for spec in item["fields"]:
            if spec["nama_field"] not in ada:
                db.add(ServiceField(service_id=row.id, **spec))
        db.flush()
        hasil[item["kode"]] = row
    return hasil


def seed_templates(db, services: dict[str, Service]) -> None:
    for kode, konten in TEMPLATES.items():
        service = services[kode]
        ada = db.execute(
            select(LetterTemplate).where(LetterTemplate.service_id == service.id)
        ).scalars().first()
        if ada is None:
            db.add(
                LetterTemplate(
                    service_id=service.id,
                    nama=f"Template {service.nama}",
                    versi=1,
                    konten_html=konten,
                    aktif=True,
                )
            )
    db.flush()


def seed_faqs(db, intents: dict[str, Intent]) -> None:
    for item in FAQS:
        ada = db.execute(select(Faq).where(Faq.pertanyaan == item["pertanyaan"])).scalar_one_or_none()
        if ada is not None:
            # Jawaban yang sudah disunting petugas tidak dikembalikan ke seed.
            continue
        db.add(
            Faq(
                intent_id=intents[item["intent_kode"]].id,
                pertanyaan=item["pertanyaan"],
                jawaban=item["jawaban"],
                kata_kunci=item["kata_kunci"],
                aktif=True,
            )
        )
    db.flush()


def seed_officials(db) -> None:
    for item in OFFICIALS:
        ada = db.execute(select(Official).where(Official.jabatan == item["jabatan"])).scalar_one_or_none()
        if ada is None:
            db.add(Official(**item))
        # Nama pejabat bisa dikoreksi petugas; seed tidak mengembalikannya.
    db.flush()


def seed_settings(db) -> None:
    for item in SETTINGS:
        ada = db.execute(select(Setting).where(Setting.kunci == item["kunci"])).scalar_one_or_none()
        if ada is None:
            db.add(Setting(**item))
        # Nilai pengaturan (nama desa, ambang keyakinan, penanda tangan) adalah
        # milik admin; seed hanya mengisi kunci yang belum ada.
    db.flush()


def seed_samples(db) -> int:
    ada = db.execute(select(TrainingSample.id).limit(1)).first()
    if ada is not None:
        return 0
    jumlah = 0
    for teks, intent in sampel_berlabel():
        db.add(TrainingSample(intent_kode=intent, teks=teks, sumber="seed", aktif=True))
        jumlah += 1
    db.flush()
    return jumlah


def seed_admin(db, email: str, password: str) -> AdminUser:
    row = db.execute(select(AdminUser).where(AdminUser.email == email)).scalar_one_or_none()
    if row is not None:
        return row
    row = AdminUser(
        email=email,
        nama_lengkap="Administrator Desa",
        password_hash=hash_password(password),
        role=C.Role.ADMIN_TEKNIS.value,
        aktif=True,
    )
    db.add(row)
    db.flush()
    return row


#: Akun contoh untuk mencoba alur persetujuan. Hanya dibuat di luar produksi.
DEMO_USERS = (
    ("operator@desakampala.id", "Operator Loket", C.Role.OPERATOR),
    ("sekdes@desakampala.id", "Sekretaris Desa", C.Role.SEKDES),
    ("kepaladesa@desakampala.id", "Kepala Desa", C.Role.KEPALA_DESA),
)


def seed_demo_users(db, password: str) -> list[AdminUser]:
    if settings.is_production:
        return []
    hasil: list[AdminUser] = []
    for email, nama, peran in DEMO_USERS:
        row = db.execute(select(AdminUser).where(AdminUser.email == email)).scalar_one_or_none()
        if row is None:
            row = AdminUser(
                email=email,
                nama_lengkap=nama,
                password_hash=hash_password(password),
                role=peran.value,
                aktif=True,
            )
            db.add(row)
        hasil.append(row)
    db.flush()
    return hasil


def seed_model(db, admin: AdminUser | None = None) -> NlpModel | None:
    ada = db.execute(select(NlpModel).where(NlpModel.aktif.is_(True))).scalar_one_or_none()
    if ada is not None:
        log.info("Model aktif sudah ada: %s", ada.versi)
        return ada

    rows = db.execute(
        select(TrainingSample).where(TrainingSample.aktif.is_(True))
    ).scalars().all()
    sampel = [(r.teks, r.intent_kode) for r in rows]
    if len(sampel) < 30:
        log.warning("Sampel latih hanya %d; lewati pelatihan.", len(sampel))
        return None

    log.info("Melatih model NLP dari %d sampel ...", len(sampel))
    hasil = nlp.latih(sampel, catatan="Pelatihan otomatis saat seed.")

    db.execute(
        NlpModel.__table__.update().where(NlpModel.aktif.is_(True)).values(aktif=False)
    )
    model = NlpModel(
        versi=hasil.versi,
        file_path=hasil.file_path,
        aktif=True,
        akurasi=hasil.akurasi,
        macro_f1=hasil.macro_f1,
        jumlah_sampel=hasil.jumlah_sampel,
        jumlah_intent=hasil.jumlah_intent,
        dilatih_oleh=admin.id if admin else None,
        catatan=f"Pelatihan otomatis saat seed. Evaluasi: {hasil.metode}.",
    )
    db.add(model)
    db.flush()
    for m in hasil.metrik_per_kelas:
        db.add(ModelMetric(model_id=model.id, **m))
    db.flush()
    log.info("Model %s aktif (akurasi %.3f, macro F1 %.3f)", model.versi, model.akurasi, model.macro_f1)
    return model


def jalankan(*, reset: bool = False) -> None:
    if reset:
        log.warning("Menghapus seluruh tabel (--reset).")
        Base.metadata.drop_all(bind=engine)
    # Di produksi skema hanya boleh dibuat oleh Alembic: `create_all` di sini
    # akan menambahkan tabel baru tanpa revisi, membuat `alembic_version`
    # menyesatkan. Entrypoint sudah menjalankan `alembic upgrade head`.
    if not settings.is_production:
        Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        intents = seed_intents(db)
        services = seed_services(db)
        seed_templates(db, services)
        seed_faqs(db, intents)
        seed_officials(db)
        seed_settings(db)
        jumlah_sampel = seed_samples(db)
        admin = seed_admin(db, settings.bootstrap_admin_email, settings.bootstrap_admin_password)
        demo = seed_demo_users(db, settings.bootstrap_demo_password)
        db.commit()

        if jumlah_sampel:
            log.info("%d sampel latih awal ditambahkan.", jumlah_sampel)

        model = seed_model(db, admin)
        db.commit()

        print("\nSILADESA siap.")
        print(f"  Layanan     : {', '.join(services)}")
        print(f"  Intent      : {len(intents)}")
        print(f"  Akun admin  : {settings.bootstrap_admin_email}")
        if demo:
            print(f"  Akun demo   : {', '.join(u.email for u in demo)} (sandi {settings.bootstrap_demo_password})")
        if model:
            print(f"  Model NLP   : {model.versi} (akurasi {model.akurasi:.3f}, macro F1 {model.macro_f1:.3f})")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed basis data SILADESA")
    parser.add_argument("--reset", action="store_true", help="hapus semua tabel sebelum seed")
    parser.add_argument("--retrain", action="store_true", help="latih ulang model NLP")
    args = parser.parse_args()

    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")

    if args.retrain:
        with SessionLocal() as db:
            db.execute(NlpModel.__table__.update().values(aktif=False))
            db.commit()
        jalankan(reset=args.reset)
        return

    jalankan(reset=args.reset)


if __name__ == "__main__":
    main()
