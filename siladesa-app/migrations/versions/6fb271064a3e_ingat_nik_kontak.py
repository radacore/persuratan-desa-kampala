"""Ingat NIK terakhir per kontak percakapan.

Menambah tabel `kontak_nik`: satu baris per pasangan (channel, kontak).
Mengurangi pertanyaan berulang saat warga mengajukan surat kedua dan
seterusnya dari perangkat yang sama.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "6fb271064a3e"
down_revision = "9acf38ee8df3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kontak_nik",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(15), nullable=False),
        sa.Column("kontak", sa.String(60), nullable=False),
        sa.Column("nik", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel", "kontak", name="uq_kontak_nik_channel_kontak"),
        sa.CheckConstraint("length(nik) = 16", name="ck_kontak_nik_panjang"),
    )
    op.create_index("ix_kontak_nik_kontak", "kontak_nik", ["kontak"])


def downgrade() -> None:
    op.drop_index("ix_kontak_nik_kontak", table_name="kontak_nik")
    op.drop_table("kontak_nik")
