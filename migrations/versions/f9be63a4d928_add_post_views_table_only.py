"""add post_views table only

Revision ID: f9be63a4d928
Revises: fd54000bbbcb
Create Date: 2025-11-16 22:37:05.365209

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9be63a4d928'
down_revision = 'fd54000bbbcb'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla post_views para tracking de vistas y deduplicación en feed
    op.create_table(
        'post_views',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('view_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Crear índices para queries eficientes
    op.create_index('ix_post_views_id', 'post_views', ['id'], unique=False)
    op.create_index('ix_post_views_post_id', 'post_views', ['post_id'], unique=False)
    op.create_index('ix_post_views_user_id', 'post_views', ['user_id'], unique=False)
    op.create_index('ix_post_views_gym_id', 'post_views', ['gym_id'], unique=False)

    # Índices compuestos para queries complejas
    op.create_index('ix_post_views_user_post', 'post_views', ['user_id', 'post_id'], unique=False)
    op.create_index('ix_post_views_gym_user', 'post_views', ['gym_id', 'user_id'], unique=False)
    op.create_index('ix_post_views_post_date', 'post_views', ['post_id', 'viewed_at'], unique=False)


def downgrade():
    # Eliminar índices
    op.drop_index('ix_post_views_post_date', table_name='post_views')
    op.drop_index('ix_post_views_gym_user', table_name='post_views')
    op.drop_index('ix_post_views_user_post', table_name='post_views')
    op.drop_index('ix_post_views_gym_id', table_name='post_views')
    op.drop_index('ix_post_views_user_id', table_name='post_views')
    op.drop_index('ix_post_views_post_id', table_name='post_views')
    op.drop_index('ix_post_views_id', table_name='post_views')

    # Eliminar tabla
    op.drop_table('post_views') 