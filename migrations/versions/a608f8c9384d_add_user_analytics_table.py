"""add user analytics table

Revision ID: a608f8c9384d
Revises: ca25a5495a32
Create Date: 2025-09-11 23:26:17.676922

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a608f8c9384d'
down_revision = 'ca25a5495a32'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla user_analytics
    op.create_table('user_analytics',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')),
        sa.Column('workouts_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('classes_attended', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('app_opens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checked_in', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('weight_logged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('social_interaction', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'gym_id', 'date')
    )
    
    # Crear índices para queries eficientes
    op.create_index('idx_analytics_date', 'user_analytics', ['date'], unique=False)
    op.create_index('idx_analytics_gym_date', 'user_analytics', ['gym_id', 'date'], unique=False)
    op.create_index('idx_analytics_user_date', 'user_analytics', ['user_id', 'date'], unique=False)


def downgrade():
    # Eliminar índices
    op.drop_index('idx_analytics_user_date', table_name='user_analytics')
    op.drop_index('idx_analytics_gym_date', table_name='user_analytics')
    op.drop_index('idx_analytics_date', table_name='user_analytics')
    
    # Eliminar tabla
    op.drop_table('user_analytics') 