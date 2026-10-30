"""Satu dokumen per pengajuan.

Menambahkan `UNIQUE(application_id)` pada tabel `document` dan melepas indeks
biasa `ix_document_application_id` (indeks unik sudah menggantikannya).

Latar belakang: penerbitan ganda (dua klik "Terbitkan" atau dua operator
sekaligus) menghasilkan dua baris dokumen dengan dua nomor surat untuk satu
berkas PDF, karena `terbitkan` hanya memeriksa status pengajuan.

Revisi: f2b8e6d4a910
Sebelumnya: a7f3c9d1e2b4 (citizen.aktif)
"""

from __future__ import annotations

from alembic import op

revision = "f2b8e6d4a910"
down_revision = "a7f3c9d1e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Basis data yang sudah berisi duplikat akan menggagalkan migrasi ini
    # dengan pesan jelas — lebih baik daripada menghapus arsip surat diam-diam.
    op.drop_index("ix_document_application_id", table_name="document")
    with op.batch_alter_table("document") as batch:
        batch.create_unique_constraint("uq_document_application", ["application_id"])


def downgrade() -> None:
    with op.batch_alter_table("document") as batch:
        batch.drop_constraint("uq_document_application", type_="unique")
    op.create_index(
        "ix_document_application_id", "document", ["application_id"], unique=False
    )
