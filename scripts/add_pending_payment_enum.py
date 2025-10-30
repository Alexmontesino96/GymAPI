#!/usr/bin/env python
"""Script para agregar el valor PENDING_PAYMENT al enum eventparticipationstatus"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine
from sqlalchemy import text

def main():
    """Agrega el valor PENDING_PAYMENT al enum eventparticipationstatus"""

    sql = "ALTER TYPE eventparticipationstatus ADD VALUE IF NOT EXISTS 'PENDING_PAYMENT'"

    print("Agregando PENDING_PAYMENT al enum eventparticipationstatus...")

    try:
        # Ejecutar con autocommit ya que ALTER TYPE ADD VALUE no puede estar en transacción
        with engine.connect() as conn:
            conn.execute(text("COMMIT"))  # Cerrar cualquier transacción pendiente
            conn.execute(text(sql))
            print("✅ Valor PENDING_PAYMENT agregado exitosamente")

            # Verificar que se agregó
            result = conn.execute(text(
                "SELECT unnest(enum_range(NULL::eventparticipationstatus))::text as value"
            ))
            values = [row[0] for row in result]
            print(f"\nValores actuales del enum: {values}")

            if 'PENDING_PAYMENT' in values:
                print("✅ Verificación exitosa: PENDING_PAYMENT está en el enum")
            else:
                print("⚠️  Advertencia: PENDING_PAYMENT no se encontró en el enum")

    except Exception as e:
        print(f"❌ Error al agregar el valor al enum: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
