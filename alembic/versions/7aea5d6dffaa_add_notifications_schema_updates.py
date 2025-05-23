"""Add notifications schema updates

Revision ID: 7aea5d6dffaa
Revises: ca4c5253be03
Create Date: 2025-05-23 12:18:35.351934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7aea5d6dffaa'
down_revision: Union[str, None] = 'ca4c5253be03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('notifications', sa.Column('subject', sa.String(length=500), nullable=True))
    op.add_column('notifications', sa.Column('scheduled_at', sa.DateTime(), nullable=True))
    op.add_column('notifications', sa.Column('delivered_at', sa.DateTime(), nullable=True))
    op.add_column('notifications', sa.Column('failed_at', sa.DateTime(), nullable=True))
    op.add_column('notifications', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_index('idx_notifications_created_at', 'notifications', ['created_at'], unique=False)
    op.create_index('idx_notifications_recipient', 'notifications', ['recipient'], unique=False)
    op.create_index('idx_notifications_status', 'notifications', ['status'], unique=False)
    op.create_index('idx_notifications_type', 'notifications', ['type'], unique=False)
    op.add_column('providers', sa.Column('priority', sa.Integer(), nullable=True))
    op.alter_column('providers', 'name',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=50),
               existing_nullable=False)
    op.alter_column('providers', 'type',
               existing_type=postgresql.ENUM('SMS', 'EMAIL', 'PUSH', 'WHATSAPP', name='providertype'),
               type_=sa.String(length=20),
               existing_nullable=False)
    op.alter_column('providers', 'config',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=True)
    op.create_index(op.f('ix_providers_name'), 'providers', ['name'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_providers_name'), table_name='providers')
    op.alter_column('providers', 'config',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=False)
    op.alter_column('providers', 'type',
               existing_type=sa.String(length=20),
               type_=postgresql.ENUM('SMS', 'EMAIL', 'PUSH', 'WHATSAPP', name='providertype'),
               existing_nullable=False)
    op.alter_column('providers', 'name',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.drop_column('providers', 'priority')
    op.drop_index('idx_notifications_type', table_name='notifications')
    op.drop_index('idx_notifications_status', table_name='notifications')
    op.drop_index('idx_notifications_recipient', table_name='notifications')
    op.drop_index('idx_notifications_created_at', table_name='notifications')
    op.drop_column('notifications', 'external_id')
    op.drop_column('notifications', 'failed_at')
    op.drop_column('notifications', 'delivered_at')
    op.drop_column('notifications', 'scheduled_at')
    op.drop_column('notifications', 'subject')
    # ### end Alembic commands ###
