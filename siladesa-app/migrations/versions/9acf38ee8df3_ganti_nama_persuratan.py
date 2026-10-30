"""Ganti nama aplikasi menjadi Persuratan Desa Kampala.

Memperbarui nilai default `setting.sapaan` agar sapaan chatbot memakai nama
baru. Hanya baris yang masih bernilai lama yang diubah; kustomisasi admin
tidak ditimpa.

Revisi: 9acf38ee8df3
Sebelumnya: f2b8e6d4a910 (satu dokumen per pengajuan)
"""

from __future__ import annotations

from alembic import op

revision = "9acf38ee8df3"
down_revision = "f2b8e6d4a910"
branch_labels = None
depends_on = None

LAMA = 'Selamat datang di layanan mandiri Desa Kampala.'
BARU = 'Selamat datang di layanan Persuratan Desa Kampala.'


def upgrade() -> None:
    op.execute(
        "UPDATE setting SET nilai = '%s' "
        "WHERE kunci = 'sapaan' AND nilai = '%s'" % (BARU, LAMA)
    )


def downgrade() -> None:
    op.execute(
        "UPDATE setting SET nilai = '%s' "
        "WHERE kunci = 'sapaan' AND nilai = '%s'" % (LAMA, BARU)
    )
