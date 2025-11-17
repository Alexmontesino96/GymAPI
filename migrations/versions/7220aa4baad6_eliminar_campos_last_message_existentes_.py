"""eliminar campos last_message existentes de chat_rooms

Revision ID: 7220aa4baad6
Revises: 459b732a1509
Create Date: 2025-07-31 23:02:24.997329

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7220aa4baad6'
down_revision = '459b732a1509'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands to remove last_message fields ###
    # Primero eliminar foreign key constraint si existe
    try:
        op.drop_constraint('fk_chat_rooms_last_message_sender_id', 'chat_rooms', type_='foreignkey')
    except Exception:
        pass  # La constraint podría no existir
    
    # Eliminar índices si existen
    try:
        op.drop_index('ix_chat_rooms_last_message_sender_id', table_name='chat_rooms')
    except Exception:
        pass  # El índice podría no existir
    
    # Eliminar columnas una por una, ignorando errores si no existen
    try:
        op.drop_column('chat_rooms', 'last_message_type')
    except Exception:
        pass
        
    try:
        op.drop_column('chat_rooms', 'last_message_sender_id')
    except Exception:
        pass
        
    try:
        op.drop_column('chat_rooms', 'last_message_text')
    except Exception:
        pass
        
    try:
        op.drop_column('chat_rooms', 'last_message_at')
    except Exception:
        pass
    # ### end commands ###


def downgrade():
    # ### commands to recreate last_message fields ###
    op.add_column('chat_rooms', sa.Column('last_message_at', sa.DateTime(), nullable=True))
    op.add_column('chat_rooms', sa.Column('last_message_text', sa.String(200), nullable=True))
    op.add_column('chat_rooms', sa.Column('last_message_sender_id', sa.Integer(), nullable=True))
    op.add_column('chat_rooms', sa.Column('last_message_type', sa.String(20), nullable=True))
    op.create_index(op.f('ix_chat_rooms_last_message_sender_id'), 'chat_rooms', ['last_message_sender_id'])
    op.create_foreign_key('fk_chat_rooms_last_message_sender_id', 'chat_rooms', 'user', ['last_message_sender_id'], ['id'])
    # ### end commands ### 