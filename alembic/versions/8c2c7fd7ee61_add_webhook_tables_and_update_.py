"""Add webhook tables and update notification foreign key

Revision ID: 8c2c7fd7ee61
Revises: 3926b60611a9
Create Date: 2025-05-27 05:24:32.396753

"""
from typing import Sequence, Union

from alembic import op  # type: ignore
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8c2c7fd7ee61'
down_revision: Union[str, None] = '3926b60611a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create webhook status enum if it doesn't exist
    op.execute("DO $$ BEGIN CREATE TYPE webhookstatus AS ENUM ('pending', 'acknowledged', 'failed', 'retrying'); EXCEPTION WHEN duplicate_object THEN null; END $$")
    
    # Create webhooks table
    op.create_table('webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['service_id'], ['service_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_webhooks_is_active', 'webhooks', ['is_active'], unique=False)
    op.create_index('idx_webhooks_service_id', 'webhooks', ['service_id'], unique=False)
    
    # Create webhook_deliveries table
    op.create_table('webhook_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('webhook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('pending', 'acknowledged', 'failed', 'retrying', name='webhookstatus'), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=True),
        sa.Column('immediate_attempts', sa.Integer(), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('response_status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_webhook_deliveries_next_retry_at', 'webhook_deliveries', ['next_retry_at'], unique=False)
    op.create_index('idx_webhook_deliveries_notification_id', 'webhook_deliveries', ['notification_id'], unique=False)
    op.create_index('idx_webhook_deliveries_status', 'webhook_deliveries', ['status'], unique=False)
    
    # Update notifications table
    # Add foreign key constraint to service_id if it doesn't exist
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    foreign_keys = inspector.get_foreign_keys('notifications')
    
    # Check if the foreign key already exists
    has_service_fk = any(fk['referred_table'] == 'service_users' and 'service_id' in fk['constrained_columns'] for fk in foreign_keys)
    
    if not has_service_fk:
        op.create_foreign_key(None, 'notifications', 'service_users', ['service_id'], ['id'])
    
    # Add service_id index if it doesn't exist
    indexes = inspector.get_indexes('notifications')
    has_service_idx = any('service_id' in idx['column_names'] for idx in indexes)
    
    if not has_service_idx:
        op.create_index('idx_notifications_service_id', 'notifications', ['service_id'], unique=False)


def downgrade() -> None:
    # Drop service_id index if it exists
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = inspector.get_indexes('notifications')
    
    if any('service_id' in idx['column_names'] for idx in indexes):
        op.drop_index('idx_notifications_service_id', table_name='notifications')
    
    # Drop foreign key constraint if it exists
    foreign_keys = inspector.get_foreign_keys('notifications')
    for fk in foreign_keys:
        if fk['referred_table'] == 'service_users' and 'service_id' in fk['constrained_columns']:
            op.drop_constraint(fk['name'], 'notifications', type_='foreignkey')
            break
    
    # Drop webhook tables
    op.drop_index('idx_webhook_deliveries_status', table_name='webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_notification_id', table_name='webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_next_retry_at', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    
    op.drop_index('idx_webhooks_service_id', table_name='webhooks')
    op.drop_index('idx_webhooks_is_active', table_name='webhooks')
    op.drop_table('webhooks')
    
    # Drop enum
    op.execute("DROP TYPE webhookstatus")
