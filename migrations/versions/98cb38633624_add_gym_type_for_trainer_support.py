"""add gym type for trainer support

Revision ID: 98cb38633624
Revises: a608f8c9384d
Create Date: 2025-10-24 23:28:21.411825

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98cb38633624'
down_revision = 'a608f8c9384d'
branch_labels = None
depends_on = None


def upgrade():
    # Crear el enum type para diferenciar gimnasios de entrenadores
    gym_type_enum = sa.Enum('gym', 'personal_trainer', name='gym_type_enum')
    gym_type_enum.create(op.get_bind(), checkfirst=True)

    # Agregar columna type con default 'gym' para mantener compatibilidad
    op.add_column('gyms',
        sa.Column('type', gym_type_enum, nullable=False, server_default='gym')
    )

    # Agregar campos específicos para entrenadores (todos opcionales)
    op.add_column('gyms',
        sa.Column('trainer_specialties', sa.JSON, nullable=True,
                  comment='Especialidades del entrenador (solo para type=personal_trainer)')
    )

    op.add_column('gyms',
        sa.Column('trainer_certifications', sa.JSON, nullable=True,
                  comment='Certificaciones del entrenador en formato JSON')
    )

    op.add_column('gyms',
        sa.Column('max_clients', sa.Integer, nullable=True,
                  comment='Máximo de clientes simultáneos para el entrenador')
    )

    # Crear índice para optimizar queries por tipo
    op.create_index('idx_gyms_type', 'gyms', ['type'])

    # Crear índice compuesto para queries de gimnasios activos por tipo
    op.create_index('idx_gyms_type_active', 'gyms', ['type', 'is_active'])


def downgrade():
    # Eliminar índices
    op.drop_index('idx_gyms_type_active', 'gyms')
    op.drop_index('idx_gyms_type', 'gyms')

    # Eliminar columnas agregadas
    op.drop_column('gyms', 'max_clients')
    op.drop_column('gyms', 'trainer_certifications')
    op.drop_column('gyms', 'trainer_specialties')
    op.drop_column('gyms', 'type')

    # Eliminar el enum
    gym_type_enum = sa.Enum('gym', 'personal_trainer', name='gym_type_enum')
    gym_type_enum.drop(op.get_bind()) 