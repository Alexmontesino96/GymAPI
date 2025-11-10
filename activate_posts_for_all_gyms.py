"""
Script para activar el módulo de posts para todos los gimnasios existentes.
"""

from sqlalchemy import create_engine, text
from app.core.config import get_settings

def main():
    settings = get_settings()
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    print("Activando módulo de posts para todos los gimnasios...")
    print("=" * 60)

    with engine.begin() as connection:
        # Obtener ID del módulo posts
        result = connection.execute(text("""
            SELECT id FROM modules WHERE code = 'posts'
        """))

        module = result.first()
        if not module:
            print("❌ Error: Módulo 'posts' no encontrado en la tabla modules")
            print("Ejecuta primero: python configure_posts_module.py")
            return

        module_id = module[0]
        print(f"✅ Módulo 'posts' encontrado (ID: {module_id})")
        print()

        # Obtener todos los gimnasios
        result = connection.execute(text("""
            SELECT id, name FROM gyms WHERE is_active = TRUE
        """))

        gyms = result.fetchall()

        if not gyms:
            print("⚠️  No hay gimnasios activos en la base de datos")
            return

        print(f"📊 Encontrados {len(gyms)} gimnasios activos:")
        for gym in gyms:
            print(f"   - Gym ID {gym[0]}: {gym[1]}")
        print()

        # Verificar cuáles ya tienen el módulo activado
        result = connection.execute(text("""
            SELECT gym_id FROM gym_modules
            WHERE module_id = :module_id
        """), {"module_id": module_id})

        existing_gym_ids = {row[0] for row in result.fetchall()}

        if existing_gym_ids:
            print(f"ℹ️  Gimnasios que ya tienen el módulo activado: {existing_gym_ids}")
            print()

        # Activar módulo para cada gimnasio que no lo tenga
        activated_count = 0
        skipped_count = 0

        for gym in gyms:
            gym_id = gym[0]
            gym_name = gym[1]

            if gym_id in existing_gym_ids:
                print(f"⏭️  Gym {gym_id} ({gym_name}): Ya tiene el módulo activado")
                skipped_count += 1
                continue

            # Insertar activación del módulo
            connection.execute(text("""
                INSERT INTO gym_modules (gym_id, module_id, active, activated_at)
                VALUES (:gym_id, :module_id, TRUE, NOW())
            """), {
                "gym_id": gym_id,
                "module_id": module_id
            })

            print(f"✅ Gym {gym_id} ({gym_name}): Módulo activado")
            activated_count += 1

        print()
        print("=" * 60)
        print(f"✅ Activación completada!")
        print(f"   - Gimnasios activados: {activated_count}")
        print(f"   - Gimnasios ya activos: {skipped_count}")
        print(f"   - Total gimnasios: {len(gyms)}")
        print()
        print("📝 El módulo 'posts' está ahora disponible para todos los gimnasios.")
        print("📝 Los usuarios pueden empezar a crear posts en /api/v1/posts")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
