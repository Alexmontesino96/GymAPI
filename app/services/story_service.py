"""
Servicio de historias para el gimnasio.
Maneja la lógica de negocio para crear, obtener y gestionar historias.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func, update
from fastapi import HTTPException, status

from app.models.story import (
    Story, StoryView, StoryReaction, StoryReport,
    StoryHighlight, StoryHighlightItem,
    StoryType, StoryPrivacy
)
from app.models.user import User
from app.models.user_gym import UserGym
from app.schemas.story import (
    StoryCreate, StoryUpdate, StoryResponse,
    StoryViewCreate, StoryReactionCreate, StoryReportCreate,
    StoryHighlightCreate, StoryHighlightUpdate
)
from app.repositories.story_feed_repository import StoryFeedRepository

logger = logging.getLogger(__name__)


class StoryService:
    """
    Servicio para gestionar historias del gimnasio.
    """

    def __init__(self, db: Session):
        self.db = db
        self.feed_repo = StoryFeedRepository()

    async def create_story(
        self,
        gym_id: int,
        user_id: int,
        story_data: StoryCreate
    ) -> Story:
        """
        Crea una nueva historia.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario creador
            story_data: Datos de la historia

        Returns:
            Historia creada
        """
        try:
            # Verificar que el usuario pertenece al gimnasio
            user_gym = await self.db.execute(
                select(UserGym).where(
                    and_(
                        UserGym.user_id == user_id,
                        UserGym.gym_id == gym_id,
                        UserGym.is_active == True
                    )
                )
            )
            if not user_gym.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuario no pertenece a este gimnasio"
                )

            # Calcular fecha de expiración
            expires_at = datetime.utcnow() + timedelta(hours=story_data.duration_hours)

            # Crear historia en BD
            story = Story(
                gym_id=gym_id,
                user_id=user_id,
                story_type=story_data.story_type,
                caption=story_data.caption,
                privacy=story_data.privacy,
                media_url=str(story_data.media_url) if story_data.media_url else None,
                workout_data=story_data.workout_data,
                duration_hours=story_data.duration_hours,
                expires_at=expires_at
            )

            self.db.add(story)
            self.db.commit()
            self.db.refresh(story)

            # Crear actividad en Stream Feeds
            try:
                activity = await self.feed_repo.create_story_activity(
                    story=story,
                    gym_id=gym_id,
                    user_id=user_id
                )

                # Guardar el ID de actividad de Stream
                story.stream_activity_id = activity.get("id")
                self.db.commit()

            except Exception as e:
                logger.error(f"Error creating Stream activity for story: {e}")
                # Continuar sin Stream si falla

            # Limpiar cache del usuario
            await self._invalidate_story_cache(gym_id, user_id)

            logger.info(f"Story {story.id} created for user {user_id} in gym {gym_id}")
            return story

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating story: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear la historia"
            )

    async def get_story_by_id(
        self,
        story_id: int,
        gym_id: int,
        user_id: int
    ) -> Story:
        """
        Obtiene una historia por ID.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario que solicita

        Returns:
            Historia encontrada
        """
        story = await self.db.execute(
            select(Story).where(
                and_(
                    Story.id == story_id,
                    Story.gym_id == gym_id,
                    Story.is_deleted == False
                )
            )
        )
        story = story.scalar_one_or_none()

        if not story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Historia no encontrada"
            )

        # Verificar privacidad
        if not await self._can_view_story(story, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para ver esta historia"
            )

        # Registrar vista si no es el propio usuario
        if user_id != story.user_id:
            await self.mark_story_as_viewed(story_id, gym_id, user_id)

        return story

    async def get_user_stories(
        self,
        target_user_id: int,
        gym_id: int,
        requesting_user_id: int,
        include_expired: bool = False
    ) -> List[Story]:
        """
        Obtiene las historias de un usuario específico.

        Args:
            target_user_id: ID del usuario del que obtener historias
            gym_id: ID del gimnasio
            requesting_user_id: ID del usuario que solicita
            include_expired: Incluir historias expiradas

        Returns:
            Lista de historias del usuario
        """
        query = select(Story).where(
            and_(
                Story.user_id == target_user_id,
                Story.gym_id == gym_id,
                Story.is_deleted == False
            )
        )

        # Filtrar historias expiradas
        if not include_expired:
            query = query.where(
                or_(
                    Story.expires_at > datetime.utcnow(),
                    Story.is_pinned == True
                )
            )

        # Ordenar por fecha de creación descendente
        query = query.order_by(Story.created_at.desc())

        result = await self.db.execute(query)
        stories = result.scalars().all()

        # Filtrar por privacidad
        filtered_stories = []
        for story in stories:
            if await self._can_view_story(story, requesting_user_id):
                filtered_stories.append(story)

        return filtered_stories

    async def get_stories_feed(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25,
        offset: int = 0,
        filter_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene el feed de historias para un usuario.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            limit: Número de historias a obtener
            offset: Offset para paginación
            filter_type: Tipo de filtro (all, following, close_friends)

        Returns:
            Feed de historias agrupadas por usuario
        """
        try:
            # Intentar obtener de Stream Feeds primero
            stream_stories = await self.feed_repo.get_timeline_stories(
                gym_id=gym_id,
                user_id=user_id,
                limit=limit,
                offset=offset,
                filter_type=filter_type
            )

            # Si Stream tiene datos, usarlos
            if stream_stories.get("results"):
                # Obtener IDs de historias de Stream
                story_ids = [
                    int(activity.get("story_id"))
                    for activity in stream_stories["results"]
                    if activity.get("story_id")
                ]

                # Cargar historias de BD
                if story_ids:
                    stories = await self.db.execute(
                        select(Story).where(
                            and_(
                                Story.id.in_(story_ids),
                                Story.is_deleted == False
                            )
                        )
                    )
                    stories = stories.scalars().all()
                else:
                    stories = []

            else:
                # Fallback a consulta directa de BD
                query = select(Story).where(
                    and_(
                        Story.gym_id == gym_id,
                        Story.is_deleted == False,
                        or_(
                            Story.expires_at > datetime.utcnow(),
                            Story.is_pinned == True
                        )
                    )
                )

                # Aplicar filtros
                if filter_type == "following":
                    # TODO: Implementar sistema de follows
                    pass
                elif filter_type == "close_friends":
                    query = query.where(Story.privacy == StoryPrivacy.CLOSE_FRIENDS)
                elif filter_type != "all":
                    query = query.where(Story.privacy == StoryPrivacy.PUBLIC)

                # Paginación y ordenamiento
                query = query.order_by(Story.created_at.desc()).limit(limit).offset(offset)

                result = await self.db.execute(query)
                stories = result.scalars().all()

            # Agrupar historias por usuario
            user_stories_map = {}
            for story in stories:
                if story.user_id not in user_stories_map:
                    # Obtener información del usuario
                    user = self.db.get(User, story.user_id)
                    user_stories_map[story.user_id] = {
                        "user_id": story.user_id,
                        "user_name": f"{user.first_name} {user.last_name}" if user else "Usuario",
                        "user_avatar": user.picture if user else None,
                        "stories": [],
                        "has_unseen": False
                    }

                # Verificar si el usuario ya vio esta historia
                has_viewed = await self._has_viewed_story(story.id, user_id)

                story_data = {
                    "id": story.id,
                    "story_type": story.story_type.value,
                    "caption": story.caption,
                    "media_url": story.media_url,
                    "thumbnail_url": story.thumbnail_url,
                    "created_at": story.created_at.isoformat(),
                    "expires_at": story.expires_at.isoformat() if story.expires_at else None,
                    "is_pinned": story.is_pinned,
                    "has_viewed": has_viewed,
                    "view_count": story.view_count,
                    "reaction_count": story.reaction_count
                }

                user_stories_map[story.user_id]["stories"].append(story_data)

                # Marcar si tiene historias sin ver
                if not has_viewed:
                    user_stories_map[story.user_id]["has_unseen"] = True

            # Convertir a lista
            user_stories = list(user_stories_map.values())

            # Ordenar usuarios con historias no vistas primero
            user_stories.sort(key=lambda x: (not x["has_unseen"], x["user_id"]))

            return {
                "user_stories": user_stories,
                "total_users": len(user_stories),
                "has_more": len(stories) == limit,
                "next_offset": offset + limit if len(stories) == limit else None,
                "last_update": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Error getting stories feed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al obtener el feed de historias"
            )

    async def mark_story_as_viewed(
        self,
        story_id: int,
        gym_id: int,
        user_id: int,
        view_data: Optional[StoryViewCreate] = None
    ) -> StoryView:
        """
        Marca una historia como vista.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario que ve
            view_data: Datos adicionales de la vista

        Returns:
            Registro de vista creado o existente
        """
        # Verificar que la historia existe y pertenece al gimnasio
        story = await self.get_story_by_id(story_id, gym_id, user_id)

        # Verificar si ya existe una vista
        existing_view = await self.db.execute(
            select(StoryView).where(
                and_(
                    StoryView.story_id == story_id,
                    StoryView.viewer_id == user_id
                )
            )
        )
        existing_view = existing_view.scalar_one_or_none()

        if existing_view:
            return existing_view

        # Crear nueva vista
        story_view = StoryView(
            story_id=story_id,
            viewer_id=user_id,
            view_duration_seconds=view_data.view_duration_seconds if view_data else None,
            device_info=view_data.device_info if view_data else None
        )

        self.db.add(story_view)

        # Actualizar contador de vistas
        story.view_count = (story.view_count or 0) + 1

        self.db.commit()
        self.db.refresh(story_view)

        # Limpiar cache
        await self._invalidate_story_cache(gym_id, story.user_id)

        return story_view

    async def add_reaction(
        self,
        story_id: int,
        gym_id: int,
        user_id: int,
        reaction_data: StoryReactionCreate
    ) -> StoryReaction:
        """
        Agrega una reacción a una historia.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario que reacciona
            reaction_data: Datos de la reacción

        Returns:
            Reacción creada
        """
        # Verificar que la historia existe
        story = await self.get_story_by_id(story_id, gym_id, user_id)

        # Verificar si ya existe una reacción del usuario
        existing_reaction = await self.db.execute(
            select(StoryReaction).where(
                and_(
                    StoryReaction.story_id == story_id,
                    StoryReaction.user_id == user_id
                )
            )
        )
        existing_reaction = existing_reaction.scalar_one_or_none()

        if existing_reaction:
            # Actualizar reacción existente
            existing_reaction.emoji = reaction_data.emoji
            existing_reaction.message = reaction_data.message
            self.db.commit()
            return existing_reaction

        # Crear nueva reacción
        reaction = StoryReaction(
            story_id=story_id,
            user_id=user_id,
            emoji=reaction_data.emoji,
            message=reaction_data.message
        )

        self.db.add(reaction)

        # Actualizar contador de reacciones
        story.reaction_count = (story.reaction_count or 0) + 1

        self.db.commit()
        self.db.refresh(reaction)

        # Agregar reacción en Stream
        try:
            await self.feed_repo.add_reaction(
                story_id=story_id,
                gym_id=gym_id,
                user_id=user_id,
                reaction_type="emoji",
                data={"emoji": reaction_data.emoji, "message": reaction_data.message}
            )
        except Exception as e:
            logger.error(f"Error adding reaction to Stream: {e}")

        # Limpiar cache
        await self._invalidate_story_cache(gym_id, story.user_id)

        return reaction

    async def delete_story(
        self,
        story_id: int,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina una historia (soft delete).

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario que elimina

        Returns:
            True si se eliminó exitosamente
        """
        # Obtener historia
        story = await self.db.execute(
            select(Story).where(
                and_(
                    Story.id == story_id,
                    Story.gym_id == gym_id,
                    Story.is_deleted == False
                )
            )
        )
        story = story.scalar_one_or_none()

        if not story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Historia no encontrada"
            )

        # Verificar permisos (solo el dueño puede eliminar)
        if story.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar esta historia"
            )

        # Soft delete
        story.is_deleted = True
        story.deleted_at = datetime.utcnow()

        self.db.commit()

        # Eliminar de Stream Feeds
        try:
            await self.feed_repo.delete_story_activity(
                story_id=story_id,
                gym_id=gym_id,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error deleting story from Stream: {e}")

        # Limpiar cache
        await self._invalidate_story_cache(gym_id, user_id)

        logger.info(f"Story {story_id} deleted by user {user_id}")
        return True

    async def create_highlight(
        self,
        gym_id: int,
        user_id: int,
        highlight_data: StoryHighlightCreate
    ) -> StoryHighlight:
        """
        Crea un highlight de historias.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            highlight_data: Datos del highlight

        Returns:
            Highlight creado
        """
        # Verificar que las historias existen y pertenecen al usuario
        stories = await self.db.execute(
            select(Story).where(
                and_(
                    Story.id.in_(highlight_data.story_ids),
                    Story.user_id == user_id,
                    Story.gym_id == gym_id,
                    Story.is_deleted == False
                )
            )
        )
        stories = stories.scalars().all()

        if len(stories) != len(highlight_data.story_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una o más historias no existen o no te pertenecen"
            )

        # Crear highlight
        highlight = StoryHighlight(
            user_id=user_id,
            gym_id=gym_id,
            title=highlight_data.title,
            cover_image_url=str(highlight_data.cover_image_url) if highlight_data.cover_image_url else None
        )

        self.db.add(highlight)
        self.db.flush()

        # Agregar historias al highlight
        for idx, story_id in enumerate(highlight_data.story_ids):
            highlight_item = StoryHighlightItem(
                highlight_id=highlight.id,
                story_id=story_id,
                display_order=idx
            )
            self.db.add(highlight_item)

            # Marcar historias como pinned
            story = next(s for s in stories if s.id == story_id)
            story.is_pinned = True

        self.db.commit()
        self.db.refresh(highlight)

        return highlight

    async def report_story(
        self,
        story_id: int,
        gym_id: int,
        user_id: int,
        report_data: StoryReportCreate
    ) -> StoryReport:
        """
        Reporta una historia.

        Args:
            story_id: ID de la historia
            gym_id: ID del gimnasio
            user_id: ID del usuario que reporta
            report_data: Datos del reporte

        Returns:
            Reporte creado
        """
        # Verificar que la historia existe
        story = await self.get_story_by_id(story_id, gym_id, user_id)

        # No se puede reportar la propia historia
        if story.user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes reportar tu propia historia"
            )

        # Verificar si ya existe un reporte del mismo usuario
        existing_report = await self.db.execute(
            select(StoryReport).where(
                and_(
                    StoryReport.story_id == story_id,
                    StoryReport.reporter_id == user_id
                )
            )
        )
        if existing_report.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya has reportado esta historia"
            )

        # Crear reporte
        report = StoryReport(
            story_id=story_id,
            reporter_id=user_id,
            reason=report_data.reason,
            description=report_data.description
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        logger.warning(f"Story {story_id} reported by user {user_id} for {report_data.reason}")

        return report

    # Métodos auxiliares privados

    async def _can_view_story(self, story: Story, user_id: int) -> bool:
        """
        Verifica si un usuario puede ver una historia basado en privacidad.
        """
        # El dueño siempre puede ver su propia historia
        if story.user_id == user_id:
            return True

        # Historias públicas todos pueden verlas
        if story.privacy == StoryPrivacy.PUBLIC:
            return True

        # TODO: Implementar lógica para FOLLOWERS y CLOSE_FRIENDS
        # Por ahora, solo historias públicas y propias son visibles

        if story.privacy == StoryPrivacy.PRIVATE:
            return False

        return False

    async def _has_viewed_story(self, story_id: int, user_id: int) -> bool:
        """
        Verifica si un usuario ya vio una historia.
        """
        result = await self.db.execute(
            select(StoryView).where(
                and_(
                    StoryView.story_id == story_id,
                    StoryView.viewer_id == user_id
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def _invalidate_story_cache(self, gym_id: int, user_id: int):
        """
        Invalida el cache relacionado con historias.

        TODO: Implementar invalidación de cache con redis_client
        Por ahora, el sistema funciona sin cache para historias.
        """
        # Nota: Para invalidar cache necesitamos acceso a redis_client
        # que no está disponible en el servicio actual.
        # El sistema funciona correctamente sin cache de historias.
        logger.debug(f"Cache invalidation skipped for gym {gym_id}, user {user_id}")