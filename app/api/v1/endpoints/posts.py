"""
Endpoints para el sistema de posts.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta, timezone
import json

from app.core.dependencies import module_enabled
from app.db.session import get_db
from app.core.tenant import get_tenant_id
from app.core.auth0_fastapi import get_current_db_user
from app.models.user import User
from app.models.post import Post as PostModel, PostType, PostPrivacy
from app.schemas.post import (
    Post, PostCreate, PostUpdate, PostResponse, PostListResponse, PostFeedResponse,
    PostStatsResponse, PostCreateMultipart,
    RankedPost, RankedFeedResponse, FeedScoreDebug
)
from app.schemas.post_interaction import (
    CommentCreate, CommentUpdate, CommentResponse, CommentsListResponse, CommentCreateResponse,
    LikeToggleResponse, PostLikesListResponse, PostReportCreate, ReportCreateResponse
)
from app.services.post_service import PostService
from app.services.post_interaction_service import PostInteractionService
from app.services.feed_ranking_service import FeedRankingService
from app.repositories.post_repository import PostRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["posts"],
    dependencies=[module_enabled("posts")]
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

        # Crear schema de PostCreate con validación de enums
        try:
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
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Valores inválidos: {str(e)}"
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
        last_update=posts[0]["created_at"] if posts else None
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
        last_update=posts[0]["created_at"] if posts else None
    )


@router.get("/feed/ranked", response_model=RankedFeedResponse)
async def get_ranked_feed(
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user),
    page: int = Query(1, ge=1, description="Número de página (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Posts por página"),
    debug: bool = Query(False, description="Incluir scores de debug"),
    exclude_seen: bool = Query(True, description="Excluir posts ya vistos")
):
    """
    Feed de posts personalizado con ranking inteligente.

    **Algoritmo de 5 señales ponderadas:**
    - Content Affinity (25%): Match con intereses del usuario
    - Social Affinity (25%): Relación con autor
    - Past Engagement (15%): Historial de interacciones
    - Timing (15%): Recency + horarios activos
    - Popularity (20%): Trending + engagement

    **Parámetros:**
    - page: Número de página (default: 1)
    - page_size: Posts por página (max: 100, default: 20)
    - debug: Si true, incluye scores detallados
    - exclude_seen: Si true, excluye posts ya vistos
    """
    # 1. Obtener posts candidatos (últimas 7 días, no borrados)
    offset = (page - 1) * page_size

    query = db.query(PostModel).filter(
        and_(
            PostModel.gym_id == gym_id,
            PostModel.is_deleted == False,
            PostModel.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        )
    )

    # 2. Excluir posts ya vistos
    if exclude_seen:
        from app.models.post_interaction import PostView

        viewed_post_ids_query = db.query(PostView.post_id).filter(
            and_(
                PostView.user_id == db_user.id,
                PostView.gym_id == gym_id,
                PostView.viewed_at >= datetime.now(timezone.utc) - timedelta(days=7)
            )
        ).subquery()

        query = query.filter(~PostModel.id.in_(viewed_post_ids_query))

    # 3. Obtener posts candidatos (tomamos 5x más para rankear)
    # Ej: si pide 20, traemos 100 para rankear y quedarnos con top 20
    candidate_limit = min(page_size * 5, 500)  # Max 500 candidatos
    candidate_posts = query.order_by(PostModel.created_at.desc()).limit(candidate_limit).all()

    if not candidate_posts:
        return RankedFeedResponse(
            posts=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
            algorithm_version="heuristic_v1"
        )

    # 4. Calcular scores para todos los candidatos
    ranking_service = FeedRankingService(db)
    feed_scores = ranking_service.calculate_feed_scores_batch(
        user_id=db_user.id,
        gym_id=gym_id,
        posts=candidate_posts
    )

    # 5. Tomar top posts según paginación
    paginated_scores = feed_scores[offset:offset + page_size]

    # 6. Enriquecer posts con información del usuario
    post_service = PostService(db)
    enriched_posts = []

    for feed_score in paginated_scores:
        # Obtener post original
        post = next((p for p in candidate_posts if p.id == feed_score.post_id), None)
        if not post:
            continue

        # Verificar si el usuario dio like
        from app.models.post_interaction import PostLike
        is_liked = db.query(PostLike).filter(
            and_(
                PostLike.post_id == post.id,
                PostLike.user_id == db_user.id
            )
        ).first() is not None

        # Construir post data
        ranked_post = RankedPost(
            id=post.id,
            user_id=post.user_id,
            post_type=post.post_type,
            caption=post.caption,
            location=post.location,
            privacy=post.privacy,
            media=[
                {
                    "media_url": m.media_url,
                    "thumbnail_url": m.thumbnail_url,
                    "media_type": m.media_type,
                    "display_order": m.display_order
                }
                for m in sorted(post.media, key=lambda x: x.display_order)
            ],
            user_info={
                "id": post.user.id,
                "name": f"{post.user.first_name or ''} {post.user.last_name or ''}".strip() or "Usuario",
                "picture": post.user.picture
            },
            like_count=post.like_count,
            comment_count=post.comment_count,
            view_count=post.view_count,
            is_liked=is_liked,
            created_at=post.created_at,
            score=FeedScoreDebug(
                content_affinity=feed_score.content_affinity,
                social_affinity=feed_score.social_affinity,
                past_engagement=feed_score.past_engagement,
                timing=feed_score.timing,
                popularity=feed_score.popularity,
                final_score=feed_score.final_score
            ) if debug else None
        )

        enriched_posts.append(ranked_post)

    return RankedFeedResponse(
        posts=enriched_posts,
        total=len(feed_scores),
        page=page,
        page_size=page_size,
        has_more=(offset + page_size) < len(feed_scores),
        algorithm_version="heuristic_v1"
    )


@router.get("/feed/location/{location}", response_model=PostListResponse)
async def get_posts_by_location(
    location: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
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

    # Enriquecer posts con user_info
    service = PostService(db)
    enriched_posts = await service._enrich_posts_bulk(posts, db_user.id)

    return PostListResponse(
        posts=enriched_posts,
        total=len(enriched_posts),
        limit=limit,
        offset=offset,
        has_more=len(enriched_posts) == limit,
        next_offset=offset + limit if len(enriched_posts) == limit else None
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


@router.put("/comments/{comment_id}", response_model=CommentResponse)
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
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
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

    # Enriquecer posts con user_info
    service = PostService(db)
    enriched_posts = await service._enrich_posts_bulk(posts, db_user.id)

    return PostListResponse(
        posts=enriched_posts,
        total=len(enriched_posts),
        limit=limit,
        offset=offset,
        has_more=len(enriched_posts) == limit,
        next_offset=offset + limit if len(enriched_posts) == limit else None
    )


@router.get("/sessions/{session_id}", response_model=PostListResponse)
async def get_posts_by_session(
    session_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
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

    # Enriquecer posts con user_info
    service = PostService(db)
    enriched_posts = await service._enrich_posts_bulk(posts, db_user.id)

    return PostListResponse(
        posts=enriched_posts,
        total=len(enriched_posts),
        limit=limit,
        offset=offset,
        has_more=len(enriched_posts) == limit,
        next_offset=offset + limit if len(enriched_posts) == limit else None
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

    # Enriquecer posts con user_info
    service = PostService(db)
    enriched_posts = await service._enrich_posts_bulk(posts, db_user.id)

    return PostListResponse(
        posts=enriched_posts,
        total=len(enriched_posts),
        limit=limit,
        offset=offset,
        has_more=len(enriched_posts) == limit,
        next_offset=offset + limit if len(enriched_posts) == limit else None
    )
