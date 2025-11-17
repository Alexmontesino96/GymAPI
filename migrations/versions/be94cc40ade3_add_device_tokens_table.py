"""add device_tokens table

Revision ID: be94cc40ade3
Revises: 3f0c8f1524ed
Create Date: 2025-04-08 11:19:29.418227

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = 'be94cc40ade3'
down_revision = '3f0c8f1524ed'
branch_labels = None
depends_on = None


def upgrade():
    # Asegurar que la extensión uuid-ossp esté habilitada
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Crear la tabla device_tokens
    op.create_table(
        'device_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('device_token', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text("true")),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('user_id', 'device_token', name='uq_user_device_token')
    )
    
    # Crear índices
    op.create_index('idx_device_token', 'device_tokens', ['device_token'])
    op.create_index('idx_device_token_user_id', 'device_tokens', ['user_id'])


def downgrade():
    # Eliminar la tabla device_tokens
    op.drop_table('device_tokens') 