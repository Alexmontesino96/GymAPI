"""add_completion_attempts_to_event

Revision ID: abea55336551
Revises: b9c74d13a363
Create Date: 2025-04-27 14:06:11.377344

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abea55336551'
down_revision = 'b9c74d13a363'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('completion_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_events_completion_attempts'), 'events', ['completion_attempts'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_events_completion_attempts'), table_name='events')
    op.drop_column('events', 'completion_attempts') 