"""Add webhook deletion support

Revision ID: d1b4e8ca7d79
Revises: 
Create Date: 2023-11-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'd1b4e8ca7d79'
down_revision = None  # Set to previous revision ID if this isn't your first migration
branch_labels = None
depends_on = None


def upgrade():
    # Alembic detected these changes:
    # - Added column 'service_id' to table 'notifications'
    # - Added column 'priority' to table 'notifications'
    # - Added column 'meta_data' to table 'notifications'
    # - Added column 'provider_response' to table 'notifications'
    # - Added column 'error_message' to table 'notifications'
    # - Added column 'retry_count' to table 'notifications'
    # - Added column 'is_instant' to table 'notifications'
    # - Changed type of 'provider_id' from UUID to String(50)
    # - Removed foreign key between 'notifications.provider_id' and 'providers.id'
    # - Added foreign key between 'notifications.service_id' and 'service_users.id'
    # - Removed column 'delivered_at' from table 'notifications'
    # - Removed column 'external_id' from table 'notifications'

    # Check if columns already exist before adding them
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('notifications')]
    
    if 'service_id' not in columns:
        op.add_column('notifications', sa.Column('service_id', postgresql.UUID(as_uuid=True), nullable=False))
    
    # Add new columns if they don't exist
    if 'priority' not in columns:
        op.add_column('notifications', sa.Column('priority', sa.String(length=20), nullable=True))
    if 'meta_data' not in columns:
        op.add_column('notifications', sa.Column('meta_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if 'provider_response' not in columns:
        op.add_column('notifications', sa.Column('provider_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if 'error_message' not in columns:
        op.add_column('notifications', sa.Column('error_message', sa.Text(), nullable=True))
    if 'retry_count' not in columns:
        op.add_column('notifications', sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'))
    if 'is_instant' not in columns:
        op.add_column('notifications', sa.Column('is_instant', sa.Boolean(), nullable=True, server_default='false'))
    
    # Remove old columns if they exist
    if 'delivered_at' in columns:
        op.drop_column('notifications', 'delivered_at')
    if 'external_id' in columns:
        op.drop_column('notifications', 'external_id')
    
    # Handle provider_id FK drop
    try:
        op.drop_constraint('notifications_provider_id_fkey', 'notifications', type_='foreignkey')
    except Exception:
        # If constraint doesn't exist or has a different name, we can continue
        pass
    
    # Change provider_id type from UUID to String
    op.alter_column('notifications', 'provider_id',
               existing_type=postgresql.UUID(),
               type_=sa.String(length=50),
               existing_nullable=True)
    
    # Create FK between service_id and service_users.id if service_id was added
    if 'service_id' not in columns:
        op.create_foreign_key('notifications_service_id_fkey', 'notifications', 'service_users', ['service_id'], ['id'])


def downgrade():
    # Remove FK constraint between service_id and service_users.id
    op.drop_constraint('notifications_service_id_fkey', 'notifications', type_='foreignkey')
    
    # Change provider_id back to UUID
    op.alter_column('notifications', 'provider_id',
               existing_type=sa.String(length=50),
               type_=postgresql.UUID(),
               existing_nullable=True)
    
    # Add back old columns
    op.add_column('notifications', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.add_column('notifications', sa.Column('delivered_at', sa.DateTime(), nullable=True))
    
    # Remove new columns
    op.drop_column('notifications', 'is_instant')
    op.drop_column('notifications', 'retry_count')
    op.drop_column('notifications', 'error_message')
    op.drop_column('notifications', 'provider_response')
    op.drop_column('notifications', 'meta_data')
    op.drop_column('notifications', 'priority')
    op.drop_column('notifications', 'service_id')
    
    # Re-add FK between provider_id and providers.id
    op.create_foreign_key('notifications_provider_id_fkey', 'notifications', 'providers', ['provider_id'], ['id'])
