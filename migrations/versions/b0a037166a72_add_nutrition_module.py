"""add_nutrition_module

Revision ID: b0a037166a72
Revises: h394dbb765b6
Create Date: 2025-07-07 22:04:42.443987

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0a037166a72'
down_revision = 'h394dbb765b6'
branch_labels = None
depends_on = None


def upgrade():
    # Insertar el módulo de nutrition
    op.execute(
        """
        INSERT INTO modules (code, name, description, is_premium, created_at, updated_at) 
        VALUES 
        ('nutrition', 'Planes Nutricionales', 'Sistema completo de planes nutricionales con seguimiento híbrido (template, live, archived)', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    
    # Activar el módulo nutrition para todos los gimnasios existentes
    op.execute(
        """
        INSERT INTO gym_modules (gym_id, module_id, active, activated_at)
        SELECT g.id, m.id, true, CURRENT_TIMESTAMP
        FROM gyms g, modules m
        WHERE m.code = 'nutrition'
        """
    )


def downgrade():
    # Desactivar el módulo nutrition para todos los gimnasios
    op.execute(
        """
        DELETE FROM gym_modules 
        WHERE module_id = (SELECT id FROM modules WHERE code = 'nutrition')
        """
    )
    
    # Eliminar el módulo nutrition
    op.execute(
        """
        DELETE FROM modules WHERE code = 'nutrition'
        """
    ) 