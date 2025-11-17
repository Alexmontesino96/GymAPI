"""add color field to user table

Revision ID: 96995857d632
Revises: cebae10190ed
Create Date: 2025-08-08 02:13:39.250897

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '96995857d632'
down_revision = 'cebae10190ed'
branch_labels = None
depends_on = None


def upgrade():
    # Añadir campo color a la tabla user
    op.add_column('user', sa.Column('color', sa.String(7), nullable=True, comment='Color hexadecimal para el perfil del usuario (ej: #FF5733)'))


def downgrade():
    # Remover campo color de la tabla user
    op.drop_column('user', 'color') 