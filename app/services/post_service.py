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
from app.models.post_interaction import PostLike
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

        IMPORTANTE: Las imágenes se suben ANTES de crear el post en BD.
        Esto evita posts huérfanos si el proceso falla durante el upload.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario creador
            post_data: Datos del post
            media_files: Archivos de media (opcional)

        Returns:
            Post creado
        """
        uploaded_media: List[Dict[str, Any]] = []
        uploaded_media_urls: List[str] = []

        try:
            # 1. Verificar que el usuario pertenece al gimnasio
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

            # 2. Determinar tipo de post basado en archivos
            post_type = post_data.post_type
            if media_files:
                if len(media_files) > 1:
                    post_type = PostType.GALLERY
                elif len(media_files) == 1:
                    file = media_files[0]
                    if file.content_type and file.content_type.startswith('video/'):
                        post_type = PostType.VIDEO
                    else:
                        post_type = PostType.SINGLE_IMAGE

            # 3. SUBIR ARCHIVOS PRIMERO (antes de crear el post en BD)
            # Si esto falla, no hay nada que limpiar en la BD
            if media_files:
                try:
                    uploaded_media = await self.media_service.upload_gallery(
                        gym_id=gym_id,
                        user_id=user_id,
                        files=media_files
                    )
                    # Guardar URLs para limpieza en caso de error posterior
                    for media_data in uploaded_media:
                        if media_data.get("media_url"):
                            uploaded_media_urls.append(media_data["media_url"])

                    logger.info(f"Media subida exitosamente: {len(uploaded_media)} archivos")

                except HTTPException:
                    # Error controlado (validación, tamaño, etc.)
                    raise
                except Exception as e:
                    logger.error(f"Error uploading media: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error al subir archivos: {str(e)}"
                    )

            # 4. CREAR POST EN BD (solo si el upload fue exitoso)
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

            # 5. Crear registros de PostMedia vinculados al post
            for media_data in uploaded_media:
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

            # 6. Procesar tags y menciones
            await self._create_tags(post, post_data)

            # 7. COMMIT - Solo aquí se persiste todo
            self.db.commit()
            self.db.refresh(post)

            # 8. Publicar en Stream Feeds (best-effort)
            try:
                await self.feed_repo.create_post_activity(
                    post=post,
                    gym_id=gym_id,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Error creating Stream activity: {e}")
                # Continuar sin Stream si falla

            logger.info(f"Post {post.id} created for user {user_id} in gym {gym_id}")

            # Enriquecer post con user_info antes de retornar
            return await self._enrich_post_with_user_info(post, user_id)

        except HTTPException:
            # Rollback de BD por si acaso
            self.db.rollback()
            # Limpiar media subida si existe
            if uploaded_media_urls:
                logger.info(f"Limpiando {len(uploaded_media_urls)} archivos por error")
                for url in uploaded_media_urls:
                    try:
                        await self.media_service.delete_post_media(url)
                    except Exception as cleanup_err:
                        logger.warning(f"Error limpiando media {url}: {cleanup_err}")
            raise

        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            self.db.rollback()
            # Limpiar media subida si existe
            if uploaded_media_urls:
                logger.info(f"Limpiando {len(uploaded_media_urls)} archivos por error")
                for url in uploaded_media_urls:
                    try:
                        await self.media_service.delete_post_media(url)
                    except Exception as cleanup_err:
                        logger.warning(f"Error limpiando media {url}: {cleanup_err}")
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

        # Enriquecer post con user_info
        return await self._enrich_post_with_user_info(post, user_id)

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

        # Enriquecer posts con user_info
        return await self._enrich_posts_bulk(filtered_posts, requesting_user_id)

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
        posts = result.scalars().all()

        # Enriquecer posts con user_info
        return await self._enrich_posts_bulk(posts, user_id)

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

        # Enriquecer post con user_info
        return await self._enrich_post_with_user_info(post, user_id)

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

    async def _enrich_post_with_user_info(self, post: Post, requesting_user_id: int) -> Dict[str, Any]:
        """
        Enriquece un post con información del usuario y engagement data.

        Args:
            post: Post a enriquecer
            requesting_user_id: ID del usuario que solicita

        Returns:
            Dict con el post enriquecido
        """
        # Obtener información del usuario que creó el post
        user = self.db.execute(
            select(User).where(User.id == post.user_id)
        ).scalar_one_or_none()

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
        like_exists = self.db.execute(
            select(PostLike).where(
                and_(
                    PostLike.post_id == post.id,
                    PostLike.user_id == requesting_user_id
                )
            )
        ).scalar_one_or_none()

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

    async def _enrich_posts_bulk(self, posts: List[Post], requesting_user_id: int) -> List[Dict[str, Any]]:
        """
        Enriquece múltiples posts con información del usuario de forma optimizada.

        Args:
            posts: Lista de posts a enriquecer
            requesting_user_id: ID del usuario que solicita

        Returns:
            Lista de dicts con posts enriquecidos
        """
        if not posts:
            return []

        # Obtener todos los user_ids únicos
        user_ids = list(set(post.user_id for post in posts))

        # Cargar todos los usuarios de una vez
        users_result = self.db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users_dict = {user.id: user for user in users_result.scalars().all()}

        # Obtener todos los post_ids
        post_ids = [post.id for post in posts]

        # Cargar todos los likes del usuario actual de una vez
        likes_result = self.db.execute(
            select(PostLike.post_id).where(
                and_(
                    PostLike.post_id.in_(post_ids),
                    PostLike.user_id == requesting_user_id
                )
            )
        )
        liked_post_ids = set(post_id for post_id in likes_result.scalars().all())

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
