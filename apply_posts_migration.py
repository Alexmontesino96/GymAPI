"""
Script para aplicar la migración de posts directamente.
"""
import sys
from sqlalchemy import create_engine, text
from app.core.config import get_settings

def main():
    settings = get_settings()
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    print("Aplicando migración de posts...")

    with engine.begin() as connection:
        # Crear tabla posts
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                gym_id INTEGER NOT NULL REFERENCES gyms(id),
                user_id INTEGER NOT NULL REFERENCES "user"(id),
                stream_activity_id VARCHAR,
                post_type VARCHAR(20) NOT NULL DEFAULT 'SINGLE_IMAGE',
                caption TEXT,
                location VARCHAR(100),
                workout_data JSON,
                privacy VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',
                is_edited BOOLEAN DEFAULT FALSE,
                edited_at TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE,
                deleted_at TIMESTAMP,
                like_count INTEGER NOT NULL DEFAULT 0,
                comment_count INTEGER NOT NULL DEFAULT 0,
                view_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP
            )
        """))

        # Crear índices para posts
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_id ON posts(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_gym_id ON posts(gym_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_user_id ON posts(user_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_created_at ON posts(created_at)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_posts_stream_activity_id ON posts(stream_activity_id) WHERE stream_activity_id IS NOT NULL"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_gym_created ON posts(gym_id, created_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_gym_engagement ON posts(gym_id, like_count, comment_count)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_location ON posts(gym_id, location) WHERE location IS NOT NULL"))

        # Crear tabla post_media
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS post_media (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                media_url VARCHAR NOT NULL,
                thumbnail_url VARCHAR,
                media_type VARCHAR(20) NOT NULL,
                display_order INTEGER NOT NULL DEFAULT 0,
                width INTEGER,
                height INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_media_id ON post_media(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_media_post_id ON post_media(post_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_media_post_order ON post_media(post_id, display_order)"))

        # Crear tabla post_tags
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS post_tags (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                tag_type VARCHAR(20) NOT NULL,
                tag_value VARCHAR(100) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(post_id, tag_type, tag_value)
            )
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_tags_id ON post_tags(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_tags_post_id ON post_tags(post_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_tags_type_value ON post_tags(tag_type, tag_value)"))

        # Crear tabla post_likes
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS post_likes (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES "user"(id),
                gym_id INTEGER NOT NULL REFERENCES gyms(id),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(post_id, user_id)
            )
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_likes_id ON post_likes(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_likes_post_id ON post_likes(post_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_likes_user_id ON post_likes(user_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_likes_gym_id ON post_likes(gym_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_likes_gym_user ON post_likes(gym_id, user_id)"))

        # Crear tabla post_comments
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS post_comments (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES "user"(id),
                gym_id INTEGER NOT NULL REFERENCES gyms(id),
                comment_text TEXT NOT NULL,
                is_edited BOOLEAN DEFAULT FALSE,
                edited_at TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE,
                deleted_at TIMESTAMP,
                like_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP
            )
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comments_id ON post_comments(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comments_post_id ON post_comments(post_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comments_gym_id ON post_comments(gym_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comments_user ON post_comments(user_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comments_post_created ON post_comments(post_id, created_at)"))

        # Crear tabla post_comment_likes
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS post_comment_likes (
                id SERIAL PRIMARY KEY,
                comment_id INTEGER NOT NULL REFERENCES post_comments(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES "user"(id),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(comment_id, user_id)
            )
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comment_likes_id ON post_comment_likes(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comment_likes_comment_id ON post_comment_likes(comment_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_comment_likes_user_id ON post_comment_likes(user_id)"))

        # Crear tabla post_reports
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS post_reports (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                reporter_id INTEGER NOT NULL REFERENCES "user"(id),
                reason VARCHAR(50) NOT NULL,
                description TEXT,
                is_reviewed BOOLEAN DEFAULT FALSE,
                reviewed_by INTEGER REFERENCES "user"(id),
                reviewed_at TIMESTAMP,
                action_taken VARCHAR(100),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_reports_id ON post_reports(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_reports_post_id ON post_reports(post_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_reports_reporter_id ON post_reports(reporter_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_reports_reviewed ON post_reports(is_reviewed)"))

        print("✅ Migración de posts aplicada exitosamente!")

        # Verificar tablas creadas
        result = connection.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE 'post%'
            ORDER BY table_name
        """))

        print("\nTablas creadas:")
        for row in result:
            print(f"  - {row[0]}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
