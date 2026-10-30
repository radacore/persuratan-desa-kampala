"""Kualitas model NLP dan kontrak layanan klasifikasi."""

from __future__ import annotations


def test_model_siap(client):
    data = client.get("/health").json()
    assert data["model_siap"] is True
    assert data["model_nlp"]


def test_klasifikasi_kalimat_umum(client):
    from app.services.nlp import nlp

    kasus = [
        ("syarat bikin surat domisili apa aja", "INFO_SYARAT_DOMISILI"),
        ("saya mau mengajukan surat keterangan tidak mampu", "AJUKAN_SKTM"),
        ("berapa lama pengurusan surat usaha", "INFO_LAMA_PROSES"),
        ("cara lacak pengajuan surat", "CEK_STATUS"),
        ("terima kasih banyak", "TERIMA_KASIH"),
    ]
    for teks, harapan in kasus:
        hasil = nlp.prediksi(teks)
        assert hasil is not None, teks
        assert hasil.intent == harapan, f"{teks!r} -> {hasil.intent}, bukan {harapan}"
        assert hasil.confidence >= 0.4


def test_metrik_model_memenuhi_ambang(client):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import NlpModel

    with SessionLocal() as db:
        model = db.execute(select(NlpModel).where(NlpModel.aktif.is_(True))).scalar_one()
        assert model.macro_f1 >= 0.80
        assert model.akurasi >= 0.85
        assert model.jumlah_intent >= 18


def test_dataset_seimbang(client):
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import TrainingSample

    with SessionLocal() as db:
        jumlah = dict(
            db.execute(
                select(TrainingSample.intent_kode, func.count(TrainingSample.id))
                .where(TrainingSample.aktif.is_(True))
                .group_by(TrainingSample.intent_kode)
            ).all()
        )
    assert len(jumlah) >= 18
    assert min(jumlah.values()) >= 5, jumlah
