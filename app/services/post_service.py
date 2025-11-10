"""
Servicio para gestionar posts del gimnasio.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func, update as sql_update
from fastapi import HTTPException, status, UploadFile

from app.models.post import Post, PostMedia, PostTag, PostType, PostPrivacy, TagType
from app.models.user import User
from app.models.user_gym import UserGym
from app.models.event import Event
from app.models.schedule import ClassSession
from app.schemas.post import PostCreate, PostUpdate
from app.services.post_media_service import PostMediaService
from app.repositories.post_feed_repository import PostFeedRepository

logger = logging.getLogger(__name__)


class PostService:
    """
    Servicio para gestionar posts del gimnasio.
    """

    def __init__(self, db: Session):
        self.db = db
        self.media_service = PostMediaService()
        self.feed_repo = PostFeedRepository()

    async def create_post(
        self,
        gym_id: int,
        user_id: int,
        post_data: PostCreate,
        media_files: Optional[List[UploadFile]] = None
    ) -> Post:
        """
        Crea un nuevo post.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario creador
            post_data: Datos del post
            media_files: Archivos de media (opcional)

        Returns:
            Post creado
        """
        uploaded_media_urls: List[str] = []
        try:
            # Verificar que el usuario pertenece al gimnasio
            user_gym = self.db.execute(
                select(UserGym).where(
                    and_(
                        UserGym.user_id == user_id,
                        UserGym.gym_id == gym_id,
                        UserGym.is_active == True
                    )
                )
            ).scalar_one_or_none()

            if not user_gym:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuario no pertenece a este gimnasio"
                )

            # Determinar tipo de post basado en archivos
            post_type = post_data.post_type
            if media_files:
                if len(media_files) > 1:
                    post_type = PostType.GALLERY
                elif len(media_files) == 1:
                    # Detectar si es imagen o video
                    file = media_files[0]
                    if file.content_type and file.content_type.startswith('video/'):
                        post_type = PostType.VIDEO
                    else:
                        post_type = PostType.SINGLE_IMAGE

            # Crear post en BD
            post = Post(
                gym_id=gym_id,
                user_id=user_id,
                post_type=post_type,
                caption=post_data.caption,
                location=post_data.location,
                privacy=post_data.privacy,
                workout_data=post_data.workout_data,
                like_count=0,
                comment_count=0,
                view_count=0
            )

            self.db.add(post)
            self.db.flush()  # Para obtener el ID

            # Subir archivos de media si existen
            if media_files:
                try:
                    uploaded_media = await self.media_service.upload_gallery(
                        gym_id=gym_id,
                        user_id=user_id,
                        files=media_files
                    )

                    # Crear registros de PostMedia
                    for media_data in uploaded_media:
                        if media_data.get("media_url"):
                            uploaded_media_urls.append(media_data["media_url"])
                        post_media = PostMedia(
                            post_id=post.id,
                            media_url=media_data["media_url"],
                            thumbnail_url=media_data.get("thumbnail_url"),
                            media_type=media_data["media_type"],
                            display_order=media_data["display_order"],
                            width=media_data.get("width"),
                            height=media_data.get("height")
                        )
                        self.db.add(post_media)

                except Exception as e:
                    logger.error(f"Error uploading media: {e}")
                    self.db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error al subir archivos: {str(e)}"
                    )

            # Procesar tags y menciones
            await self._create_tags(post, post_data)

            self.db.commit()
            self.db.refresh(post)

            # Publicar en Stream Feeds
            try:
                await self.feed_repo.create_post_activity(
                    post=post,
                    gym_id=gym_id,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Error creating Stream activity: {e}")
                # Continuar sin Stream si falla

            # TODO: Enviar notificaciones a usuarios mencionados

            logger.info(f"Post {post.id} created for user {user_id} in gym {gym_id}")
            return post

        except HTTPException:
            # Ya hubo manejo específico; intentar limpiar media si existe
            if uploaded_media_urls:
                for url in uploaded_media_urls:
                    try:
                        await self.media_service.delete_post_media(url)
                    except Exception:
                        pass
            raise
        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            self.db.rollback()
            # Limpieza best-effort de media subida si falla creación
            if uploaded_media_urls:
                for url in uploaded_media_urls:
                    try:
                        await self.media_service.delete_post_media(url)
                    except Exception:
                        pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el post"
            )

    async def get_post_by_id(
        self,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> Post:
        """
        Obtiene un post por ID.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que solicita

        Returns:
            Post encontrado
        """
        post = self.db.execute(
            select(Post).where(
                and_(
                    Post.id == post_id,
                    Post.gym_id == gym_id,
                    Post.is_deleted == False
                )
            )
        ).scalar_one_or_none()

        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )

        # Verificar privacidad
        if not await self._can_view_post(post, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para ver este post"
            )

        return post

    async def get_user_posts(
        self,
        target_user_id: int,
        gym_id: int,
        requesting_user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene los posts de un usuario específico.

        Args:
            target_user_id: ID del usuario del que obtener posts
            gym_id: ID del gimnasio
            requesting_user_id: ID del usuario que solicita
            limit: Número máximo de posts
            offset: Offset para paginación

        Returns:
            Lista de posts del usuario
        """
        query = select(Post).where(
            and_(
                Post.user_id == target_user_id,
                Post.gym_id == gym_id,
                Post.is_deleted == False
            )
        )

        # Ordenar por fecha de creación descendente
        query = query.order_by(Post.created_at.desc())

        # Paginación
        query = query.limit(limit).offset(offset)

        result = self.db.execute(query)
        posts = result.scalars().all()

        # Filtrar por privacidad
        filtered_posts = []
        for post in posts:
            if await self._can_view_post(post, requesting_user_id):
                filtered_posts.append(post)

        return filtered_posts

    async def get_gym_posts(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        feed_type: str = "timeline"
    ) -> List[Post]:
        """
        Obtiene posts del gimnasio (feed global).

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario que solicita
            limit: Número máximo de posts
            offset: Offset para paginación
            feed_type: Tipo de feed ('timeline', 'explore')

        Returns:
            Lista de posts
        """
        query = select(Post).where(
            and_(
                Post.gym_id == gym_id,
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC  # Solo posts públicos en feed global
            )
        )

        # Ordenar según tipo de feed
        if feed_type == "explore":
            # Ordenar por engagement (calculado en runtime)
            # En producción esto debería ser un campo calculado o usar ranking de Stream
            query = query.order_by(
                (Post.like_count + Post.comment_count * 2).desc(),
                Post.created_at.desc()
            )
        else:
            # Timeline cronológico
            query = query.order_by(Post.created_at.desc())

        # Paginación
        query = query.limit(limit).offset(offset)

        result = self.db.execute(query)
        return result.scalars().all()

    async def update_post(
        self,
        post_id: int,
        gym_id: int,
        user_id: int,
        update_data: PostUpdate
    ) -> Post:
        """
        Actualiza un post (solo caption y location son editables).

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que edita
            update_data: Datos a actualizar

        Returns:
            Post actualizado
        """
        post = await self.get_post_by_id(post_id, gym_id, user_id)

        # Verificar ownership
        if post.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para editar este post"
            )

        # Actualizar campos permitidos
        if update_data.caption is not None:
            post.caption = update_data.caption
        if update_data.location is not None:
            post.location = update_data.location

        # Marcar como editado
        post.is_edited = True
        post.edited_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(post)

        logger.info(f"Post {post_id} updated by user {user_id}")
        return post

    async def delete_post(
        self,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina un post (soft delete).

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que elimina

        Returns:
            True si se eliminó exitosamente
        """
        post = self.db.execute(
            select(Post).where(
                and_(
                    Post.id == post_id,
                    Post.gym_id == gym_id,
                    Post.is_deleted == False
                )
            )
        ).scalar_one_or_none()

        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )

        # Verificar permisos (solo el dueño puede eliminar)
        if post.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar este post"
            )

        # Soft delete
        post.is_deleted = True
        post.deleted_at = datetime.utcnow()

        self.db.commit()

        # Eliminar de Stream Feeds
        try:
            await self.feed_repo.delete_post_activity(
                post_id=post_id,
                gym_id=gym_id,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error deleting post from Stream: {e}")

        # Eliminar archivos de media del storage (best-effort)
        try:
            # Cargar media asociada (puede estar lazy_loaded via relación)
            media_items = list(post.media) if hasattr(post, 'media') and post.media is not None else []
            for m in media_items:
                if m.media_url:
                    await self.media_service.delete_post_media(m.media_url)
                if m.thumbnail_url:
                    await self.media_service.delete_post_media(m.thumbnail_url)
        except Exception as e:
            logger.error(f"Error cleaning post media from storage: {e}")

        logger.info(f"Post {post_id} deleted by user {user_id}")
        return True

    # Métodos auxiliares privados

    async def _can_view_post(self, post: Post, user_id: int) -> bool:
        """
        Verifica si un usuario puede ver un post basado en privacidad.
        """
        # El dueño siempre puede ver su propio post
        if post.user_id == user_id:
            return True

        # Posts públicos todos pueden verlos
        if post.privacy == PostPrivacy.PUBLIC:
            return True

        # Posts privados solo el dueño
        if post.privacy == PostPrivacy.PRIVATE:
            return False

        return False

    async def _create_tags(self, post: Post, post_data: PostCreate):
        """
        Crea tags para el post (menciones, eventos, sesiones).
        """
        # Procesar menciones de usuarios
        if post_data.mentioned_user_ids:
            for mentioned_user_id in post_data.mentioned_user_ids:
                # Verificar que el usuario existe en el gym
                user_exists = self.db.execute(
                    select(UserGym).where(
                        and_(
                            UserGym.user_id == mentioned_user_id,
                            UserGym.gym_id == post.gym_id,
                            UserGym.is_active == True
                        )
                    )
                ).scalar_one_or_none()

                if user_exists:
                    tag = PostTag(
                        post_id=post.id,
                        tag_type=TagType.MENTION,
                        tag_value=str(mentioned_user_id)
                    )
                    self.db.add(tag)

        # Procesar evento etiquetado
        if post_data.tagged_event_id:
            event = self.db.get(Event, post_data.tagged_event_id)
            if event and event.gym_id == post.gym_id:
                tag = PostTag(
                    post_id=post.id,
                    tag_type=TagType.EVENT,
                    tag_value=str(post_data.tagged_event_id)
                )
                self.db.add(tag)

        # Procesar sesión etiquetada
        if post_data.tagged_session_id:
            session = self.db.get(ClassSession, post_data.tagged_session_id)
            if session and session.gym_id == post.gym_id:
                tag = PostTag(
                    post_id=post.id,
                    tag_type=TagType.SESSION,
                    tag_value=str(post_data.tagged_session_id)
                )
                self.db.add(tag)

        # Extraer menciones del caption (formato @username)
        if post.caption:
            mention_pattern = r'@(\w+)'
            mentions = re.findall(mention_pattern, post.caption)
            for mention in mentions:
                # Intentar encontrar usuario por username
                # TODO: Implementar búsqueda por username cuando esté disponible
                pass

    def _process_mentions(self, caption: Optional[str]) -> List[str]:
        """
        Extrae menciones del caption.
        """
        if not caption:
            return []

        mention_pattern = r'@(\w+)'
        return re.findall(mention_pattern, caption)
