from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.core.dependencies import module_enabled
from app.models.gym import Gym
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timezone
from pydantic import BaseModel

# Importar los esquemas necesarios
from app.schemas.schedule import (
    ClassParticipation as ClassParticipationSchema,
    ParticipationWithSessionInfo,
    format_participation_with_session_info,
    Class as ClassSchema,
    ClassSession as ClassSessionSchema
)
from app.schemas.participation_status import (
    ParticipationStatusResponse
)
from app.models.user import User
from app.models.user_gym import UserGym as Member
from app.services.schedule import ClassParticipationService

router = APIRouter()

@router.post("/register/{session_id}", response_model=ClassParticipationSchema)
async def register_for_class(
    session_id: int = Path(..., description="ID of the session"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Register Current User for a Class Session

    Registers the currently authenticated user for a specific class session.

    Args:
        session_id (int): The ID of the class session to register for.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'register:classes' scope.

    Returns:
        ClassParticipationSchema: The created participation record.

    Raises:
        HTTPException 400: Bad request (e.g., session full, already registered, session not scheduled).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session or User not found, or session doesn't belong to this gym.
    """
    # Get current user's local ID
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )

    # Service layer handles checking session existence/status and registration logic
    return await class_participation_service.register_for_class(
        db, member_id=db_user.id, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/register/{session_id}/{member_id}", response_model=ClassParticipationSchema)
async def register_member_for_class(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member to register"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Register Specific Member for a Class Session (Admin)

    Registers a specific member (by their user ID) for a class session.
    Intended for use by trainers or administrators.

    Args:
        session_id (int): The ID of the class session.
        member_id (int): The local user ID of the member to register.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).

    Returns:
        ClassParticipationSchema: The created participation record.

    Raises:
        HTTPException 400: Bad request (e.g., session full, member already registered, session not scheduled).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session, Gym, or Member not found, or session/member doesn't belong to this gym.
    """
    # Verify session belongs to the current gym
    # The service call below implicitly verifies this via gym_id parameter

    # Verify the target member exists and belongs to the current gym
    target_member_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=member_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not target_member_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this gym"
        )

    # Service layer handles the rest of the registration logic
    return await class_participation_service.register_for_class(
        db, member_id=member_id, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/cancel-registration/{session_id}", response_model=ClassParticipationSchema)
async def cancel_my_registration(
    session_id: int = Path(..., description="ID of the session"),
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Cancel Current User's Registration

    Cancels the currently authenticated user's registration for a specific class session.

    Args:
        session_id (int): The ID of the session to cancel registration for.
        reason (str, optional): Optional reason for cancellation. Defaults to None.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'register:classes' scope.

    Returns:
        ClassParticipationSchema: The updated participation record with status CANCELLED.

    Raises:
        HTTPException 400: Bad request (e.g., already cancelled, session already started).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session, User, or Participation record not found, or session doesn't belong to gym.
    """
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )

    # Service handles checking session/participation and cancellation
    return await class_participation_service.cancel_registration(
        db, member_id=db_user.id, session_id=session_id, reason=reason, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/cancel-registration/{session_id}/{member_id}", response_model=ClassParticipationSchema)
async def cancel_member_registration(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member whose registration to cancel"),
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Cancel Specific Member's Registration (Admin)

    Cancels a specific member's registration for a class session.
    Intended for use by trainers or administrators.

    Args:
        session_id (int): The ID of the class session.
        member_id (int): The local user ID of the member.
        reason (str, optional): Optional reason for cancellation. Defaults to None.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).

    Returns:
        ClassParticipationSchema: The updated participation record with status CANCELLED.

    Raises:
        HTTPException 400: Bad request (e.g., already cancelled).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session, Gym, Member, or Participation record not found, or session/member doesn't belong to gym.
    """
    # Verify the target member exists and belongs to the current gym
    target_member_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=member_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not target_member_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this gym"
        )

    # Service handles checking session/participation and cancellation
    return await class_participation_service.cancel_registration(
        db, member_id=member_id, session_id=session_id, reason=reason, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/attendance/{session_id}/{member_id}", response_model=ClassParticipationSchema)
async def mark_attendance(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member who attended"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Mark Member Attendance (Admin/Trainer)

    Marks a specific member as having attended a class session.

    Args:
        session_id (int): The ID of the class session.
        member_id (int): The local user ID of the member who attended.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).

    Returns:
        ClassParticipationSchema: The updated participation record with status ATTENDED.

    Raises:
        HTTPException 400: Bad request (e.g., session not completed, participation already marked).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session, Gym, Member, or Participation record not found, or session/member doesn't belong to gym.
    """
    # Verify member exists in gym
    target_member_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=member_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not target_member_membership:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this gym")

    # Service handles marking attendance
    return await class_participation_service.mark_attendance(
        db,
        session_id=session_id,
        member_id=member_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.post("/mark-no-show/{session_id}/{member_id}", response_model=ClassParticipationSchema)
async def mark_no_show(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member who was a no-show"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Mark Member as No-Show (Admin/Trainer)

    Marks a registered member as having not shown up for a class session.

    Args:
        session_id (int): The ID of the class session.
        member_id (int): The local user ID of the member.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).

    Returns:
        ClassParticipationSchema: The updated participation record with status NO_SHOW.

    Raises:
        HTTPException 400: Bad request (e.g., participation status not REGISTERED).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session, Gym, Member, or Participation record not found, or session/member doesn't belong to gym.
    """
    # Verify member exists in gym
    target_member_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=member_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not target_member_membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this gym")

    # Service handles marking as no-show
    return await class_participation_service.mark_no_show(
        db, member_id=member_id, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )


@router.get("/participants/{session_id}", response_model=List[ClassParticipationSchema])
async def get_session_participants(
    session_id: int = Path(..., description="ID of the session"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Session Participants (Admin/Trainer)

    Retrieves a list of all participation records (including status like registered,
    attended, cancelled, no-show) for a specific class session.

    Args:
        session_id (int): The ID of the class session.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).

    Returns:
        List[ClassParticipationSchema]: A list of participation records for the session.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session or Gym not found, or session doesn't belong to this gym.
    """
    # Verify the session belongs to the current gym
    session = await class_session_service.get_session(
        db,
        session_id=session_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found in this gym"
        )

    # Service retrieves participants for the session within the gym
    return await class_participation_service.get_session_participants(
        db,
        session_id=session_id,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/my-classes", response_model=List[Dict[str, Any]])
async def get_my_upcoming_classes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get My Upcoming Registered Classes

    Retrieves a list of upcoming class sessions the currently authenticated user is registered for.

    Timezone
    - Cada item contiene `session` con `timezone` y `start_time_local`/`end_time_local` poblados.
    - `start_time` permanece en UTC para interoperabilidad.

    Args:
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:own_schedules' scope.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing:
                               - `participation`: ClassParticipationSchema object.
                               - `session`: ClassSessionSchema object.
                               - `class`: ClassSchema object.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: User or Gym not found.
    """
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )

    # Service retrieves upcoming classes for the member within the gym
    raw_results = await class_participation_service.get_member_upcoming_classes(
        db, member_id=db_user.id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    )
    # Poblar timezone en sesiones
    from app.services.schedule import populate_sessions_with_timezone
    sessions = [item["session"] for item in raw_results]
    sessions_with_tz = await populate_sessions_with_timezone(sessions, current_gym.id, db)

    # Serializar resultados con sesiones enriquecidas
    serialized_results = []
    for i, item in enumerate(raw_results):
        serialized_results.append({
            "participation": ClassParticipationSchema.model_validate(item["participation"]),
            "session": ClassSessionSchema.model_validate(sessions_with_tz[i]),
            "gym_class": ClassSchema.model_validate(item["gym_class"])
        })
    return serialized_results


@router.get("/my-classes-simple")
async def get_my_upcoming_classes_simple(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    📱 **Get My Upcoming Classes (Simple/Mobile)**

    Endpoint simplificado que devuelve solo información básica de las clases
    registradas del usuario. Optimizado para aplicaciones móviles.

    Args:
        skip (int): Registros a omitir para paginación
        limit (int): Máximo número de registros
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        user: Usuario autenticado
        redis_client: Cliente Redis

    Permissions:
        - Requires 'resource:read' scope

    Timezone
    - Incluye tanto `start_time` (UTC) como `start_time_local` (hora local del gimnasio) para
      facilitar la renderización en UI simple/móvil.

    Returns:
        List[Dict]: Lista simple con información básica:
        - session_id: ID de la sesión (para cancelar)
        - class_name: Nombre de la clase
        - start_time: Fecha y hora de inicio (UTC)
        - start_time_local: Fecha y hora local del gimnasio
        - participation_status: Estado de participación
        - room: Sala (si existe)
        - current_participants: Participantes actuales
        - max_capacity: Capacidad máxima
    """
    auth0_id = user.id
    # Usar versión con caché
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )

    # Reutilizar el servicio existente
    raw_results = await class_participation_service.get_member_upcoming_classes(
        db, member_id=db_user.id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    )
    
    # Extraer solo información esencial
    simple_results = []
    for item in raw_results:
        participation = item["participation"]
        session = item["session"]
        gym_class = item["gym_class"]
        
        # Calcular capacidad efectiva
        effective_capacity = session.override_capacity if session.override_capacity else gym_class.max_capacity
        
        # Calcular hora local
        from app.core.timezone_utils import convert_utc_to_local
        local_dt = convert_utc_to_local(session.start_time, current_gym.timezone)
        
        simple_results.append({
            "session_id": session.id,
            "class_name": gym_class.name,
            "start_time": session.start_time,
            "start_time_local": local_dt.replace(tzinfo=None),
            "participation_status": participation.status.value,  # Convertir enum a string
            "room": session.room,
            "current_participants": session.current_participants,
            "max_capacity": effective_capacity
        })
    
    return simple_results


@router.get("/member-classes/{member_id}", response_model=List[Dict[str, Any]])
async def get_member_upcoming_classes(
    member_id: int = Path(..., description="ID of the member"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Specific Member's Upcoming Classes (Admin/Trainer)

    Retrieves a list of upcoming class sessions a specific member is registered for.
    Intended for use by trainers or administrators.

    Args:
        member_id (int): The local user ID of the member.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing participation, session, and class info.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Member or Gym not found, or member doesn't belong to this gym.
    """
    # Verify the target member exists and belongs to the current gym
    target_member_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=member_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not target_member_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this gym"
        )

    # Service retrieves upcoming classes for the member within the gym
    raw_results = await class_participation_service.get_member_upcoming_classes(
        db, member_id=member_id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    )
    # Poblar timezone en sesiones
    from app.services.schedule import populate_sessions_with_timezone
    sessions = [item["session"] for item in raw_results]
    sessions_with_tz = await populate_sessions_with_timezone(sessions, current_gym.id, db)

    # Serializar resultados con sesiones enriquecidas
    serialized_results = []
    for i, item in enumerate(raw_results):
        serialized_results.append({
            "participation": ClassParticipationSchema.model_validate(item["participation"]),
            "session": ClassSessionSchema.model_validate(sessions_with_tz[i]),
            "gym_class": ClassSchema.model_validate(item["gym_class"])
        })
    return serialized_results


@router.get("/member/{member_id}/history", response_model=List[ParticipationWithSessionInfo])
async def get_member_attendance_history(
    member_id: int = Path(..., description="ID of the member whose attendance history to retrieve"),
    start_date: Optional[date] = Query(None, description="Start date for filtering (inclusive). Format: YYYY-MM-DD (e.g., 2025-01-15)"),
    end_date: Optional[date] = Query(None, description="End date for filtering (inclusive). Format: YYYY-MM-DD (e.g., 2025-08-15)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return (1-100)"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    👥 **Get Member Attendance History** (Admin Only)
    
    Retrieves the complete attendance history for a specific gym member.
    This endpoint is designed for gym administrators and trainers to review
    individual member participation patterns and attendance records.
    
    ## Features
    - ✅ Admin-only access with proper authorization
    - ✅ Comprehensive participation data with session details
    - ✅ Date range filtering with gym timezone support
    - ✅ Modern structured response format
    - ✅ Performance optimized with caching
    
    ## Query Parameters
    
    ### Path Parameters
    - **member_id** (required): The internal user ID of the gym member
    
    ### Date Range Filtering
    - **start_date** (optional): Start date for filtering results (inclusive)
        - **Format**: `YYYY-MM-DD` (ISO 8601 date format)
        - **Examples**: `2025-01-15`, `2025-08-07`
        - **Timezone**: Interpreted as gym's local timezone
    
    - **end_date** (optional): End date for filtering results (inclusive)
        - **Format**: `YYYY-MM-DD` (ISO 8601 date format)
        - **Examples**: `2025-08-15`, `2025-12-31`
        - **Timezone**: Interpreted as gym's local timezone
    
    ### Pagination
    - **skip**: Number of records to skip (default: 0, min: 0)
    - **limit**: Maximum records to return (default: 20, min: 1, max: 100)
    
    ## Timezone
    - Los parámetros `start_date`/`end_date` se interpretan en la zona horaria del gimnasio.
    - Las sesiones incluidas en la respuesta se devuelven con `start_time`/`end_time` en UTC
      y campos locales `start_time_local`/`end_time_local` para fácil renderizado.

    ## Response Format
    
    Returns structured participation data with comprehensive session information:
    
    ```json
    [
        {
            "participation": {
                "id": 456,
                "session_id": 789,
                "member_id": 123,
                "gym_id": 4,
                "status": "attended",
                "registration_time": "2025-08-07T10:30:00Z",
                "attendance_time": "2025-08-07T18:00:00Z",
                "cancellation_time": null,
                "cancellation_reason": null
            },
            "session": {
                "id": 789,
                "class_id": 101,
                "trainer_id": 202,
                "gym_id": 4,
                "start_time": "2025-08-07T18:00:00Z",
                "end_time": "2025-08-07T19:00:00Z",
                "status": "completed",
                "room": "Studio A",
                "current_participants": 15
            },
            "class": {
                "id": 101,
                "name": "Yoga Flow",
                "description": "Vinyasa-style yoga class",
                "duration": 60,
                "max_capacity": 20,
                "difficulty_level": "intermediate"
            }
        }
    ]
    ```
    
    ## Authentication & Permissions
    - **Required Scope**: `resource:admin`
    - **User Access**: Admin/trainer access to any gym member's data
    - **Gym Context**: Automatically filtered to current gym membership
    - **Member Verification**: Validates member belongs to current gym
    
    ## Error Responses
    - **401 Unauthorized**: Invalid or missing authentication token
    - **403 Forbidden**: Token lacks required `resource:admin` scope
    - **404 Not Found**: Member not found or doesn't belong to current gym
    - **422 Validation Error**: Invalid date format or parameter values
    
    ## Use Cases
    - **Member Progress Tracking**: Review individual attendance patterns
    - **Performance Analytics**: Analyze member engagement over time
    - **Attendance Reports**: Generate detailed attendance summaries
    - **Member Support**: Investigate attendance-related member inquiries
    
    ## Usage Examples
    
    ```bash
    # Get all attendance history for member ID 123
    GET /api/v1/schedule/participation/member/123/history
    
    # Get January 2025 history for member
    GET /api/v1/schedule/participation/member/123/history?start_date=2025-01-01&end_date=2025-01-31
    
    # Get recent history with pagination  
    GET /api/v1/schedule/participation/member/123/history?skip=0&limit=10
    ```
    """
    # Verificar que el miembro pertenece al gimnasio actual
    member = db.query(Member).filter(Member.id == member_id, Member.gym_id == current_gym.id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )

    # Convertir date a datetime para el servicio
    start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None

    # Obtener el historial de asistencia
    history = await class_participation_service.get_member_attendance_history(
        db=db,
        member_id=member_id,
        gym_id=current_gym.id,
        start_date=start_datetime,
        end_date=end_datetime,
        skip=skip,
        limit=limit,
        redis_client=redis_client
    )
    
    # Formatear la respuesta usando la función importada
    # Poblar timezone en sesiones del historial
    from app.services.schedule import populate_sessions_with_timezone
    sessions = [item["session"] for item in history]
    sessions_with_tz = await populate_sessions_with_timezone(sessions, current_gym.id, db)
    result = []
    for i, item in enumerate(history):
        participation = item["participation"]
        gym_class = item["gym_class"]
        # Usar sesión enriquecida
        result.append(
            format_participation_with_session_info(participation, ClassSessionSchema.model_validate(sessions_with_tz[i]), gym_class)
        )
    return result

@router.get("/my-history", response_model=List[ParticipationWithSessionInfo])
async def get_my_attendance_history(
    start_date: Optional[date] = Query(None, description="Start date for filtering (inclusive). Format: YYYY-MM-DD (e.g., 2025-01-15)"),
    end_date: Optional[date] = Query(None, description="End date for filtering (inclusive). Format: YYYY-MM-DD (e.g., 2025-08-15)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return (1-100)"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    📊 **Get My Attendance History** (Recommended Endpoint)
    
    Retrieves the authenticated user's complete history of class participations with 
    comprehensive session and class information. This is the recommended endpoint for 
    attendance history queries.
    
    ## Features
    - ✅ Modern structured response format  
    - ✅ Comprehensive session and class details
    - ✅ Optimized for performance with caching
    - ✅ Proper timezone handling (UTC storage, gym local display)
    
    ## Query Parameters
    
    ### Date Range Filtering
    - **start_date** (optional): Start date for filtering results (inclusive)
        - **Format**: `YYYY-MM-DD` (ISO 8601 date format)
        - **Examples**: `2025-01-15`, `2025-08-07` 
        - **Timezone**: Interpreted as gym's local timezone
    
    - **end_date** (optional): End date for filtering results (inclusive)
        - **Format**: `YYYY-MM-DD` (ISO 8601 date format) 
        - **Examples**: `2025-08-15`, `2025-12-31`
        - **Timezone**: Interpreted as gym's local timezone
    
    ### Pagination  
    - **skip**: Number of records to skip (default: 0, min: 0)
    - **limit**: Maximum records to return (default: 20, min: 1, max: 100)
    
    ## Timezone
    - Los parámetros `start_date`/`end_date` se interpretan en la zona horaria del gimnasio.
    - Las sesiones incluidas en la respuesta se devuelven con `start_time`/`end_time` en UTC
      y campos locales `start_time_local`/`end_time_local` para fácil renderizado.

    ## Response Format
    
    Returns a structured list with comprehensive information:
    
    ```json
    [
        {
            "participation": {
                "id": 123,
                "session_id": 456,
                "member_id": 789,
                "gym_id": 4,
                "status": "attended",
                "registration_time": "2025-08-07T10:30:00Z",
                "attendance_time": "2025-08-07T18:00:00Z"
            },
            "session": {
                "id": 456,
                "class_id": 101,
                "trainer_id": 202,
                "gym_id": 4,
                "start_time": "2025-08-07T18:00:00Z", 
                "end_time": "2025-08-07T19:00:00Z",
                "status": "completed",
                "room": "Studio A",
                "current_participants": 15
            },
            "class": {
                "id": 101,
                "name": "Yoga Flow", 
                "description": "Vinyasa-style yoga class",
                "duration": 60,
                "max_capacity": 20,
                "difficulty_level": "intermediate",
                "category": "yoga"
            }
        }
    ]
    ```
    
    ## Authentication & Permissions
    - **Required Scope**: `resource:read`
    - **User Access**: Own data only (cannot access other users' history)
    - **Gym Context**: Automatically filtered to current gym membership
    
    ## Error Responses
    - **401 Unauthorized**: Invalid or missing authentication token
    - **403 Forbidden**: Token lacks required `resource:read` scope
    - **404 Not Found**: User not found in database 
    - **422 Validation Error**: Invalid date format or parameter values
    
    ## Usage Examples
    
    ```bash
    # Get recent attendance history (last 20 records)
    GET /api/v1/schedule/participation/my-history
    
    # Get history for January 2025
    GET /api/v1/schedule/participation/my-history?start_date=2025-01-01&end_date=2025-01-31
    
    # Get next page of results
    GET /api/v1/schedule/participation/my-history?skip=20&limit=20
    ```
    """
    # Obtener el ID del usuario actual
    auth0_id = current_user.id
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe en la base de datos"
        )
    
    # Convertir date a datetime para el servicio
    start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None

    # Obtener el historial de asistencia
    history = await class_participation_service.get_member_attendance_history(
        db=db,
        member_id=db_user.id,
        gym_id=current_gym.id,
        start_date=start_datetime,
        end_date=end_datetime,
        skip=skip,
        limit=limit,
        redis_client=redis_client
    )
    
    # Formatear la respuesta usando la función importada
    # Poblar timezone en sesiones del historial
    from app.services.schedule import populate_sessions_with_timezone
    sessions = [item["session"] for item in history]
    sessions_with_tz = await populate_sessions_with_timezone(sessions, current_gym.id, db)
    result = []
    for i, item in enumerate(history):
        participation = item["participation"]
        gym_class = item["gym_class"]
        result.append(
            format_participation_with_session_info(participation, ClassSessionSchema.model_validate(sessions_with_tz[i]), gym_class)
        )
    return result


@router.get("/my-participation-status", response_model=ParticipationStatusResponse)
async def get_my_participation_status(
    start_date: date = Query(..., description="Start date for filtering (required). Format: YYYY-MM-DD (e.g., 2025-01-15)"),
    end_date: date = Query(..., description="End date for filtering (required). Format: YYYY-MM-DD (e.g., 2025-08-15)"),
    session_ids: Optional[str] = Query(None, description="Comma-separated list of specific session IDs to filter (optional)"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    🚀 **Get My Participation Status** (Ultra-Optimized)
    
    Este endpoint está diseñado para ser extremadamente rápido y ligero, optimizado para el 
    frontend que necesita cargar solo los estados de participación del usuario sin 
    información completa de sesiones o clases.
    
    ## ⚡ Optimizaciones de Performance
    - **Query ultra-optimizada**: Solo consulta tabla `class_participation`
    - **Cache agresivo**: TTL de 5 minutos con invalidación inteligente
    - **Payload mínimo**: Solo campos esenciales (~90% más pequeño)
    - **Tiempo respuesta**: Objetivo <50ms vs 352ms del endpoint completo
    
    ## 🎯 Caso de Uso Frontend
    
    Estrategia de carga en dos fases para mejor UX:
    
    1. **Fase 1**: Frontend carga sesiones/eventos del rango con endpoint completo
    2. **Fase 2**: Frontend carga solo estados con este endpoint ultra-rápido
    3. **Mapeo**: Frontend mapea participaciones por `session_id`
    
    ```javascript
    // Ejemplo de uso frontend
    const sessions = await api.get('/sessions', {start_date, end_date});
    const participations = await api.get('/my-participation-status', {start_date, end_date});
    
    // Mapear estados a eventos
    sessions.forEach(session => {
        session.myStatus = participations.participations.find(p => p.session_id === session.id);
    });
    ```
    
    ## 📋 Parámetros Requeridos
    - `start_date` & `end_date`: **Requeridos** para optimizar cache y consulta
    - Rango máximo recomendado: 3 meses para mejor performance
    
    ## 📊 Respuesta Ultra-Ligera
    
    ```json
    {
        "participations": [
            {
                "session_id": 123,
                "status": "registered", 
                "registration_time": "2025-01-15T10:30:00Z",
                "attendance_time": null,
                "cancellation_time": null
            }
        ],
        "total_count": 1
    }
    ```
    
    ## 🔐 Authentication & Permissions
    - **Required Scope**: `resource:read`
    - **User Access**: Solo datos propios del usuario autenticado
    - **Gym Context**: Automáticamente filtrado por gimnasio actual
    
    ## ❌ Error Responses
    - **401 Unauthorized**: Token inválido o faltante
    - **403 Forbidden**: Token sin scope `resource:read` requerido
    - **422 Validation Error**: Fechas inválidas o faltan parámetros requeridos
    
    ## 📈 Métricas Esperadas
    - **Cache Hit Ratio**: >90% (vs 33% endpoint actual)
    - **Tiempo Respuesta**: <50ms (vs 352ms endpoint actual)
    - **Payload Size**: ~90% más pequeño
    - **DB Queries**: 1 query simple vs múltiples joins
    
    ## 💡 Usage Examples
    
    ```bash
    # Estados básicos para enero 2025
    GET /api/v1/schedule/participation/my-participation-status?start_date=2025-01-01&end_date=2025-01-31
    
    # Estados para sesiones específicas
    GET /api/v1/schedule/participation/my-participation-status?start_date=2025-01-01&end_date=2025-01-31&session_ids=123,456,789
    ```
    """
    # Obtener el ID del usuario actual desde el token JWT
    from app.services.user import user_service
    current_user_db = await user_service.get_user_by_auth0_id_cached(
        db=db, auth0_id=user.id, redis_client=redis_client
    )
    
    if not current_user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Verificar que el usuario pertenece al gimnasio actual
    target_member_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=current_user_db.id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not target_member_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en este gimnasio"
        )
    
    # Parsear session_ids si se proporcionan
    session_ids_list = None
    if session_ids:
        try:
            session_ids_list = [int(id.strip()) for id in session_ids.split(',') if id.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="session_ids debe contener números separados por comas"
            )
    
    # Convertir dates a datetime UTC para el servicio
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    # Validar rango de fechas (máximo 3 meses para performance)
    date_diff = end_datetime - start_datetime
    if date_diff.days > 90:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rango de fechas no puede exceder 90 días para óptima performance"
        )
    
    # Obtener estados de participación (ultra-optimizado)
    participations_data = await class_participation_service.get_member_participation_status(
        db=db,
        member_id=current_user_db.id,
        start_date=start_datetime,
        end_date=end_datetime,
        gym_id=current_gym.id,
        session_ids=session_ids_list,
        redis_client=redis_client
    )
    
    return ParticipationStatusResponse(
        participations=participations_data,
        total_count=len(participations_data)
    )
