"""
Alter class_session timestamps to timestamptz (UTC)

Revision ID: 20250813_alter_class_session_to_timestamptz
Revises: 402f9b8ef40e
Create Date: 2025-08-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'ae10f2c3d4b5'
down_revision = '402f9b8ef40e'
branch_labels = None
depends_on = None


def upgrade():
    """
    Convert class_session.start_time/end_time to TIMESTAMP WITH TIME ZONE.
    Assumes stored values represent UTC wall time (tzinfo lost); re-tag as UTC.
    """
    conn = op.get_bind()

    # Drop dependent indexes if any reference these columns directly (safe no-op if they don't exist)
    try:
        conn.execute(text("DROP INDEX IF EXISTS ix_class_session_start_time"))
    except Exception:
        pass

    # Alter columns using AT TIME ZONE 'UTC' to preserve actual moment
    op.alter_column(
        'class_session',
        'start_time',
        type_=sa.DateTime(timezone=True),
        postgresql_using="start_time AT TIME ZONE 'UTC'"
    )
    op.alter_column(
        'class_session',
        'end_time',
        type_=sa.DateTime(timezone=True),
        postgresql_using="end_time AT TIME ZONE 'UTC'"
    )

    # Recreate useful index on start_time
    op.create_index('ix_class_session_start_time', 'class_session', ['start_time'])


def downgrade():
    """
    Revert to TIMESTAMP WITHOUT TIME ZONE (not recommended).
    """
    conn = op.get_bind()
    try:
        conn.execute(text("DROP INDEX IF EXISTS ix_class_session_start_time"))
    except Exception:
        pass

    op.alter_column(
        'class_session',
        'start_time',
        type_=sa.DateTime(timezone=False),
        postgresql_using="start_time AT TIME ZONE 'UTC'"
    )
    op.alter_column(
        'class_session',
        'end_time',
        type_=sa.DateTime(timezone=False),
        postgresql_using="end_time AT TIME ZONE 'UTC'"
    )

    op.create_index('ix_class_session_start_time', 'class_session', ['start_time'])
