"""fix_is_closed_open_close_null

Revision ID: dbe094e2866a
Revises: a762df8c3a1e
Create Date: 2025-07-02 00:00:00.000000

Asegura que, para los registros marcados como is_closed=True, los campos open_time y close_time
estén a NULL (ya que el gimnasio está cerrado ese día).
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'dbe094e2866a'
down_revision = 'a762df8c3a1e'
branch_labels = None
depends_on = None

def upgrade():
    # Actualizar gym_hours
    op.execute(sa.text("""
        UPDATE gym_hours
        SET open_time = NULL, close_time = NULL
        WHERE is_closed = TRUE
    """))

    # Actualizar gym_special_hours
    op.execute(sa.text("""
        UPDATE gym_special_hours
        SET open_time = NULL, close_time = NULL
        WHERE is_closed = TRUE
    """))


def downgrade():
    # No es posible restaurar automáticamente los horarios anteriores.
    # Dejar vacío o lanzar advertencia si se requiere.
    pass 