"""
Script para verificar que el módulo posts está activo para los gimnasios.
"""

from sqlalchemy import create_engine, text
from app.core.config import get_settings

def main():
    settings = get_settings()
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    print("Verificando activación del módulo posts...")
    print("=" * 60)

    with engine.connect() as connection:
        # Consultar gimnasios con el módulo posts activo
        result = connection.execute(text("""
            SELECT
                g.id,
                g.name,
                m.name as module_name,
                gm.active,
                gm.activated_at
            FROM gym_modules gm
            JOIN gyms g ON g.id = gm.gym_id
            JOIN modules m ON m.id = gm.module_id
            WHERE m.code = 'posts'
            ORDER BY g.id
        """))

        gyms_with_posts = result.fetchall()

        if not gyms_with_posts:
            print("⚠️  No hay gimnasios con el módulo posts activado")
            return

        print(f"✅ Gimnasios con módulo 'posts' activo: {len(gyms_with_posts)}")
        print()

        for gym in gyms_with_posts:
            gym_id, gym_name, module_name, active, activated_at = gym
            status = "✅ ACTIVO" if active else "❌ INACTIVO"
            activated_date = activated_at.strftime("%Y-%m-%d %H:%M:%S") if activated_at else "N/A"

            print(f"Gym {gym_id}: {gym_name}")
            print(f"   Estado: {status}")
            print(f"   Módulo: {module_name}")
            print(f"   Activado: {activated_date}")
            print()

        print("=" * 60)
        print(f"✅ Verificación completada")
        print(f"   Total gimnasios con posts: {len(gyms_with_posts)}")
        print()
        print("Los endpoints de posts están disponibles en:")
        print("   • POST   /api/v1/posts")
        print("   • GET    /api/v1/posts/feed/timeline")
        print("   • GET    /api/v1/posts/feed/explore")
        print("   • Y 18 endpoints más...")
        print()
        print("Documentación en: http://localhost:8000/api/v1/docs")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
