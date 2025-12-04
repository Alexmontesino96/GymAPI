"""
AsyncPostFeedRepository - Repositorio async para integración de posts con Stream Feeds.

Este repositorio es un wrapper HTTP async para Stream Feeds API.
NO accede a base de datos directamente, solo a la API externa de Stream.

Gestiona actividades de posts en el feed social distribuido con Stream Feeds.

Migrado en FASE 2 de la conversión sync → async.
"""
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.stream_feeds_client import get_stream_feeds_client, is_stream_feeds_available
from app.models.post import Post

logger = logging.getLogger(__name__)


class AsyncPostFeedRepository:
    """
    Repositorio async para manejar posts en Stream Feeds API.

    Este repositorio NO hereda de AsyncBaseRepository porque no accede
    a base de datos, sino que es un HTTP client para Stream Feeds API.

    Métodos principales:
    - create_post_activity() - Publicar post en Stream Feeds
    - get_gym_feed() - Obtener feed del gimnasio
    - get_explore_feed() - Feed de exploración (trending)
    - delete_post_activity() - Eliminar post de Stream

    Note:
        Stream Feeds es un servicio de feeds distribuido en tiempo real.
        Feed ID format: gym_{gym_id}_user_{user_id}
    """

    def __init__(self):
        """Inicializa el cliente de Stream Feeds."""
        self.client = None
        if is_stream_feeds_available():
            try:
                self.client = get_stream_feeds_client()
            except Exception as e:
                logger.warning(f"Stream Feeds client no disponible: {e}")

    def _sanitize_user_id(self, user_id: int) -> str:
        """
        Sanitiza el user_id para cumplir con restricciones de Stream.

        Args:
            user_id: ID del usuario (int)

        Returns:
            User ID sanitizado (solo letras, números y guiones bajos)

        Note:
            Stream solo permite: [a-zA-Z0-9_]
        """
        user_id_str = str(user_id)
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id_str)
        return sanitized

    def _get_feed(self, gym_id: int, user_id: int, feed_slug: str):
        """
        Obtiene un feed de Stream Feeds.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            feed_slug: Tipo de feed (user, timeline, etc.)

        Returns:
            Feed object de Stream

        Raises:
            Exception: Si Stream client no disponible

        Note:
            Feed ID unificado: gym_{gym_id}_user_{safe_user_id}
        """
        if not self.client:
            raise Exception("Stream client not available")

        sanitized_user_id = self._sanitize_user_id(user_id)
        feed_id = f"gym_{gym_id}_user_{sanitized_user_id}"
        return self.client.feed(feed_slug, feed_id)

    async def create_post_activity(
        self,
        post: Post,
        gym_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una actividad de post en Stream Feeds.

        Args:
            post: Post a publicar (modelo SQLAlchemy)
            gym_id: ID del gimnasio (multi-tenant)
            user_id: ID del usuario autor

        Returns:
            Actividad creada o None si Stream no disponible

        Note:
            - Publica en user feed del autor
            - Si es público, también en timeline global del gym
            - Limita caption a 500 chars para Stream
        """
        if not self.client:
            logger.info("Stream Feeds no disponible, saltando creación de actividad")
            return None

        try:
            sanitized_user_id = self._sanitize_user_id(user_id)

            # Construir datos de la actividad
            activity_data = {
                "actor": f"gym_{gym_id}_user_{sanitized_user_id}",
                "verb": "post",
                "object": f"post:{post.id}",
                "foreign_id": f"post_{post.id}",
                "time": post.created_at.isoformat() if post.created_at else datetime.utcnow().isoformat(),
                "post_id": post.id,
                "post_type": post.post_type.value if post.post_type else "single_image",
                "caption": post.caption[:500] if post.caption else "",
                "location": post.location,
                "privacy": post.privacy.value if post.privacy else "public",
                "gym_id": gym_id,
                "user_id": user_id,
                "like_count": post.like_count,
                "comment_count": post.comment_count
            }

            # Obtener feed del usuario
            user_feed = self._get_feed(gym_id, user_id, "user")

            # Publicar actividad
            activity = user_feed.add_activity(activity_data)

            logger.info(f"Actividad de post {post.id} creada en Stream Feeds")

            # Si es público, también publicar en feed global del gym
            if post.privacy.value == "public":
                try:
                    gym_feed = self.client.feed("timeline", f"gym_{gym_id}")
                    gym_feed.add_activity(activity_data)
                except Exception as e:
                    logger.error(f"Error publicando en feed global: {e}")

            return activity

        except Exception as e:
            logger.error(f"Error creando actividad en Stream: {e}")
            return None

    async def get_gym_feed(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Obtiene el feed de posts del gimnasio.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario solicitante
            limit: Número de posts a obtener
            offset: Offset para paginación

        Returns:
            Dict con results, duration y metadata

        Note:
            Feed timeline global del gimnasio con posts públicos.
        """
        if not self.client:
            return {"results": [], "duration": "0ms"}

        try:
            gym_feed = self.client.feed("timeline", f"gym_{gym_id}")

            # Obtener actividades con paginación
            activities = gym_feed.get(limit=limit, offset=offset)

            logger.info(f"Obtenidas {len(activities.get('results', []))} actividades del feed del gym {gym_id}")
            return activities

        except Exception as e:
            logger.error(f"Error obteniendo feed del gym: {e}")
            return {"results": [], "duration": "0ms"}

    async def get_explore_feed(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25
    ) -> Dict[str, Any]:
        """
        Obtiene el feed de exploración (posts más populares).

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario solicitante
            limit: Número de posts

        Returns:
            Dict con posts trending ordenados por engagement

        Note:
            Formula engagement: likes + (comments * 2) - (age_hours * 0.1)
            Obtiene limit*2 posts y rankea por engagement score.
        """
        if not self.client:
            return {"results": [], "duration": "0ms"}

        try:
            gym_feed = self.client.feed("timeline", f"gym_{gym_id}")

            # Obtener más actividades para rankear
            activities = gym_feed.get(limit=limit * 2)

            # Rankear por engagement
            results = activities.get("results", [])
            scored_results = []

            for activity in results:
                # Calcular engagement score
                likes = activity.get("like_count", 0)
                comments = activity.get("comment_count", 0)

                # Calcular edad en horas
                time_str = activity.get("time", "")
                try:
                    activity_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    age_hours = (datetime.utcnow() - activity_time.replace(tzinfo=None)).total_seconds() / 3600
                except:
                    age_hours = 0

                # Formula: likes + (comments * 2) - (age_hours * 0.1)
                score = likes + (comments * 2) - (age_hours * 0.1)

                scored_results.append({
                    **activity,
                    "engagement_score": score
                })

            # Ordenar por score descendente
            scored_results.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

            # Limitar resultados
            top_results = scored_results[:limit]

            return {
                "results": top_results,
                "duration": activities.get("duration", "0ms")
            }

        except Exception as e:
            logger.error(f"Error obteniendo feed explore: {e}")
            return {"results": [], "duration": "0ms"}

    async def delete_post_activity(
        self,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina una actividad de post de Stream Feeds.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario autor

        Returns:
            True si se eliminó, False si hubo error

        Note:
            Elimina por foreign_id para evitar buscar el activity_id.
        """
        if not self.client:
            logger.info("Stream Feeds no disponible, saltando eliminación")
            return True

        try:
            user_feed = self._get_feed(gym_id, user_id, "user")

            # Eliminar por foreign_id
            user_feed.remove_activity(foreign_id=f"post_{post_id}")

            logger.info(f"Actividad de post {post_id} eliminada de Stream Feeds")
            return True

        except Exception as e:
            logger.error(f"Error eliminando actividad de Stream: {e}")
            return False


# Instancia singleton del repositorio async
async_post_feed_repository = AsyncPostFeedRepository()
