"""
AsyncPostInteractionService - Servicio async para interacciones con posts.

Este módulo proporciona un servicio totalmente async para gestión de likes, comentarios
y reportes en posts del gimnasio.

Migrado en FASE 3 de la conversión sync → async.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update as sql_update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.post import Post
from app.models.post_interaction import (
    PostLike, PostComment, PostCommentLike, PostReport, ReportReason
)
from app.models.user import User
from app.schemas.post_interaction import CommentCreate, CommentUpdate, PostReportCreate

logger = logging.getLogger(__name__)


class AsyncPostInteractionService:
    """
    Servicio async para gestionar interacciones con posts.

    Todos los métodos son async y utilizan AsyncSession.

    Interacciones soportadas:
    - Likes en posts (toggle like/unlike)
    - Comentarios en posts (CRUD)
    - Likes en comentarios (toggle)
    - Reportes de posts (spam, harassment, etc.)

    Métodos principales:
    - toggle_like() - Like/unlike en post con contador atómico
    - get_post_likes() - Listar usuarios que dieron like
    - add_comment() - Agregar comentario a post
    - update_comment() - Editar comentario (solo owner)
    - delete_comment() - Soft delete (owner o admin)
    - get_post_comments() - Listar comentarios del post
    - toggle_comment_like() - Like/unlike en comentario
    - report_post() - Reportar contenido inapropiado
    """

    async def toggle_like(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Toggle like/unlike en un post.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            Dict con action ('liked' o 'unliked') y total_likes

        Note:
            - Idempotente: múltiples calls con mismo user_id no crean duplicados
            - Actualiza contador like_count atómicamente
            - Protegido contra race conditions con IntegrityError handling
        """
        # Verificar que el post existe
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

        # Verificar si ya existe un like
        result = await db.execute(
            select(PostLike).where(
                and_(
                    PostLike.post_id == post_id,
                    PostLike.user_id == user_id
                )
            )
        )
        existing_like = result.scalar_one_or_none()

        if existing_like:
            # Unlike - eliminar like
            await db.delete(existing_like)

            # Decrementar contador atómicamente
            await db.execute(
                sql_update(Post)
                .where(Post.id == post_id)
                .values(like_count=Post.like_count - 1)
            )

            await db.commit()

            # Obtener nuevo total
            await db.refresh(post)

            return {
                "action": "unliked",
                "total_likes": post.like_count
            }
        else:
            # Like - crear nuevo like
            try:
                new_like = PostLike(
                    post_id=post_id,
                    user_id=user_id,
                    gym_id=gym_id
                )
                db.add(new_like)

                # Incrementar contador atómicamente
                await db.execute(
                    sql_update(Post)
                    .where(Post.id == post_id)
                    .values(like_count=Post.like_count + 1)
                )

                await db.commit()
            except IntegrityError:
                # Carrera: ya existe like por constraint único
                await db.rollback()
            finally:
                # Obtener total actualizado
                await db.refresh(post)

            return {"action": "liked", "total_likes": post.like_count}

    async def get_post_likes(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[PostLike]:
        """
        Obtiene la lista de likes de un post.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            limit: Número máximo de likes
            offset: Offset para paginación

        Returns:
            Lista de likes ordenados por fecha descendente

        Raises:
            HTTPException: Si el post no existe
        """
        # Verificar que el post existe
        result = await db.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()

        if not post or post.gym_id != gym_id or post.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )

        query = select(PostLike).where(
            PostLike.post_id == post_id
        ).order_by(PostLike.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        return result.scalars().all()

    async def add_comment(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        user_id: int,
        comment_data: CommentCreate
    ) -> PostComment:
        """
        Agrega un comentario a un post.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que comenta
            comment_data: Datos del comentario

        Returns:
            Comentario creado

        Raises:
            HTTPException: Si el post no existe

        Note:
            - Actualiza contador comment_count automáticamente
            - TODO: Notificar al dueño del post
            - TODO: Notificar usuarios mencionados (@username)
        """
        # Verificar que el post existe
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

        # Crear comentario
        comment = PostComment(
            post_id=post_id,
            user_id=user_id,
            gym_id=gym_id,
            comment_text=comment_data.comment_text,
            like_count=0
        )

        db.add(comment)

        # Incrementar contador de comentarios atómicamente
        await db.execute(
            sql_update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1)
        )

        await db.commit()
        await db.refresh(comment)

        # TODO: Notificar al dueño del post
        # TODO: Notificar usuarios mencionados en el comentario

        logger.info(f"Comment added to post {post_id} by user {user_id}")
        return comment

    async def update_comment(
        self,
        db: AsyncSession,
        comment_id: int,
        gym_id: int,
        user_id: int,
        update_data: CommentUpdate
    ) -> PostComment:
        """
        Actualiza un comentario (solo propietario).

        Args:
            db: Sesión async de base de datos
            comment_id: ID del comentario
            gym_id: ID del gimnasio
            user_id: ID del usuario que edita
            update_data: Datos a actualizar

        Returns:
            Comentario actualizado

        Raises:
            HTTPException: Si el comentario no existe o no tiene permiso

        Note:
            Marca automáticamente is_edited=True y establece edited_at.
        """
        result = await db.execute(
            select(PostComment).where(
                and_(
                    PostComment.id == comment_id,
                    PostComment.gym_id == gym_id,
                    PostComment.is_deleted == False
                )
            )
        )
        comment = result.scalar_one_or_none()

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
        comment.edited_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(comment)

        logger.info(f"Comment {comment_id} updated by user {user_id}")
        return comment

    async def delete_comment(
        self,
        db: AsyncSession,
        comment_id: int,
        gym_id: int,
        user_id: int,
        is_admin: bool = False
    ) -> bool:
        """
        Elimina un comentario (soft delete).

        Args:
            db: Sesión async de base de datos
            comment_id: ID del comentario
            gym_id: ID del gimnasio
            user_id: ID del usuario que elimina
            is_admin: Si el usuario es admin (puede eliminar cualquier comentario)

        Returns:
            True si se eliminó exitosamente

        Raises:
            HTTPException: Si el comentario no existe o no tiene permiso

        Note:
            - Owner puede eliminar su comentario
            - Admin puede eliminar cualquier comentario
            - Actualiza contador comment_count automáticamente
        """
        result = await db.execute(
            select(PostComment).where(
                and_(
                    PostComment.id == comment_id,
                    PostComment.gym_id == gym_id,
                    PostComment.is_deleted == False
                )
            )
        )
        comment = result.scalar_one_or_none()

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
        comment.deleted_at = datetime.now(timezone.utc)

        # Decrementar contador de comentarios
        await db.execute(
            sql_update(Post)
            .where(Post.id == comment.post_id)
            .values(comment_count=Post.comment_count - 1)
        )

        await db.commit()

        logger.info(f"Comment {comment_id} deleted by user {user_id}")
        return True

    async def get_post_comments(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[PostComment]:
        """
        Obtiene los comentarios de un post.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            limit: Número máximo de comentarios
            offset: Offset para paginación

        Returns:
            Lista de comentarios ordenados por fecha descendente

        Raises:
            HTTPException: Si el post no existe
        """
        # Verificar que el post existe
        result = await db.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()

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

        result = await db.execute(query)
        return result.scalars().all()

    async def toggle_comment_like(
        self,
        db: AsyncSession,
        comment_id: int,
        gym_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Toggle like/unlike en un comentario.

        Args:
            db: Sesión async de base de datos
            comment_id: ID del comentario
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Returns:
            Dict con action ('liked' o 'unliked') y total_likes

        Raises:
            HTTPException: Si el comentario no existe

        Note:
            Similar a toggle_like de posts pero para comentarios.
            Actualiza contador like_count atómicamente.
        """
        # Verificar que el comentario existe
        result = await db.execute(
            select(PostComment).where(
                and_(
                    PostComment.id == comment_id,
                    PostComment.gym_id == gym_id,
                    PostComment.is_deleted == False
                )
            )
        )
        comment = result.scalar_one_or_none()

        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )

        # Verificar si ya existe un like
        result = await db.execute(
            select(PostCommentLike).where(
                and_(
                    PostCommentLike.comment_id == comment_id,
                    PostCommentLike.user_id == user_id
                )
            )
        )
        existing_like = result.scalar_one_or_none()

        if existing_like:
            # Unlike
            await db.delete(existing_like)

            # Decrementar contador
            await db.execute(
                sql_update(PostComment)
                .where(PostComment.id == comment_id)
                .values(like_count=PostComment.like_count - 1)
            )

            await db.commit()
            await db.refresh(comment)

            return {
                "action": "unliked",
                "total_likes": comment.like_count
            }
        else:
            # Like
            try:
                new_like = PostCommentLike(
                    comment_id=comment_id,
                    user_id=user_id
                )
                db.add(new_like)

                # Incrementar contador
                await db.execute(
                    sql_update(PostComment)
                    .where(PostComment.id == comment_id)
                    .values(like_count=PostComment.like_count + 1)
                )

                await db.commit()
            except IntegrityError:
                await db.rollback()
            finally:
                await db.refresh(comment)

            return {"action": "liked", "total_likes": comment.like_count}

    async def report_post(
        self,
        db: AsyncSession,
        post_id: int,
        gym_id: int,
        user_id: int,
        report_data: PostReportCreate
    ) -> PostReport:
        """
        Reporta un post por contenido inapropiado.

        Args:
            db: Sesión async de base de datos
            post_id: ID del post
            gym_id: ID del gimnasio
            user_id: ID del usuario que reporta
            report_data: Datos del reporte (reason, description)

        Returns:
            Reporte creado

        Raises:
            HTTPException: Si intenta reportar su propio post o ya reportó

        Note:
            - No se puede reportar el propio post
            - Un usuario solo puede reportar un post una vez
            - TODO: Notificar a admins del gimnasio
        """
        # Verificar que el post existe
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

        # No se puede reportar el propio post
        if post.user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes reportar tu propio post"
            )

        # Verificar si ya existe un reporte del mismo usuario
        result = await db.execute(
            select(PostReport).where(
                and_(
                    PostReport.post_id == post_id,
                    PostReport.reporter_id == user_id
                )
            )
        )
        existing_report = result.scalar_one_or_none()

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

        db.add(report)
        await db.commit()
        await db.refresh(report)

        # TODO: Notificar a admins

        logger.warning(f"Post {post_id} reported by user {user_id} for {report_data.reason}")
        return report


# Instancia singleton del servicio async
async_post_interaction_service = AsyncPostInteractionService()
