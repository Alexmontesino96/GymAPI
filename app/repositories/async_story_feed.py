"""
AsyncStoryFeedRepository - Repositorio async para integración de stories con Stream Feeds.

Este repositorio es un wrapper HTTP async para Stream Feeds API.
NO accede a base de datos directamente, solo a la API externa de Stream.

Gestiona actividades de stories (historias efímeras) en el feed social distribuido con Stream Feeds.

Migrado en FASE 2 de la conversión sync → async.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from app.core.stream_feeds_client import get_stream_feeds_client, is_stream_feeds_available
from app.models.story import Story, StoryType

logger = logging.getLogger(__name__)


class AsyncStoryFeedRepository:
    """
    Repositorio async para manejar stories en Stream Feeds API.

    Este repositorio NO hereda de AsyncBaseRepository porque no accede
    a base de datos, sino que es un HTTP client para Stream Feeds API.

    Métodos principales:
    - create_story_activity() - Publicar story en Stream Feeds
    - get_user_stories() - Obtener stories de un usuario
    - get_timeline_stories() - Feed de stories del timeline
    - delete_story_activity() - Eliminar story de Stream
    - add_reaction() - Agregar reacción a una story
    - follow_user() - Seguir usuario para ver sus stories
    - unfollow_user() - Dejar de seguir usuario
    - get_story_analytics() - Analytics de una story

    Note:
        Stream Feeds es un servicio de feeds distribuido en tiempo real.
        Feed ID format: gym_{gym_id}_user_{user_id}
        Stories tienen expiración automática (24h por defecto).
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

    async def create_story_activity(
        self,
        story: Story,
        gym_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una actividad de story en Stream Feeds.

        Args:
            story: Story a publicar (modelo SQLAlchemy)
            gym_id: ID del gimnasio (multi-tenant)
            user_id: ID del usuario autor

        Returns:
            Actividad creada o None si Stream no disponible

        Note:
            - Publica en user feed del autor
            - Si es público, también en timeline global del gym
            - Stories expiran automáticamente según expires_at
            - Soporta tipos: IMAGE, VIDEO, WORKOUT, TEXT
        """
        if not self.client:
            logger.info("Stream Feeds no disponible, story solo en base de datos")
            return {
                "id": f"local_{story.id}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        try:
            sanitized_user_id = self._sanitize_user_id(user_id)

            # Construir datos de la actividad
            activity_data = {
                "actor": f"gym_{gym_id}_user_{sanitized_user_id}",
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

            # Obtener feed del usuario
            user_feed = self._get_feed(gym_id, user_id, "user")

            # Publicar actividad
            activity = user_feed.add_activity(activity_data)

            logger.info(f"Actividad de story {story.id} creada en Stream Feeds")

            # Si es público, hacer que timeline global siga al usuario
            if story.privacy.value == "public":
                try:
                    gym_feed = self.client.feed("timeline", f"gym_{gym_id}")
                    gym_feed.follow("user", f"gym_{gym_id}_user_{sanitized_user_id}")
                except Exception as e:
                    # Puede fallar si ya está siguiendo
                    logger.debug(f"Timeline ya sigue al usuario: {e}")

            return activity

        except Exception as e:
            logger.error(f"Error creando actividad de story en Stream: {e}")
            return None

    async def get_user_stories(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Obtiene las stories de un usuario específico.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            limit: Número de stories a obtener
            offset: Offset para paginación

        Returns:
            Dict con results, next y duration

        Note:
            Filtra automáticamente stories expiradas (excepto pinned).
            Stories por defecto expiran en 24 horas desde creación.
        """
        if not self.client:
            return {"results": [], "next": None, "duration": "0ms"}

        try:
            user_feed = self._get_feed(gym_id, user_id, "user")

            # Obtener actividades con paginación
            activities = user_feed.get(limit=limit, offset=offset)

            # Filtrar stories no expiradas
            now = datetime.now(timezone.utc)
            filtered_activities = []

            for activity in activities.get("results", []):
                # Verificar si la story ha expirado
                if activity.get("expires_at"):
                    expires_at = datetime.fromisoformat(activity["expires_at"].replace("Z", "+00:00"))
                    is_pinned = activity.get("is_pinned", False)

                    # Skip si expiró y no está pinned
                    if expires_at < now and not is_pinned:
                        continue

                filtered_activities.append(activity)

            return {
                "results": filtered_activities,
                "next": activities.get("next"),
                "duration": activities.get("duration", "0ms")
            }

        except Exception as e:
            logger.error(f"Error obteniendo stories del usuario: {e}")
            return {"results": [], "next": None, "duration": "0ms"}

    async def get_timeline_stories(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25,
        offset: int = 0,
        filter_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene el feed de stories del timeline (stories de usuarios seguidos).

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario solicitante
            limit: Número de stories a obtener
            offset: Offset para paginación
            filter_type: Tipo de filtro (all, following, close_friends)

        Returns:
            Dict con results, next y duration

        Note:
            - filter_type='all': Stories públicas del gimnasio
            - filter_type='following': Stories de usuarios seguidos
            - filter_type='close_friends': Solo stories de close_friends
            Filtra automáticamente stories expiradas.
        """
        if not self.client:
            return {"results": [], "next": None, "duration": "0ms"}

        try:
            # Timeline feed del usuario para ver stories de seguidos
            timeline_feed = self._get_feed(gym_id, user_id, "timeline")

            # Para feed global del gimnasio
            if filter_type == "all":
                timeline_feed = self.client.feed("timeline", f"gym_{gym_id}")

            # Obtener actividades con paginación
            limit_int = int(limit) if limit else 25
            offset_int = int(offset) if offset else 0

            activities = timeline_feed.get(limit=limit_int, offset=offset_int)

            # Filtrar stories no expiradas y aplicar filtros adicionales
            now = datetime.now(timezone.utc)
            filtered_activities = []

            for activity in activities.get("results", []):
                try:
                    # Verificar si la story ha expirado
                    if activity.get("expires_at"):
                        expires_at_str = activity["expires_at"]

                        # Manejar diferentes formatos de fecha
                        if isinstance(expires_at_str, str):
                            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                        else:
                            expires_at = expires_at_str

                        # Obtener is_pinned como booleano
                        is_pinned = activity.get("is_pinned", False)
                        if isinstance(is_pinned, str):
                            is_pinned = is_pinned.lower() == "true"

                        # Skip si expiró y no está pinned
                        if expires_at < now and not is_pinned:
                            continue

                    # Aplicar filtros de privacidad
                    if filter_type == "close_friends":
                        if activity.get("privacy") != "close_friends":
                            continue

                    filtered_activities.append(activity)

                except (ValueError, TypeError, AttributeError) as e:
                    logger.warning(f"Error procesando actividad de Stream: {e}")
                    continue

            return {
                "results": filtered_activities,
                "next": activities.get("next"),
                "duration": activities.get("duration", "0ms")
            }

        except Exception as e:
            logger.error(f"Error obteniendo feed de stories: {e}")
            return {"results": [], "next": None, "duration": "0ms"}

    async def delete_story_activity(
        self,
        story_id: int,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina una actividad de story de Stream Feeds.

        Args:
            story_id: ID de la story
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
            user_feed.remove_activity(foreign_id=f"story_{story_id}")

            logger.info(f"Actividad de story {story_id} eliminada de Stream Feeds")
            return True

        except Exception as e:
            logger.error(f"Error eliminando actividad de story: {e}")
            return False

    async def add_reaction(
        self,
        story_id: int,
        gym_id: int,
        user_id: int,
        reaction_type: str = "like",
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Agrega una reacción a una story en Stream.

        Args:
            story_id: ID de la story
            gym_id: ID del gimnasio
            user_id: ID del usuario que reacciona
            reaction_type: Tipo de reacción (like, emoji, etc.)
            data: Datos adicionales de la reacción

        Returns:
            Datos de la reacción creada o None si error

        Note:
            Stream Feeds v3 no tiene sistema de reactions integrado.
            Almacenamos reacciones en BD y retornamos datos para tracking.
        """
        if not self.client:
            logger.info("Stream Feeds no disponible")
            return None

        try:
            sanitized_user_id = self._sanitize_user_id(user_id)

            reaction_data = {
                "kind": reaction_type,
                "activity_id": f"story_{story_id}",
                "user_id": f"gym_{gym_id}_user_{sanitized_user_id}",
                "data": data or {}
            }

            logger.info(f"Reacción agregada para story {story_id}")
            return reaction_data

        except Exception as e:
            logger.error(f"Error agregando reacción a story: {e}")
            return None

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

        Note:
            El timeline feed del seguidor empezará a recibir
            stories del usuario seguido automáticamente.
        """
        if not self.client:
            logger.info("Stream Feeds no disponible")
            return False

        try:
            sanitized_following_id = self._sanitize_user_id(following_id)

            # Timeline del seguidor sigue al feed del usuario seguido
            follower_timeline = self._get_feed(gym_id, follower_id, "timeline")
            following_user_feed = f"gym_{gym_id}_user_{sanitized_following_id}"

            follower_timeline.follow("user", following_user_feed)

            logger.info(f"Usuario {follower_id} ahora sigue a usuario {following_id}")
            return True

        except Exception as e:
            logger.error(f"Error siguiendo usuario en Stream: {e}")
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

        Note:
            El timeline feed del seguidor dejará de recibir
            stories del usuario seguido.
        """
        if not self.client:
            logger.info("Stream Feeds no disponible")
            return False

        try:
            sanitized_following_id = self._sanitize_user_id(following_id)

            # Timeline del seguidor deja de seguir al feed del usuario
            follower_timeline = self._get_feed(gym_id, follower_id, "timeline")
            following_user_feed = f"gym_{gym_id}_user_{sanitized_following_id}"

            follower_timeline.unfollow("user", following_user_feed)

            logger.info(f"Usuario {follower_id} dejó de seguir a usuario {following_id}")
            return True

        except Exception as e:
            logger.error(f"Error dejando de seguir usuario en Stream: {e}")
            return False

    async def get_story_analytics(
        self,
        story_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Obtiene analytics de una story específica.

        Args:
            story_id: ID de la story
            gym_id: ID del gimnasio
            user_id: ID del usuario dueño de la story

        Returns:
            Dict con métricas de la story

        Note:
            Stream Feeds v3 no tiene analytics integrado.
            Retorna estructura básica para tracking en BD.
        """
        if not self.client:
            return {
                "story_id": story_id,
                "impressions": 0,
                "engagement_rate": 0.0,
                "reach": 0
            }

        try:
            # Analytics deben ser trackeados en nuestra BD
            return {
                "story_id": story_id,
                "impressions": 0,  # Trackear en BD con vistas
                "engagement_rate": 0.0,  # Calcular con reacciones/vistas
                "reach": 0  # Usuarios únicos que vieron
            }

        except Exception as e:
            logger.error(f"Error obteniendo analytics de story: {e}")
            return {}


# Instancia singleton del repositorio async
async_story_feed_repository = AsyncStoryFeedRepository()
