#!/usr/bin/env python
"""
Script para activar el módulo de nutrición para el gym 1kick.
"""

import sys
from pathlib import Path
from datetime import datetime

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.db.session import SessionLocal
from sqlalchemy import text


def activate_nutrition_for_1kick():
    """Activa el módulo de nutrición para el gym 1kick usando SQL directo."""
    db = SessionLocal()
    try:
        print("🔍 Buscando gym '1kick'...")

        # Buscar gym por nombre usando SQL directo
        result = db.execute(
            text("SELECT id, name FROM gyms WHERE LOWER(name) LIKE LOWER(:name)"),
            {"name": "%1kick%"}
        ).fetchone()

        if not result:
            print("❌ No se encontró el gym '1kick'")
            print("\nGyms disponibles:")
            gyms = db.execute(text("SELECT id, name FROM gyms")).fetchall()
            for g in gyms:
                print(f"  - ID: {g[0]}, Nombre: {g[1]}")
            return False

        gym_id, gym_name = result[0], result[1]
        print(f"✅ Gym encontrado: {gym_name} (ID: {gym_id})")

        # Buscar el módulo de nutrición
        print("\n🔍 Buscando módulo de nutrición...")
        module_result = db.execute(
            text("SELECT id, name, code FROM modules WHERE code = :code"),
            {"code": "nutrition"}
        ).fetchone()

        if not module_result:
            print("⚠️  El módulo 'nutrition' no existe en el sistema")
            print("\nMódulos disponibles:")
            modules = db.execute(text("SELECT id, name, code FROM modules")).fetchall()
            for m in modules:
                print(f"  - ID: {m[0]}, Nombre: {m[1]}, Código: {m[2]}")
            return False

        module_id, module_name, module_code = module_result[0], module_result[1], module_result[2]
        print(f"✅ Módulo encontrado: {module_name} (ID: {module_id}, Code: {module_code})")

        # Verificar si ya existe la relación gym_module
        print("\n🔍 Verificando estado actual...")
        gym_module_result = db.execute(
            text("""
                SELECT active
                FROM gym_modules
                WHERE gym_id = :gym_id AND module_id = :module_id
            """),
            {"gym_id": gym_id, "module_id": module_id}
        ).fetchone()

        if gym_module_result:
            is_active = gym_module_result[0]
            if is_active:
                print("✅ El módulo de nutrición ya está activado para este gym")
                return True
            else:
                # Reactivar módulo
                print("\n🔄 Reactivando módulo de nutrición...")
                db.execute(
                    text("""
                        UPDATE gym_modules
                        SET active = true, deactivated_at = NULL
                        WHERE gym_id = :gym_id AND module_id = :module_id
                    """),
                    {"gym_id": gym_id, "module_id": module_id}
                )
                db.commit()
        else:
            # Crear nueva relación
            print("\n🔄 Activando módulo de nutrición...")
            db.execute(
                text("""
                    INSERT INTO gym_modules (gym_id, module_id, active, activated_at)
                    VALUES (:gym_id, :module_id, true, :activated_at)
                """),
                {
                    "gym_id": gym_id,
                    "module_id": module_id,
                    "activated_at": datetime.utcnow()
                }
            )
            db.commit()

        print("✅ Módulo de nutrición activado exitosamente!")
        print(f"\n📊 Resumen:")
        print(f"   Gym: {gym_name} (ID: {gym_id})")
        print(f"   Módulo: {module_name}")
        print(f"   Estado: ACTIVO ✅")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    success = activate_nutrition_for_1kick()
    sys.exit(0 if success else 1)
