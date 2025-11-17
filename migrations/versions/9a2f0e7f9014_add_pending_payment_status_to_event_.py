"""add_pending_payment_status_to_event_participation

Revision ID: 9a2f0e7f9014
Revises: d359dce0fab1
Create Date: 2025-10-30 02:40:24.860938

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a2f0e7f9014'
down_revision = 'add_survey_system'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar nuevo valor 'PENDING_PAYMENT' al enum eventparticipationstatus
    # IMPORTANTE: En PostgreSQL, ALTER TYPE ADD VALUE no puede ejecutarse dentro de una transacción
    # por lo que usamos execute con autocommit
    op.execute("ALTER TYPE eventparticipationstatus ADD VALUE IF NOT EXISTS 'PENDING_PAYMENT'")


def downgrade():
    # NOTA: PostgreSQL no permite eliminar valores de un enum directamente
    # Si realmente necesitas hacer downgrade, tendrías que:
    # 1. Crear un nuevo enum sin el valor
    # 2. Migrar todos los datos
    # 3. Eliminar el enum viejo
    # 4. Renombrar el nuevo enum
    # Por ahora, dejamos este downgrade como no-op
    pass 