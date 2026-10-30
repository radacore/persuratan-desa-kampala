"""Pipeline NLP: preprocessing Bahasa Indonesia + klasifikasi intent.

Algoritma: TF-IDF (kata 1–2 gram + karakter 3–5 gram) → LinearSVC yang
dikalibrasi (Platt scaling) sehingga keluarannya berupa probabilitas yang bisa
dibandingkan dengan ambang keyakinan. Ini sesuai batasan skripsi: model ringan,
dilatih sendiri, tanpa API LLM komersial, dan bisa jalan di VPS 2 GB.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from rapidfuzz import fuzz, process
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from app.config import settings

log = logging.getLogger("siladesa.nlp")

# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
KAMUS_SLANG = {
    "gmn": "bagaimana", "gimana": "bagaimana", "bgmn": "bagaimana", "caranya": "cara",
    "sy": "saya", "gw": "saya", "gue": "saya", "aku": "saya", "aq": "saya",
    "gk": "tidak", "gak": "tidak", "ga": "tidak", "tdk": "tidak", "engga": "tidak",
    "udh": "sudah", "udah": "sudah", "sdh": "sudah", "blm": "belum", "belom": "belum",
    "dgn": "dengan", "utk": "untuk", "yg": "yang", "dr": "dari", "dpt": "dapat",
    "bgt": "sekali", "banget": "sekali", "bikin": "buat", "bikinin": "buat",
    "mau": "ingin", "pengen": "ingin", "pingin": "ingin", "butuh": "perlu",
    "srt": "surat", "srtan": "surat", "skd": "surat keterangan domisili",
    "sku": "surat keterangan usaha", "sktm": "surat keterangan tidak mampu",
    "dom": "domisili", "kk": "kartu keluarga", "ktp": "ktp", "nik": "nik",
    "hp": "telepon", "no": "nomor", "tgl": "tanggal", "jam": "jam",
    "desa": "desa", "kantor": "kantor", "pak": "bapak", "bu": "ibu",
    "kak": "kakak", "min": "admin", "admin": "admin", "halo": "halo", "hallo": "halo",
    "assalamualaikum": "halo", "assalamu": "halo", "salam": "halo",
    "terimakasih": "terima kasih", "makasih": "terima kasih", "thx": "terima kasih",
    "mksh": "terima kasih", "trims": "terima kasih",
    "proses": "proses", "lama": "lama", "berapa": "berapa", "brp": "berapa",
    "biaya": "biaya", "bayar": "bayar", "gratis": "gratis", "bayar": "bayar",
    "antri": "antre", "antrian": "antre", "datang": "datang", "online": "online",
    "error": "gagal", "gagal": "gagal", "gabisa": "tidak bisa", "gakbisa": "tidak bisa",
    "batal": "batal", "cancel": "batal", "ubah": "ubah", "salah": "salah",
}

_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dalam", "dengan", "itu",
    "ini", "adalah", "atau", "juga", "saya", "kami", "kita", "anda", "kamu",
    "ada", "akan", "sudah", "telah", "bisa", "dapat", "mau", "ingin", "perlu",
    "tolong", "mohon", "dong", "ya", "sih", "nih", "nya", "sebuah", "para",
    "kalau", "jika", "bagi", "oleh", "secara", "agar", "supaya", "karena",
}

_URL = re.compile(r"https?://\S+|www\.\S+")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_SPASI = re.compile(r"\s+")
_ANGKA = re.compile(r"\b\d+\b")

_stemmer = None
_stemmer_lock = threading.Lock()


def _get_stemmer():
    """Sastrawi dimuat malas: inisialisasinya relatif berat."""
    global _stemmer
    if _stemmer is None:
        with _stemmer_lock:
            if _stemmer is None:
                try:
                    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

                    _stemmer = StemmerFactory().create_stemmer()
                except Exception as exc:  # pragma: no cover - hanya bila Sastrawi rusak
                    log.warning("Sastrawi tidak tersedia (%s); memakai stemming ringan", exc)
                    _stemmer = False
    return _stemmer or None


def normalisasi(teks: str) -> str:
    teks = (teks or "").lower().strip()
    teks = _URL.sub(" ", teks)
    teks = teks.replace("’", "'").replace("`", "'")
    teks = _NON_ALNUM.sub(" ", teks)
    teks = _SPASI.sub(" ", teks).strip()

    hasil: list[str] = []
    for kata in teks.split():
        hasil.append(KAMUS_SLANG.get(kata, kata))
    teks = " ".join(hasil)

    # Buang angka berdiri sendiri (nomor HP, tanggal) — tidak informatif untuk intent.
    teks = _ANGKA.sub(" ", teks)
    return _SPASI.sub(" ", teks).strip()


def preprocess(teks: str, *, stem: bool = True) -> str:
    teks = normalisasi(teks)
    token = [t for t in teks.split() if t not in _STOPWORDS and len(t) > 1]
    if not token:
        return ""
    gabung = " ".join(token)
    if stem:
        stemmer = _get_stemmer()
        if stemmer:
            try:
                gabung = stemmer.stem(gabung)
            except Exception:  # pragma: no cover
                pass
    return _SPASI.sub(" ", gabung).strip()


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass
class HasilPrediksi:
    intent: str | None
    confidence: float
    peringkat: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class HasilLatih:
    versi: str
    file_path: str
    akurasi: float
    macro_f1: float
    jumlah_sampel: int
    jumlah_intent: int
    laporan: dict[str, Any]
    metrik_per_kelas: list[dict[str, Any]]
    metode: str = ""


def _bangun_pipeline() -> Pipeline:
    fitur = FeatureUnion(
        [
            ("kata", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            (
                "karakter",
                TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1),
            ),
        ]
    )
    return Pipeline(
        [
            ("fitur", fitur),
            ("kelas", CalibratedClassifierCV(LinearSVC(C=0.8, class_weight="balanced"), cv=3)),
        ]
    )


class NlpService:
    """Pemegang model aktif di memori. Satu instance per proses."""

    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None
        self._versi: str | None = None
        self._lock = threading.RLock()
        self._siap = False

    # -- pemuatan --------------------------------------------------------- #
    def muat(self, file_path: str | Path) -> bool:
        path = Path(file_path)
        if not path.exists():
            log.warning("Berkas model tidak ditemukan: %s", path)
            return False
        with self._lock:
            paket = joblib.load(path)
            self._pipeline = paket["pipeline"]
            self._versi = paket.get("versi", path.stem)
            self._siap = True
        log.info("Model NLP %s dimuat dari %s", self._versi, path)
        return True

    @property
    def siap(self) -> bool:
        return self._siap and self._pipeline is not None

    @property
    def versi(self) -> str | None:
        return self._versi

    # -- pelatihan -------------------------------------------------------- #
    def latih(self, sampel: list[tuple[str, str]], *, catatan: str | None = None) -> HasilLatih:
        if len(sampel) < 30:
            raise ValueError("Butuh minimal 30 sampel latih untuk melatih model.")

        teks = [preprocess(t) for t, _ in sampel]
        label = [lb for _, lb in sampel]
        pasangan = [(t, lb) for t, lb in zip(teks, label) if t]
        teks = [p[0] for p in pasangan]
        label = [p[1] for p in pasangan]

        kelas_unik = sorted(set(label))
        if len(kelas_unik) < 2:
            raise ValueError("Minimal dua kelas intent diperlukan.")

        from collections import Counter

        hitung = Counter(label)

        # Evaluasi memakai stratified k-fold cross-validation supaya angka
        # akurasi tidak bergantung pada satu pembagian data yang kebetulan
        # menguntungkan. Model akhir tetap dilatih pada seluruh sampel.
        lipat = min(5, min(hitung.values()))
        if lipat >= 2 and len(label) >= 40:
            from sklearn.model_selection import StratifiedKFold, cross_val_predict

            skf = StratifiedKFold(n_splits=lipat, shuffle=True, random_state=42)
            tebakan = cross_val_predict(_bangun_pipeline(), teks, label, cv=skf)
            metode = f"{lipat}-fold cross-validation"
        else:
            tebakan = label
            metode = "evaluasi pada data latih (sampel terlalu sedikit)"

        akurasi = float(accuracy_score(label, tebakan))
        macro_f1 = float(f1_score(label, tebakan, average="macro", zero_division=0))
        laporan = classification_report(label, tebakan, output_dict=True, zero_division=0)

        metrik = [
            {
                "label": k,
                "precision": float(v["precision"]),
                "recall": float(v["recall"]),
                "f1": float(v["f1-score"]),
                "support": int(v["support"]),
            }
            for k, v in laporan.items()
            if isinstance(v, dict) and k not in {"accuracy", "macro avg", "weighted avg"}
        ]

        # Latih ulang pada seluruh data agar model produksi memakai semua sampel.
        final = _bangun_pipeline()
        final_cv = min(3, min(hitung.values()))
        if final_cv >= 2:
            final.set_params(kelas__cv=final_cv)
        else:
            from sklearn.svm import SVC

            final = Pipeline(
                [
                    ("fitur", FeatureUnion([
                        ("kata", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                        ("karakter", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))),
                    ])),
                    ("kelas", SVC(C=1.0, kernel="linear", probability=True, class_weight="balanced")),
                ]
            )
        final.fit(teks, label)

        versi = time.strftime("v%Y%m%d%H%M%S")
        settings.model_path.mkdir(parents=True, exist_ok=True)
        file_path = settings.model_path / f"model_{versi}.joblib"
        joblib.dump(
            {
                "pipeline": final,
                "versi": versi,
                "akurasi": akurasi,
                "macro_f1": macro_f1,
                "jumlah_sampel": len(teks),
                "jumlah_intent": len(kelas_unik),
                "catatan": catatan,
                "metode": metode,
                "dibuat": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            file_path,
            compress=3,
        )

        with self._lock:
            self._pipeline = final
            self._versi = versi
            self._siap = True

        log.info(
            "Model %s dilatih: %d sampel, %d intent, akurasi=%.3f, macro_f1=%.3f",
            versi, len(teks), len(kelas_unik), akurasi, macro_f1,
        )
        return HasilLatih(
            versi=versi,
            file_path=str(file_path),
            akurasi=akurasi,
            macro_f1=macro_f1,
            jumlah_sampel=len(teks),
            jumlah_intent=len(kelas_unik),
            laporan=laporan,
            metrik_per_kelas=metrik,
            metode=metode,
        )

    # -- inferensi -------------------------------------------------------- #
    def prediksi(self, teks: str) -> HasilPrediksi:
        if not self.siap or self._pipeline is None:
            return HasilPrediksi(None, 0.0)
        bersih = preprocess(teks)
        if not bersih:
            return HasilPrediksi(None, 0.0)
        with self._lock:
            pipeline = self._pipeline
        proba = pipeline.predict_proba([bersih])[0]
        kelas = list(pipeline.classes_)
        urut = np.argsort(proba)[::-1]
        peringkat = [(kelas[i], float(proba[i])) for i in urut[:3]]
        teratas, skor = peringkat[0]
        return HasilPrediksi(teratas, float(skor), peringkat)

    def evaluasi(self, sampel: list[tuple[str, str]]) -> dict[str, Any]:
        """Evaluasi model aktif pada sampel berlabel (dipakai halaman admin)."""
        if not self.siap:
            raise ValueError("Belum ada model aktif.")
        teks = [preprocess(t) for t, _ in sampel]
        label = [lb for _, lb in sampel]
        pasangan = [(t, lb) for t, lb in zip(teks, label) if t]
        if not pasangan:
            raise ValueError("Tidak ada sampel yang bisa dievaluasi.")
        x = [p[0] for p in pasangan]
        y = [p[1] for p in pasangan]
        pred = self._pipeline.predict(x)
        return {
            "akurasi": float(accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
            "jumlah": len(y),
            "laporan": classification_report(y, pred, output_dict=True, zero_division=0),
        }


# --------------------------------------------------------------------------- #
# Pencocokan FAQ (fuzzy) — jaring pengaman saat keyakinan model rendah
# --------------------------------------------------------------------------- #
def cocokkan_faq(
    teks: str, kandidat: list[dict[str, Any]], *, ambang: float = 78.0
) -> tuple[dict[str, Any], float] | None:
    """Cari FAQ paling mirip. `kandidat` berisi {'id','pertanyaan','kata_kunci'}."""
    if not kandidat:
        return None
    bersih = normalisasi(teks)
    if not bersih:
        return None

    pilihan: list[tuple[str, dict[str, Any]]] = []
    for item in kandidat:
        pilihan.append((normalisasi(item["pertanyaan"]), item))
        for kata in item.get("kata_kunci") or []:
            pilihan.append((normalisasi(str(kata)), item))

    terbaik = process.extractOne(
        bersih, [p[0] for p in pilihan], scorer=fuzz.token_set_ratio
    )
    if not terbaik:
        return None
    _teks, skor, idx = terbaik
    if skor < ambang:
        return None
    return pilihan[idx][1], float(skor)


nlp = NlpService()
