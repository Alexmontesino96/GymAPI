from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.models.gym import Gym
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from pydantic import BaseModel

# Importar los esquemas necesarios
from app.schemas.schedule import (
    ClassParticipation as ClassParticipationSchema,
    ParticipationWithSessionInfo, 
    format_participation_with_session_info,
    Class as ClassSchema,
    ClassSession as ClassSessionSchema
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
    
    # Serializar los resultados para evitar el error de Pydantic
    serialized_results = []
    for item in raw_results:
        serialized_results.append({
            "participation": ClassParticipationSchema.model_validate(item["participation"]),
            "session": ClassSessionSchema.model_validate(item["session"]),
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

    Returns:
        List[Dict]: Lista simple con información básica:
        - session_id: ID de la sesión (para cancelar)
        - class_name: Nombre de la clase
        - start_time: Fecha y hora de inicio
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
        
        simple_results.append({
            "session_id": session.id,
            "class_name": gym_class.name,
            "start_time": session.start_time,
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
    
    # Serializar los resultados para evitar el error de Pydantic
    serialized_results = []
    for item in raw_results:
        serialized_results.append({
            "participation": ClassParticipationSchema.model_validate(item["participation"]),
            "session": ClassSessionSchema.model_validate(item["session"]),
            "gym_class": ClassSchema.model_validate(item["gym_class"])
        })
    
    return serialized_results


@router.get("/attendance-history/{member_id}", response_model=List[Dict[str, Any]])
async def get_member_attendance_history_legacy(
    member_id: int = Path(..., description="ID of the member"),
    start_date: Optional[date] = Query(None, description="Start date for attendance history (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for attendance history (YYYY-MM-DD)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Member Attendance History (DEPRECATED - use /member/{member_id}/history instead)
    
    This endpoint is maintained for backward compatibility. 
    Please use /member/{member_id}/history for new implementations.
    
    Retrieves a member's history of attended class sessions, with optional date range filtering.
    This endpoint is for gym trainers and administrators to review a specific member's attendance.
    
    Args:
        member_id (int): The ID of the member whose attendance history to retrieve.
        start_date (date, optional): If provided, only include attendances on or after this date.
        end_date (date, optional): If provided, only include attendances on or before this date.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency.
        current_gym (Gym, optional): Current gym context dependency.
        user (Auth0User, optional): Authenticated user.
        redis_client (Redis, optional): Redis client dependency.
    
    Permissions:
        - Requires 'manage:class_registrations' scope (typically for trainers/admins).
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing:
                            - `participation`: ClassParticipationSchema object.
                            - `session`: ClassSessionSchema object.
                            - `gym_class`: ClassSchema object.
    
    Raises:
        HTTPException 400: Member doesn't belong to this gym.
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym not found.
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
    
    # Convert date objects to datetime if provided
    start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
    
    # Service retrieves attendance history for the member
    raw_results = await class_participation_service.get_member_attendance_history(
        db, 
        member_id=member_id, 
        gym_id=current_gym.id,
        start_date=start_datetime,
        end_date=end_datetime,
        skip=skip,
        limit=limit, 
        redis_client=redis_client
    )
    
    # Serializar los resultados para evitar el error de Pydantic
    serialized_results = []
    for item in raw_results:
        serialized_results.append({
            "participation": ClassParticipationSchema.model_validate(item["participation"]),
            "session": ClassSessionSchema.model_validate(item["session"]),
            "gym_class": ClassSchema.model_validate(item["gym_class"])
        })
    
    return serialized_results

@router.get("/my-attendance-history", response_model=List[Dict[str, Any]])
async def get_my_attendance_history_legacy(
    start_date: Optional[date] = Query(None, description="Start date for attendance history (inclusive). Format: YYYY-MM-DD (e.g., 2025-01-15)"),
    end_date: Optional[date] = Query(None, description="End date for attendance history (inclusive). Format: YYYY-MM-DD (e.g., 2025-08-15)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return (1-500)"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    📊 **Get My Attendance History** (DEPRECATED - use /my-history instead)
    
    **⚠️ DEPRECATED**: This endpoint is maintained for backward compatibility.
    Please use `/my-history` for new implementations.
    
    Retrieves the authenticated user's complete history of class participations, including 
    attended sessions, cancelled registrations, and no-shows. Results are ordered by 
    session start time (most recent first).
    
    ## Query Parameters
    
    ### Date Range Filtering
    - **start_date** (optional): Start date for filtering results (inclusive)
        - **Format**: `YYYY-MM-DD` (ISO 8601 date format)
        - **Examples**: `2025-01-15`, `2025-08-07`
        - **Timezone**: Uses gym's local timezone for date comparisons
    
    - **end_date** (optional): End date for filtering results (inclusive)  
        - **Format**: `YYYY-MM-DD` (ISO 8601 date format)
        - **Examples**: `2025-08-15`, `2025-12-31`
        - **Timezone**: Uses gym's local timezone for date comparisons
    
    ### Pagination
    - **skip**: Number of records to skip (default: 0, min: 0)
    - **limit**: Maximum records to return (default: 100, min: 1, max: 500)
    
    ## Response Format
    
    Returns a list of dictionaries, each containing:
    
    ```json
    [
        {
            "participation": {
                "id": 123,
                "status": "attended",
                "registration_time": "2025-08-07T10:30:00Z",
                "attendance_time": "2025-08-07T18:00:00Z",
                "cancellation_time": null,
                "cancellation_reason": null
            },
            "session": {
                "id": 456,
                "start_time": "2025-08-07T18:00:00Z",
                "end_time": "2025-08-07T19:00:00Z", 
                "status": "completed",
                "room": "Studio A",
                "current_participants": 15
            },
            "gym_class": {
                "id": 789,
                "name": "Yoga Flow",
                "description": "Vinyasa-style yoga class",
                "duration": 60,
                "max_capacity": 20,
                "difficulty_level": "intermediate"
            }
        }
    ]
    ```
    
    ## Participation Status Values
    - `registered`: User is registered but class hasn't occurred yet
    - `attended`: User attended the class session
    - `cancelled`: User cancelled their registration
    - `no_show`: User was registered but didn't attend
    
    ## Session Status Values  
    - `scheduled`: Class is scheduled but hasn't started
    - `in_progress`: Class is currently happening
    - `completed`: Class has finished
    - `cancelled`: Class was cancelled by gym staff
    
    ## Authentication & Permissions
    - **Required Scope**: `resource:read`
    - **User Access**: Own data only (cannot view other users' history)
    - **Gym Context**: Automatically filtered to current gym
    
    ## Error Responses
    - **401 Unauthorized**: Invalid or missing authentication token
    - **403 Forbidden**: Token lacks required `resource:read` scope  
    - **404 Not Found**: User not found in database
    - **422 Validation Error**: Invalid date format or parameter values
    
    ## Usage Examples
    
    ```bash
    # Get all attendance history
    GET /api/v1/schedule/participation/my-attendance-history
    
    # Get history for specific date range
    GET /api/v1/schedule/participation/my-attendance-history?start_date=2025-01-01&end_date=2025-08-07
    
    # Get recent history with pagination
    GET /api/v1/schedule/participation/my-attendance-history?skip=0&limit=20
    ```
    """
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )
    
    # Convert date objects to datetime if provided
    start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
    
    # Service retrieves attendance history for the current user within the gym
    raw_results = await class_participation_service.get_member_attendance_history(
        db, 
        member_id=db_user.id, 
        gym_id=current_gym.id,
        start_date=start_datetime,
        end_date=end_datetime,
        skip=skip,
        limit=limit, 
        redis_client=redis_client
    )
    
    # Serializar los resultados para evitar el error de Pydantic
    serialized_results = []
    for item in raw_results:
        serialized_results.append({
            "participation": ClassParticipationSchema.model_validate(item["participation"]),
            "session": ClassSessionSchema.model_validate(item["session"]),
            "gym_class": ClassSchema.model_validate(item["gym_class"])
        })
    
    return serialized_results

@router.get("/member/{member_id}/history", response_model=List[ParticipationWithSessionInfo])
async def get_member_attendance_history(
    member_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Obtener el historial de asistencia de un miembro específico.
    
    Args:
        member_id: ID del miembro
        start_date: Fecha de inicio para filtrar (opcional)
        end_date: Fecha de fin para filtrar (opcional)
        skip: Número de registros a saltar para paginación
        limit: Número máximo de registros a devolver
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        current_user: Usuario autenticado
        redis_client: Cliente Redis
    
    Returns:
        Lista de participaciones con información de la sesión
        
    Raises:
        HTTPException 400: Si el miembro no pertenece al gimnasio actual
        HTTPException 403: Si el usuario no tiene permisos suficientes
        HTTPException 404: Si el miembro o gimnasio no se encuentran
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
    result = []
    for item in history:
        participation = item["participation"]
        session = item["session"]
        gym_class = item["gym_class"]
        
        result.append(
            format_participation_with_session_info(participation, session, gym_class)
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
    result = []
    for item in history:
        participation = item["participation"]
        session = item["session"]
        gym_class = item["gym_class"]
        
        result.append(
            format_participation_with_session_info(participation, session, gym_class)
        )
    
    return result 