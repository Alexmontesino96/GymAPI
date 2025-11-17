"""
Merge heads for schedule+user branches

Revision ID: 20250813_merge_heads
Revises: 96995857d632, 20250813_add_unique_participation_constraint
Create Date: 2025-08-13 00:12:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c26b3d4e5f60'
down_revision = ('96995857d632', 'b16a2c3d4e5f')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
