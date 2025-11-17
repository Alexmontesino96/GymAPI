"""
Servicio para ranking inteligente del feed de posts.

Implementa algoritmo heurístico con 5 señales ponderadas:
1. Content Affinity (25%) - Match con intereses del usuario
2. Social Affinity (25%) - Relación con el autor
3. Past Engagement (15%) - Historial de interacciones
4. Timing (15%) - Recency + horarios activos
5. Popularity (20%) - Trending + engagement

Formula final:
    final_score = (ca * 0.25) + (sa * 0.25) + (pe * 0.15) + (t * 0.15) + (p * 0.20)

Todos los scores están normalizados en el rango [0.0, 1.0].
"""

from typing import List, Dict, Optional, NamedTuple
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import math
import logging

from app.models.post import Post
from app.repositories.feed_ranking_repo import FeedRankingRepository

logger = logging.getLogger(__name__)


class FeedScore(NamedTuple):
    """Resultado detallado del scoring de un post"""
    post_id: int
    final_score: float
    content_affinity: float
    social_affinity: float
    past_engagement: float
    timing: float
    popularity: float


class FeedRankingService:
    """Servicio de ranking de feed con múltiples señales"""

    # Ponderación de señales (deben sumar 1.0)
    WEIGHTS = {
        "content_affinity": 0.25,
        "social_affinity": 0.25,
        "past_engagement": 0.15,
        "timing": 0.15,
        "popularity": 0.20
    }

    # Categorías relacionadas para content affinity
    RELATED_CATEGORIES = {
        "cardio": ["hiit", "running", "cycling", "spinning"],
        "strength": ["powerlifting", "bodybuilding", "crossfit", "weightlifting"],
        "flexibility": ["yoga", "pilates", "stretching"],
        "group": ["zumba", "dance", "aerobics"],
        "combat": ["boxing", "kickboxing", "martial_arts"]
    }

    def __init__(self, db: Session):
        self.db = db
        self.repo = FeedRankingRepository(db)

    def content_affinity_score(
        self,
        user_id: int,
        gym_id: int,
        post_id: int
    ) -> float:
        """
        Calcula content affinity (0.0 - 1.0) entre usuario y post.

        Basado en:
        - Categoría primaria del usuario (de clases asistidas)
        - Categorías del post (tags)
        - Match exacto = 1.0
        - Match parcial (categorías relacionadas) = 0.7
        - Sin match = 0.2 (base para diversidad)
        """
        try:
            # 1. Obtener categoría primaria del usuario
            user_category = self.repo.get_user_primary_category(user_id, gym_id)

            # 2. Obtener categorías del post
            post_categories = self.repo.get_post_categories(post_id)

            # 3. Calcular match
            if not user_category:
                return 0.5  # Sin datos, score neutral

            if not post_categories:
                return 0.3  # Post sin categorías, score bajo pero no cero

            # Match exacto
            if user_category.lower() in [cat.lower() for cat in post_categories]:
                return 1.0

            # Match parcial con categorías relacionadas
            related = self.RELATED_CATEGORIES.get(user_category.lower(), [])
            for cat in post_categories:
                if cat.lower() in related:
                    return 0.7

            # Sin match, pero score base para diversidad
            return 0.2

        except Exception as e:
            logger.error(f"Error en content_affinity_score: {e}", exc_info=True)
            return 0.5  # Score neutral en caso de error

    def social_affinity_score(
        self,
        user_id: int,
        author_id: int,
        gym_id: int
    ) -> float:
        """
        Calcula social affinity (0.0 - 1.0) entre usuario y autor.

        Ponderación:
        - Trainer del usuario: 1.0 (máxima relevancia)
        - Usuario entrena al autor: 0.8
        - Usuario sigue al autor: 0.7
        - Interacciones frecuentes (5+): 0.6
        - Interacciones ocasionales (1-4): 0.4
        - Mismo gym, sin interacción: 0.2
        - Sin relación: 0.1
        """
        try:
            if user_id == author_id:
                return 0.0  # Propio post, no rankear por social

            # 1. Verificar relación directa
            relationship = self.repo.get_user_relationship_type(user_id, author_id, gym_id)

            if relationship == "trainer":
                return 1.0  # Trainer del usuario = máxima prioridad

            if relationship == "trainee":
                return 0.8  # Usuario es trainer del autor

            if relationship == "following":
                return 0.7  # Usuario sigue al autor

            # 2. Verificar interacciones históricas
            interactions = self.repo.get_past_interactions_count(user_id, author_id, days=30)

            if interactions >= 5:
                return 0.6  # Alta interacción previa

            if interactions >= 1:
                return 0.4  # Interacción ocasional

            # 3. Mismo gym sin interacción
            if relationship == "same_gym":
                return 0.2

            # 4. Sin relación
            return 0.1

        except Exception as e:
            logger.error(f"Error en social_affinity_score: {e}", exc_info=True)
            return 0.3  # Score bajo en caso de error

    def past_engagement_score(
        self,
        user_id: int,
        gym_id: int,
        post_id: int,
        post_type: str,
        post_categories: List[str]
    ) -> float:
        """
        Calcula past engagement score (0.0 - 1.0).

        Basado en:
        - Match con tipo de post preferido (40% del score)
        - Match con categorías que le gustan (40% del score)
        - Boost por engagement frecuente (20% del score)
        """
        try:
            patterns = self.repo.get_user_engagement_patterns(user_id, gym_id)

            # Usuario nuevo o sin engagement
            if patterns["total_likes"] == 0:
                return 0.5  # Score neutral

            score = 0.0

            # 1. Match con tipo de post preferido (40%)
            if post_type in patterns["preferred_post_types"]:
                score += 0.4

            # 2. Match con categorías preferidas (40%)
            # TODO: Implementar cuando tengamos categorías en preferred_categories
            # Por ahora, dar score base
            score += 0.2

            # 3. Boost por engagement frecuente (20%)
            avg_likes_per_day = patterns["avg_likes_per_day"]
            if avg_likes_per_day >= 3.0:
                score += 0.2
            elif avg_likes_per_day >= 1.0:
                score += 0.1

            return min(score, 1.0)  # Cap en 1.0

        except Exception as e:
            logger.error(f"Error en past_engagement_score: {e}", exc_info=True)
            return 0.5

    def timing_score(
        self,
        user_id: int,
        gym_id: int,
        post_created_at: datetime,
        current_time: datetime = None
    ) -> float:
        """
        Calcula timing score (0.0 - 1.0).

        Componentes:
        - 70% recency (decaimiento exponencial, half-life 6h)
        - 30% match con horarios activos del usuario
        """
        try:
            if current_time is None:
                current_time = datetime.now(timezone.utc)

            # Asegurar timezone-aware
            if post_created_at.tzinfo is None:
                post_created_at = post_created_at.replace(tzinfo=timezone.utc)

            # 1. Recency score (70%)
            hours_ago = (current_time - post_created_at).total_seconds() / 3600

            # Decaimiento exponencial: score = e^(-lambda * t)
            # Half-life de 6 horas: lambda = ln(2) / 6 ≈ 0.1155
            decay_lambda = 0.1155
            recency_score = math.exp(-decay_lambda * hours_ago)

            # 2. Active hours match (30%)
            active_hours = self.repo.get_user_active_hours(user_id, gym_id)
            post_hour = post_created_at.hour
            active_hours_score = 0.5  # Default neutral

            if active_hours:
                if post_hour in active_hours[:2]:  # Top 2 horas más activas
                    active_hours_score = 1.0
                elif post_hour in active_hours[:5]:  # Top 5
                    active_hours_score = 0.7

            # Score final ponderado
            final_score = (recency_score * 0.7) + (active_hours_score * 0.3)

            return min(final_score, 1.0)

        except Exception as e:
            logger.error(f"Error en timing_score: {e}", exc_info=True)
            return 0.5

    def popularity_score(
        self,
        post_id: int,
        gym_id: int
    ) -> float:
        """
        Calcula popularity score (0.0 - 1.0).

        Componentes:
        - 50% trending (velocity vs gym median)
        - 30% engagement absoluto (likes + comments)
        - 20% engagement rate (engagement / views)
        """
        try:
            # Métricas del post
            metrics = self.repo.get_post_engagement_metrics(post_id, gym_id)

            # Percentiles del gym (últimas 24h)
            percentiles = self.repo.get_gym_engagement_percentiles(gym_id, hours_lookback=24)

            # 1. Trending score (50%) - basado en velocity
            velocity = metrics["velocity"]
            velocity_p90 = percentiles["velocity_p90"]

            if velocity_p90 > 0:
                trending_score = min(velocity / velocity_p90, 1.0)
            else:
                trending_score = 0.5  # Sin referencia, neutral

            # 2. Engagement absoluto (30%) - basado en likes totales
            likes = metrics["likes_count"]
            likes_p90 = percentiles["likes_p90"]

            if likes_p90 > 0:
                engagement_score = min(likes / likes_p90, 1.0)
            else:
                engagement_score = 0.5 if likes > 0 else 0.0

            # 3. Engagement rate (20%)
            engagement_rate = metrics["engagement_rate"]
            # Normalizar: rate > 0.3 (30%) es excelente
            rate_score = min(engagement_rate / 0.3, 1.0)

            # Score final ponderado
            final_score = (
                (trending_score * 0.5) +
                (engagement_score * 0.3) +
                (rate_score * 0.2)
            )

            return min(final_score, 1.0)

        except Exception as e:
            logger.error(f"Error en popularity_score: {e}", exc_info=True)
            return 0.3

    def calculate_feed_score(
        self,
        user_id: int,
        gym_id: int,
        post: Post
    ) -> FeedScore:
        """
        Calcula el score final de ranking para un post.

        Returns:
            FeedScore con score final y componentes individuales
        """
        try:
            # 1. Calcular cada señal
            content = self.content_affinity_score(
                user_id=user_id,
                gym_id=gym_id,
                post_id=post.id
            )

            social = self.social_affinity_score(
                user_id=user_id,
                author_id=post.user_id,
                gym_id=gym_id
            )

            # Obtener categorías del post para past_engagement
            post_categories = self.repo.get_post_categories(post.id)

            past_eng = self.past_engagement_score(
                user_id=user_id,
                gym_id=gym_id,
                post_id=post.id,
                post_type=str(post.post_type.value) if post.post_type else "SINGLE_IMAGE",
                post_categories=post_categories
            )

            timing = self.timing_score(
                user_id=user_id,
                gym_id=gym_id,
                post_created_at=post.created_at
            )

            popularity = self.popularity_score(
                post_id=post.id,
                gym_id=gym_id
            )

            # 2. Aplicar ponderación
            final = (
                (content * self.WEIGHTS["content_affinity"]) +
                (social * self.WEIGHTS["social_affinity"]) +
                (past_eng * self.WEIGHTS["past_engagement"]) +
                (timing * self.WEIGHTS["timing"]) +
                (popularity * self.WEIGHTS["popularity"])
            )

            return FeedScore(
                post_id=post.id,
                final_score=round(final, 4),
                content_affinity=round(content, 4),
                social_affinity=round(social, 4),
                past_engagement=round(past_eng, 4),
                timing=round(timing, 4),
                popularity=round(popularity, 4)
            )

        except Exception as e:
            logger.error(f"Error en calculate_feed_score para post {post.id}: {e}", exc_info=True)
            # Retornar score neutral en caso de error
            return FeedScore(
                post_id=post.id,
                final_score=0.5,
                content_affinity=0.5,
                social_affinity=0.5,
                past_engagement=0.5,
                timing=0.5,
                popularity=0.5
            )

    def calculate_feed_scores_batch(
        self,
        user_id: int,
        gym_id: int,
        posts: List[Post]
    ) -> List[FeedScore]:
        """
        Calcula scores para múltiples posts en batch.

        Returns:
            List[FeedScore] ordenados por score final descendente
        """
        scores = []

        for post in posts:
            score = self.calculate_feed_score(user_id, gym_id, post)
            scores.append(score)

        # Ordenar por score final descendente
        scores.sort(key=lambda x: x.final_score, reverse=True)

        return scores
