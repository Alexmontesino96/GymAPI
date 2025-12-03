"""
Repositorio para queries especializadas de posts.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta

from app.models.post import Post, PostTag, PostPrivacy, TagType
from app.repositories.base import BaseRepository
from app.schemas.post import PostCreate, PostUpdate


class PostRepository(BaseRepository[Post, PostCreate, PostUpdate]):
    """
    Repositorio para operaciones de posts.
    """

    def __init__(self):
        super().__init__(Post)

    def get_by_location(
        self,
        db: Session,
        gym_id: int,
        location: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts por ubicación.
        """
        query = select(Post).where(
            and_(
                Post.gym_id == gym_id,
                Post.location.ilike(f"%{location}%"),
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = db.execute(query)
        return result.scalars().all()

    def get_by_event(
        self,
        db: Session,
        gym_id: int,
        event_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts etiquetados con un evento específico.
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

        result = db.execute(query)
        return result.scalars().all()

    def get_by_session(
        self,
        db: Session,
        gym_id: int,
        session_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts etiquetados con una sesión específica.
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

        result = db.execute(query)
        return result.scalars().all()

    def get_trending(
        self,
        db: Session,
        gym_id: int,
        hours: int = 24,
        limit: int = 20
    ) -> List[Post]:
        """
        Obtiene posts trending (más populares en las últimas X horas).

        Usa engagement score: likes + (comments * 2) - (age_hours * 0.1)
        """
        since = datetime.utcnow() - timedelta(hours=hours)

        # Calcular engagement score en la query
        # En producción esto debería ser un campo calculado o materialized view
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

        result = db.execute(query)
        return result.scalars().all()

    def get_user_mentions(
        self,
        db: Session,
        gym_id: int,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """
        Obtiene posts donde el usuario fue mencionado.
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

        result = db.execute(query)
        return result.scalars().all()

    def count_user_posts(
        self,
        db: Session,
        gym_id: int,
        user_id: int
    ) -> int:
        """
        Cuenta el total de posts de un usuario.
        """
        query = select(func.count(Post.id)).where(
            and_(
                Post.user_id == user_id,
                Post.gym_id == gym_id,
                Post.is_deleted == False
            )
        )

        result = db.execute(query)
        return result.scalar() or 0

    # ============= ASYNC METHODS =============

    async def get_by_location_async(
        self,
        db: AsyncSession,
        gym_id: int,
        location: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """Obtiene posts por ubicación (async)."""
        query = select(Post).where(
            and_(
                Post.gym_id == gym_id,
                Post.location.ilike(f"%{location}%"),
                Post.is_deleted == False,
                Post.privacy == PostPrivacy.PUBLIC
            )
        ).order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_event_async(
        self,
        db: AsyncSession,
        gym_id: int,
        event_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """Obtiene posts etiquetados con un evento específico (async)."""
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
        return result.scalars().all()

    async def get_by_session_async(
        self,
        db: AsyncSession,
        gym_id: int,
        session_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """Obtiene posts etiquetados con una sesión específica (async)."""
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
        return result.scalars().all()

    async def get_trending_async(
        self,
        db: AsyncSession,
        gym_id: int,
        hours: int = 24,
        limit: int = 20
    ) -> List[Post]:
        """Obtiene posts trending (más populares en las últimas X horas) (async)."""
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
        return result.scalars().all()

    async def get_user_mentions_async(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Post]:
        """Obtiene posts donde el usuario fue mencionado (async)."""
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
        return result.scalars().all()

    async def count_user_posts_async(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int
    ) -> int:
        """Cuenta el total de posts de un usuario (async)."""
        query = select(func.count(Post.id)).where(
            and_(
                Post.user_id == user_id,
                Post.gym_id == gym_id,
                Post.is_deleted == False
            )
        )

        result = await db.execute(query)
        return result.scalar() or 0
