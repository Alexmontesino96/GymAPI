"""ensure override_capacity column exists

Revision ID: ensure_override_capacity
Revises: fix_override_capacity
Create Date: 2025-04-18 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ensure_override_capacity'
down_revision = 'fix_override_capacity'
branch_labels = None
depends_on = None


def upgrade():
    # Forzamos la creación de la columna override_capacity
    # Si hay error porque ya existe, lo capturamos y seguimos
    try:
        op.execute("ALTER TABLE class_session ADD COLUMN override_capacity INTEGER")
        print("Columna override_capacity añadida con éxito")
    except Exception as e:
        # Si falla porque la columna ya existe, el mensaje incluirá "already exists"
        if "already exists" in str(e):
            print("La columna override_capacity ya existe, no se requiere acción")
        else:
            # Si es otro tipo de error, lo propagamos
            raise e


def downgrade():
    # No eliminar la columna en caso de rollback
    pass 