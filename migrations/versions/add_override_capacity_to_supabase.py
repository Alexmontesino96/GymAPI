"""add_override_capacity_to_supabase

Revision ID: add_override_capacity_to_supabase
Revises: direct_add_override_capacity
Create Date: 2025-04-18 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, exc


# revision identifiers, used by Alembic.
revision = 'add_override_capacity_to_supabase'
down_revision = 'direct_add_override_capacity'
branch_labels = None
depends_on = None


def upgrade():
    # Intentamos añadir la columna override_capacity a Supabase
    try:
        op.execute(text(
            "ALTER TABLE class_session ADD COLUMN IF NOT EXISTS override_capacity INTEGER"
        ))
        print("Columna override_capacity añadida a Supabase (o ya existía)")
    except exc.SQLAlchemyError as e:
        print(f"Error al añadir la columna en Supabase (es posible que ya exista): {e}")
        # Permitimos que la migración continúe incluso si hay error


def downgrade():
    # No eliminamos la columna en caso de rollback
    pass 