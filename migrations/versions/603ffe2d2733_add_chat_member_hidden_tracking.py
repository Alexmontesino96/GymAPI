"""add chat member hidden tracking

Revision ID: 603ffe2d2733
Revises: 9268f18fc9bd
Create Date: 2025-12-13 19:21:22.684828

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '603ffe2d2733'
down_revision = '9268f18fc9bd'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla chat_member_hidden
    op.create_table(
        'chat_member_hidden',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('hidden_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['room_id'], ['chat_rooms.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'room_id', name='uq_user_room_hidden')
    )

    # Crear índices
    op.create_index('ix_chat_hidden_user_room', 'chat_member_hidden', ['user_id', 'room_id'])
    op.create_index(op.f('ix_chat_member_hidden_user_id'), 'chat_member_hidden', ['user_id'])
    op.create_index(op.f('ix_chat_member_hidden_room_id'), 'chat_member_hidden', ['room_id'])
    op.create_index(op.f('ix_chat_member_hidden_id'), 'chat_member_hidden', ['id'])


def downgrade():
    # Eliminar índices
    op.drop_index(op.f('ix_chat_member_hidden_id'), table_name='chat_member_hidden')
    op.drop_index(op.f('ix_chat_member_hidden_room_id'), table_name='chat_member_hidden')
    op.drop_index(op.f('ix_chat_member_hidden_user_id'), table_name='chat_member_hidden')
    op.drop_index('ix_chat_hidden_user_room', table_name='chat_member_hidden')

    # Eliminar tabla
    op.drop_table('chat_member_hidden') 