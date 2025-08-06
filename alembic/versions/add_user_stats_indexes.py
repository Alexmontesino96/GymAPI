"""Add indexes for user stats performance

Revision ID: add_user_stats_indexes
Revises: 
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_stats_indexes'
down_revision = '7220aa4baad6'
depends_on = None


def upgrade():
    """Add performance indexes for user stats queries."""
    
    # Índice compuesto para ClassParticipation - optimiza queries de stats de usuario
    op.create_index(
        'ix_class_participation_user_gym_status_date',
        'class_participation',
        ['user_id', 'gym_id', 'status', 'created_at'],
        unique=False
    )
    
    # Índice para optimizar queries de racha actual
    op.create_index(
        'ix_class_participation_user_gym_attended',
        'class_participation',
        ['user_id', 'gym_id', 'created_at'],
        unique=False,
        postgresql_where=sa.text("status = 'attended'")
    )
    
    # Índice para EventParticipation - optimiza queries de eventos
    op.create_index(
        'ix_event_participation_member_gym_date', 
        'event_participations',
        ['member_id', 'gym_id', 'attended'],
        unique=False
    )
    
    # Índice para ChatMember - optimiza queries sociales
    op.create_index(
        'ix_chat_member_user_room',
        'chat_members', 
        ['user_id', 'room_id'],
        unique=False
    )
    
    # Índice para UserGym - optimiza queries de membresía
    op.create_index(
        'ix_user_gym_user_gym_created',
        'user_gyms',
        ['user_id', 'gym_id', 'created_at'],
        unique=False
    )


def downgrade():
    """Remove performance indexes."""
    
    op.drop_index('ix_class_participation_user_gym_status_date', table_name='class_participation')
    op.drop_index('ix_class_participation_user_gym_attended', table_name='class_participation')
    op.drop_index('ix_event_participation_member_gym_date', table_name='event_participations')
    op.drop_index('ix_chat_member_user_room', table_name='chat_members')
    op.drop_index('ix_user_gym_user_gym_created', table_name='user_gyms')