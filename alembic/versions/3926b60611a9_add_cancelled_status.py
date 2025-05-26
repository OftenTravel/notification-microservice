"""add_cancelled_status

Revision ID: 3926b60611a9
Revises: d014fe1e4d84
Create Date: 2025-05-26 23:13:26.616623

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3926b60611a9'
down_revision = 'd014fe1e4d84'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add CANCELLED to the notificationstatus enum
    op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # Note: Removing enum values in PostgreSQL is complex and usually not done
    # This would require recreating the enum type without the value
    pass