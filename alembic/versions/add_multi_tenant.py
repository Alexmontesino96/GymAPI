"""
Migración para implementar estructura multi-tenant (gimnasios).

Revision ID: add_multi_tenant
Create Date: 2023-04-01 10:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from datetime import datetime

# Importar enums para conservarlos en la migración
from sqlalchemy import Enum
import enum

# Definir enums usados en la migración
class GymRoleType(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    TRAINER = "TRAINER"
    MEMBER = "MEMBER"


# revision identifiers, used by Alembic.
revision = 'add_multi_tenant'
down_revision = '4dfcdddc1734'  # Revisión anterior
branch_labels = None
depends_on = None


def upgrade():
    # 1. Crear tabla de gimnasios (tenants)
    op.create_table(
        'gyms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('subdomain', sa.String(100), nullable=False),
        sa.Column('logo_url', sa.String(255), nullable=True),
        sa.Column('address', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(100), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Índice para búsqueda rápida por subdominio
    op.create_index('ix_gyms_subdomain', 'gyms', ['subdomain'], unique=True)
    
    # 2. Crear gimnasio predeterminado
    op.execute("""
        INSERT INTO gyms (id, name, subdomain, is_active, created_at, updated_at)
        VALUES (1, 'Gimnasio Predeterminado', 'default', true, NOW(), NOW())
    """)
    
    # 3. Crear tabla de asociación usuario-gimnasio
    op.create_table(
        'user_gyms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Enum(GymRoleType), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'gym_id', name='uq_user_gym')
    )
    
    # 4. Migrar usuarios existentes al gimnasio predeterminado
    op.execute("""
        INSERT INTO user_gyms (user_id, gym_id, role, created_at)
        SELECT id, 1, 
            CASE 
                WHEN role = 'ADMIN' THEN 'ADMIN'::gymroletype
                WHEN role = 'TRAINER' THEN 'TRAINER'::gymroletype
                ELSE 'MEMBER'::gymroletype
            END,
            created_at
        FROM user
    """)
    
    # 5. Añadir columna gym_id a las tablas existentes
    tables_to_update = [
        'events',
        'class_types',
        'class_sessions',
        'gym_schedules',
        'special_days',
        'event_participations',
        'class_registrations',
        'chat_rooms'
    ]
    
    for table in tables_to_update:
        try:
            # Añadir columna nullable primero
            op.add_column(table, sa.Column('gym_id', sa.Integer(), nullable=True))
            
            # Establecer gimnasio predeterminado para registros existentes
            op.execute(f"UPDATE {table} SET gym_id = 1")
            
            # Hacer columna NOT NULL después de actualizar datos
            op.alter_column(table, 'gym_id', nullable=False)
            
            # Añadir clave foránea
            op.create_foreign_key(
                f'fk_{table}_gym_id', 
                table, 'gyms', 
                ['gym_id'], ['id'], 
                ondelete='CASCADE'
            )
            
            # Añadir índice para mejorar rendimiento de consultas por gimnasio
            op.create_index(f'ix_{table}_gym_id', table, ['gym_id'])
        except Exception as e:
            print(f"Error al actualizar tabla {table}: {e}")
            # Continuar con las demás tablas si una falla
    
    # 6. Crear índices compuestos para optimizar consultas comunes
    # Eventos por gimnasio y estado
    op.create_index('ix_events_gym_status', 'events', ['gym_id', 'status'])
    
    # Clases por gimnasio y fecha
    op.create_index('ix_class_sessions_gym_date', 'class_sessions', ['gym_id', 'start_time'])
    
    # Horarios por gimnasio
    op.create_index('ix_gym_schedules_gym_day', 'gym_schedules', ['gym_id', 'day_of_week'])


def downgrade():
    # Eliminar índices compuestos
    op.drop_index('ix_gym_schedules_gym_day')
    op.drop_index('ix_class_sessions_gym_date')
    op.drop_index('ix_events_gym_status')
    
    # Eliminar columna gym_id de las tablas
    tables_to_update = [
        'events',
        'class_types',
        'class_sessions',
        'gym_schedules',
        'special_days',
        'event_participations',
        'class_registrations',
        'chat_rooms'
    ]
    
    for table in tables_to_update:
        try:
            # Eliminar clave foránea e índice primero
            op.drop_constraint(f'fk_{table}_gym_id', table, type_='foreignkey')
            op.drop_index(f'ix_{table}_gym_id', table_name=table)
            
            # Eliminar columna
            op.drop_column(table, 'gym_id')
        except Exception as e:
            print(f"Error al revertir tabla {table}: {e}")
    
    # Eliminar tabla user_gyms
    op.drop_table('user_gyms')
    
    # Eliminar tabla gyms
    op.drop_index('ix_gyms_subdomain')
    op.drop_table('gyms') 