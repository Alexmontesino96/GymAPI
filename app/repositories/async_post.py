"""
AsyncPostRepository - Repositorio async para operaciones de posts.

Este repositorio hereda de AsyncBaseRepository y agrega métodos específicos
para búsquedas y filtros avanzados de posts del feed social del gimnasio.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.repositories.async_base import AsyncBaseRepository
from app.models.post import Post, PostTag, PostPrivacy, TagType
from app.schemas.post import PostCreate, PostUpdate


class AsyncPostRepository(AsyncBaseRepository[Post, PostCreate, PostUpdate]):
    """
    Repositorio async para operaciones de posts.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener post por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples posts
    - create(db, obj_in, gym_id) - Crear post
    - update(db, db_obj, obj_in, gym_id) - Actualizar post
    - remove(db, id, gym_id) - Eliminar post
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos de Post:
    - get_by_location() - Posts por ubicación
    - get_by_event() - Posts etiquetados con un evento
    - get_by_session() - Posts etiquetados con una sesión
    - get_trending() - Posts más populares (engagement)
    - get_user_mentions() - Posts donde se menciona al usuario
    - count_user_posts() - Contador de posts de un usuario
    """

    async def get_by_location(
        self,
        db: AsyncSession,
        gym_id: int,
        location: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts por ubicación.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            location: Término de búsqueda de ubicación
            limit: Máximo de posts a retornar
            offset: Número de posts a omitir (paginación)

        Returns:
            Lista de posts públicos con la ubicación especificada

        Note:
            Búsqueda case-insensitive en el campo location
            Solo retorna posts públicos no eliminados
        """
        query = select(Post).where(
            and_(
                Post.gym_id == gym_id,
                Post.location.ilike(f"%{location}%"),
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_event(
        self,
        db: AsyncSession,
        gym_id: int,
        event_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts etiquetados con un evento específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            event_id: ID del evento etiquetado
            limit: Máximo de posts a retornar
            offset: Número de posts a omitir

        Returns:
            Lista de posts públicos etiquetados con el evento

        Note:
            Utiliza una subquery para filtrar por tags de tipo EVENT
        """
        # Subquery para encontrar post_ids con el tag
        tag_subquery = select(PostTag.post_id).where(
            and_(
                PostTag.tag_type == TagType.EVENT,
                PostTag.tag_value == str(event_id)
            )
        )

        query = select(Post).where(
            and_(
                Post.id.in_(tag_subquery),
                Post.gym_id == gym_id,
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_session(
        self,
        db: AsyncSession,
        gym_id: int,
        session_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts etiquetados con una sesión de clase específica.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            session_id: ID de la sesión etiquetada
            limit: Máximo de posts a retornar
            offset: Número de posts a omitir

        Returns:
            Lista de posts públicos etiquetados con la sesión

        Note:
            Utiliza una subquery para filtrar por tags de tipo SESSION
        """
        # Subquery para encontrar post_ids con el tag
        tag_subquery = select(PostTag.post_id).where(
            and_(
                PostTag.tag_type == TagType.SESSION,
                PostTag.tag_value == str(session_id)
            )
        )

        query = select(Post).where(
            and_(
                Post.id.in_(tag_subquery),
                Post.gym_id == gym_id,
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_trending(
        self,
        db: AsyncSession,
        gym_id: int,
        hours: int = 24,
        limit: int = 20
    ) -> List[Post]:
        """
        Obtiene posts trending (más populares en las últimas X horas).

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            hours: Ventana de tiempo para considerar trending
            limit: Máximo de posts a retornar

        Returns:
            Lista de posts ordenados por engagement score

        Note:
            Engagement score: likes + (comments * 2)
            En producción debería ser un campo calculado o materialized view
        """
        since = datetime.utcnow() - timedelta(hours=hours)

        query = select(Post).where(
            and_(
                Post.gym_id == gym_id,
                Post.created_at >= since,
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(
            (Post.like_count + Post.comment_count * 2).desc(),
            Post.created_at.desc()
        ).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_user_mentions(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts donde el usuario fue mencionado.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            user_id: ID del usuario mencionado
            limit: Máximo de posts a retornar
            offset: Número de posts a omitir

        Returns:
            Lista de posts públicos donde se menciona al usuario

        Note:
            Utiliza una subquery para filtrar por tags de tipo MENTION
        """
        # Subquery para encontrar post_ids donde el usuario fue mencionado
        tag_subquery = select(PostTag.post_id).where(
            and_(
                PostTag.tag_type == TagType.MENTION,
                PostTag.tag_value == str(user_id)
            )
        )

        query = select(Post).where(
            and_(
                Post.id.in_(tag_subquery),
                Post.gym_id == gym_id,
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def count_user_posts(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int
    ) -> int:
        """
        Cuenta el total de posts de un usuario.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            user_id: ID del usuario

        Returns:
            Número total de posts no eliminados del usuario

        Note:
            Incluye posts de cualquier privacidad (PUBLIC, FRIENDS_ONLY, PRIVATE)
        """
        query = select(func.count(Post.id)).where(
            and_(
                Post.user_id == user_id,
                Post.gym_id == gym_id,
                Post.is_deleted == False
            )
        )

        result = await db.execute(query)
        return result.scalar() or 0


# Instancia singleton del repositorio async
async_post_repository = AsyncPostRepository(Post)
