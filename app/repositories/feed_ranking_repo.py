"""
Repositorio con queries SQL optimizadas para feed ranking.

Contiene todas las queries necesarias para calcular las 5 señales del algoritmo:
1. Content Affinity - Match con intereses del usuario
2. Social Affinity - Relación con el autor
3. Past Engagement - Historial de interacciones
4. Timing - Recency + horarios activos
5. Popularity - Trending + engagement

Optimizado para performance con cache y batch queries.
"""

from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class FeedRankingRepository:
    """Repositorio con queries SQL para componentes de feed ranking"""

    def __init__(self, db: Session):
        self.db = db

    # ========== CONTENT AFFINITY QUERIES ==========

    def get_user_primary_category(self, user_id: int, gym_id: int) -> Optional[str]:
        """
        Obtiene la categoría fitness primaria del usuario.
        Basado en clases asistidas (últimos 90 días).

        Returns:
            str: Categoría primaria (ej: "cardio", "strength", "yoga") o None
        """
        query = text("""
            SELECT c.category_enum
            FROM class_participation cp
            JOIN class_session cs ON cp.session_id = cs.id
            JOIN class c ON cs.class_id = c.id
            WHERE cp.member_id = :user_id
              AND c.gym_id = :gym_id
              AND cp.attendance_time >= NOW() - INTERVAL '90 days'
              AND cp.status = 'ATTENDED'
            GROUP BY c.category_enum
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """)

        result = self.db.execute(query, {"user_id": user_id, "gym_id": gym_id})
        row = result.fetchone()
        return row[0] if row else None

    def get_user_category_distribution(self, user_id: int, gym_id: int) -> Dict[str, float]:
        """
        Obtiene la distribución de categorías del usuario.

        Returns:
            Dict: {"cardio": 0.4, "strength": 0.6, ...}
        """
        query = text("""
            WITH category_counts AS (
                SELECT
                    c.category_enum,
                    COUNT(*) as count
                FROM class_participation cp
                JOIN class_session cs ON cp.session_id = cs.id
                JOIN class c ON cs.class_id = c.id
                WHERE cp.member_id = :user_id
                  AND c.gym_id = :gym_id
                  AND cp.attendance_time >= NOW() - INTERVAL '90 days'
                  AND cp.status = 'ATTENDED'
                GROUP BY c.category_enum
            ),
            total AS (
                SELECT SUM(count) as total_count
                FROM category_counts
            )
            SELECT
                cc.category_enum,
                cc.count::float / t.total_count as percentage
            FROM category_counts cc
            CROSS JOIN total t
            ORDER BY cc.count DESC
        """)

        result = self.db.execute(query, {"user_id": user_id, "gym_id": gym_id})
        return {row[0]: round(row[1], 2) for row in result.fetchall()}

    def get_post_categories(self, post_id: int) -> List[str]:
        """
        Obtiene categorías/tags del post.

        Returns:
            List[str]: Lista de categorías del post
        """
        query = text("""
            SELECT tag_value
            FROM post_tags
            WHERE post_id = :post_id
              AND tag_type = 'EVENT'  -- Asumiendo que categorías están en EVENT tags
        """)

        result = self.db.execute(query, {"post_id": post_id})
        return [row[0] for row in result.fetchall()]

    # ========== SOCIAL AFFINITY QUERIES ==========

    def get_user_relationship_type(
        self,
        user_id: int,
        author_id: int,
        gym_id: int
    ) -> Optional[str]:
        """
        Determina el tipo de relación entre usuario y autor.

        Returns:
            str: "trainer" | "trainee" | "following" | "same_gym" | None
        """
        # 1. Verificar si author es trainer del user
        query_trainer = text("""
            SELECT 1 FROM trainermemberrelationship
            WHERE trainer_id = :author_id
              AND member_id = :user_id
              AND gym_id = :gym_id
              AND status = 'ACCEPTED'
            LIMIT 1
        """)

        result = self.db.execute(query_trainer, {
            "author_id": author_id,
            "user_id": user_id,
            "gym_id": gym_id
        })
        if result.fetchone():
            return "trainer"

        # 2. Verificar si user es trainer del author
        query_trainee = text("""
            SELECT 1 FROM trainermemberrelationship
            WHERE trainer_id = :user_id
              AND member_id = :author_id
              AND gym_id = :gym_id
              AND status = 'ACCEPTED'
            LIMIT 1
        """)

        result = self.db.execute(query_trainee, {
            "user_id": user_id,
            "author_id": author_id,
            "gym_id": gym_id
        })
        if result.fetchone():
            return "trainee"

        # 3. Verificar si el usuario sigue al autor
        query_following = text("""
            SELECT 1 FROM user_follows
            WHERE follower_id = :user_id
              AND following_id = :author_id
              AND gym_id = :gym_id
              AND is_active = true
            LIMIT 1
        """)

        result = self.db.execute(query_following, {
            "user_id": user_id,
            "author_id": author_id,
            "gym_id": gym_id
        })
        if result.fetchone():
            return "following"

        # 4. Si comparten gym (siempre true por parametros)
        return "same_gym"

    def get_past_interactions_count(
        self,
        user_id: int,
        author_id: int,
        days: int = 30
    ) -> int:
        """
        Cuenta interacciones previas del usuario con posts del autor.

        Returns:
            int: Número total de interacciones (likes + comentarios)
        """
        query = text("""
            SELECT COUNT(*) as interaction_count
            FROM (
                -- Likes
                SELECT pl.created_at
                FROM post_likes pl
                JOIN posts p ON pl.post_id = p.id
                WHERE pl.user_id = :user_id
                  AND p.user_id = :author_id
                  AND pl.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)

                UNION ALL

                -- Comentarios
                SELECT pc.created_at
                FROM post_comments pc
                JOIN posts p ON pc.post_id = p.id
                WHERE pc.user_id = :user_id
                  AND p.user_id = :author_id
                  AND pc.is_deleted = false
                  AND pc.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)
            ) interactions
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "author_id": author_id,
            "days": days
        })
        row = result.fetchone()
        return row[0] if row else 0

    # ========== PAST ENGAGEMENT QUERIES ==========

    def get_user_engagement_patterns(
        self,
        user_id: int,
        gym_id: int,
        days: int = 30
    ) -> Dict[str, any]:
        """
        Analiza patrones de engagement del usuario.

        Returns:
            {
                "total_likes": int,
                "total_comments": int,
                "avg_likes_per_day": float,
                "preferred_post_types": List[str],
                "preferred_categories": List[str]
            }
        """
        query = text("""
            WITH user_likes AS (
                SELECT
                    p.id as post_id,
                    p.post_type,
                    pl.created_at
                FROM post_likes pl
                JOIN posts p ON pl.post_id = p.id
                WHERE pl.user_id = :user_id
                  AND p.gym_id = :gym_id
                  AND pl.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)
            ),
            user_comments AS (
                SELECT COUNT(*) as comment_count
                FROM post_comments pc
                JOIN posts p ON pc.post_id = p.id
                WHERE pc.user_id = :user_id
                  AND p.gym_id = :gym_id
                  AND pc.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)
                  AND pc.is_deleted = false
            ),
            post_type_counts AS (
                SELECT
                    post_type,
                    COUNT(*) as count
                FROM user_likes
                GROUP BY post_type
                ORDER BY count DESC
            )
            SELECT
                (SELECT COUNT(*) FROM user_likes) as total_likes,
                (SELECT comment_count FROM user_comments) as total_comments,
                (SELECT COUNT(*) FROM user_likes)::float / :days as avg_likes_per_day,
                COALESCE(
                    (SELECT json_agg(post_type ORDER BY count DESC)
                     FROM (SELECT post_type, count FROM post_type_counts LIMIT 2) t),
                    '[]'::json
                ) as preferred_types
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "gym_id": gym_id,
            "days": f"{days} days"
        })
        row = result.fetchone()

        if not row or row[0] == 0:
            return {
                "total_likes": 0,
                "total_comments": 0,
                "avg_likes_per_day": 0.0,
                "preferred_post_types": [],
                "preferred_categories": []
            }

        return {
            "total_likes": row[0] or 0,
            "total_comments": row[1] or 0,
            "avg_likes_per_day": round(row[2] or 0.0, 2),
            "preferred_post_types": row[3] or [],
            "preferred_categories": []  # TODO: Agregar cuando tengamos categorías en posts
        }

    # ========== TIMING QUERIES ==========

    def get_user_active_hours(
        self,
        user_id: int,
        gym_id: int,
        days: int = 30
    ) -> List[int]:
        """
        Detecta las horas del día en las que el usuario es más activo.

        Returns:
            List[int]: Horas (0-23) ordenadas por actividad descendente
        """
        query = text("""
            WITH user_activity AS (
                -- Likes
                SELECT EXTRACT(HOUR FROM pl.created_at)::int as hour
                FROM post_likes pl
                WHERE pl.user_id = :user_id
                  AND pl.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)

                UNION ALL

                -- Comentarios
                SELECT EXTRACT(HOUR FROM pc.created_at)::int as hour
                FROM post_comments pc
                WHERE pc.user_id = :user_id
                  AND pc.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)

                UNION ALL

                -- Posts creados
                SELECT EXTRACT(HOUR FROM p.created_at)::int as hour
                FROM posts p
                WHERE p.user_id = :user_id
                  AND p.gym_id = :gym_id
                  AND p.created_at >= NOW() - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT hour, COUNT(*) as activity_count
            FROM user_activity
            GROUP BY hour
            ORDER BY activity_count DESC
            LIMIT 5
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "gym_id": gym_id,
            "days": f"{days} days"
        })
        return [int(row[0]) for row in result.fetchall()]

    # ========== POPULARITY QUERIES ==========

    def get_post_engagement_metrics(
        self,
        post_id: int,
        gym_id: int
    ) -> Dict[str, any]:
        """
        Obtiene métricas de engagement del post.

        Returns:
            {
                "likes_count": int,
                "comments_count": int,
                "views_count": int,
                "engagement_rate": float,
                "velocity": float  # engagement / hours_since_creation
            }
        """
        query = text("""
            SELECT
                p.like_count as likes,
                p.comment_count as comments,
                p.view_count as views,
                EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0 as hours_old
            FROM posts p
            WHERE p.id = :post_id
              AND p.gym_id = :gym_id
        """)

        result = self.db.execute(query, {"post_id": post_id, "gym_id": gym_id})
        row = result.fetchone()

        if not row:
            return {
                "likes_count": 0,
                "comments_count": 0,
                "views_count": 0,
                "engagement_rate": 0.0,
                "velocity": 0.0
            }

        likes = row[0] or 0
        comments = row[1] or 0
        views = row[2] or 0
        hours_old = max(row[3] or 0.1, 0.1)  # Evitar división por 0

        # Engagement rate: (likes + comments*2) / views
        engagement_rate = (likes + comments * 2) / max(views, 1) if views > 0 else 0.0

        # Velocity: engagement / hours_old
        velocity = (likes + comments * 2) / hours_old

        return {
            "likes_count": likes,
            "comments_count": comments,
            "views_count": views,
            "engagement_rate": round(engagement_rate, 3),
            "velocity": round(velocity, 3)
        }

    def get_gym_engagement_percentiles(
        self,
        gym_id: int,
        hours_lookback: int = 24
    ) -> Dict[str, float]:
        """
        Calcula percentiles de engagement para posts recientes del gym.

        Returns:
            {
                "likes_p50": float,  # Mediana
                "likes_p90": float,  # Top 10%
                "velocity_p50": float,
                "velocity_p90": float
            }
        """
        query = text("""
            WITH recent_posts AS (
                SELECT
                    p.id,
                    p.like_count as likes,
                    (p.like_count + p.comment_count * 2.0) /
                        GREATEST(EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0, 0.1) as velocity
                FROM posts p
                WHERE p.gym_id = :gym_id
                  AND p.created_at >= NOW() - CAST(:hours_lookback || ' hours' AS INTERVAL)
                  AND p.is_deleted = false
            )
            SELECT
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY likes) as likes_p50,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY likes) as likes_p90,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY velocity) as velocity_p50,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY velocity) as velocity_p90
            FROM recent_posts
        """)

        result = self.db.execute(query, {
            "gym_id": gym_id,
            "hours_lookback": f"{hours_lookback} hours"
        })
        row = result.fetchone()

        if not row:
            return {
                "likes_p50": 0.0,
                "likes_p90": 0.0,
                "velocity_p50": 0.0,
                "velocity_p90": 0.0
            }

        return {
            "likes_p50": float(row[0] or 0.0),
            "likes_p90": float(row[1] or 0.0),
            "velocity_p50": float(row[2] or 0.0),
            "velocity_p90": float(row[3] or 0.0)
        }

    # ========== UTILITY QUERIES ==========

    def get_viewed_post_ids(self, user_id: int, gym_id: int, days: int = 7) -> List[int]:
        """
        Obtiene IDs de posts ya vistos por el usuario.

        Returns:
            List[int]: IDs de posts vistos
        """
        query = text("""
            SELECT DISTINCT post_id
            FROM post_views
            WHERE user_id = :user_id
              AND gym_id = :gym_id
              AND viewed_at >= NOW() - CAST(:days || ' days' AS INTERVAL)
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "gym_id": gym_id,
            "days": f"{days} days"
        })
        return [row[0] for row in result.fetchall()]
