"""add user gym subscriptions table

Revision ID: add_user_gym_subscriptions
Revises: add_multi_tenant
Create Date: 2025-01-11 04:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_user_gym_subscriptions'
down_revision = 'add_multi_tenant'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla de suscripciones vinculadas
    op.create_table('user_gym_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_gym_stripe_profile_id', sa.Integer(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Claves primarias y foráneas
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_gym_stripe_profile_id'], ['user_gym_stripe_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['membership_plans.id'], ondelete='CASCADE'),
        
        # Índices únicos y de rendimiento
        sa.UniqueConstraint('stripe_subscription_id', name='uq_stripe_subscription_id'),
        sa.Index('idx_user_gym_subscriptions_profile_status', 'user_gym_stripe_profile_id', 'status'),
        sa.Index('idx_user_gym_subscriptions_plan', 'plan_id'),
        sa.Index('idx_user_gym_subscriptions_created', 'created_at'),
    )
    
    # Migrar datos existentes de UserGymStripeProfile
    # Solo si tienen stripe_subscription_id
    op.execute("""
        INSERT INTO user_gym_subscriptions (
            user_gym_stripe_profile_id,
            stripe_subscription_id,
            plan_id,
            status,
            created_at,
            notes
        )
        SELECT 
            ugsp.id,
            ugsp.stripe_subscription_id,
            COALESCE(
                (SELECT mp.id FROM membership_plans mp WHERE mp.gym_id = ugsp.gym_id LIMIT 1),
                1
            ) as plan_id,
            'active' as status,
            ugsp.created_at,
            'Migrado desde UserGymStripeProfile' as notes
        FROM user_gym_stripe_profiles ugsp
        WHERE ugsp.stripe_subscription_id IS NOT NULL
        AND ugsp.stripe_subscription_id != ''
    """)
    
    # Eliminar columna stripe_subscription_id de UserGymStripeProfile
    # (Opcional - mantenerla por ahora para compatibilidad)
    # op.drop_column('user_gym_stripe_profiles', 'stripe_subscription_id')


def downgrade():
    # Restaurar columna stripe_subscription_id si fue eliminada
    # op.add_column('user_gym_stripe_profiles', 
    #     sa.Column('stripe_subscription_id', sa.String(255), nullable=True))
    
    # Restaurar datos desde user_gym_subscriptions
    op.execute("""
        UPDATE user_gym_stripe_profiles 
        SET stripe_subscription_id = ugs.stripe_subscription_id
        FROM user_gym_subscriptions ugs
        WHERE user_gym_stripe_profiles.id = ugs.user_gym_stripe_profile_id
        AND ugs.status = 'active'
    """)
    
    # Eliminar tabla
    op.drop_table('user_gym_subscriptions') 