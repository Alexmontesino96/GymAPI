"""Add gym_id column to class_session table

Revision ID: 80b8d0ec43e8
Revises: d90cfda03499
Create Date: 2025-04-02 22:42:50.228690

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '80b8d0ec43e8'
down_revision = 'd90cfda03499'
branch_labels = None
depends_on = None


def upgrade():
    # Añadir la columna gym_id a la tabla class_session
    op.add_column('class_session', sa.Column('gym_id', sa.Integer(), nullable=True))
    
    # Crear la restricción de clave foránea a la tabla gyms
    op.create_foreign_key(
        'fk_class_session_gym_id_gyms',
        'class_session', 'gyms',
        ['gym_id'], ['id']
    )
    
    # Actualizar los registros existentes para asignar un gym_id (por defecto 1)
    # Esto asume que ya hay al menos un gimnasio con ID 1
    op.execute("UPDATE class_session SET gym_id = 1")
    
    # Cambiar la columna a NOT NULL después de actualizar los datos
    op.alter_column('class_session', 'gym_id', nullable=False)


def downgrade():
    # Eliminar la restricción de clave foránea
    op.drop_constraint('fk_class_session_gym_id_gyms', 'class_session', type_='foreignkey')
    
    # Eliminar la columna gym_id
    op.drop_column('class_session', 'gym_id') 