"""merge migration heads before adding post_views

Revision ID: fd54000bbbcb
Revises: e4f5a6b7c8d9, f546b56de5bb
Create Date: 2025-11-16 21:17:43.827609

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd54000bbbcb'
down_revision = ('e4f5a6b7c8d9', 'f546b56de5bb')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass 