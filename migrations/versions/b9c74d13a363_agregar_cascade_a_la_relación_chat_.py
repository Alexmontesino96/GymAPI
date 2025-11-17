"""Agregar cascade a la relación chat_rooms en Event

Revision ID: b9c74d13a363
Revises: add_override_capacity_to_supabase
Create Date: 2025-04-25 12:40:16.165007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9c74d13a363'
down_revision = 'add_override_capacity_to_supabase'
branch_labels = None
depends_on = None


def upgrade():
    # Este cambio modifica la relación ORM en el código Python, no la estructura de la base de datos.
    # Se agregó cascade="all, delete-orphan" a la relación chat_rooms en el modelo Event.
    # No es necesario hacer cambios en el esquema de base de datos.
    pass


def downgrade():
    # El cambio solo afecta al código Python, no a la estructura de la base de datos.
    # Para revertir, eliminar cascade="all, delete-orphan" de la relación chat_rooms en el modelo Event.
    pass 