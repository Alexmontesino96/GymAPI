"""
Servicio para gestionar interacciones con posts (likes, comentarios, reportes).
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, update as sql_update, delete as sql_delete
from fastapi import HTTPException, status

from app.models.post import Post
from app.models.post_interaction import (
    PostLike, PostComment, PostCommentLike, PostReport, ReportReason
)
from app.models.user import User
from app.schemas.post_interaction import CommentCreate, CommentUpdate, PostReportCreate

logger = logging.getLogger(__name__)


class PostInteractionService:
    """
    Servicio para gestionar interacciones con posts.
    """

    def __init__(self, db: Session):
        self.db = db

    async def toggle_like(
        self,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Toggle like/unlike en un post.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            Dict con action ('liked' o 'unliked') y total de likes
        """
        # Verificar que el post existe
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

        # Verificar si ya existe un like
        existing_like = self.db.execute(
            select(PostLike).where(
                and_(
                    PostLike.post_id == post_id,
                    PostLike.user_id == user_id
                )
            )
        ).scalar_one_or_none()

        if existing_like:
            # Unlike - eliminar like
            self.db.delete(existing_like)

            # Decrementar contador atómicamente
            self.db.execute(
                sql_update(Post)
                .where(Post.id == post_id)
                .values(like_count=Post.like_count - 1)
            )

            self.db.commit()

            # Obtener nuevo total
            self.db.refresh(post)

            return {
                "action": "unliked",
                "total_likes": post.like_count
            }
        else:
            # Like - crear nuevo like
            new_like = PostLike(
                post_id=post_id,
                user_id=user_id,
                gym_id=gym_id
            )
            self.db.add(new_like)

            # Incrementar contador atómicamente
            self.db.execute(
                sql_update(Post)
                .where(Post.id == post_id)
                .values(like_count=Post.like_count + 1)
            )

            self.db.commit()

            # Obtener nuevo total
            self.db.refresh(post)

            # TODO: Notificar al dueño del post

            return {
                "action": "liked",
                "total_likes": post.like_count
            }

    async def get_post_likes(
        self,
        post_id: int,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[PostLike]:
        """
        Obtiene la lista de likes de un post.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            limit: Número máximo de likes
            offset: Offset para paginación

        Returns:
            Lista de likes
        """
        # Verificar que el post existe
        post = self.db.get(Post, post_id)
        if not post or post.gym_id != gym_id or post.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )

        query = select(PostLike).where(
            PostLike.post_id == post_id
        ).order_by(PostLike.created_at.desc()).limit(limit).offset(offset)

        result = self.db.execute(query)
        return result.scalars().all()

    async def add_comment(
        self,
        post_id: int,
        gym_id: int,
        user_id: int,
        comment_data: CommentCreate
    ) -> PostComment:
        """
        Agrega un comentario a un post.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que comenta
            comment_data: Datos del comentario

        Returns:
            Comentario creado
        """
        # Verificar que el post existe
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

        # Crear comentario
        comment = PostComment(
            post_id=post_id,
            user_id=user_id,
            gym_id=gym_id,
            comment_text=comment_data.comment_text,
            like_count=0
        )

        self.db.add(comment)

        # Incrementar contador de comentarios atómicamente
        self.db.execute(
            sql_update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1)
        )

        self.db.commit()
        self.db.refresh(comment)

        # TODO: Notificar al dueño del post
        # TODO: Notificar usuarios mencionados en el comentario

        logger.info(f"Comment added to post {post_id} by user {user_id}")
        return comment

    async def update_comment(
        self,
        comment_id: int,
        gym_id: int,
        user_id: int,
        update_data: CommentUpdate
    ) -> PostComment:
        """
        Actualiza un comentario.

        Args:
            comment_id: ID del comentario
            gym_id: ID del gimnasio
            user_id: ID del usuario que edita
            update_data: Datos a actualizar

        Returns:
            Comentario actualizado
        """
        comment = self.db.execute(
            select(PostComment).where(
                and_(
                    PostComment.id == comment_id,
                    PostComment.gym_id == gym_id,
                    PostComment.is_deleted == False
                )
            )
        ).scalar_one_or_none()

        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )

        # Verificar ownership
        if comment.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para editar este comentario"
            )

        # Actualizar texto
        comment.comment_text = update_data.comment_text
        comment.is_edited = True
        comment.edited_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(comment)

        logger.info(f"Comment {comment_id} updated by user {user_id}")
        return comment

    async def delete_comment(
        self,
        comment_id: int,
        gym_id: int,
        user_id: int,
        is_admin: bool = False
    ) -> bool:
        """
        Elimina un comentario (soft delete).

        Args:
            comment_id: ID del comentario
            gym_id: ID del gimnasio
            user_id: ID del usuario que elimina
            is_admin: Si el usuario es admin

        Returns:
            True si se eliminó exitosamente
        """
        comment = self.db.execute(
            select(PostComment).where(
                and_(
                    PostComment.id == comment_id,
                    PostComment.gym_id == gym_id,
                    PostComment.is_deleted == False
                )
            )
        ).scalar_one_or_none()

        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )

        # Verificar permisos (owner o admin)
        if comment.user_id != user_id and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar este comentario"
            )

        # Soft delete
        comment.is_deleted = True
        comment.deleted_at = datetime.utcnow()

        # Decrementar contador de comentarios
        self.db.execute(
            sql_update(Post)
            .where(Post.id == comment.post_id)
            .values(comment_count=Post.comment_count - 1)
        )

        self.db.commit()

        logger.info(f"Comment {comment_id} deleted by user {user_id}")
        return True

    async def get_post_comments(
        self,
        post_id: int,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[PostComment]:
        """
        Obtiene los comentarios de un post.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            limit: Número máximo de comentarios
            offset: Offset para paginación

        Returns:
            Lista de comentarios
        """
        # Verificar que el post existe
        post = self.db.get(Post, post_id)
        if not post or post.gym_id != gym_id or post.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )

        query = select(PostComment).where(
            and_(
                PostComment.post_id == post_id,
                PostComment.is_deleted == False
            )
        ).order_by(PostComment.created_at.desc()).limit(limit).offset(offset)

        result = self.db.execute(query)
        return result.scalars().all()

    async def toggle_comment_like(
        self,
        comment_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Toggle like/unlike en un comentario.

        Args:
            comment_id: ID del comentario
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            Dict con action y total de likes
        """
        # Verificar que el comentario existe
        comment = self.db.execute(
            select(PostComment).where(
                and_(
                    PostComment.id == comment_id,
                    PostComment.gym_id == gym_id,
                    PostComment.is_deleted == False
                )
            )
        ).scalar_one_or_none()

        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )

        # Verificar si ya existe un like
        existing_like = self.db.execute(
            select(PostCommentLike).where(
                and_(
                    PostCommentLike.comment_id == comment_id,
                    PostCommentLike.user_id == user_id
                )
            )
        ).scalar_one_or_none()

        if existing_like:
            # Unlike
            self.db.delete(existing_like)

            # Decrementar contador
            self.db.execute(
                sql_update(PostComment)
                .where(PostComment.id == comment_id)
                .values(like_count=PostComment.like_count - 1)
            )

            self.db.commit()
            self.db.refresh(comment)

            return {
                "action": "unliked",
                "total_likes": comment.like_count
            }
        else:
            # Like
            new_like = PostCommentLike(
                comment_id=comment_id,
                user_id=user_id
            )
            self.db.add(new_like)

            # Incrementar contador
            self.db.execute(
                sql_update(PostComment)
                .where(PostComment.id == comment_id)
                .values(like_count=PostComment.like_count + 1)
            )

            self.db.commit()
            self.db.refresh(comment)

            return {
                "action": "liked",
                "total_likes": comment.like_count
            }

    async def report_post(
        self,
        post_id: int,
        gym_id: int,
        user_id: int,
        report_data: PostReportCreate
    ) -> PostReport:
        """
        Reporta un post.

        Args:
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que reporta
            report_data: Datos del reporte

        Returns:
            Reporte creado
        """
        # Verificar que el post existe
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

        # No se puede reportar el propio post
        if post.user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes reportar tu propio post"
            )

        # Verificar si ya existe un reporte del mismo usuario
        existing_report = self.db.execute(
            select(PostReport).where(
                and_(
                    PostReport.post_id == post_id,
                    PostReport.reporter_id == user_id
                )
            )
        ).scalar_one_or_none()

        if existing_report:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya has reportado este post"
            )

        # Crear reporte
        report = PostReport(
            post_id=post_id,
            reporter_id=user_id,
            reason=report_data.reason,
            description=report_data.description
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # TODO: Notificar a admins

        logger.warning(f"Post {post_id} reported by user {user_id} for {report_data.reason}")
        return report
