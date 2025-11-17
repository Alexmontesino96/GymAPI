"""add_stripe_connect_tables

Revision ID: a1b2c3d4e5f6
Revises: 7b04db828651
Create Date: 2025-07-11 01:00:00.000000

Añade tablas para Stripe Connect y vinculación de usuarios con customers.
Resuelve el problema de duplicación de customers en entorno multitenant.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '7b04db828651'  # Última migración en el historial
branch_labels = None
depends_on = None

def upgrade():
    # Crear tabla gym_stripe_accounts
    op.create_table('gym_stripe_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('stripe_account_id', sa.String(length=255), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=False),
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False),
        sa.Column('charges_enabled', sa.Boolean(), nullable=False),
        sa.Column('payouts_enabled', sa.Boolean(), nullable=False),
        sa.Column('details_submitted', sa.Boolean(), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('default_currency', sa.String(length=3), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('onboarding_url', sa.String(length=500), nullable=True),
        sa.Column('onboarding_expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gym_id'),
        sa.UniqueConstraint('stripe_account_id')
    )
    op.create_index(op.f('ix_gym_stripe_accounts_id'), 'gym_stripe_accounts', ['id'], unique=False)
    
    # Crear tabla user_gym_stripe_profiles
    op.create_table('user_gym_stripe_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_account_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('customer_created_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'gym_id', name='uq_user_gym_stripe'),
        sa.UniqueConstraint('stripe_customer_id', 'stripe_account_id', name='uq_customer_account')
    )
    op.create_index(op.f('ix_user_gym_stripe_profiles_id'), 'user_gym_stripe_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_user_gym_stripe_profiles_user_id'), 'user_gym_stripe_profiles', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_gym_stripe_profiles_gym_id'), 'user_gym_stripe_profiles', ['gym_id'], unique=False)
    op.create_index(op.f('ix_user_gym_stripe_profiles_stripe_customer_id'), 'user_gym_stripe_profiles', ['stripe_customer_id'], unique=False)
    op.create_index(op.f('ix_user_gym_stripe_profiles_stripe_account_id'), 'user_gym_stripe_profiles', ['stripe_account_id'], unique=False)

def downgrade():
    # Eliminar tablas en orden inverso
    op.drop_index(op.f('ix_user_gym_stripe_profiles_stripe_account_id'), table_name='user_gym_stripe_profiles')
    op.drop_index(op.f('ix_user_gym_stripe_profiles_stripe_customer_id'), table_name='user_gym_stripe_profiles')
    op.drop_index(op.f('ix_user_gym_stripe_profiles_gym_id'), table_name='user_gym_stripe_profiles')
    op.drop_index(op.f('ix_user_gym_stripe_profiles_user_id'), table_name='user_gym_stripe_profiles')
    op.drop_index(op.f('ix_user_gym_stripe_profiles_id'), table_name='user_gym_stripe_profiles')
    op.drop_table('user_gym_stripe_profiles')
    
    op.drop_index(op.f('ix_gym_stripe_accounts_id'), table_name='gym_stripe_accounts')
    op.drop_table('gym_stripe_accounts') 