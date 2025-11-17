"""
Add unique constraint on class_participation (session_id, member_id)

Revision ID: 20250813_add_unique_participation_constraint
Revises: 20250813_alter_class_session_to_timestamptz
Create Date: 2025-08-13 00:05:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'b16a2c3d4e5f'
down_revision = 'ae10f2c3d4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        'uq_participation_session_member',
        'class_participation',
        ['session_id', 'member_id']
    )


def downgrade():
    op.drop_constraint('uq_participation_session_member', 'class_participation', type_='unique')
