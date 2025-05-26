"""merge_heads

Revision ID: d014fe1e4d84
Revises: 91b2b1790f3a, d1b4e8ca7d79
Create Date: 2025-05-27 04:43:07.352066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd014fe1e4d84'
down_revision: Union[str, None] = ('91b2b1790f3a', 'd1b4e8ca7d79')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
