"""
AsyncPostService - Servicio async para gestión de posts del gimnasio.

Este módulo proporciona un servicio totalmente async para operaciones CRUD de posts,
incluyendo manejo de media, privacidad, tags, menciones y Stream Feeds.

Migrado en FASE 3 de la conversión sync → async.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status, UploadFile

from app.models.post import Post, PostMedia, PostTag, PostType, PostPrivacy, TagType
from app.models.user import User
from app.models.user_gym import UserGym
from app.models.event import Event
from app.models.schedule import ClassSession
from app.models.post_interaction import PostLike
from app.schemas.post import PostCreate, PostUpdate
from app.services.post_media_service import PostMediaService
from app.repositories.async_post_feed import async_post_feed_repository

logger = logging.getLogger(__name__)


class AsyncPostService:
    """
    Servicio async para gestión de posts del gimnasio.

    Todos los métodos son async y utilizan AsyncSession y repositorios async.

    Métodos principales:
    - create_post() - Crear post con media upload y Stream Feeds
    - get_post_by_id() - Obtener post con validación de privacidad
    - get_user_posts() - Posts de usuario con filtrado de privacidad
    - get_gym_posts() - Feed global del gimnasio (timeline/explore)
    - update_post() - Actualizar caption y location
    - delete_post() - Soft delete con limpieza de media y Stream
    """

    def __init__(self):
        self.media_service = PostMediaService()
        self.feed_repo = async_post_feed_repository

    async def create_post(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int,
        post_data: PostCreate,
        media_files: Optional[List[UploadFile]] = None
    ) -> Post:
        """
        Crea un nuevo post con media y publicación en Stream Feeds.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario creador
            post_data: Datos del post
            media_files: Archivos de media (opcional)

        Returns:
            Post creado

        Raises:
            HTTPException: Si el usuario no pertenece al gimnasio o error al subir media

        Note:
            - Detecta tipo de post automáticamente según archivos
            - Sube media a S3 vía PostMediaService
            - Publica actividad en Stream Feeds
            - Procesa tags y menciones
            - Limpia media automáticamente si falla la creación
        """
        uploaded_media_urls: List[str] = []
        try:
            # Verificar que el usuario pertenece al gimnasio
            result = await db.execute(
                select(UserGym).where(
                    and_(
                        UserGym.user_id == user_id,
                        UserGym.gym_id == gym_id,
                        UserGym.is_active == True
                    )
                )
            )
            user_gym = result.scalar_one_or_none()

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

            db.add(post)
            await db.flush()  # Para obtener el ID

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
                        db.add(post_media)

                except Exception as e:
                    logger.error(f"Error uploading media: {e}")
                    await db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error al subir archivos: {str(e)}"
                    )

            # Procesar tags y menciones
            await self._create_tags(db, post, post_data)

            await db.commit()
            await db.refresh(post)

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

            # Enriquecer post con user_info antes de retornar
            return await self._enrich_post_with_user_info(db, post, user_id)

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
            await db.rollback()
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
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Obtiene un post por ID con validación de privacidad.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que solicita

        Returns:
            Post enriquecido con información del usuario

        Raises:
            HTTPException: Si el post no existe o no tiene permiso para verlo
        """
        result = await db.execute(
            select(Post).where(
                and_(
                    Post.id == post_id,
                    Post.gym_id == gym_id,
                    Post.is_deleted == False
                )
            )
        )
        post = result.scalar_one_or_none()

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

        # Enriquecer post con user_info
        return await self._enrich_post_with_user_info(db, post, user_id)

    async def get_user_posts(
        self,
        db: AsyncSession,
        target_user_id: int,
        gym_id: int,
        requesting_user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Obtiene los posts de un usuario específico con filtrado de privacidad.

        Args:
            db: Sesión async de base de datos
            target_user_id: ID del usuario del que obtener posts
            gym_id: ID del gimnasio
            requesting_user_id: ID del usuario que solicita
            limit: Número máximo de posts
            offset: Offset para paginación

        Returns:
            Lista de posts enriquecidos del usuario

        Note:
            Filtra automáticamente posts según privacidad (PUBLIC/PRIVATE).
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

        result = await db.execute(query)
        posts = result.scalars().all()

        # Filtrar por privacidad
        filtered_posts = []
        for post in posts:
            if await self._can_view_post(post, requesting_user_id):
                filtered_posts.append(post)

        # Enriquecer posts con user_info
        return await self._enrich_posts_bulk(db, filtered_posts, requesting_user_id)

    async def get_gym_posts(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        feed_type: str = "timeline"
    ) -> List[Dict[str, Any]]:
        """
        Obtiene posts del gimnasio (feed global).

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario que solicita
            limit: Número máximo de posts
            offset: Offset para paginación
            feed_type: Tipo de feed ('timeline', 'explore')

        Returns:
            Lista de posts enriquecidos

        Note:
            - 'timeline': Ordenado cronológicamente
            - 'explore': Ordenado por engagement (likes + comments*2)
            Solo incluye posts públicos.
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

        result = await db.execute(query)
        posts = result.scalars().all()

        # Enriquecer posts con user_info
        return await self._enrich_posts_bulk(db, posts, user_id)

    async def update_post(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        user_id: int,
        update_data: PostUpdate
    ) -> Dict[str, Any]:
        """
        Actualiza un post (solo caption y location son editables).

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que edita
            update_data: Datos a actualizar

        Returns:
            Post actualizado y enriquecido

        Raises:
            HTTPException: Si el post no existe o no tiene permiso para editarlo

        Note:
            Solo el propietario del post puede editarlo.
            Marca automáticamente el post como editado con timestamp.
        """
        post_data = await self.get_post_by_id(db, post_id, gym_id, user_id)

        # Obtener el post original para actualización
        result = await db.execute(
            select(Post).where(
                and_(
                    Post.id == post_id,
                    Post.gym_id == gym_id
                )
            )
        )
        post = result.scalar_one_or_none()

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
        post.edited_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(post)

        logger.info(f"Post {post_id} updated by user {user_id}")

        # Enriquecer post con user_info
        return await self._enrich_post_with_user_info(db, post, user_id)

    async def delete_post(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina un post (soft delete) con limpieza de media y Stream Feeds.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que elimina

        Returns:
            True si se eliminó exitosamente

        Raises:
            HTTPException: Si el post no existe o no tiene permiso para eliminarlo

        Note:
            - Soft delete: marca is_deleted=True
            - Elimina actividad de Stream Feeds
            - Limpia archivos de media de S3 (best-effort)
            Solo el propietario del post puede eliminarlo.
        """
        result = await db.execute(
            select(Post).where(
                and_(
                    Post.id == post_id,
                    Post.gym_id == gym_id,
                    Post.is_deleted == False
                )
            )
        )
        post = result.scalar_one_or_none()

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
        post.deleted_at = datetime.now(timezone.utc)

        await db.commit()

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

        Args:
            post: Post a verificar
            user_id: ID del usuario que solicita

        Returns:
            True si puede ver el post, False en caso contrario

        Note:
            - Propietario: siempre puede ver
            - PUBLIC: todos pueden ver
            - PRIVATE: solo propietario
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

    async def _create_tags(
        self,
        db: AsyncSession,
        post: Post,
        post_data: PostCreate
    ):
        """
        Crea tags para el post (menciones, eventos, sesiones).

        Args:
            db: Sesión async de base de datos
            post: Post al que agregar tags
            post_data: Datos del post con IDs de tags

        Note:
            Valida que usuarios mencionados, eventos y sesiones existan
            en el gimnasio antes de crear los tags.
        """
        # Procesar menciones de usuarios
        if post_data.mentioned_user_ids:
            for mentioned_user_id in post_data.mentioned_user_ids:
                # Verificar que el usuario existe en el gym
                result = await db.execute(
                    select(UserGym).where(
                        and_(
                            UserGym.user_id == mentioned_user_id,
                            UserGym.gym_id == post.gym_id,
                            UserGym.is_active == True
                        )
                    )
                )
                user_exists = result.scalar_one_or_none()

                if user_exists:
                    tag = PostTag(
                        post_id=post.id,
                        tag_type=TagType.MENTION,
                        tag_value=str(mentioned_user_id)
                    )
                    db.add(tag)

        # Procesar evento etiquetado
        if post_data.tagged_event_id:
            result = await db.execute(
                select(Event).where(Event.id == post_data.tagged_event_id)
            )
            event = result.scalar_one_or_none()
            if event and event.gym_id == post.gym_id:
                tag = PostTag(
                    post_id=post.id,
                    tag_type=TagType.EVENT,
                    tag_value=str(post_data.tagged_event_id)
                )
                db.add(tag)

        # Procesar sesión etiquetada
        if post_data.tagged_session_id:
            result = await db.execute(
                select(ClassSession).where(ClassSession.id == post_data.tagged_session_id)
            )
            session = result.scalar_one_or_none()
            if session and session.gym_id == post.gym_id:
                tag = PostTag(
                    post_id=post.id,
                    tag_type=TagType.SESSION,
                    tag_value=str(post_data.tagged_session_id)
                )
                db.add(tag)

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

        Args:
            caption: Caption del post

        Returns:
            Lista de usernames mencionados (sin @)

        Note:
            Usa regex r'@(\w+)' para encontrar menciones.
        """
        if not caption:
            return []

        mention_pattern = r'@(\w+)'
        return re.findall(mention_pattern, caption)

    async def _enrich_post_with_user_info(
        self,
        db: AsyncSession,
        post: Post,
        requesting_user_id: int
    ) -> Dict[str, Any]:
        """
        Enriquece un post con información del usuario y engagement data.

        Args:
            db: Sesión async de base de datos
            post: Post a enriquecer
            requesting_user_id: ID del usuario que solicita

        Returns:
            Dict con el post enriquecido

        Note:
            Incluye:
            - user_info: Información del creador del post
            - is_own_post: Si el usuario es propietario
            - has_liked: Si el usuario dio like
            - engagement_score: Score calculado
            - media: Lista de archivos media
            - tags: Lista de tags (menciones, eventos, sesiones)
        """
        # Obtener información del usuario que creó el post
        result = await db.execute(
            select(User).where(User.id == post.user_id)
        )
        user = result.scalar_one_or_none()

        user_info = None
        if user:
            user_info = {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "picture": user.picture,
                "email": user.email
            }

        # Verificar si es post propio
        is_own_post = (post.user_id == requesting_user_id)

        # Verificar si el usuario actual dio like
        result = await db.execute(
            select(PostLike).where(
                and_(
                    PostLike.post_id == post.id,
                    PostLike.user_id == requesting_user_id
                )
            )
        )
        like_exists = result.scalar_one_or_none()
        has_liked = like_exists is not None

        # Convertir el post a dict y agregar campos adicionales
        post_dict = {
            "id": post.id,
            "gym_id": post.gym_id,
            "user_id": post.user_id,
            "stream_activity_id": post.stream_activity_id,
            "post_type": post.post_type,
            "caption": post.caption,
            "location": post.location,
            "workout_data": post.workout_data,
            "privacy": post.privacy,
            "is_edited": post.is_edited,
            "edited_at": post.edited_at,
            "is_deleted": post.is_deleted,
            "deleted_at": post.deleted_at,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "view_count": post.view_count,
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "media": [
                {
                    "id": m.id,
                    "post_id": m.post_id,
                    "media_url": m.media_url,
                    "thumbnail_url": m.thumbnail_url,
                    "media_type": m.media_type,
                    "display_order": m.display_order,
                    "width": m.width,
                    "height": m.height,
                    "created_at": m.created_at
                }
                for m in (post.media if hasattr(post, 'media') and post.media else [])
            ],
            "tags": [
                {
                    "id": t.id,
                    "tag_type": t.tag_type,
                    "tag_value": t.tag_value,
                    "created_at": t.created_at
                }
                for t in (post.tags if hasattr(post, 'tags') and post.tags else [])
            ],
            "user_info": user_info,
            "is_own_post": is_own_post,
            "has_liked": has_liked,
            "engagement_score": post.engagement_score  # Esta es una property calculada
        }

        return post_dict

    async def _enrich_posts_bulk(
        self,
        db: AsyncSession,
        posts: List[Post],
        requesting_user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Enriquece múltiples posts con información del usuario de forma optimizada.

        Args:
            db: Sesión async de base de datos
            posts: Lista de posts a enriquecer
            requesting_user_id: ID del usuario que solicita

        Returns:
            Lista de dicts con posts enriquecidos

        Note:
            Optimización: Carga todos los usuarios y likes en una sola query
            en lugar de N queries individuales (N+1 problem).
        """
        if not posts:
            return []

        # Obtener todos los user_ids únicos
        user_ids = list(set(post.user_id for post in posts))

        # Cargar todos los usuarios de una vez
        result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users_dict = {user.id: user for user in result.scalars().all()}

        # Obtener todos los post_ids
        post_ids = [post.id for post in posts]

        # Cargar todos los likes del usuario actual de una vez
        result = await db.execute(
            select(PostLike.post_id).where(
                and_(
                    PostLike.post_id.in_(post_ids),
                    PostLike.user_id == requesting_user_id
                )
            )
        )
        liked_post_ids = set(post_id for post_id in result.scalars().all())

        # Enriquecer cada post
        enriched_posts = []
        for post in posts:
            user = users_dict.get(post.user_id)

            user_info = None
            if user:
                user_info = {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "picture": user.picture,
                    "email": user.email
                }

            is_own_post = (post.user_id == requesting_user_id)
            has_liked = post.id in liked_post_ids

            # Convertir el post a dict y agregar campos adicionales
            post_dict = {
                "id": post.id,
                "gym_id": post.gym_id,
                "user_id": post.user_id,
                "stream_activity_id": post.stream_activity_id,
                "post_type": post.post_type,
                "caption": post.caption,
                "location": post.location,
                "workout_data": post.workout_data,
                "privacy": post.privacy,
                "is_edited": post.is_edited,
                "edited_at": post.edited_at,
                "is_deleted": post.is_deleted,
                "deleted_at": post.deleted_at,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
                "view_count": post.view_count,
                "created_at": post.created_at,
                "updated_at": post.updated_at,
                "media": [
                    {
                        "id": m.id,
                        "post_id": m.post_id,
                        "media_url": m.media_url,
                        "thumbnail_url": m.thumbnail_url,
                        "media_type": m.media_type,
                        "display_order": m.display_order,
                        "width": m.width,
                        "height": m.height,
                        "created_at": m.created_at
                    }
                    for m in (post.media if hasattr(post, 'media') and post.media else [])
                ],
                "tags": [
                    {
                        "id": t.id,
                        "tag_type": t.tag_type,
                        "tag_value": t.tag_value,
                        "created_at": t.created_at
                    }
                    for t in (post.tags if hasattr(post, 'tags') and post.tags else [])
                ],
                "user_info": user_info,
                "is_own_post": is_own_post,
                "has_liked": has_liked,
                "engagement_score": post.engagement_score  # Esta es una property calculada
            }

            enriched_posts.append(post_dict)

        return enriched_posts


# Instancia singleton del servicio async
async_post_service = AsyncPostService()
