"""agregar_gym_id_a_class_category_custom

Revision ID: 3f0c8f1524ed
Revises: 80b8d0ec43e8
Create Date: 2025-04-03 22:11:00.984900

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f0c8f1524ed'
down_revision = '80b8d0ec43e8'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Añadir columna gym_id como nullable primero
    op.add_column('class_category_custom', sa.Column('gym_id', sa.Integer(), nullable=True))
    
    # 2. Asignar todas las categorías existentes al gimnasio predeterminado (ID=1)
    op.execute("UPDATE class_category_custom SET gym_id = 1")
    
    # 3. Añadir la restricción de clave foránea
    op.create_foreign_key(
        'fk_class_category_custom_gym_id', 
        'class_category_custom', 'gyms', 
        ['gym_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 4. Hacer la columna NOT NULL después de actualizar los datos
    op.alter_column('class_category_custom', 'gym_id', nullable=False)
    
    # 5. Crear un índice para mejorar el rendimiento
    op.create_index('ix_class_category_custom_gym_id', 'class_category_custom', ['gym_id'])


def downgrade():
    # 1. Eliminar el índice
    op.drop_index('ix_class_category_custom_gym_id', table_name='class_category_custom')
    
    # 2. Eliminar la restricción de clave foránea
    op.drop_constraint('fk_class_category_custom_gym_id', 'class_category_custom', type_='foreignkey')
    
    # 3. Eliminar la columna
    op.drop_column('class_category_custom', 'gym_id')