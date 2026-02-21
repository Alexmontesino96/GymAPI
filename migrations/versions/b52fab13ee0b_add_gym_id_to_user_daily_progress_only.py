"""add gym_id to user_daily_progress only

Revision ID: b52fab13ee0b
Revises: d2f3930aa2b1
Create Date: 2026-02-20 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b52fab13ee0b'
down_revision = 'd2f3930aa2b1'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar columna gym_id como nullable temporalmente
    op.add_column('user_daily_progress', sa.Column('gym_id', sa.Integer(), nullable=True))

    # 2. Popular gym_id desde daily_plan → nutrition_plan
    op.execute("""
        UPDATE user_daily_progress udp
        SET gym_id = np.gym_id
        FROM daily_nutrition_plans dnp
        JOIN nutrition_plans np ON dnp.nutrition_plan_id = np.id
        WHERE udp.daily_plan_id = dnp.id
    """)

    # 3. Hacer NOT NULL después de popular
    op.alter_column('user_daily_progress', 'gym_id', nullable=False)

    # 4. Agregar FK y índice
    op.create_index(op.f('ix_user_daily_progress_gym_id'), 'user_daily_progress', ['gym_id'], unique=False)
    op.create_foreign_key('fk_user_daily_progress_gym_id', 'user_daily_progress', 'gyms', ['gym_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_user_daily_progress_gym_id', 'user_daily_progress', type_='foreignkey')
    op.drop_index(op.f('ix_user_daily_progress_gym_id'), table_name='user_daily_progress')
    op.drop_column('user_daily_progress', 'gym_id')
