"""add gym_id to nutrition_plan_followers

Revision ID: f8d4b9a3c2e1
Revises: b52fab13ee0b
Create Date: 2026-02-23 23:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8d4b9a3c2e1'
down_revision = 'b52fab13ee0b'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar columna gym_id como nullable temporalmente
    op.add_column('nutrition_plan_followers', sa.Column('gym_id', sa.Integer(), nullable=True))

    # 2. Popular gym_id desde nutrition_plans
    op.execute("""
        UPDATE nutrition_plan_followers npf
        SET gym_id = np.gym_id
        FROM nutrition_plans np
        WHERE npf.plan_id = np.id
    """)

    # 3. Hacer NOT NULL después de popular
    op.alter_column('nutrition_plan_followers', 'gym_id', nullable=False)

    # 4. Agregar FK y índice
    op.create_index(op.f('ix_nutrition_plan_followers_gym_id'), 'nutrition_plan_followers', ['gym_id'], unique=False)
    op.create_foreign_key('fk_nutrition_plan_followers_gym_id', 'nutrition_plan_followers', 'gyms', ['gym_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_nutrition_plan_followers_gym_id', 'nutrition_plan_followers', type_='foreignkey')
    op.drop_index(op.f('ix_nutrition_plan_followers_gym_id'), table_name='nutrition_plan_followers')
    op.drop_column('nutrition_plan_followers', 'gym_id')
