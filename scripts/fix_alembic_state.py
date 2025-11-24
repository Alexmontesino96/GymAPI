"""
Script para diagnosticar y arreglar el estado de alembic.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)

print("=== Verificando estado de alembic_version ===\n")

with engine.connect() as conn:
    # Ver versiones actuales
    result = conn.execute(text("SELECT * FROM alembic_version"))
    rows = result.fetchall()

    print(f"Versiones en alembic_version:")
    for row in rows:
        print(f"  - {row[0]}")

    print(f"\nTotal: {len(rows)} versiones")

    if len(rows) > 1:
        print("\n⚠️  Problema detectado: Múltiples versiones en alembic_version")
        print("   Esto causa conflictos en las migraciones.")
        print("\n¿Deseas limpiar y dejar solo la última versión correcta?")
        print("Opciones:")
        print("  1. Dejar solo 'add_survey_system' (última versión común)")
        print("  2. Dejar solo 'fd54000bbbcb' (merge más reciente)")
        print("  3. Ver más detalles sin modificar")

        choice = input("\nSelecciona opción (1/2/3): ").strip()

        if choice == "1":
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version VALUES ('add_survey_system')"))
            conn.commit()
            print("✓ Estado limpiado. Ejecuta: alembic upgrade head")

        elif choice == "2":
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version VALUES ('fd54000bbbcb')"))
            conn.commit()
            print("✓ Estado actualizado al merge más reciente")

        elif choice == "3":
            # Mostrar historial de migraciones
            print("\n=== Estructura de migraciones ===")
            import subprocess
            result = subprocess.run(
                ["alembic", "history", "--verbose"],
                capture_output=True,
                text=True
            )
            print(result.stdout)
    else:
        print("\n✓ Estado de alembic parece correcto")
