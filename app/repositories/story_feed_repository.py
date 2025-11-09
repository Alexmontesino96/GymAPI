"""
Repositorio para interactuar con Stream Feeds API.
Maneja la creación, obtención y gestión de historias en Stream Activity Feeds.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

try:
    from app.core.stream_feeds_client import stream_feeds_client
    STREAM_AVAILABLE = stream_feeds_client is not None
except Exception as e:
    logging.getLogger(__name__).warning(f"Stream Feeds not available: {e}")
    stream_feeds_client = None
    STREAM_AVAILABLE = False

from app.core.config import get_settings
from app.models.story import Story, StoryType
from app.schemas.story import StoryCreate

logger = logging.getLogger(__name__)
settings = get_settings()


class StoryFeedRepository:
    """
    Repositorio para gestionar historias en Stream Activity Feeds.
    """

    def __init__(self):
        self.client = stream_feeds_client if STREAM_AVAILABLE else None
        self.app_id = settings.STREAM_APP_ID if STREAM_AVAILABLE else None
        self.available = STREAM_AVAILABLE

    def _sanitize_user_id(self, user_id: Any) -> str:
        """
        Sanitiza el user_id para cumplir con restricciones de Stream.
        Stream solo permite letras, números y guiones bajos.

        Args:
            user_id: ID del usuario (puede ser int o str)

        Returns:
            ID sanitizado como string
        """
        # Convertir a string
        user_id_str = str(user_id)

        # Reemplazar caracteres no permitidos con guión bajo
        # Stream solo permite: letras, números y _
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id_str)

        return sanitized

    def _get_feed(self, gym_id: int, user_id: int, feed_type: str = "user"):
        """
        Obtiene un feed específico de Stream.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            feed_type: Tipo de feed (user, timeline, etc.)
        """
        # Sanitizar user_id para Stream
        safe_user_id = self._sanitize_user_id(user_id)
        feed_id = f"gym_{gym_id}_user_{safe_user_id}"
        return self.client.feed(feed_type, feed_id)

    async def create_story_activity(
        self,
        story: Story,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Crea una actividad de historia en Stream Feeds.

        Args:
            story: Modelo de historia de SQLAlchemy
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            Datos de la actividad creada en Stream
        """
        if not self.available or not self.client:
            logger.warning("Stream Feeds not available, story will only exist in database")
            return {"id": f"local_{story.id}", "created_at": datetime.utcnow().isoformat()}

        try:
            # Sanitizar user_id para Stream
            safe_user_id = self._sanitize_user_id(user_id)

            # Preparar datos de la actividad
            activity_data = {
                "actor": f"gym_{gym_id}_user_{safe_user_id}",
                "verb": "story",
                "object": f"story:{story.id}",
                "foreign_id": f"story_{story.id}",
                "time": story.created_at.isoformat(),

                # Datos de la historia
                "story_id": story.id,
                "story_type": story.story_type.value,
                "caption": story.caption,
                "media_url": story.media_url,
                "thumbnail_url": story.thumbnail_url,
                "privacy": story.privacy.value,

                # Metadata adicional
                "gym_id": gym_id,
                "user_id": user_id,
                "expires_at": story.expires_at.isoformat() if story.expires_at else None,
                "is_pinned": story.is_pinned,

                # Datos específicos del tipo
                "workout_data": story.workout_data if story.story_type == StoryType.WORKOUT else None,
            }

            # Eliminar campos None
            activity_data = {k: v for k, v in activity_data.items() if v is not None}

            # Crear actividad en el feed del usuario
            user_feed = self._get_feed(gym_id, user_id, "user")
            activity = user_feed.add_activity(activity_data)

            # Si la historia es pública, agregar a feeds de seguidores
            if story.privacy.value == "public":
                # Obtener timeline feed del gimnasio
                gym_timeline_feed = self.client.feed("timeline", f"gym_{gym_id}")

                # Hacer que el timeline del gimnasio siga al usuario
                # Esto permite que las historias públicas aparezcan en el feed global
                try:
                    gym_timeline_feed.follow("user", f"gym_{gym_id}_user_{safe_user_id}")
                except Exception as e:
                    # Puede fallar si ya está siguiendo
                    logger.debug(f"Timeline already following user: {e}")

            logger.info(f"Story activity created in Stream for story {story.id}")
            return activity

        except Exception as e:
            logger.error(f"Error creating story activity in Stream: {str(e)}")
            raise

    async def get_user_stories(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Obtiene las historias de un usuario específico.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            limit: Número de historias a obtener
            offset: Offset para paginación

        Returns:
            Historias del usuario desde Stream
        """
        if not self.available or not self.client:
            logger.debug("Stream Feeds not available, returning empty results")
            return {"results": [], "next": None}

        try:
            user_feed = self._get_feed(gym_id, user_id, "user")

            # Obtener actividades con paginación
            activities = user_feed.get(
                limit=limit,
                offset=offset
            )

            # Filtrar historias no expiradas
            now = datetime.utcnow()
            filtered_activities = []

            for activity in activities.get("results", []):
                # Verificar si la historia ha expirado
                if activity.get("expires_at"):
                    expires_at = datetime.fromisoformat(activity["expires_at"].replace("Z", "+00:00"))
                    if expires_at < now and not activity.get("is_pinned"):
                        continue

                filtered_activities.append(activity)

            return {
                "results": filtered_activities,
                "next": activities.get("next"),
                "duration": activities.get("duration")
            }

        except Exception as e:
            logger.error(f"Error getting user stories from Stream: {str(e)}")
            return {"results": [], "next": None}

    async def get_timeline_stories(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25,
        offset: int = 0,
        filter_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene el feed de historias del timeline (historias de usuarios seguidos).

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            limit: Número de historias a obtener
            offset: Offset para paginación
            filter_type: Tipo de filtro (all, following, close_friends)

        Returns:
            Feed de historias desde Stream
        """
        if not self.available or not self.client:
            logger.debug("Stream Feeds not available, returning empty results")
            return {"results": [], "next": None}

        try:
            # Usar timeline feed del usuario para ver historias de seguidos
            timeline_feed = self._get_feed(gym_id, user_id, "timeline")

            # Para feed global del gimnasio
            if filter_type == "all":
                timeline_feed = self.client.feed("timeline", f"gym_{gym_id}")

            # Obtener actividades con paginación
            activities = timeline_feed.get(
                limit=limit,
                offset=offset
            )

            # Filtrar historias no expiradas y aplicar filtros adicionales
            now = datetime.utcnow()
            filtered_activities = []

            for activity in activities.get("results", []):
                # Verificar si la historia ha expirado
                if activity.get("expires_at"):
                    expires_at = datetime.fromisoformat(activity["expires_at"].replace("Z", "+00:00"))
                    if expires_at < now and not activity.get("is_pinned"):
                        continue

                # Aplicar filtros de privacidad si es necesario
                if filter_type == "close_friends":
                    if activity.get("privacy") != "close_friends":
                        continue

                filtered_activities.append(activity)

            return {
                "results": filtered_activities,
                "next": activities.get("next"),
                "duration": activities.get("duration")
            }

        except Exception as e:
            logger.error(f"Error getting timeline stories from Stream: {str(e)}")
            return {"results": [], "next": None}

    async def delete_story_activity(
        self,
        story_id: int,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina una actividad de historia de Stream Feeds.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            True si se eliminó exitosamente
        """
        if not self.available or not self.client:
            logger.debug("Stream Feeds not available, skipping delete from stream")
            return True

        try:
            user_feed = self._get_feed(gym_id, user_id, "user")

            # Eliminar por foreign_id
            user_feed.remove_activity(foreign_id=f"story_{story_id}")

            logger.info(f"Story activity {story_id} deleted from Stream")
            return True

        except Exception as e:
            logger.error(f"Error deleting story activity from Stream: {str(e)}")
            return False

    async def add_reaction(
        self,
        story_id: int,
        gym_id: int,
        user_id: int,
        reaction_type: str = "like",
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Agrega una reacción a una historia en Stream.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario que reacciona
            reaction_type: Tipo de reacción (like, emoji, etc.)
            data: Datos adicionales de la reacción

        Returns:
            Datos de la reacción creada
        """
        try:
            # Sanitizar user_id para Stream
            safe_user_id = self._sanitize_user_id(user_id)

            reaction_data = {
                "kind": reaction_type,
                "activity_id": f"story_{story_id}",
                "user_id": f"gym_{gym_id}_user_{safe_user_id}",
                "data": data or {}
            }

            # Stream Feeds maneja reacciones de manera diferente en v3
            # Por ahora, almacenaremos las reacciones en nuestra BD
            # y actualizaremos el contador en la actividad

            logger.info(f"Reaction added for story {story_id}")
            return reaction_data

        except Exception as e:
            logger.error(f"Error adding reaction to story in Stream: {str(e)}")
            raise

    async def follow_user(
        self,
        gym_id: int,
        follower_id: int,
        following_id: int
    ) -> bool:
        """
        Hace que un usuario siga a otro en Stream Feeds.

        Args:
            gym_id: ID del gimnasio
            follower_id: ID del usuario que sigue
            following_id: ID del usuario seguido

        Returns:
            True si se siguió exitosamente
        """
        try:
            # Sanitizar IDs para Stream
            safe_following_id = self._sanitize_user_id(following_id)

            # Timeline del seguidor sigue al feed del usuario seguido
            follower_timeline = self._get_feed(gym_id, follower_id, "timeline")
            following_user_feed = f"gym_{gym_id}_user_{safe_following_id}"

            follower_timeline.follow("user", following_user_feed)

            logger.info(f"User {follower_id} now following user {following_id}")
            return True

        except Exception as e:
            logger.error(f"Error following user in Stream: {str(e)}")
            return False

    async def unfollow_user(
        self,
        gym_id: int,
        follower_id: int,
        following_id: int
    ) -> bool:
        """
        Hace que un usuario deje de seguir a otro en Stream Feeds.

        Args:
            gym_id: ID del gimnasio
            follower_id: ID del usuario que deja de seguir
            following_id: ID del usuario que era seguido

        Returns:
            True si se dejó de seguir exitosamente
        """
        try:
            # Sanitizar IDs para Stream
            safe_following_id = self._sanitize_user_id(following_id)

            # Timeline del seguidor deja de seguir al feed del usuario
            follower_timeline = self._get_feed(gym_id, follower_id, "timeline")
            following_user_feed = f"gym_{gym_id}_user_{safe_following_id}"

            follower_timeline.unfollow("user", following_user_feed)

            logger.info(f"User {follower_id} unfollowed user {following_id}")
            return True

        except Exception as e:
            logger.error(f"Error unfollowing user in Stream: {str(e)}")
            return False

    async def get_story_analytics(
        self,
        story_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Obtiene analytics de una historia específica.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario dueño de la historia

        Returns:
            Datos analíticos de la historia
        """
        try:
            # Stream Feeds v3 no tiene analytics integrado
            # Retornamos datos básicos que podemos obtener

            return {
                "story_id": story_id,
                "impressions": 0,  # Se debe trackear en nuestra BD
                "engagement_rate": 0.0,
                "reach": 0
            }

        except Exception as e:
            logger.error(f"Error getting story analytics from Stream: {str(e)}")
            return {}