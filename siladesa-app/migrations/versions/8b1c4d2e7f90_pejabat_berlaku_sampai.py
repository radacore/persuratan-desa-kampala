"""pejabat: tambah kolom berlaku_sampai

Revision ID: 8b1c4d2e7f90
Revises: 3e639546ecd8
Create Date: 2026-10-18 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8b1c4d2e7f90'
down_revision: Union[str, Sequence[str], None] = '3e639546ecd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('official', schema=None) as batch_op:
        batch_op.add_column(sa.Column('berlaku_sampai', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('official', schema=None) as batch_op:
        batch_op.drop_column('berlaku_sampai')
