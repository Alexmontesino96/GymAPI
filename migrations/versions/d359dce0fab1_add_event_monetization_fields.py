"""add_event_monetization_fields

Revision ID: d359dce0fab1
Revises: 98cb38633624
Create Date: 2025-10-27 01:18:11.176284

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd359dce0fab1'
down_revision = '98cb38633624'
branch_labels = None
depends_on = None


def upgrade():
    # Crear nuevos enums
    refund_policy_type = sa.Enum('NO_REFUND', 'FULL_REFUND', 'PARTIAL_REFUND', 'CREDIT', name='refundpolicytype')
    payment_status_type = sa.Enum('PENDING', 'PAID', 'REFUNDED', 'CREDITED', 'EXPIRED', name='paymentstatustype')

    refund_policy_type.create(op.get_bind(), checkfirst=True)
    payment_status_type.create(op.get_bind(), checkfirst=True)

    # Agregar campos de monetización a la tabla events
    op.add_column('events', sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('events', sa.Column('price_cents', sa.Integer(), nullable=True))
    op.add_column('events', sa.Column('currency', sa.String(length=3), nullable=True, server_default='EUR'))
    op.add_column('events', sa.Column('refund_policy', refund_policy_type, nullable=True))
    op.add_column('events', sa.Column('refund_deadline_hours', sa.Integer(), nullable=True, server_default='24'))
    op.add_column('events', sa.Column('partial_refund_percentage', sa.Integer(), nullable=True, server_default='50'))
    op.add_column('events', sa.Column('stripe_product_id', sa.String(length=255), nullable=True))
    op.add_column('events', sa.Column('stripe_price_id', sa.String(length=255), nullable=True))

    # Crear índices para búsqueda eficiente
    op.create_index('ix_events_is_paid', 'events', ['is_paid'], unique=False)
    op.create_index('ix_events_stripe_product_id', 'events', ['stripe_product_id'], unique=False)
    op.create_index('ix_events_stripe_price_id', 'events', ['stripe_price_id'], unique=False)

    # Agregar campos de pago a la tabla event_participations
    op.add_column('event_participations', sa.Column('payment_status', payment_status_type, nullable=True))
    op.add_column('event_participations', sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True))
    op.add_column('event_participations', sa.Column('amount_paid_cents', sa.Integer(), nullable=True))
    op.add_column('event_participations', sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('event_participations', sa.Column('refund_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('event_participations', sa.Column('refund_amount_cents', sa.Integer(), nullable=True))
    op.add_column('event_participations', sa.Column('payment_expiry', sa.DateTime(timezone=True), nullable=True))

    # Crear índices para búsqueda eficiente
    op.create_index('ix_event_participations_payment_status', 'event_participations', ['payment_status'], unique=False)
    op.create_index('ix_event_participations_stripe_payment_intent_id', 'event_participations', ['stripe_payment_intent_id'], unique=False)

    # Establecer valor por defecto para registros existentes
    op.execute("UPDATE events SET is_paid = false WHERE is_paid IS NULL")


def downgrade():
    # Eliminar índices
    op.drop_index('ix_event_participations_stripe_payment_intent_id', table_name='event_participations')
    op.drop_index('ix_event_participations_payment_status', table_name='event_participations')
    op.drop_index('ix_events_stripe_price_id', table_name='events')
    op.drop_index('ix_events_stripe_product_id', table_name='events')
    op.drop_index('ix_events_is_paid', table_name='events')

    # Eliminar columnas de event_participations
    op.drop_column('event_participations', 'payment_expiry')
    op.drop_column('event_participations', 'refund_amount_cents')
    op.drop_column('event_participations', 'refund_date')
    op.drop_column('event_participations', 'payment_date')
    op.drop_column('event_participations', 'amount_paid_cents')
    op.drop_column('event_participations', 'stripe_payment_intent_id')
    op.drop_column('event_participations', 'payment_status')

    # Eliminar columnas de events
    op.drop_column('events', 'stripe_price_id')
    op.drop_column('events', 'stripe_product_id')
    op.drop_column('events', 'partial_refund_percentage')
    op.drop_column('events', 'refund_deadline_hours')
    op.drop_column('events', 'refund_policy')
    op.drop_column('events', 'currency')
    op.drop_column('events', 'price_cents')
    op.drop_column('events', 'is_paid')

    # Eliminar enums
    sa.Enum(name='paymentstatustype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='refundpolicytype').drop(op.get_bind(), checkfirst=True) 