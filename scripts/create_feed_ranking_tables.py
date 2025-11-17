#!/usr/bin/env python3
"""
Script para crear tablas de feed ranking usando Python y psycopg2.
No requiere psql instalado.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_tables():
    """Crear tablas post_views y user_follows manualmente"""

    # Obtener DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL no está configurado")
        sys.exit(1)

    print("🔧 Creando tablas de feed ranking...")
    print("")

    # Crear engine
    engine = create_engine(database_url)

    # SQL para crear las tablas
    sql_statements = [
        # ========== POST_VIEWS ==========
        """
        CREATE TABLE IF NOT EXISTS post_views (
            id SERIAL PRIMARY KEY,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            gym_id INTEGER NOT NULL,
            viewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            view_duration_seconds INTEGER,
            device_type VARCHAR(50),
            CONSTRAINT fk_post_views_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
            CONSTRAINT fk_post_views_user FOREIGN KEY (user_id) REFERENCES "user"(id),
            CONSTRAINT fk_post_views_gym FOREIGN KEY (gym_id) REFERENCES gyms(id)
        );
        """,

        # Índices para post_views
        "CREATE INDEX IF NOT EXISTS ix_post_views_id ON post_views(id);",
        "CREATE INDEX IF NOT EXISTS ix_post_views_post_id ON post_views(post_id);",
        "CREATE INDEX IF NOT EXISTS ix_post_views_user_id ON post_views(user_id);",
        "CREATE INDEX IF NOT EXISTS ix_post_views_gym_id ON post_views(gym_id);",
        "CREATE INDEX IF NOT EXISTS ix_post_views_user_post ON post_views(user_id, post_id);",
        "CREATE INDEX IF NOT EXISTS ix_post_views_gym_user ON post_views(gym_id, user_id);",
        "CREATE INDEX IF NOT EXISTS ix_post_views_post_date ON post_views(post_id, viewed_at);",

        # ========== USER_FOLLOWS ==========
        """
        CREATE TABLE IF NOT EXISTS user_follows (
            id SERIAL PRIMARY KEY,
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            gym_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT fk_user_follows_follower FOREIGN KEY (follower_id) REFERENCES "user"(id),
            CONSTRAINT fk_user_follows_following FOREIGN KEY (following_id) REFERENCES "user"(id),
            CONSTRAINT fk_user_follows_gym FOREIGN KEY (gym_id) REFERENCES gyms(id),
            CONSTRAINT unique_user_follow UNIQUE (follower_id, following_id, gym_id)
        );
        """,

        # Índices para user_follows
        "CREATE INDEX IF NOT EXISTS ix_user_follows_id ON user_follows(id);",
        "CREATE INDEX IF NOT EXISTS ix_user_follows_follower_id ON user_follows(follower_id);",
        "CREATE INDEX IF NOT EXISTS ix_user_follows_following_id ON user_follows(following_id);",
        "CREATE INDEX IF NOT EXISTS ix_user_follows_gym_id ON user_follows(gym_id);",
        "CREATE INDEX IF NOT EXISTS ix_user_follows_active ON user_follows(is_active);",
        "CREATE INDEX IF NOT EXISTS ix_user_follows_follower_gym ON user_follows(follower_id, gym_id);",
        "CREATE INDEX IF NOT EXISTS ix_user_follows_following_gym ON user_follows(following_id, gym_id);",
    ]

    try:
        with engine.connect() as conn:
            # Ejecutar cada statement
            for i, sql in enumerate(sql_statements, 1):
                print(f"  [{i}/{len(sql_statements)}] Ejecutando SQL...")
                conn.execute(text(sql))
                conn.commit()

            print("")
            print("✅ Tablas creadas exitosamente")
            print("")

            # Verificar que las tablas existen
            print("📊 Verificando tablas creadas:")
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('post_views', 'user_follows')
                ORDER BY table_name;
            """))

            tables = [row[0] for row in result]
            for table in tables:
                print(f"  ✓ {table}")

            if len(tables) == 2:
                print("")
                print("🎉 ¡Perfecto! Ambas tablas están creadas")
                return True
            else:
                print("")
                print(f"⚠️  Solo se crearon {len(tables)} de 2 tablas")
                return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_tables()

    if success:
        print("")
        print("📝 Próximo paso: Actualizar estado de Alembic")
        print("   Ejecuta: alembic stamp 9268f18fc9bd")
        print("")
        print("Luego prueba el endpoint:")
        print("   GET /api/v1/posts/feed/ranked?page=1&debug=true")
        sys.exit(0)
    else:
        sys.exit(1)
