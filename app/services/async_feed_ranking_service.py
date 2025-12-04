"""
AsyncFeedRankingService - Servicio async para ranking inteligente del feed de posts.

Implementa algoritmo heurístico con 5 señales ponderadas:
1. Content Affinity (25%) - Match con intereses del usuario
2. Social Affinity (25%) - Relación con el autor
3. Past Engagement (15%) - Historial de interacciones
4. Timing (15%) - Recency + horarios activos
5. Popularity (20%) - Trending + engagement

Formula final:
    final_score = (ca * 0.25) + (sa * 0.25) + (pe * 0.15) + (t * 0.15) + (p * 0.20)

Todos los scores están normalizados en el rango [0.0, 1.0].

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import List, Dict, Optional, NamedTuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import math
import logging

from app.models.post import Post
from app.repositories.async_feed_ranking import async_feed_ranking_repository

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


class AsyncFeedRankingService:
    """
    Servicio async de ranking de feed con múltiples señales.

    Todos los métodos son async y utilizan AsyncSession y async_feed_ranking_repository.

    Métodos principales:
    - content_affinity_score() - Match con intereses del usuario
    - social_affinity_score() - Relación con el autor
    - past_engagement_score() - Historial de interacciones
    - timing_score() - Recency + horarios activos
    - popularity_score() - Trending + engagement
    - calculate_feed_score() - Score final de un post
    - calculate_feed_scores_batch() - Scores de múltiples posts
    """

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

    async def content_affinity_score(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        post_id: int
    ) -> float:
        """
        Calcula content affinity (0.0 - 1.0) entre usuario y post.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            post_id: ID del post

        Returns:
            Score de 0.0 a 1.0

        Note:
            Basado en:
            - Categoría primaria del usuario (de clases asistidas)
            - Categorías del post (tags)
            - Match exacto = 1.0
            - Match parcial (categorías relacionadas) = 0.7
            - Sin match = 0.2 (base para diversidad)
        """
        try:
            # 1. Obtener categoría primaria del usuario
            user_category = await async_feed_ranking_repository.get_user_primary_category(
                db, user_id, gym_id
            )

            # 2. Obtener categorías del post
            post_categories = await async_feed_ranking_repository.get_post_categories(db, post_id)

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

    async def social_affinity_score(
        self,
        db: AsyncSession,
        user_id: int,
        author_id: int,
        gym_id: int
    ) -> float:
        """
        Calcula social affinity (0.0 - 1.0) entre usuario y autor.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            author_id: ID del autor del post
            gym_id: ID del gimnasio

        Returns:
            Score de 0.0 a 1.0

        Note:
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
            relationship = await async_feed_ranking_repository.get_user_relationship_type(
                db, user_id, author_id, gym_id
            )

            if relationship == "trainer":
                return 1.0  # Trainer del usuario = máxima prioridad

            if relationship == "trainee":
                return 0.8  # Usuario es trainer del autor

            if relationship == "following":
                return 0.7  # Usuario sigue al autor

            # 2. Verificar interacciones históricas
            interactions = await async_feed_ranking_repository.get_past_interactions_count(
                db, user_id, author_id, days=30
            )

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

    async def past_engagement_score(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        post_id: int,
        post_type: str,
        post_categories: List[str]
    ) -> float:
        """
        Calcula past engagement score (0.0 - 1.0).

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            post_id: ID del post
            post_type: Tipo de post (SINGLE_IMAGE, VIDEO, etc.)
            post_categories: Categorías del post

        Returns:
            Score de 0.0 a 1.0

        Note:
            Basado en:
            - Match con tipo de post preferido (40% del score)
            - Match con categorías que le gustan (40% del score)
            - Boost por engagement frecuente (20% del score)
        """
        try:
            patterns = await async_feed_ranking_repository.get_user_engagement_patterns(
                db, user_id, gym_id
            )

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

    async def timing_score(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        post_created_at: datetime,
        current_time: datetime = None
    ) -> float:
        """
        Calcula timing score (0.0 - 1.0).

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            post_created_at: Fecha de creación del post
            current_time: Fecha actual (opcional, default: now)

        Returns:
            Score de 0.0 a 1.0

        Note:
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
            active_hours = await async_feed_ranking_repository.get_user_active_hours(
                db, user_id, gym_id
            )
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

    async def popularity_score(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int
    ) -> float:
        """
        Calcula popularity score (0.0 - 1.0).

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio

        Returns:
            Score de 0.0 a 1.0

        Note:
            Componentes:
            - 50% trending (velocity vs gym median)
            - 30% engagement absoluto (likes + comments)
            - 20% engagement rate (engagement / views)
        """
        try:
            # Métricas del post
            metrics = await async_feed_ranking_repository.get_post_engagement_metrics(
                db, post_id, gym_id
            )

            # Percentiles del gym (últimas 24h)
            percentiles = await async_feed_ranking_repository.get_gym_engagement_percentiles(
                db, gym_id, hours_lookback=24
            )

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

    async def calculate_feed_score(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        post: Post
    ) -> FeedScore:
        """
        Calcula el score final de ranking para un post.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            post: Objeto Post a rankear

        Returns:
            FeedScore con score final y componentes individuales

        Note:
            Aplica ponderación a las 5 señales y retorna score normalizado.
        """
        try:
            # 1. Calcular cada señal
            content = await self.content_affinity_score(
                db=db,
                user_id=user_id,
                gym_id=gym_id,
                post_id=post.id
            )

            social = await self.social_affinity_score(
                db=db,
                user_id=user_id,
                author_id=post.user_id,
                gym_id=gym_id
            )

            # Obtener categorías del post para past_engagement
            post_categories = await async_feed_ranking_repository.get_post_categories(db, post.id)

            past_eng = await self.past_engagement_score(
                db=db,
                user_id=user_id,
                gym_id=gym_id,
                post_id=post.id,
                post_type=str(post.post_type.value) if post.post_type else "SINGLE_IMAGE",
                post_categories=post_categories
            )

            timing = await self.timing_score(
                db=db,
                user_id=user_id,
                gym_id=gym_id,
                post_created_at=post.created_at
            )

            popularity = await self.popularity_score(
                db=db,
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

    async def calculate_feed_scores_batch(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        posts: List[Post]
    ) -> List[FeedScore]:
        """
        Calcula scores para múltiples posts en batch.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            posts: Lista de posts a rankear

        Returns:
            List[FeedScore] ordenados por score final descendente

        Note:
            Procesa cada post secuencialmente y ordena por score final.
        """
        scores = []

        for post in posts:
            score = await self.calculate_feed_score(db, user_id, gym_id, post)
            scores.append(score)

        # Ordenar por score final descendente
        scores.sort(key=lambda x: x.final_score, reverse=True)

        return scores


# Instancia singleton del servicio async
async_feed_ranking_service = AsyncFeedRankingService()
