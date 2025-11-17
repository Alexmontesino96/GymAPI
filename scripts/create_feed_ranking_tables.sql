-- Script para crear manualmente las tablas de feed ranking
-- Ejecutar en producción si alembic upgrade head falla

-- ========== TABLA POST_VIEWS ==========

-- Eliminar tabla si existe (solo si quieres empezar de cero)
-- DROP TABLE IF EXISTS post_views CASCADE;

CREATE TABLE IF NOT EXISTS post_views (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    gym_id INTEGER NOT NULL,
    viewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    view_duration_seconds INTEGER,
    device_type VARCHAR(50),

    -- Foreign keys
    CONSTRAINT fk_post_views_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_post_views_user FOREIGN KEY (user_id) REFERENCES "user"(id),
    CONSTRAINT fk_post_views_gym FOREIGN KEY (gym_id) REFERENCES gyms(id)
);

-- Índices para post_views
CREATE INDEX IF NOT EXISTS ix_post_views_id ON post_views(id);
CREATE INDEX IF NOT EXISTS ix_post_views_post_id ON post_views(post_id);
CREATE INDEX IF NOT EXISTS ix_post_views_user_id ON post_views(user_id);
CREATE INDEX IF NOT EXISTS ix_post_views_gym_id ON post_views(gym_id);
CREATE INDEX IF NOT EXISTS ix_post_views_user_post ON post_views(user_id, post_id);
CREATE INDEX IF NOT EXISTS ix_post_views_gym_user ON post_views(gym_id, user_id);
CREATE INDEX IF NOT EXISTS ix_post_views_post_date ON post_views(post_id, viewed_at);

-- ========== TABLA USER_FOLLOWS ==========

-- Eliminar tabla si existe (solo si quieres empezar de cero)
-- DROP TABLE IF EXISTS user_follows CASCADE;

CREATE TABLE IF NOT EXISTS user_follows (
    id SERIAL PRIMARY KEY,
    follower_id INTEGER NOT NULL,
    following_id INTEGER NOT NULL,
    gym_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,

    -- Foreign keys
    CONSTRAINT fk_user_follows_follower FOREIGN KEY (follower_id) REFERENCES "user"(id),
    CONSTRAINT fk_user_follows_following FOREIGN KEY (following_id) REFERENCES "user"(id),
    CONSTRAINT fk_user_follows_gym FOREIGN KEY (gym_id) REFERENCES gyms(id),

    -- Constraint único
    CONSTRAINT unique_user_follow UNIQUE (follower_id, following_id, gym_id)
);

-- Índices para user_follows
CREATE INDEX IF NOT EXISTS ix_user_follows_id ON user_follows(id);
CREATE INDEX IF NOT EXISTS ix_user_follows_follower_id ON user_follows(follower_id);
CREATE INDEX IF NOT EXISTS ix_user_follows_following_id ON user_follows(following_id);
CREATE INDEX IF NOT EXISTS ix_user_follows_gym_id ON user_follows(gym_id);
CREATE INDEX IF NOT EXISTS ix_user_follows_active ON user_follows(is_active);
CREATE INDEX IF NOT EXISTS ix_user_follows_follower_gym ON user_follows(follower_id, gym_id);
CREATE INDEX IF NOT EXISTS ix_user_follows_following_gym ON user_follows(following_id, gym_id);

-- ========== VERIFICACIÓN ==========

-- Verificar que las tablas se crearon
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name AND table_schema = 'public') as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('post_views', 'user_follows')
ORDER BY table_name;

-- Verificar índices creados
SELECT
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('post_views', 'user_follows')
ORDER BY tablename, indexname;
