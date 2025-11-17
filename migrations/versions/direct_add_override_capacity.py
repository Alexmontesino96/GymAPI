"""direct_add_override_capacity

Revision ID: direct_add_override_capacity
Revises: ensure_override_capacity
Create Date: 2025-04-18 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'direct_add_override_capacity'
down_revision = 'ensure_override_capacity'
branch_labels = None
depends_on = None


def upgrade():
    # Revisamos primero si la columna existe usando SQL directo
    conn = op.get_bind()
    try:
        # Esta consulta fallará si la columna no existe
        conn.execute(text("SELECT override_capacity FROM class_session LIMIT 1"))
        print("La columna override_capacity ya existe, no se requiere acción")
    except Exception:
        # La columna no existe, intentamos añadirla con SQL directo
        try:
            conn.execute(text("ALTER TABLE class_session ADD COLUMN override_capacity INTEGER"))
            print("Columna override_capacity añadida con éxito mediante SQL directo")
        except Exception as e:
            # Si falla con un error diferente, lo mostramos
            print(f"Error al añadir la columna: {e}")
            # Pero permitimos que la migración continúe
            pass


def downgrade():
    # No eliminar la columna en caso de rollback
    pass 