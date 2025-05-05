"""add_modules_system

Revision ID: a762df8c3a1e
Revises: 4e3caf355ba8
Create Date: 2025-05-05 01:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a762df8c3a1e'
down_revision = '4e3caf355ba8'  # La revisión actual es 4e3caf355ba8
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla "modules"
    op.create_table(
        'modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_premium', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modules_code'), 'modules', ['code'], unique=True)
    op.create_index(op.f('ix_modules_id'), 'modules', ['id'], unique=False)
    
    # Crear tabla "gym_modules"
    op.create_table(
        'gym_modules',
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), default=True, nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('gym_id', 'module_id')
    )
    
    # Insertar módulos básicos
    op.execute(
        """
        INSERT INTO modules (code, name, description, is_premium, created_at, updated_at) 
        VALUES 
        ('schedule', 'Horarios y Clases', 'Gestión de horarios, clases y participación', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('events', 'Eventos', 'Gestión de eventos especiales', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('users', 'Usuarios', 'Gestión de usuarios y perfiles', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('relationships', 'Relaciones', 'Gestión de relaciones entrenador-miembro', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('chat', 'Chat', 'Sistema de mensajería en tiempo real', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    
    # Activar módulos básicos para todos los gimnasios existentes
    op.execute(
        """
        INSERT INTO gym_modules (gym_id, module_id, active, activated_at)
        SELECT g.id, m.id, true, CURRENT_TIMESTAMP
        FROM gyms g, modules m
        """
    )


def downgrade():
    op.drop_table('gym_modules')
    op.drop_index(op.f('ix_modules_id'), table_name='modules')
    op.drop_index(op.f('ix_modules_code'), table_name='modules')
    op.drop_table('modules')
