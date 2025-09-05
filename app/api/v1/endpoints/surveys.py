"""
Survey API Endpoints

This module provides REST API endpoints for the survey system.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Security, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis_client import get_redis_client
from app.core.auth0_fastapi import get_current_user, Auth0User, auth
from app.core.tenant import verify_gym_access, GymSchema
from app.models.user import User
from app.models.survey import SurveyStatus
from app.schemas.survey import (
    Survey as SurveySchema,
    SurveyCreate,
    SurveyUpdate,
    SurveyWithQuestions,
    SurveyList,
    ResponseCreate,
    Response as ResponseSchema,
    ResponseWithAnswers,
    SurveyStatistics,
    Template as TemplateSchema,
    TemplateCreate,
    CreateFromTemplate
)
from app.services.survey import survey_service
from app.repositories.survey import survey_repository
import logging

logger = logging.getLogger("surveys_api")

router = APIRouter()


# ============= Public Survey Endpoints (for users) =============

@router.get("/available", response_model=List[SurveySchema])
async def get_available_surveys(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> List[SurveySchema]:
    """
    Get available surveys for the current user.
    
    This endpoint returns all active surveys that the user can answer,
    filtering out surveys they've already completed (unless multiple responses are allowed).
    
    Returns:
        List of available surveys the user can respond to
    """
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    user_id = user.id if user else None
    
    surveys = await survey_service.get_available_surveys(
        db=db,
        gym_id=current_gym.id,
        user_id=user_id,
        redis_client=redis_client
    )
    
    return surveys


@router.post("/responses", response_model=ResponseSchema, status_code=status.HTTP_201_CREATED)
async def submit_survey_response(
    *,
    db: Session = Depends(get_db),
    response_in: ResponseCreate,
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> ResponseSchema:
    """
    Submit a response to a survey.
    
    This endpoint allows users to submit their answers to a survey.
    Validation is performed to ensure all required questions are answered
    and answer types match question types.
    
    Args:
        response_in: Survey response with answers
        
    Returns:
        Created response record
    """
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    response = await survey_service.submit_response(
        db=db,
        response_in=response_in,
        user_id=user.id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    
    return response


@router.get("/my-responses", response_model=List[ResponseWithAnswers])
async def get_my_survey_responses(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
) -> List[ResponseWithAnswers]:
    """
    Get current user's survey responses.
    
    Returns all surveys the user has responded to, including their answers.
    
    Returns:
        List of user's survey responses with answers
    """
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        return []
    
    responses = await survey_service.get_my_responses(
        db=db,
        user_id=user.id,
        gym_id=current_gym.id,
        skip=skip,
        limit=limit
    )
    
    return responses


# ============= Template Endpoints (must be before /{survey_id}) =============

@router.get("/templates", response_model=List[TemplateSchema])
async def get_survey_templates(
    *,
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
) -> List[TemplateSchema]:
    """
    Get available survey templates.
    
    Returns public templates and gym-specific templates.
    
    Args:
        category: Optional filter by template category
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of available templates
    """
    templates = survey_repository.get_templates(
        db=db,
        gym_id=current_gym.id,
        category=category,
        skip=skip,
        limit=limit
    )
    
    return templates


@router.post("/from-template", response_model=SurveySchema, status_code=status.HTTP_201_CREATED)
async def create_survey_from_template(
    *,
    db: Session = Depends(get_db),
    template_data: CreateFromTemplate,
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> SurveySchema:
    """
    Create a new survey from a template.
    
    Uses a predefined template to quickly create a new survey.
    
    Permissions:
        - Requires 'resource:write' scope (trainers and admins)
        
    Args:
        template_data: Template ID and customization options
        
    Returns:
        Created survey
    """
    # Check if user is trainer or admin
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_trainer = "resource:write" in user_permissions
    
    if not (is_admin or is_trainer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only trainers and administrators can create surveys"
        )
    
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    survey = survey_repository.create_survey_from_template(
        db=db,
        template_id=template_data.template_id,
        title=template_data.title,
        description=template_data.description,
        creator_id=user.id,
        gym_id=current_gym.id
    )
    
    # Invalidate cache
    if redis_client:
        await survey_service._invalidate_survey_caches(
            redis_client,
            gym_id=current_gym.id
        )
    
    return survey


@router.get("/my-surveys", response_model=List[SurveySchema])
async def get_my_created_surveys(
    *,
    db: Session = Depends(get_db),
    status_filter: Optional[SurveyStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> List[SurveySchema]:
    """
    Get surveys created by the current user.
    
    Returns all surveys created by the authenticated user,
    optionally filtered by status.
    
    Args:
        status_filter: Optional filter by survey status
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of surveys created by the user
    """
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        return []
    
    surveys = await survey_service.get_my_surveys(
        db=db,
        creator_id=user.id,
        gym_id=current_gym.id,
        status_filter=status_filter,
        redis_client=redis_client
    )
    
    return surveys[skip:skip + limit]


# ============= Survey Details Endpoint (with path parameter) =============

@router.get("/{survey_id}", response_model=SurveyWithQuestions)
async def get_survey_details(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
) -> SurveyWithQuestions:
    """
    Get detailed information about a specific survey.
    
    Returns the survey with all its questions and choices.
    Only published surveys are visible to regular users.
    
    Args:
        survey_id: ID of the survey
        
    Returns:
        Survey with questions and choices
    """
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    # Regular users can only see published surveys
    if survey.status != SurveyStatus.PUBLISHED:
        if not user or survey.creator_id != user.id:
            # Check if admin
            user_permissions = getattr(current_user, "permissions", []) or []
            is_admin = "resource:admin" in user_permissions
            
            if not is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Survey is not available"
                )
    
    # Get response count
    response_count = len(survey.responses) if survey.responses else 0
    
    return SurveyWithQuestions(
        **survey.__dict__,
        response_count=response_count
    )


# ============= Survey Management Endpoints (for admins/trainers) =============

@router.post("/", response_model=SurveySchema, status_code=status.HTTP_201_CREATED)
async def create_survey(
    *,
    db: Session = Depends(get_db),
    survey_in: SurveyCreate,
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> SurveySchema:
    """
    Create a new survey.
    
    Creates a survey in DRAFT status. The survey must be published
    separately to make it available to users.
    
    Permissions:
        - Requires 'resource:write' scope (trainers and admins)
        
    Args:
        survey_in: Survey data with questions
        
    Returns:
        Created survey
    """
    # Check if user is trainer or admin
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_trainer = "resource:write" in user_permissions
    
    if not (is_admin or is_trainer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only trainers and administrators can create surveys"
        )
    
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    survey = await survey_service.create_survey(
        db=db,
        survey_in=survey_in,
        creator_id=user.id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    
    return survey


@router.put("/{survey_id}", response_model=SurveySchema)
async def update_survey(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    survey_in: SurveyUpdate,
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> SurveySchema:
    """
    Update a survey.
    
    Only draft surveys can be edited. Published surveys can only be closed.
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey to update
        survey_in: Updated survey data
        
    Returns:
        Updated survey
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    # Check permissions
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this survey"
        )
    
    updated_survey = survey_repository.update_survey(
        db=db,
        survey_id=survey_id,
        survey_in=survey_in,
        gym_id=current_gym.id
    )
    
    # Invalidate cache
    if redis_client:
        await survey_service._invalidate_survey_caches(
            redis_client,
            gym_id=current_gym.id,
            survey_id=survey_id
        )
    
    return updated_survey


@router.post("/{survey_id}/publish", response_model=SurveySchema)
async def publish_survey(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client),
    background_tasks: BackgroundTasks
) -> SurveySchema:
    """
    Publish a survey to make it available to users.
    
    Once published, the survey will appear in available surveys
    and users will be notified based on target audience.
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey to publish
        
    Returns:
        Published survey
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID and check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to publish this survey"
        )
    
    published_survey = await survey_service.publish_survey(
        db=db,
        survey_id=survey_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    
    return published_survey


@router.post("/{survey_id}/close", response_model=SurveySchema)
async def close_survey(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> SurveySchema:
    """
    Close a survey to stop accepting responses.
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey to close
        
    Returns:
        Closed survey
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID and check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to close this survey"
        )
    
    closed_survey = await survey_service.close_survey(
        db=db,
        survey_id=survey_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    
    return closed_survey


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_survey(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> None:
    """
    Delete a survey (only if in DRAFT status).
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey to delete
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID and check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this survey"
        )
    
    result = survey_repository.delete_survey(
        db=db,
        survey_id=survey_id,
        gym_id=current_gym.id
    )
    
    if result and redis_client:
        await survey_service._invalidate_survey_caches(
            redis_client,
            gym_id=current_gym.id,
            survey_id=survey_id
        )
    
    return None


# ============= Statistics & Results Endpoints =============

@router.get("/{survey_id}/statistics", response_model=SurveyStatistics)
async def get_survey_statistics(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> SurveyStatistics:
    """
    Get comprehensive statistics for a survey.
    
    Returns detailed analytics including response rates, completion times,
    and per-question statistics.
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey
        
    Returns:
        Survey statistics and analytics
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID and check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view survey statistics"
        )
    
    statistics = await survey_service.get_survey_statistics(
        db=db,
        survey_id=survey_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    
    return statistics


@router.get("/{survey_id}/responses", response_model=List[ResponseWithAnswers])
async def get_survey_responses(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    only_complete: bool = Query(True),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
) -> List[ResponseWithAnswers]:
    """
    Get all responses for a survey.
    
    Returns detailed response data including all answers.
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey
        skip: Number of records to skip
        limit: Maximum number of records to return
        only_complete: Whether to return only complete responses
        
    Returns:
        List of survey responses with answers
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID and check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view survey responses"
        )
    
    responses = survey_repository.get_survey_responses(
        db=db,
        survey_id=survey_id,
        gym_id=current_gym.id,
        skip=skip,
        limit=limit,
        only_complete=only_complete
    )
    
    return responses


@router.get("/{survey_id}/export")
async def export_survey_results(
    *,
    db: Session = Depends(get_db),
    survey_id: int = Path(..., ge=1),
    format: str = Query("csv", regex="^(csv|excel)$"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Export survey results to CSV or Excel.
    
    Downloads a file with all survey responses and statistics.
    
    Permissions:
        - Survey creator or admin
        
    Args:
        survey_id: ID of the survey
        format: Export format (csv or excel)
        
    Returns:
        File download with survey results
    """
    # Check ownership or admin
    survey = survey_repository.get_survey(db, survey_id, current_gym.id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get internal user ID and check permissions
    auth0_id = current_user.id
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "resource:admin" in user_permissions
    is_owner = user and survey.creator_id == user.id
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to export survey results"
        )
    
    # Export data
    output = await survey_service.export_survey_results(
        db=db,
        survey_id=survey_id,
        gym_id=current_gym.id,
        format=format
    )
    
    if not output:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting survey results"
        )
    
    # Set appropriate headers
    filename = f"survey_{survey_id}_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if format == "excel":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename += ".xlsx"
    else:
        media_type = "text/csv"
        filename += ".csv"
    
    return StreamingResponse(
        output,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )