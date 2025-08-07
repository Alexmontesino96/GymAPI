"""
Migración para convertir ClassSession timestamps a UTC con timezone-aware.

Revision ID: migrate_class_sessions_to_utc
Revises: dbe094e2866a
Create Date: 2025-08-07 10:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'migrate_class_sessions_to_utc'
down_revision = 'dbe094e2866a'
branch_labels = None
depends_on = None


def upgrade():
    """
    Migración de campos DateTime naive a DateTime(timezone=True) con datos en UTC.
    """
    
    # Paso 1: Añadir nuevas columnas timezone-aware
    op.add_column('class_session', 
        sa.Column('start_time_utc', sa.DateTime(timezone=True), nullable=True))
    op.add_column('class_session', 
        sa.Column('end_time_utc', sa.DateTime(timezone=True), nullable=True))
    
    # Paso 2: Migrar datos existentes de hora local a UTC
    # Usar la función AT TIME ZONE de PostgreSQL para conversión correcta
    connection = op.get_bind()
    
    # Obtener todas las sesiones con la timezone del gimnasio
    result = connection.execute(text("""
        SELECT cs.id, cs.start_time, cs.end_time, g.timezone
        FROM class_session cs
        JOIN gyms g ON cs.gym_id = g.id
        WHERE cs.start_time IS NOT NULL AND cs.end_time IS NOT NULL
    """))
    
    # Convertir cada sesión a UTC usando la timezone del gimnasio
    for row in result:
        if row.start_time and row.end_time:
            # PostgreSQL convierte: hora_naive AT TIME ZONE 'gym_tz' AT TIME ZONE 'UTC'
            # Primero interpreta como hora local del gym, luego convierte a UTC
            connection.execute(text("""
                UPDATE class_session 
                SET start_time_utc = :start_time AT TIME ZONE :tz AT TIME ZONE 'UTC',
                    end_time_utc = :end_time AT TIME ZONE :tz AT TIME ZONE 'UTC'
                WHERE id = :id
            """), {
                'id': row.id,
                'start_time': row.start_time,
                'end_time': row.end_time,
                'tz': row.timezone
            })
    
    # Paso 3: Hacer las nuevas columnas no-nullables
    op.alter_column('class_session', 'start_time_utc', nullable=False)
    op.alter_column('class_session', 'end_time_utc', nullable=False)
    
    # Paso 4: Eliminar las columnas viejas
    op.drop_column('class_session', 'start_time')
    op.drop_column('class_session', 'end_time')
    
    # Paso 5: Renombrar las nuevas columnas para mantener consistencia
    op.alter_column('class_session', 'start_time_utc', new_column_name='start_time')
    op.alter_column('class_session', 'end_time_utc', new_column_name='end_time')
    
    # Paso 6: Crear índices optimizados para las queries del background task
    op.create_index('idx_session_gym_status_times', 'class_session', 
                    ['gym_id', 'status', 'start_time', 'end_time'])
    op.create_index('idx_session_end_time', 'class_session', ['end_time'])
    
    # Índice parcial para sesiones activas (más eficiente)
    connection.execute(text("""
        CREATE INDEX idx_active_sessions 
        ON class_session(gym_id, start_time, end_time) 
        WHERE status IN ('scheduled', 'in_progress')
    """))


def downgrade():
    """
    Revertir a campos DateTime naive con hora local.
    """
    
    # Eliminar índices
    op.drop_index('idx_active_sessions', 'class_session')
    op.drop_index('idx_session_end_time', 'class_session')
    op.drop_index('idx_session_gym_status_times', 'class_session')
    
    # Renombrar columnas actuales
    op.alter_column('class_session', 'start_time', new_column_name='start_time_utc')
    op.alter_column('class_session', 'end_time', new_column_name='end_time_utc')
    
    # Añadir columnas naive
    op.add_column('class_session', 
        sa.Column('start_time', sa.DateTime(), nullable=True))
    op.add_column('class_session', 
        sa.Column('end_time', sa.DateTime(), nullable=True))
    
    # Convertir datos de UTC a hora local
    connection = op.get_bind()
    
    result = connection.execute(text("""
        SELECT cs.id, cs.start_time_utc, cs.end_time_utc, g.timezone
        FROM class_session cs
        JOIN gyms g ON cs.gym_id = g.id
    """))
    
    for row in result:
        if row.start_time_utc and row.end_time_utc:
            # Convertir de UTC a hora local del gimnasio
            connection.execute(text("""
                UPDATE class_session 
                SET start_time = :start_utc AT TIME ZONE 'UTC' AT TIME ZONE :tz,
                    end_time = :end_utc AT TIME ZONE 'UTC' AT TIME ZONE :tz
                WHERE id = :id
            """), {
                'id': row.id,
                'start_utc': row.start_time_utc,
                'end_utc': row.end_time_utc,
                'tz': row.timezone
            })
    
    # Hacer columnas no-nullables
    op.alter_column('class_session', 'start_time', nullable=False)
    op.alter_column('class_session', 'end_time', nullable=False)
    
    # Eliminar columnas UTC
    op.drop_column('class_session', 'start_time_utc')
    op.drop_column('class_session', 'end_time_utc')
    
    # Recrear índice original
    op.create_index('ix_class_session_start_time', 'class_session', ['start_time'])