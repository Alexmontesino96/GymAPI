"""add_nutrition_hybrid_system

Revision ID: h394dbb765b6
Revises: b394dbb765a5
Create Date: 2025-07-06 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h394dbb765b6'
down_revision = 'b394dbb765a5'
branch_labels = None
depends_on = None


def upgrade():
    # ### Agregar nuevos campos para el sistema híbrido ###
    
    # 1. Agregar enum PlanType
    op.execute("CREATE TYPE plantype AS ENUM ('TEMPLATE', 'LIVE', 'ARCHIVED')")
    
    # 2. Agregar nuevos campos a nutrition_plans
    op.add_column('nutrition_plans', sa.Column('plan_type', sa.Enum('TEMPLATE', 'LIVE', 'ARCHIVED', name='plantype'), nullable=False, server_default='TEMPLATE'))
    
    # Campos para planes LIVE
    op.add_column('nutrition_plans', sa.Column('live_start_date', sa.DateTime(), nullable=True))
    op.add_column('nutrition_plans', sa.Column('live_end_date', sa.DateTime(), nullable=True))
    op.add_column('nutrition_plans', sa.Column('is_live_active', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('nutrition_plans', sa.Column('live_participants_count', sa.Integer(), nullable=False, server_default='0'))
    
    # Campos para planes ARCHIVED
    op.add_column('nutrition_plans', sa.Column('original_live_plan_id', sa.Integer(), nullable=True))
    op.add_column('nutrition_plans', sa.Column('archived_at', sa.DateTime(), nullable=True))
    op.add_column('nutrition_plans', sa.Column('original_participants_count', sa.Integer(), nullable=True))
    
    # 3. Crear índices para los nuevos campos
    op.create_index(op.f('ix_nutrition_plans_plan_type'), 'nutrition_plans', ['plan_type'], unique=False)
    op.create_index(op.f('ix_nutrition_plans_live_start_date'), 'nutrition_plans', ['live_start_date'], unique=False)
    op.create_index(op.f('ix_nutrition_plans_live_end_date'), 'nutrition_plans', ['live_end_date'], unique=False)
    op.create_index(op.f('ix_nutrition_plans_is_live_active'), 'nutrition_plans', ['is_live_active'], unique=False)
    op.create_index(op.f('ix_nutrition_plans_original_live_plan_id'), 'nutrition_plans', ['original_live_plan_id'], unique=False)
    
    # 4. Crear foreign key para la relación self-referencial
    op.create_foreign_key(
        'fk_nutrition_plans_original_live_plan',
        'nutrition_plans', 'nutrition_plans',
        ['original_live_plan_id'], ['id']
    )
    
    # 5. Remover default después de la migración
    op.alter_column('nutrition_plans', 'plan_type', server_default=None)
    op.alter_column('nutrition_plans', 'is_live_active', server_default=None)
    op.alter_column('nutrition_plans', 'live_participants_count', server_default=None)


def downgrade():
    # ### Revertir cambios del sistema híbrido ###
    
    # 1. Eliminar foreign key
    op.drop_constraint('fk_nutrition_plans_original_live_plan', 'nutrition_plans', type_='foreignkey')
    
    # 2. Eliminar índices
    op.drop_index(op.f('ix_nutrition_plans_original_live_plan_id'), table_name='nutrition_plans')
    op.drop_index(op.f('ix_nutrition_plans_is_live_active'), table_name='nutrition_plans')
    op.drop_index(op.f('ix_nutrition_plans_live_end_date'), table_name='nutrition_plans')
    op.drop_index(op.f('ix_nutrition_plans_live_start_date'), table_name='nutrition_plans')
    op.drop_index(op.f('ix_nutrition_plans_plan_type'), table_name='nutrition_plans')
    
    # 3. Eliminar columnas
    op.drop_column('nutrition_plans', 'original_participants_count')
    op.drop_column('nutrition_plans', 'archived_at')
    op.drop_column('nutrition_plans', 'original_live_plan_id')
    op.drop_column('nutrition_plans', 'live_participants_count')
    op.drop_column('nutrition_plans', 'is_live_active')
    op.drop_column('nutrition_plans', 'live_end_date')
    op.drop_column('nutrition_plans', 'live_start_date')
    op.drop_column('nutrition_plans', 'plan_type')
    
    # 4. Eliminar enum type
    op.execute("DROP TYPE plantype") 