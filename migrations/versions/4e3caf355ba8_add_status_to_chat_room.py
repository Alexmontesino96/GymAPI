"""add_status_to_chat_room

Revision ID: 4e3caf355ba8
Revises: 1f05122523da
Create Date: 2025-04-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e3caf355ba8'
down_revision = '1f05122523da'
branch_labels = None
depends_on = None


def upgrade():
    # Crear el tipo enum para el estado de la sala
    status_type = sa.Enum('ACTIVE', 'CLOSED', name='chatroomstatus')
    status_type.create(op.get_bind())
    
    # Añadir la columna con valor por defecto 'ACTIVE'
    op.add_column('chat_rooms', 
                 sa.Column('status', 
                          status_type, 
                          server_default='ACTIVE',
                          nullable=False))
    
    # Crear índice para la nueva columna
    op.create_index(op.f('ix_chat_rooms_status'), 'chat_rooms', ['status'], unique=False)


def downgrade():
    # Eliminar índice y columna
    op.drop_index(op.f('ix_chat_rooms_status'), table_name='chat_rooms')
    op.drop_column('chat_rooms', 'status')
    
    # Eliminar el tipo enum
    sa.Enum(name='chatroomstatus').drop(op.get_bind()) 