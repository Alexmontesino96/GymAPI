"""
Endpoints de API para el sistema de historias.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.dependencies import (
    module_enabled
)
from app.db.session import get_db
from app.core.tenant import get_tenant_id
from app.core.auth0_fastapi import get_current_user, get_current_db_user, Auth0User
from app.models.user import User
from app.services.story_service import StoryService
from app.services.media_service import get_media_service
from app.schemas.story import (
    StoryCreate,
    StoryResponse,
    StoryUpdate,
    StoryListResponse,
    StoryViewCreate,
    StoryReactionCreate,
    StoryReactionResponse,
    StoryReportCreate,
    StoryHighlightCreate,
    StoryHighlightUpdate,
    StoryFeedResponse,
    StoryViewerResponse
)

router = APIRouter(
    tags=["stories"],
    dependencies=[module_enabled("stories")]
)


@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    story_type: str = Form(...),
    caption: Optional[str] = Form(None, max_length=500),
    privacy: str = Form("public"),
    duration_hours: int = Form(24, ge=1, le=48),
    workout_data: Optional[str] = Form(None),  # JSON string
    media_url: Optional[str] = Form(None),
    media: Optional[UploadFile] = File(None),
    current_user: Auth0User = Depends(get_current_user),
    db_user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Crear una nueva historia.

    - **caption**: Texto o caption de la historia
    - **story_type**: Tipo de historia (image, video, text, workout, achievement)
    - **privacy**: Nivel de privacidad (public, followers, close_friends, private)
    - **duration_hours**: Duración antes de expirar (1-48 horas)
    - **workout_data**: JSON con datos del entrenamiento (para tipo workout)
    - **media**: Archivo de imagen/video a subir
    - **media_url**: URL de media ya subida (alternativo a media)
    """
# Procesar media si se proporciona
    processed_media_url = media_url
    thumbnail_url = None

    if media:
        # Determinar tipo de media basado en content_type
        media_type = "video" if media.content_type.startswith("video/") else "image"

        # Subir media usando MediaService
        media_service = get_media_service()
        media_result = await media_service.upload_story_media(
            gym_id=gym_id,
            user_id=db_user.id,  # Usar ID numérico de BD, no Auth0 ID
            file=media,
            media_type=media_type
        )

        processed_media_url = media_result.get("media_url")
        thumbnail_url = media_result.get("thumbnail_url")

    # Parsear workout_data si es string JSON
    import json
    parsed_workout_data = None
    if workout_data:
        try:
            parsed_workout_data = json.loads(workout_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workout_data debe ser un JSON válido"
            )

    # Crear datos de la historia
    story_data = StoryCreate(
        caption=caption,
        story_type=story_type,
        privacy=privacy,
        media_url=processed_media_url,
        workout_data=parsed_workout_data,
        duration_hours=duration_hours
    )

    # Crear historia usando el servicio
    service = StoryService(db)
    story = await service.create_story(
        gym_id=gym_id,
        user_id=db_user.id,  # Usar ID numérico de BD
        story_data=story_data
    )

    # Agregar campos adicionales para la respuesta
    return StoryResponse(
        **story.__dict__,
        is_expired=story.is_expired,
        is_own_story=True,
        has_viewed=False,
        has_reacted=False,
        user_info={
            "id": db_user.id,
            "name": f"{db_user.first_name} {db_user.last_name}" if db_user.first_name else db_user.email,
            "avatar": db_user.picture
        }
    )


@router.get("/feed", response_model=StoryFeedResponse)
async def get_stories_feed(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    filter_type: Optional[str] = Query(None, regex="^(all|following|close_friends)$"),
    story_types: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)  # Usar db_user en vez de current_user
):
    """
    Obtener el feed de historias del usuario.

    - **limit**: Número de historias por página
    - **offset**: Offset para paginación
    - **filter_type**: Filtrar por tipo (all, following, close_friends)
    - **story_types**: Filtrar por tipos de historia específicos
    """
    service = StoryService(db)
    feed = await service.get_stories_feed(
        gym_id=gym_id,
        user_id=db_user.id,  # ID numérico de BD
        limit=limit,
        offset=offset,
        filter_type=filter_type
    )

    return StoryFeedResponse(**feed)


@router.get("/user/{user_id}", response_model=StoryListResponse)
async def get_user_stories(
    user_id: int,
    include_expired: bool = Query(False),
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)  # Usar db_user
):
    """
    Obtener las historias de un usuario específico.

    - **user_id**: ID del usuario
    - **include_expired**: Incluir historias expiradas (solo para propias historias)
    """
    # Solo el propio usuario puede ver sus historias expiradas
    if include_expired and user_id != db_user.id:
        include_expired = False

    service = StoryService(db)
    stories = await service.get_user_stories(
        target_user_id=user_id,
        gym_id=gym_id,
        requesting_user_id=db_user.id,  # ID numérico
        include_expired=include_expired
    )

    # Convertir a respuesta
    story_responses = []
    for story in stories:
        # Obtener información del usuario
        story_user = db.get(User, story.user_id)

        story_responses.append(StoryResponse(
            **story.__dict__,
            is_expired=story.is_expired,
            is_own_story=(story.user_id == db_user.id),
            has_viewed=await service._has_viewed_story(story.id, db_user.id),  # ID numérico
            has_reacted=False,  # TODO: Implementar verificación de reacción
            user_info={
                "id": story_user.id if story_user else user_id,
                "name": f"{story_user.first_name} {story_user.last_name}" if story_user else "Usuario",
                "avatar": story_user.picture if story_user else None
            }
        ))

    return StoryListResponse(
        stories=story_responses,
        total=len(story_responses),
        has_more=False,
        next_offset=None
    )


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtener una historia específica por ID.
    """
    service = StoryService(db)
    story = await service.get_story_by_id(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id  # ID numérico
    )

    # Obtener información del usuario
    story_user = db.get(User, story.user_id)

    return StoryResponse(
        **story.__dict__,
        is_expired=story.is_expired,
        is_own_story=(story.user_id == db_user.id),
        has_viewed=await service._has_viewed_story(story.id, db_user.id),  # ID numérico
        has_reacted=False,  # TODO: Implementar verificación
        user_info={
            "id": story_user.id if story_user else story.user_id,
            "name": f"{story_user.first_name} {story_user.last_name}" if story_user else "Usuario",
            "avatar": story_user.picture if story_user else None
        }
    )


@router.post("/{story_id}/view")
async def mark_story_viewed(
    story_id: int,
    view_data: Optional[StoryViewCreate] = None,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Marcar una historia como vista.
    """
    service = StoryService(db)
    await service.mark_story_as_viewed(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id,  # ID numérico
        view_data=view_data
    )

    return {"success": True, "message": "Historia marcada como vista"}


@router.get("/{story_id}/viewers", response_model=List[StoryViewerResponse])
async def get_story_viewers(
    story_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Obtener la lista de usuarios que vieron una historia.
    Solo el dueño de la historia puede ver esta información.
    """
    service = StoryService(db)
    story = await service.get_story_by_id(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id  # ID numérico
    )

    # Solo el dueño puede ver quién vio su historia
    if story.user_id != db_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta información"
        )

    # Obtener vistas de la historia
    viewers = []
    for view in story.views:
        viewer = db.get(User, view.viewer_id)
        if viewer:
            viewers.append(StoryViewerResponse(
                viewer_id=viewer.id,
                viewer_name=f"{viewer.first_name} {viewer.last_name}",
                viewer_avatar=viewer.picture,
                viewed_at=view.viewed_at,
                view_duration_seconds=view.view_duration_seconds
            ))

    return viewers


@router.post("/{story_id}/reaction", response_model=StoryReactionResponse)
async def add_story_reaction(
    story_id: int,
    reaction_data: StoryReactionCreate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Agregar una reacción a una historia.
    """
    service = StoryService(db)
    reaction = await service.add_reaction(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id,
        reaction_data=reaction_data
    )

    return StoryReactionResponse(
        success=True,
        reaction_id=reaction.id,
        message="Reacción agregada exitosamente"
    )


@router.delete("/{story_id}")
async def delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Eliminar una historia (solo el dueño puede eliminar).
    """
    service = StoryService(db)
    await service.delete_story(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id
    )

    return {"success": True, "message": "Historia eliminada exitosamente"}


@router.put("/{story_id}", response_model=StoryResponse)
async def update_story(
    story_id: int,
    story_update: StoryUpdate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Actualizar una historia (solo caption y privacidad).
    """
    service = StoryService(db)
    story = await service.get_story_by_id(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id
    )

    # Solo el dueño puede actualizar
    if story.user_id != db_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar esta historia"
        )

    # Actualizar campos permitidos
    if story_update.caption is not None:
        story.caption = story_update.caption
    if story_update.privacy is not None:
        story.privacy = story_update.privacy

    db.commit()
    db.refresh(story)

    # Obtener información del usuario
    story_user = db.get(User, story.user_id)

    return StoryResponse(
        **story.__dict__,
        is_expired=story.is_expired,
        is_own_story=True,
        has_viewed=False,
        has_reacted=False,
        user_info={
            "id": story_user.id if story_user else story.user_id,
            "name": f"{story_user.first_name} {story_user.last_name}" if story_user else "Usuario",
            "avatar": story_user.picture if story_user else None
        }
    )


@router.post("/{story_id}/report")
async def report_story(
    story_id: int,
    report_data: StoryReportCreate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Reportar una historia por contenido inapropiado.
    """
    service = StoryService(db)
    report = await service.report_story(
        story_id=story_id,
        gym_id=gym_id,
        user_id=db_user.id,
        report_data=report_data
    )

    return {
        "success": True,
        "report_id": report.id,
        "message": "Historia reportada exitosamente. Será revisada por los administradores."
    }


@router.post("/highlights", response_model=dict)
async def create_story_highlight(
    highlight_data: StoryHighlightCreate,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    db_user: User = Depends(get_current_db_user)
):
    """
    Crear un highlight de historias (colección de historias destacadas).
    """
    service = StoryService(db)
    highlight = await service.create_highlight(
        gym_id=gym_id,
        user_id=db_user.id,
        highlight_data=highlight_data
    )

    return {
        "success": True,
        "highlight_id": highlight.id,
        "message": "Highlight creado exitosamente"
    }