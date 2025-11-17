"""initialize_completion_attempts_to_zero

Revision ID: 1f05122523da
Revises: abea55336551
Create Date: 2025-04-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = '1f05122523da'
down_revision = 'abea55336551'
branch_labels = None
depends_on = None


def upgrade():
    # Actualizar todos los registros existentes en la tabla events 
    # para asegurar que completion_attempts sea 0
    op.execute(text("UPDATE events SET completion_attempts = 0"))


def downgrade():
    # No hay acción de reversión necesaria
    pass 