"""document: tambah kolom sent_at

FR-20 mewajibkan waktu pengiriman dokumen ke percakapan warga dicatat pada
tabel `document`.

Revision ID: c4d7a1f93b28
Revises: 8b1c4d2e7f90
Create Date: 2026-10-18 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d7a1f93b28'
down_revision: Union[str, Sequence[str], None] = '8b1c4d2e7f90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.drop_column('sent_at')
