"""nullify_times_when_closed

Revision ID: e1c3c9ad31f2
Revises: fcef249f3cff
Create Date: 2025-07-02 00:30:00.000000

Pone open_time y close_time a NULL en gym_hours y gym_special_hours donde is_closed=True.
"""

from alembic import op
import sqlalchemy as sa

revision = 'e1c3c9ad31f2'
down_revision = 'fcef249f3cff'
branch_labels = None
depends_on = None

def upgrade():
    # Actualizar gym_hours
    op.execute(sa.text("""
        UPDATE gym_hours
        SET open_time = NULL, close_time = NULL
        WHERE is_closed = TRUE;
    """))

    # Actualizar gym_special_hours
    op.execute(sa.text("""
        UPDATE gym_special_hours
        SET open_time = NULL, close_time = NULL
        WHERE is_closed = TRUE;
    """))

def downgrade():
    # No podemos restaurar los valores originales automáticamente.
    pass 