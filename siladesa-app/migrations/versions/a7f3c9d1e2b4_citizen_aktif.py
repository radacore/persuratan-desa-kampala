"""citizen: tambah kolom aktif

Data warga yang pindah domisili atau meninggal tidak dihapus supaya riwayat
surat tetap utuh, melainkan dinonaktifkan. NIK nonaktif ditolak saat
validasi di chat.

Revision ID: a7f3c9d1e2b4
Revises: c4d7a1f93b28
Create Date: 2026-10-19 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7f3c9d1e2b4'
down_revision: Union[str, Sequence[str], None] = 'c4d7a1f93b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('citizen', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('aktif', sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('citizen', schema=None) as batch_op:
        batch_op.drop_column('aktif')
