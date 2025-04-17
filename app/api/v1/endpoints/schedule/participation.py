from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.models.gym import Gym

router = APIRouter()

@router.post("/register/{session_id}", response_model=ClassParticipation)
async def register_for_class(
    session_id: int = Path(..., description="ID of the session"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["register:classes"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Register Current User for a Class Session

    Registers the currently authenticated user for a specific class session.

    Args:
        session_id (int): The ID of the class session to register for.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["register:classes"]).
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


@router.post("/register/{session_id}/{member_id}", response_model=ClassParticipation)
async def register_member_for_class(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member to register"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
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
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["manage:class_registrations"]).
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


@router.post("/cancel-registration/{session_id}", response_model=ClassParticipation)
async def cancel_my_registration(
    session_id: int = Path(..., description="ID of the session"),
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["register:classes"]),
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
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["register:classes"]).
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


@router.post("/cancel-registration/{session_id}/{member_id}", response_model=ClassParticipation)
async def cancel_member_registration(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member whose registration to cancel"),
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
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
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["manage:class_registrations"]).
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


@router.post("/attendance/{session_id}/{member_id}", response_model=ClassParticipation)
async def mark_attendance(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member who attended"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
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
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["manage:class_registrations"]).
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


@router.post("/mark-no-show/{session_id}/{member_id}", response_model=ClassParticipation)
async def mark_no_show(
    session_id: int = Path(..., description="ID of the session"),
    member_id: int = Path(..., description="ID of the member who was a no-show"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
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
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["manage:class_registrations"]).
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


@router.get("/participants/{session_id}", response_model=List[ClassParticipation])
async def get_session_participants(
    session_id: int = Path(..., description="ID of the session"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
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
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["manage:class_registrations"]).
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
    user: Auth0User = Security(auth.get_user, scopes=["read:own_schedules"]),
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
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["read:own_schedules"]).
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
    return await class_participation_service.get_member_upcoming_classes(
        db, member_id=db_user.id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    )


@router.get("/member-classes/{member_id}", response_model=List[Dict[str, Any]])
async def get_member_upcoming_classes(
    member_id: int = Path(..., description="ID of the member"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
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
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["manage:class_registrations"]).
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
    return await class_participation_service.get_member_upcoming_classes(
        db, member_id=member_id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    ) 