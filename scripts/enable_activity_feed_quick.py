#!/usr/bin/env python
"""
Script rápido para habilitar el módulo activity_feed usando SQL directo.

Uso:
    python scripts/enable_activity_feed_quick.py 4
"""

import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime

# Configuración de base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL no está configurada")
    print("   Configura la variable de entorno DATABASE_URL primero")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/enable_activity_feed_quick.py <gym_id>")
        print("Ejemplo: python scripts/enable_activity_feed_quick.py 4")
        sys.exit(1)

    gym_id = int(sys.argv[1])

    # Crear conexión
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Iniciar transacción
        trans = conn.begin()

        try:
            # 1. Verificar si el módulo existe
            result = conn.execute(
                text("SELECT id, name FROM modules WHERE code = :code"),
                {"code": "activity_feed"}
            ).first()

            if not result:
                print("❌ El módulo 'activity_feed' no existe en la base de datos")
                print("   Creando módulo...")

                # Crear el módulo
                conn.execute(
                    text("""
                        INSERT INTO modules (code, name, description, is_premium, created_at, updated_at)
                        VALUES (:code, :name, :description, :is_premium, :created_at, :updated_at)
                    """),
                    {
                        "code": "activity_feed",
                        "name": "Activity Feed",
                        "description": "Feed de actividades anónimo con estadísticas en tiempo real",
                        "is_premium": False,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )

                # Obtener el ID del nuevo módulo
                result = conn.execute(
                    text("SELECT id FROM modules WHERE code = :code"),
                    {"code": "activity_feed"}
                ).first()

                print(f"✅ Módulo creado con ID {result.id}")

            module_id = result.id

            # 2. Verificar si el gimnasio existe
            gym = conn.execute(
                text("SELECT id, name FROM gyms WHERE id = :gym_id"),
                {"gym_id": gym_id}
            ).first()

            if not gym:
                print(f"❌ Gimnasio con ID {gym_id} no existe")
                trans.rollback()
                sys.exit(1)

            gym_name = gym.name

            # 3. Verificar si la relación gym_modules existe
            gym_module = conn.execute(
                text("""
                    SELECT gym_id, module_id, active
                    FROM gym_modules
                    WHERE gym_id = :gym_id AND module_id = :module_id
                """),
                {"gym_id": gym_id, "module_id": module_id}
            ).first()

            if gym_module:
                if gym_module.active:
                    print(f"ℹ️  El módulo ya está ACTIVO para gimnasio {gym_id} ({gym_name})")
                else:
                    # Activar el módulo
                    conn.execute(
                        text("""
                            UPDATE gym_modules
                            SET active = true
                            WHERE gym_id = :gym_id AND module_id = :module_id
                        """),
                        {
                            "gym_id": gym_id,
                            "module_id": module_id
                        }
                    )
                    print(f"✅ Módulo ACTIVADO para gimnasio {gym_id} ({gym_name})")
            else:
                # Crear la relación
                conn.execute(
                    text("""
                        INSERT INTO gym_modules (gym_id, module_id, active)
                        VALUES (:gym_id, :module_id, :active)
                    """),
                    {
                        "gym_id": gym_id,
                        "module_id": module_id,
                        "active": True
                    }
                )
                print(f"✅ Módulo HABILITADO para gimnasio {gym_id} ({gym_name})")

            # Commit de la transacción
            trans.commit()

            # 4. Verificar el estado final
            print("\n📊 Verificación final:")
            print("-" * 40)

            # Verificar todos los módulos del gimnasio
            modules = conn.execute(
                text("""
                    SELECT m.code, m.name, gm.active
                    FROM gym_modules gm
                    JOIN modules m ON m.id = gm.module_id
                    WHERE gm.gym_id = :gym_id
                    ORDER BY m.code
                """),
                {"gym_id": gym_id}
            ).fetchall()

            print(f"Módulos para gimnasio {gym_id} ({gym_name}):")
            for module in modules:
                status = "✅ ACTIVO" if module.active else "❌ INACTIVO"
                special = " ⭐" if module.code == "activity_feed" else ""
                print(f"  - {module.code}: {status}{special}")

            print("\n🎉 Proceso completado exitosamente!")
            print(f"\nEl frontend ya puede usar:")
            print(f"  GET /api/v1/activity-feed/realtime")
            print(f"  con X-Gym-Id: {gym_id}")

        except Exception as e:
            trans.rollback()
            print(f"❌ Error: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()