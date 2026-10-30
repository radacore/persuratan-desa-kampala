"""Percakapan: klasifikasi, slot-filling, dan penerbitan tiket."""

from __future__ import annotations

from conftest import buat_pengajuan_domisili, nik_unik


def _sesi(client, kontak: str | None = None) -> str:
    if kontak is None:
        import random

        kontak = "08" + "".join(str(random.randint(0, 9)) for _ in range(10))
    r = client.post("/api/v1/chat/sessions", json={"channel": "web", "kontak": kontak})
    assert r.status_code == 201, r.text[:300]
    data = r.json()
    assert data["balasan"], "sapaan tidak boleh kosong"
    assert data["pilihan"], "menu awal harus punya pilihan"
    return data["session_id"]


def _kirim(client, sid: str, pesan: str) -> dict:
    r = client.post("/api/v1/chat/messages", json={"session_id": sid, "pesan": pesan})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def test_sapaan_awal(client):
    data = client.post(
        "/api/v1/chat/sessions", json={"channel": "web", "kontak": "081200000002"}
    ).json()
    teks = " ".join(data["balasan"]).lower()
    assert "selamat datang" in teks
    assert data["state"] in {"MENU", "IDLE"}


def test_sesi_tidak_dikenal(client):
    r = client.post(
        "/api/v1/chat/messages", json={"session_id": "tidak-ada", "pesan": "halo"}
    )
    assert r.status_code == 404


def test_tanya_syarat_domisili(client):
    sid = _sesi(client)
    data = _kirim(client, sid, "apa syarat surat keterangan domisili")
    teks = " ".join(data["balasan"]).lower()
    assert "syarat" in teks
    assert "ktp" in teks


def test_pertanyaan_di_luar_cakupan(client):
    sid = _sesi(client)
    data = _kirim(client, sid, "bagaimana cara membuat paspor di imigrasi")
    teks = " ".join(data["balasan"]).lower()
    assert "petugas" in teks or "belum" in teks or "hubungi" in teks


def test_validasi_nik_ditolak(client):
    sid = _sesi(client)
    _kirim(client, sid, "1")
    _kirim(client, sid, "1")
    data = _kirim(client, sid, "ya")
    teks = " ".join(data["balasan"]).lower()
    assert "nik" in teks
    data = _kirim(client, sid, "123")
    teks = " ".join(data["balasan"]).lower()
    assert "16" in teks or "digit" in teks or "valid" in teks


def test_alur_lengkap_menghasilkan_tiket(client):
    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)
    assert tiket.startswith("APP-")
    assert len(tiket.split("-")[-1]) == 6

    lacak = client.get(f"/lacak?tiket={tiket}&nik={nik}")
    assert tiket in lacak.text
    assert "MENUNGGU" in lacak.text.upper() or "menunggu" in lacak.text.lower()

def test_lacak_wajib_nik(client):
    """Nomor tiket berurutan: tanpa NIK siapa pun bisa membaca surat orang lain."""
    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)

    tanpa_nik = client.get(f"/lacak?tiket={tiket}")
    assert "Riwayat proses" not in tanpa_nik.text
    assert "Unduh surat" not in tanpa_nik.text
    assert "NIK" in tanpa_nik.text

    nik_salah = client.get(f"/lacak?tiket={tiket}&nik={nik_unik()}")
    assert "Riwayat proses" not in nik_salah.text

    benar = client.get(f"/lacak?tiket={tiket}&nik={nik}")
    assert tiket in benar.text
    assert "Riwayat proses" in benar.text

def test_chat_cek_status_wajib_nik(client):
    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)
    sid = _sesi(client)

    tanya = _kirim(client, sid, f"cek {tiket}")
    teks = " ".join(tanya["balasan"]).lower()
    assert "nik" in teks
    assert "/d/" not in teks

    jawab = _kirim(client, sid, nik)
    teks = " ".join(jawab["balasan"])
    assert tiket in teks

def test_api_track_wajib_nik(client):
    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)
    assert client.get(f"/api/v1/track/{tiket}").status_code == 422
    assert client.get(f"/api/v1/track/{tiket}?nik={nik_unik()}").status_code == 404
    r = client.get(f"/api/v1/track/{tiket}?nik={nik}")
    assert r.status_code == 200
    assert r.json()["ticket_no"] == tiket


def test_batas_pengajuan_aktif(client):
    nik = nik_unik()
    for _ in range(3):
        buat_pengajuan_domisili(client, nik)

    sid = _sesi(client)
    _kirim(client, sid, "1")
    _kirim(client, sid, "1")
    data = _kirim(client, sid, "ya")
    from conftest import JAWABAN_DOMISILI

    for _ in range(40):
        teks = "\n".join(data.get("balasan") or []).lower()
        if data.get("tiket") or "batas" in teks or "maksimal" in teks:
            break
        if "data warga ditemukan" in teks:
            data = _kirim(client, sid, "1")
            continue
        if "ketik" in teks and "ya" in teks:
            data = _kirim(client, sid, "ya")
            continue
        jawab = None
        for label, nilai in JAWABAN_DOMISILI:
            if label.lower() in teks:
                jawab = nik if nilai is None else nilai
                break
        assert jawab is not None, f"tidak tahu harus menjawab apa: {teks[:300]}"
        data = _kirim(client, sid, jawab)

    teks = " ".join(data.get("balasan") or []).lower()
    assert data.get("tiket") is None
    assert "batas" in teks or "maksimal" in teks or "aktif" in teks


def test_menu_selesai(client):
    sid = _sesi(client)
    data = _kirim(client, sid, "terima kasih")
    teks = " ".join(data["balasan"]).lower()
    assert "kembali" in teks or "sama-sama" in teks or "terima kasih" in teks


def test_prompt_field_tidak_menggandakan_contoh(client):
    """Placeholder seed sudah berawalan "Contoh: " — prompt tidak boleh menambah lagi."""
    from conftest import JAWABAN_DOMISILI

    sid = _sesi(client)
    _kirim(client, sid, "1")
    _kirim(client, sid, "1")
    data = _kirim(client, sid, "ya")

    nik = nik_unik()
    for _, nilai in JAWABAN_DOMISILI:
        teks = "\n".join(data.get("balasan") or [])
        assert "contoh: contoh:" not in teks.lower()
        assert teks.lower().count("format: yyyy-mm-dd") <= 1
        if "ketik" in teks.lower() and "ya" in teks.lower():
            data = _kirim(client, sid, "ya")
            continue
        data = _kirim(client, sid, nik if nilai is None else nilai)
        if data.get("state") == "KONFIRMASI":
            break


def test_jawaban_menu_tidak_masuk_antrean_gagal(client):
    """Pilihan angka, menu, ya/tidak, terima kasih: intent SISTEM, bukan gagal."""
    from app.db import SessionLocal
    from app.models import ChatMessage

    sid = _sesi(client)
    for jawaban in ["menu", "5", "6", "ya", "tidak", "terima kasih", "1", "batal"]:
        data = _kirim(client, sid, jawaban)
        assert data["state"] in {"MENU", "TRACKING", "ESKALASI", "CONSENT", "IDLE"}, jawaban

    with SessionLocal() as db:
        gagal = db.query(ChatMessage).filter(
            ChatMessage.session_id == sid,
            ChatMessage.arah == "in",
            ChatMessage.intent_kode.is_(None),
        ).all()
        assert gagal == [], [m.isi for m in gagal]


def test_jawaban_menu_tercatat_intent_sistem(client):
    """Setiap jawaban navigasi tersimpan dengan intent SISTEM_* berkeyakinan penuh."""
    from app.db import SessionLocal
    from app.models import ChatMessage

    sid = _sesi(client)
    for jawaban in ["5", "6", "ya", "menu"]:
        _kirim(client, sid, jawaban)

    with SessionLocal() as db:
        baris = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == sid, ChatMessage.arah == "in")
            .order_by(ChatMessage.id)
            .all()
        )
    assert len(baris) >= 4
    for m in baris[-4:]:
        assert m.intent_kode in {"SISTEM_MENU", "SISTEM_RESPON", "CEK_STATUS", "BICARA_PETUGAS"}, (
            m.isi, m.intent_kode,
        )
        assert m.confidence == 1.0, (m.isi, m.confidence)
