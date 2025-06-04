"""add task_id fields for revocation

Revision ID: e2f3g4h5i6j7
Revises: d014fe1e4d84
Create Date: 2025-05-28 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3g4h5i6j7'
down_revision: Union[str, None] = 'd014fe1e4d84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add task_id column to notifications table
    op.add_column('notifications', sa.Column('task_id', sa.String(length=255), nullable=True))
    
    # Add task_id column to webhook_deliveries table
    op.add_column('webhook_deliveries', sa.Column('task_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Remove task_id column from webhook_deliveries table
    op.drop_column('webhook_deliveries', 'task_id')
    
    # Remove task_id column from notifications table
    op.drop_column('notifications', 'task_id')