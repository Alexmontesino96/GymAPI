"""
Script para configurar el módulo de posts en la base de datos.
"""

from sqlalchemy import create_engine, text
from app.core.config import get_settings

def main():
    settings = get_settings()
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    print("Configurando módulo de posts...")

    with engine.begin() as connection:
        # Insertar módulo si no existe
        result = connection.execute(text("""
            INSERT INTO modules (code, name, description, is_premium, created_at, updated_at)
            VALUES ('posts', 'Publicaciones', 'Sistema de posts permanentes tipo Instagram con galería, likes y comentarios', FALSE, NOW(), NOW())
            ON CONFLICT (code) DO UPDATE
            SET name = EXCLUDED.name,
                description = EXCLUDED.description,
                updated_at = NOW()
            RETURNING id
        """))

        module_id = result.scalar()
        print(f"✅ Módulo 'posts' configurado (ID: {module_id})")

        # Verificar si ya está activo para algún gym
        result = connection.execute(text("""
            SELECT COUNT(*) FROM gym_modules WHERE module_id = :module_id
        """), {"module_id": module_id})

        active_count = result.scalar()
        print(f"📊 Módulo activo en {active_count} gimnasios")

        print("\n✅ Configuración completada!")
        print("\nPara activar el módulo en un gimnasio específico, ejecuta:")
        print("INSERT INTO gym_modules (gym_id, module_id, active, activated_at) VALUES (GYM_ID, {}, TRUE, NOW());".format(module_id))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
