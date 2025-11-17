"""fix override_capacity column in class_session

Revision ID: fix_override_capacity
Revises: eb04b46638c6
Create Date: 2025-04-18 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision = 'fix_override_capacity'
down_revision = 'eb04b46638c6'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la columna ya existe antes de intentar crearla
    connection = op.get_bind()
    inspector = reflection.Inspector.from_engine(connection)
    columns = [c['name'] for c in inspector.get_columns('class_session')]
    
    if 'override_capacity' not in columns:
        # La columna no existe, la añadimos
        op.add_column('class_session', sa.Column('override_capacity', sa.Integer(), nullable=True))
        print("Columna override_capacity añadida con éxito")
    else:
        print("La columna override_capacity ya existe, no se requiere acción")


def downgrade():
    # No hacemos nada en el rollback para evitar eliminar la columna si ya existía
    pass 