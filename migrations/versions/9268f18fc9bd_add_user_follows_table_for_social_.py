"""add user_follows table for social features

Revision ID: 9268f18fc9bd
Revises: f9be63a4d928
Create Date: 2025-11-16 23:11:04.139135

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9268f18fc9bd'
down_revision = 'f9be63a4d928'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla user_follows para sistema de seguimiento entre usuarios
    op.create_table(
        'user_follows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('follower_id', sa.Integer(), nullable=False),
        sa.Column('following_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['follower_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['following_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('follower_id', 'following_id', 'gym_id', name='unique_user_follow')
    )

    # Crear índices para queries eficientes
    op.create_index('ix_user_follows_id', 'user_follows', ['id'], unique=False)
    op.create_index('ix_user_follows_follower_id', 'user_follows', ['follower_id'], unique=False)
    op.create_index('ix_user_follows_following_id', 'user_follows', ['following_id'], unique=False)
    op.create_index('ix_user_follows_gym_id', 'user_follows', ['gym_id'], unique=False)
    op.create_index('ix_user_follows_active', 'user_follows', ['is_active'], unique=False)

    # Índices compuestos para queries de followers/following por gym
    op.create_index('ix_user_follows_follower_gym', 'user_follows', ['follower_id', 'gym_id'], unique=False)
    op.create_index('ix_user_follows_following_gym', 'user_follows', ['following_id', 'gym_id'], unique=False)


def downgrade():
    # Eliminar índices
    op.drop_index('ix_user_follows_following_gym', table_name='user_follows')
    op.drop_index('ix_user_follows_follower_gym', table_name='user_follows')
    op.drop_index('ix_user_follows_active', table_name='user_follows')
    op.drop_index('ix_user_follows_gym_id', table_name='user_follows')
    op.drop_index('ix_user_follows_following_id', table_name='user_follows')
    op.drop_index('ix_user_follows_follower_id', table_name='user_follows')
    op.drop_index('ix_user_follows_id', table_name='user_follows')

    # Eliminar tabla
    op.drop_table('user_follows') 