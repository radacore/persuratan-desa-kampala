"""Data dan perhitungan kuesioner penerimaan pengguna (Bab IV bagian 4.5).

PENTING — STATUS DATA
---------------------
Angka pada `BUTIR` di bawah ini adalah **contoh ilustrasi** yang disusun agar
seluruh perhitungan konsisten. Angka tersebut BUKAN hasil survei lapangan.
Ganti dengan rekapitulasi kuesioner yang sebenarnya sebelum skripsi diserahkan:

    BUTIR = [
        ("K1", "Pernyataan butir 1", ss, s, ks, ts, sts),
        ...
    ]

Jumlah jawaban setiap butir wajib sama dengan `JUMLAH_RESPONDEN`; skrip ini
menolak jalan bila tidak sama, sehingga tidak ada tabel yang tampak benar
tetapi aritmetikanya salah.

Rumus yang dipakai (mengikuti Bab III):

    skor butir   = 5·SS + 4·S + 3·KS + 2·TS + 1·STS
    skor maks    = 5 · jumlah responden
    persentase   = skor butir / skor maks × 100
    kriteria     = sangat layak  : 80% < x ≤ 100%
                   layak         : 60% < x ≤ 80%
                   cukup layak   : 40% < x ≤ 60%
                   tidak layak   : 20% < x ≤ 40%
                   sangat tidak layak : 0% ≤ x ≤ 20%
"""

from __future__ import annotations

JUMLAH_RESPONDEN = 93

#: (kode indikator, pernyataan, SS, S, KS, TS, STS)
BUTIR: list[tuple[str, str, int, int, int, int, int]] = [
    ("K1", "Sistem mudah diakses melalui widget web, Telegram, maupun WhatsApp",
     42, 44, 6, 1, 0),
    ("K1", "Percakapan dengan chatbot mudah diikuti tanpa pelatihan khusus",
     38, 46, 8, 1, 0),
    ("K1", "Pengisian formulir bertahap mudah dipahami dan tidak membingungkan",
     40, 45, 7, 1, 0),
    ("K2", "Persyaratan surat dijelaskan dengan bahasa yang jelas dan ringkas",
     45, 42, 5, 1, 0),
    ("K2", "Bahasa yang dipakai chatbot mudah dipahami warga desa",
     41, 45, 6, 1, 0),
    ("K2", "Status pengajuan dapat dilacak dengan jelas melalui nomor tiket",
     39, 46, 7, 1, 0),
    ("K3", "Jawaban chatbot diterima dengan cepat",
     48, 41, 4, 0, 0),
    ("K3", "Waktu penerbitan surat lebih singkat dibanding cara manual",
     40, 44, 8, 1, 0),
    ("K4", "Surat yang dihasilkan sesuai dengan keperluan yang diajukan",
     43, 44, 5, 1, 0),
    ("K4", "Format surat sesuai dengan format resmi kantor desa",
     46, 43, 4, 0, 0),
]

INDIKATOR = {
    "K1": "Kemudahan penggunaan",
    "K2": "Kejelasan informasi",
    "K3": "Kecepatan layanan",
    "K4": "Kesesuaian hasil",
}

BOBOT = {"SS": 5, "S": 4, "KS": 3, "TS": 2, "STS": 1}


def kriteria(persen: float) -> str:
    if persen > 80:
        return "Sangat layak"
    if persen > 60:
        return "Layak"
    if persen > 40:
        return "Cukup layak"
    if persen > 20:
        return "Tidak layak"
    return "Sangat tidak layak"


def _persen(skor: int, maks: int) -> float:
    return skor / maks * 100 if maks else 0.0


def validasi() -> None:
    """Pastikan aritmetika konsisten sebelum dipakai menyusun tabel."""
    if len(BUTIR) != 10:
        raise ValueError(f"Butir kuesioner harus 10, bukan {len(BUTIR)}.")
    for i, (kode, teks, ss, s, ks, ts, sts) in enumerate(BUTIR, start=1):
        if kode not in INDIKATOR:
            raise ValueError(f"Butir {i}: indikator {kode!r} tidak dikenal.")
        total = ss + s + ks + ts + sts
        if total != JUMLAH_RESPONDEN:
            raise ValueError(
                f"Butir {i} ({teks[:40]}…): jumlah jawaban {total}, "
                f"seharusnya {JUMLAH_RESPONDEN}."
            )
    for kode in INDIKATOR:
        if not any(b[0] == kode for b in BUTIR):
            raise ValueError(f"Indikator {kode} tidak punya butir.")


def baris_butir() -> list[list[str]]:
    """Data Tabel 4.13: satu baris per butir pernyataan."""
    validasi()
    hasil: list[list[str]] = []
    maks = BOBOT["SS"] * JUMLAH_RESPONDEN
    for i, (_kode, teks, ss, s, ks, ts, sts) in enumerate(BUTIR, start=1):
        skor = (BOBOT["SS"] * ss + BOBOT["S"] * s + BOBOT["KS"] * ks
                + BOBOT["TS"] * ts + BOBOT["STS"] * sts)
        persen = _persen(skor, maks)
        hasil.append([
            str(i), teks, str(ss), str(s), str(ks), str(ts), str(sts),
            str(skor), f"{persen:.2f}".replace(".", ","),
        ])
    return hasil


def baris_indikator() -> list[list[str]]:
    """Data Tabel 4.14: agregasi per indikator."""
    validasi()
    hasil: list[list[str]] = []
    maks_butir = BOBOT["SS"] * JUMLAH_RESPONDEN
    for nomor, (kode, nama) in enumerate(INDIKATOR.items(), start=1):
        butir = [b for b in BUTIR if b[0] == kode]
        skor = 0
        for _k, _t, ss, s, ks, ts, sts in butir:
            skor += (BOBOT["SS"] * ss + BOBOT["S"] * s + BOBOT["KS"] * ks
                     + BOBOT["TS"] * ts + BOBOT["STS"] * sts)
        maks = maks_butir * len(butir)
        persen = _persen(skor, maks)
        hasil.append([
            str(nomor), nama, str(len(butir)), str(skor), str(maks),
            f"{persen:.2f}".replace(".", ","), kriteria(persen),
        ])

    total_skor = sum(int(r[3]) for r in hasil)
    total_maks = sum(int(r[4]) for r in hasil)
    persen_total = _persen(total_skor, total_maks)
    hasil.append([
        "", "Rata-rata keseluruhan", str(len(BUTIR)), str(total_skor),
        str(total_maks), f"{persen_total:.2f}".replace(".", ","),
        kriteria(persen_total),
    ])
    return hasil


def ringkasan() -> dict[str, float | str]:
    """Angka yang dipakai pada narasi."""
    baris = baris_indikator()
    total = baris[-1]
    per_butir = baris_butir()
    return {
        "responden": JUMLAH_RESPONDEN,
        "butir": len(BUTIR),
        "persen_total": float(total[5].replace(",", ".")),
        "kriteria_total": total[6],
        "persen_terendah": min(float(b[8].replace(",", ".")) for b in per_butir),
        "persen_tertinggi": max(float(b[8].replace(",", ".")) for b in per_butir),
        "jumlah_sangat_setuju": sum(b[2] for b in BUTIR),
    }


if __name__ == "__main__":
    for r in baris_butir():
        print(" | ".join(r))
    print()
    for r in baris_indikator():
        print(" | ".join(r))
    print()
    print(ringkasan())
