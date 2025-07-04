"""add_billing_module

Revision ID: f9b8c7d5e2a1
Revises: e1c3c9ad31f2
Create Date: 2025-07-02 12:00:00.000000

Añade el módulo de billing con Stripe al sistema de módulos activables.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f9b8c7d5e2a1'
down_revision = 'e1c3c9ad31f2'
branch_labels = None
depends_on = None

def upgrade():
    # Insertar el módulo de billing
    op.execute(
        """
        INSERT INTO modules (code, name, description, is_premium, created_at, updated_at) 
        VALUES 
        ('billing', 'Facturación y Pagos', 'Integración con Stripe para procesamiento de pagos, suscripciones y facturación automática', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    
    # El módulo billing NO se activa automáticamente para gimnasios existentes
    # ya que es premium y requiere configuración específica de Stripe

def downgrade():
    # Desactivar el módulo billing para todos los gimnasios
    op.execute(
        """
        DELETE FROM gym_modules 
        WHERE module_id = (SELECT id FROM modules WHERE code = 'billing')
        """
    )
    
    # Eliminar el módulo billing
    op.execute(
        """
        DELETE FROM modules WHERE code = 'billing'
        """
    ) 