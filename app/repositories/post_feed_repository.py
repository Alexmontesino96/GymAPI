"""
Repositorio para integración de posts con Stream Feeds.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import re

from app.core.stream_feeds_client import get_stream_feeds_client, is_stream_feeds_available
from app.models.post import Post

logger = logging.getLogger(__name__)


class PostFeedRepository:
    """
    Repositorio para manejar posts en Stream Feeds.
    """

    def __init__(self):
        self.client = None
        if is_stream_feeds_available():
            try:
                self.client = get_stream_feeds_client()
            except Exception as e:
                logger.warning(f"Stream Feeds client no disponible: {e}")

    def _sanitize_user_id(self, user_id: int) -> str:
        """
        Sanitiza el user_id para cumplir con restricciones de Stream.
        Stream no permite user IDs que empiecen con números.
        """
        # Stream requiere que el ID empiece con letra
        return f"u{user_id}"

    def _get_feed(self, gym_id: int, user_id: int, feed_slug: str):
        """
        Obtiene un feed de Stream Feeds.
        """
        if not self.client:
            raise Exception("Stream client not available")

        sanitized_user_id = self._sanitize_user_id(user_id)
        feed_id = f"gym_{gym_id}_{sanitized_user_id}"
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
            post: Post a publicar
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            Actividad creada o None si Stream no disponible
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
                "caption": post.caption[:500] if post.caption else "",  # Limitar tamaño
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
            Dict con posts y metadata
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
            Dict con posts trending
        """
        if not self.client:
            return {"results": [], "duration": "0ms"}

        try:
            gym_feed = self.client.feed("timeline", f"gym_{gym_id}")

            # Obtener actividades recientes
            activities = gym_feed.get(limit=limit * 2)  # Obtener más para rankear

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

            # Ordenar por score
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
            user_id: ID del usuario

        Returns:
            True si se eliminó, False si hubo error
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

    def _calculate_engagement_score(
        self,
        likes: int,
        comments: int,
        age_hours: float
    ) -> float:
        """
        Calcula el score de engagement de un post.

        Formula: likes + (comments * 2) - (age_hours * 0.1)
        """
        return likes + (comments * 2) - (age_hours * 0.1)
