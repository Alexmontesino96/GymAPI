"""
Endpoints para el sistema de posts.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
import json

from app.core.dependencies import get_db, get_current_db_user, get_tenant_id, module_enabled
from app.models.user import User
from app.models.post import Post, PostType, PostPrivacy
from app.schemas.post import (
    PostCreate, PostUpdate, PostResponse, PostListResponse, PostFeedResponse,
    PostStatsResponse, PostCreateMultipart
)
from app.schemas.post_interaction import (
    CommentCreate, CommentUpdate, CommentsListResponse, CommentCreateResponse,
    LikeToggleResponse, PostLikesListResponse, PostReportCreate, ReportCreateResponse
)
from app.services.post_service import PostService
from app.services.post_interaction_service import PostInteractionService
from app.repositories.post_repository import PostRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/posts",
    tags=["posts"],
    dependencies=[Depends(module_enabled("posts"))]
)


# ==================== POSTS CRUD ====================

@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    caption: Optional[str] = Form(None),
    post_type: str = Form("single_image"),
    privacy: str = Form("public"),
    location: Optional[str] = Form(None),
    workout_data_json: Optional[str] = Form(None),
    tagged_event_id: Optional[int] = Form(None),
    tagged_session_id: Optional[int] = Form(None),
    mentioned_user_ids_json: Optional[str] = Form(None),
    files: List[UploadFile] = File(None),
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Crea un nuevo post con archivos de media opcionales.

    Soporta:
    - Imagen única
    - Galería (hasta 10 imágenes/videos)
    - Posts de workout con datos
    """
    try:
        # Parsear workout_data si está presente
        workout_data = None
        if workout_data_json:
            try:
                workout_data = json.loads(workout_data_json)
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="workout_data_json debe ser un JSON válido"
                )

        # Parsear mentioned_user_ids si está presente
        mentioned_user_ids = None
        if mentioned_user_ids_json:
            try:
                mentioned_user_ids = json.loads(mentioned_user_ids_json)
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="mentioned_user_ids_json debe ser un JSON array válido"
                )

        # Crear schema de PostCreate
        post_data = PostCreate(
            caption=caption,
            post_type=PostType(post_type),
            privacy=PostPrivacy(privacy),
            location=location,
            workout_data=workout_data,
            tagged_event_id=tagged_event_id,
            tagged_session_id=tagged_session_id,
            mentioned_user_ids=mentioned_user_ids
        )

        service = PostService(db)
        post = await service.create_post(
            gym_id=gym_id,
            user_id=db_user.id,
            post_data=post_data,
            media_files=files if files else None
        )

        return PostResponse(success=True, post=post)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{post_id}", response_model=Post)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtiene un post por ID.
    """
    service = PostService(db)
    return await service.get_post_by_id(post_id, gym_id, db_user.id)


@router.get("/user/{user_id}", response_model=PostListResponse)
async def get_user_posts(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtiene los posts de un usuario específico.
    """
    service = PostService(db)
    posts = await service.get_user_posts(
        target_user_id=user_id,
        gym_id=gym_id,
        requesting_user_id=db_user.id,
        limit=limit,
        offset=offset
    )

    total = len(posts)  # TODO: Implementar count real
    has_more = len(posts) == limit

    return PostListResponse(
        posts=posts,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_offset=offset + limit if has_more else None
    )


@router.put("/{post_id}", response_model=Post)
async def update_post(
    post_id: int,
    update_data: PostUpdate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Actualiza un post (solo caption y location son editables).
    """
    service = PostService(db)
    return await service.update_post(
        post_id=post_id,
        gym_id=gym_id,
        user_id=db_user.id,
        update_data=update_data
    )


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Elimina un post.
    """
    service = PostService(db)
    await service.delete_post(post_id, gym_id, db_user.id)
    return None


# ==================== FEEDS ====================

@router.get("/feed/timeline", response_model=PostFeedResponse)
async def get_timeline_feed(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtiene el feed principal (timeline cronológico).
    """
    service = PostService(db)
    posts = await service.get_gym_posts(
        gym_id=gym_id,
        user_id=db_user.id,
        limit=limit,
        offset=offset,
        feed_type="timeline"
    )

    return PostFeedResponse(
        posts=posts,
        total_posts=len(posts),
        feed_type="timeline",
        has_more=len(posts) == limit,
        next_offset=offset + limit if len(posts) == limit else None,
        last_update=posts[0].created_at if posts else None
    )


@router.get("/feed/explore", response_model=PostFeedResponse)
async def get_explore_feed(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtiene el feed de exploración (posts más populares).
    """
    service = PostService(db)
    posts = await service.get_gym_posts(
        gym_id=gym_id,
        user_id=db_user.id,
        limit=limit,
        offset=offset,
        feed_type="explore"
    )

    return PostFeedResponse(
        posts=posts,
        total_posts=len(posts),
        feed_type="explore",
        has_more=len(posts) == limit,
        next_offset=offset + limit if len(posts) == limit else None,
        last_update=posts[0].created_at if posts else None
    )


@router.get("/feed/location/{location}", response_model=PostListResponse)
async def get_posts_by_location(
    location: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Obtiene posts por ubicación.
    """
    repo = PostRepository()
    posts = repo.get_by_location(
        db=db,
        gym_id=gym_id,
        location=location,
        limit=limit,
        offset=offset
    )

    return PostListResponse(
        posts=posts,
        total=len(posts),
        limit=limit,
        offset=offset,
        has_more=len(posts) == limit,
        next_offset=offset + limit if len(posts) == limit else None
    )


# ==================== LIKES ====================

@router.post("/{post_id}/like", response_model=LikeToggleResponse)
async def toggle_post_like(
    post_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Toggle like/unlike en un post.
    """
    service = PostInteractionService(db)
    result = await service.toggle_like(
        post_id=post_id,
        gym_id=gym_id,
        user_id=db_user.id
    )

    return LikeToggleResponse(
        success=True,
        action=result["action"],
        total_likes=result["total_likes"],
        message=f"Post {'liked' if result['action'] == 'liked' else 'unliked'} exitosamente"
    )


@router.get("/{post_id}/likes", response_model=PostLikesListResponse)
async def get_post_likes(
    post_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Obtiene la lista de likes de un post.
    """
    service = PostInteractionService(db)
    likes = await service.get_post_likes(
        post_id=post_id,
        gym_id=gym_id,
        limit=limit,
        offset=offset
    )

    return PostLikesListResponse(
        likes=likes,
        total=len(likes),
        limit=limit,
        offset=offset,
        has_more=len(likes) == limit
    )


# ==================== COMMENTS ====================

@router.post("/{post_id}/comment", response_model=CommentCreateResponse)
async def add_comment(
    post_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Agrega un comentario a un post.
    """
    service = PostInteractionService(db)
    comment = await service.add_comment(
        post_id=post_id,
        gym_id=gym_id,
        user_id=db_user.id,
        comment_data=comment_data
    )

    return CommentCreateResponse(
        success=True,
        comment=comment
    )


@router.get("/{post_id}/comments", response_model=CommentsListResponse)
async def get_post_comments(
    post_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Obtiene los comentarios de un post.
    """
    service = PostInteractionService(db)
    comments = await service.get_post_comments(
        post_id=post_id,
        gym_id=gym_id,
        limit=limit,
        offset=offset
    )

    return CommentsListResponse(
        comments=comments,
        total=len(comments),
        limit=limit,
        offset=offset,
        has_more=len(comments) == limit
    )


@router.put("/comments/{comment_id}", response_model=Post)
async def update_comment(
    comment_id: int,
    update_data: CommentUpdate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Actualiza un comentario.
    """
    service = PostInteractionService(db)
    return await service.update_comment(
        comment_id=comment_id,
        gym_id=gym_id,
        user_id=db_user.id,
        update_data=update_data
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Elimina un comentario.
    """
    service = PostInteractionService(db)
    await service.delete_comment(
        comment_id=comment_id,
        gym_id=gym_id,
        user_id=db_user.id
    )
    return None


@router.post("/comments/{comment_id}/like", response_model=LikeToggleResponse)
async def toggle_comment_like(
    comment_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Toggle like/unlike en un comentario.
    """
    service = PostInteractionService(db)
    result = await service.toggle_comment_like(
        comment_id=comment_id,
        gym_id=gym_id,
        user_id=db_user.id
    )

    return LikeToggleResponse(
        success=True,
        action=result["action"],
        total_likes=result["total_likes"],
        message=f"Comentario {'liked' if result['action'] == 'liked' else 'unliked'}"
    )


# ==================== REPORTS ====================

@router.post("/{post_id}/report", response_model=ReportCreateResponse)
async def report_post(
    post_id: int,
    report_data: PostReportCreate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Reporta un post inapropiado.
    """
    service = PostInteractionService(db)
    report = await service.report_post(
        post_id=post_id,
        gym_id=gym_id,
        user_id=db_user.id,
        report_data=report_data
    )

    return ReportCreateResponse(
        success=True,
        report_id=report.id
    )


# ==================== TAGS ====================

@router.get("/events/{event_id}", response_model=PostListResponse)
async def get_posts_by_event(
    event_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Obtiene posts etiquetados con un evento específico.
    """
    repo = PostRepository()
    posts = repo.get_by_event(
        db=db,
        gym_id=gym_id,
        event_id=event_id,
        limit=limit,
        offset=offset
    )

    return PostListResponse(
        posts=posts,
        total=len(posts),
        limit=limit,
        offset=offset,
        has_more=len(posts) == limit,
        next_offset=offset + limit if len(posts) == limit else None
    )


@router.get("/sessions/{session_id}", response_model=PostListResponse)
async def get_posts_by_session(
    session_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Obtiene posts etiquetados con una sesión/clase específica.
    """
    repo = PostRepository()
    posts = repo.get_by_session(
        db=db,
        gym_id=gym_id,
        session_id=session_id,
        limit=limit,
        offset=offset
    )

    return PostListResponse(
        posts=posts,
        total=len(posts),
        limit=limit,
        offset=offset,
        has_more=len(posts) == limit,
        next_offset=offset + limit if len(posts) == limit else None
    )


@router.get("/mentions/me", response_model=PostListResponse)
async def get_my_mentions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtiene posts donde fui mencionado.
    """
    repo = PostRepository()
    posts = repo.get_user_mentions(
        db=db,
        gym_id=gym_id,
        user_id=db_user.id,
        limit=limit,
        offset=offset
    )

    return PostListResponse(
        posts=posts,
        total=len(posts),
        limit=limit,
        offset=offset,
        has_more=len(posts) == limit,
        next_offset=offset + limit if len(posts) == limit else None
    )
