"""add event cancellation audit fields

Revision ID: e4f5a6b7c8d9
Revises: c2cc1116104f
Create Date: 2025-10-30 21:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e4f5a6b7c8d9'
down_revision = 'c2cc1116104f'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar campos de auditoría de cancelación a la tabla events
    op.add_column('events', sa.Column('cancellation_date', sa.DateTime(timezone=True), nullable=True,
                                      comment='Fecha en que el evento fue cancelado'))
    op.add_column('events', sa.Column('cancelled_by_user_id', sa.Integer(), nullable=True,
                                      comment='ID del usuario que canceló el evento (admin/owner)'))
    op.add_column('events', sa.Column('cancellation_reason', sa.Text(), nullable=True,
                                      comment='Razón de la cancelación del evento'))
    op.add_column('events', sa.Column('total_refunded_cents', sa.Integer(), nullable=True,
                                      comment='Total de dinero reembolsado en cancelación masiva (en centavos)'))

    # Crear foreign key para cancelled_by_user_id
    op.create_foreign_key('fk_events_cancelled_by_user_id', 'events', 'user', ['cancelled_by_user_id'], ['id'])

    # Crear índice para cancelled_by_user_id
    op.create_index('ix_events_cancelled_by_user_id', 'events', ['cancelled_by_user_id'])


def downgrade():
    # Eliminar índice
    op.drop_index('ix_events_cancelled_by_user_id', table_name='events')

    # Eliminar foreign key
    op.drop_constraint('fk_events_cancelled_by_user_id', 'events', type_='foreignkey')

    # Eliminar columnas
    op.drop_column('events', 'total_refunded_cents')
    op.drop_column('events', 'cancellation_reason')
    op.drop_column('events', 'cancelled_by_user_id')
    op.drop_column('events', 'cancellation_date')
