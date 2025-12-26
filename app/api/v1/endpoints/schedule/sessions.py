from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.core.dependencies import module_enabled
from app.models.gym import Gym
from app.models.user import UserRole
from app.models.user_gym import GymRoleType
from app.services.gym import gym_service
from app.schemas.schedule import ClassSessionWithTimezone, format_session_with_timezone, SessionWithClassAndTimezone, format_session_with_class_and_timezone

router = APIRouter()

@router.get("/sessions", response_model=List[SessionWithClass])
async def get_upcoming_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Upcoming Class Sessions

    Retrieves a list of upcoming (scheduled and future) class sessions for the current gym.

    Timezone
    - start_time/end_time are stored in UTC.
    - The response populates `session.timezone` (gym TZ) and `session.start_time_local`/`end_time_local` (gym local).
    - Clients should render the local fields or convert from UTC using the provided timezone.

    Args:
        skip (int, optional): Number of records to skip for pagination. Defaults to 0.
        limit (int, optional): Maximum number of records to return. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[SessionWithClass]: A list of upcoming class session objects.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym not found.
    """
    # Obtener las sesiones próximas
    upcoming = await class_session_service.get_upcoming_sessions(
        db,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Poblar campos timezone para las sesiones
    from app.services.schedule import populate_sessions_with_timezone
    sessions_with_tz = await populate_sessions_with_timezone(upcoming, current_gym.id, db)

    # Para cada sesión, obtener la definición de la clase y empaquetar
    results: List[SessionWithClass] = []
    for i, sess in enumerate(upcoming):
        try:
            class_obj = await class_service.get_class(
                db,
                class_id=sess.class_id,
                gym_id=current_gym.id,
                redis_client=redis_client
            )
        except Exception:
            class_obj = None

        # Usar la sesión con timezone de nuestro array poblado
        session_with_tz_dict = sessions_with_tz[i]
        session_schema = ClassSession.model_validate(session_with_tz_dict)
        class_schema = Class.model_validate(class_obj) if class_obj else None
        results.append(SessionWithClass(session=session_schema, class_info=class_schema))

    return results


@router.get("/sessions-with-timezone", response_model=List[SessionWithClassAndTimezone])
async def get_upcoming_sessions_with_timezone(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Upcoming Class Sessions with Timezone Information
    
    Retrieves a list of upcoming class sessions with timezone information
    and their associated class details. Same format as /date-range but with timezone info.

    Timezone
    - Adds `session.gym_timezone` and `session.time_info`.
    - `session.time_info.local_time` is the gym-local start time; `utc_time` is the UTC instant.
    - Also includes `session.start_time_local`/`end_time_local` for convenience.
    
    Args:
        skip (int): Records to skip for pagination
        limit (int): Maximum records to return  
        db: Database session
        current_gym: Current gym context
        user: Authenticated user
        redis_client: Redis client
        
    Returns:
        List[SessionWithClassAndTimezone]: Sessions with class info and timezone data
        
    Example Response:
        [{
            "session": {
                "id": 837,
                "start_time": "2025-07-27T17:00:00",
                "gym_timezone": "America/New_York",
                "time_info": {
                    "local_time": "2025-07-27T17:00:00",
                    "gym_timezone": "America/New_York",
                    "iso_with_timezone": "2025-07-27T17:00:00-04:00",
                    "utc_time": "2025-07-27T21:00:00+00:00"
                }
                // ... other session fields
            },
            "class_info": {
                "id": 145,
                "name": "Cardio Hit",
                // ... other class fields
            }
        }]
    """
    # Obtener las sesiones próximas
    upcoming = await class_session_service.get_upcoming_sessions(
        db,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Para cada sesión, obtener la clase y formatear con timezone
    results: List[SessionWithClassAndTimezone] = []
    for sess in upcoming:
        try:
            class_obj = await class_service.get_class(
                db,
                class_id=sess.class_id,
                gym_id=current_gym.id,
                redis_client=redis_client
            )
        except Exception:
            class_obj = None

        if class_obj:
            session_with_class_tz = format_session_with_class_and_timezone(
                sess, class_obj, current_gym.timezone
            )
            results.append(session_with_class_tz)

    return results


@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session_with_details(
    session_id: int = Path(..., description="ID of the session"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Specific Session with Details

    Retrieves details of a specific class session, including associated class information
    and current participation/availability status (registered count, spots left).

    Args:
        session_id (int): The ID of the class session.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        Dict[str, Any]: A dictionary containing:
                         - `session`: The ClassSessionSchema object.
                         - `class`: The ClassSchema object for the session's class.
                         - `registered_count`: Number of currently registered participants.
                         - `available_spots`: Number of spots remaining.
                         - `is_full`: Boolean indicating if the session has reached max capacity.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Session or Gym not found, or session doesn't belong to this gym.
    """
    # Service method verifies session belongs to the gym
    session_details = await class_session_service.get_session_with_details(
        db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not session_details:
        # Handle case where service returns None (e.g., not found)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found in this gym")
    return session_details


@router.post("/sessions", response_model=ClassSession, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: ClassSessionCreate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Create Single Class Session

    Creates a new, single instance of a class session.

    Args:
        session_data (ClassSessionCreate): Data for the new session.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'create:schedules' scope.

    Request Body (ClassSessionCreate):
        {
          "class_id": integer,
          "trainer_id": integer,
          "start_time": "YYYY-MM-DDTHH:MM:SSZ (ISO 8601)",
          "end_time": "YYYY-MM-DDTHH:MM:SSZ (optional, calculated if omitted)",
          "room": "string (optional)",
          "status": "string (scheduled|in_progress|completed|cancelled, default: scheduled)",
          "notes": "string (optional)"
        }

    Returns:
        ClassSessionSchema: The newly created class session object.

    Raises:
        HTTPException 400: Invalid data (e.g., class inactive, end_time before start_time).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym, Class, or Trainer not found, or class/trainer doesn't belong to gym.
        HTTPException 422: Validation error in request body.
    """
    # Get current user's local ID
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    created_by_id = db_user.id if db_user else None

    # Verify class exists, is active, and belongs to the gym (service does this)
    # Verify trainer exists and belongs to the gym
    if session_data.trainer_id:
        trainer_membership = await user_service.check_user_gym_membership_cached(
            db=db, user_id=session_data.trainer_id, gym_id=current_gym.id, redis_client=redis_client
        )
        if not trainer_membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trainer not found in this gym"
            )

    # Logging de entrada - mostrar datos recibidos
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📅 CREATE SESSION - Gym: {current_gym.name} (ID: {current_gym.id})")
    logger.info(f"   Timezone del gimnasio: {current_gym.timezone}")
    logger.info(f"   Datos recibidos del frontend:")
    logger.info(f"     start_time: {session_data.start_time}")
    logger.info(f"     end_time: {session_data.end_time}")
    logger.info(f"     start_time type: {type(session_data.start_time)}")
    logger.info(f"     start_time tzinfo: {getattr(session_data.start_time, 'tzinfo', 'No tzinfo')}")

    # Service handles gym_id assignment, end_time calculation, and creation
    new_session = await class_session_service.create_session(
        db, session_data=session_data, gym_id=current_gym.id, created_by_id=created_by_id, redis_client=redis_client
    )

    # Logging después de crear en DB
    logger.info(f"   Datos guardados en DB:")
    logger.info(f"     start_time: {new_session.start_time}")
    logger.info(f"     end_time: {new_session.end_time}")
    logger.info(f"     start_time type: {type(new_session.start_time)}")
    logger.info(f"     start_time tzinfo: {getattr(new_session.start_time, 'tzinfo', 'No tzinfo')}")

    # Poblar campos timezone para la nueva sesión
    from app.services.schedule import populate_sessions_with_timezone
    sessions_with_tz = await populate_sessions_with_timezone([new_session], current_gym.id, db)

    # Logging de la respuesta final
    from app.schemas.schedule import ClassSession
    if sessions_with_tz:
        final_response = ClassSession.model_validate(sessions_with_tz[0])
        logger.info(f"   Respuesta final al frontend:")
        logger.info(f"     start_time: {final_response.start_time}")
        logger.info(f"     end_time: {final_response.end_time}")
        logger.info(f"     timezone: {final_response.timezone}")
        logger.info(f"     start_time_local: {final_response.start_time_local}")
        logger.info(f"     end_time_local: {final_response.end_time_local}")
        return final_response
    else:
        final_response = ClassSession.model_validate(new_session)
        logger.info(f"   Respuesta final al frontend (sin timezone):")
        logger.info(f"     start_time: {final_response.start_time}")
        logger.info(f"     end_time: {final_response.end_time}")
        return final_response


@router.post("/sessions/recurring", response_model=List[ClassSession])
async def create_recurring_sessions(
    base_session_data: ClassSessionCreate = Body(..., alias="base_session"),
    start_date: date = Body(..., description="Start date for recurrence"),
    end_date: date = Body(..., description="End date for recurrence"),
    days_of_week: List[int] = Body(
        ..., description="Days of week (0=Mon, 6=Sun)", example=[0, 2, 4]
    ),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Create Recurring Class Sessions

    Creates multiple class sessions based on a template, date range, and specified days of the week.

    Args:
        base_session_data (ClassSessionCreate): Template data (class_id, trainer_id, time, room, etc.).
        start_date (date): First date to potentially create a session.
        end_date (date): Last date to potentially create a session.
        days_of_week (List[int]): List of integers representing days (0=Monday, 6=Sunday) for recurrence.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'create:schedules' scope (typically for trainers/admins).

    Request Body:
        {
          "base_session": {
            "class_id": integer,
            "trainer_id": integer,
            "start_time": "YYYY-MM-DDTHH:MM:SSZ" /* Time part used for recurrence */,
            "room": "string (optional)",
            "notes": "string (optional)"
          },
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "days_of_week": [integer] /* 0-6 */
        }

    Returns:
        List[ClassSessionSchema]: A list of all the created class session objects.

    Raises:
        HTTPException 400: Invalid data (e.g., end_date before start_date, invalid days_of_week).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym, Class, or Trainer not found, or class/trainer doesn't belong to gym.
        HTTPException 422: Validation error in request body.
    """
    # Logging de entrada para sesiones recurrentes
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📅 CREATE RECURRING SESSIONS - Gym: {current_gym.name} (ID: {current_gym.id})")
    logger.info(f"   Timezone del gimnasio: {current_gym.timezone}")
    logger.info(f"   Datos recibidos del frontend:")
    logger.info(f"     base_session start_time: {base_session_data.start_time}")
    logger.info(f"     base_session end_time: {base_session_data.end_time}")
    logger.info(f"     start_date: {start_date}")
    logger.info(f"     end_date: {end_date}")
    logger.info(f"     days_of_week: {days_of_week}")
    logger.info(f"     start_time type: {type(base_session_data.start_time)}")
    logger.info(f"     start_time tzinfo: {getattr(base_session_data.start_time, 'tzinfo', 'No tzinfo')}")

    # Get current user's local ID
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)
    created_by_id = db_user.id if db_user else None

    # Service handles validation of class/trainer, date logic, and creation
    created_sessions = await class_session_service.create_recurring_sessions(
        db,
        base_session_data=base_session_data,
        start_date=start_date,
        end_date=end_date,
        days_of_week=days_of_week,
        created_by_id=created_by_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Logging después de crear las sesiones
    logger.info(f"   ✅ Creadas {len(created_sessions)} sesiones recurrentes")
    if created_sessions:
        first_session = created_sessions[0]
        logger.info(f"   Ejemplo - Primera sesión guardada en DB:")
        logger.info(f"     start_time: {first_session.start_time}")
        logger.info(f"     end_time: {first_session.end_time}")
        logger.info(f"     start_time type: {type(first_session.start_time)}")
        logger.info(f"     start_time tzinfo: {getattr(first_session.start_time, 'tzinfo', 'No tzinfo')}")

    # Poblar campos timezone para todas las sesiones
    from app.services.schedule import populate_sessions_with_timezone
    sessions_with_tz = await populate_sessions_with_timezone(created_sessions, current_gym.id, db)

    # Logging de la respuesta final
    from app.schemas.schedule import ClassSession
    if sessions_with_tz:
        final_sessions = [ClassSession.model_validate(session_dict) for session_dict in sessions_with_tz]
        if final_sessions:
            logger.info(f"   Respuesta final al frontend - Ejemplo primera sesión:")
            first_response = final_sessions[0]
            logger.info(f"     start_time: {first_response.start_time}")
            logger.info(f"     end_time: {first_response.end_time}")
            logger.info(f"     timezone: {first_response.timezone}")
            logger.info(f"     start_time_local: {first_response.start_time_local}")
            logger.info(f"     end_time_local: {first_response.end_time_local}")
        return final_sessions
    else:
        final_sessions = [ClassSession.model_validate(session) for session in created_sessions]
        logger.info(f"   Respuesta final al frontend (sin timezone): {len(final_sessions)} sesiones")
        return final_sessions


@router.put("/sessions/{session_id}", response_model=ClassSession)
async def update_session(
    session_id: int = Path(..., description="ID of the session"),
    session_data: ClassSessionUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update Class Session

    Updates details of an existing class session.

    Args:
        session_id (int): The ID of the session to update.
        session_data (ClassSessionUpdate): Fields to update.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'update:schedules' scope (typically for trainers/admins).

    Request Body (ClassSessionUpdate - all fields optional):
        {
          "class_id": integer,
          "trainer_id": integer,
          "start_time": "YYYY-MM-DDTHH:MM:SSZ",
          "end_time": "YYYY-MM-DDTHH:MM:SSZ",
          "room": "string",
          "status": "string (scheduled|in_progress|completed|cancelled)",
          "notes": "string"
        }

    Returns:
        ClassSessionSchema: The updated class session object.

    Raises:
        HTTPException 400: Invalid data (e.g., end_time before start_time).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session, Gym, or referenced Class/Trainer not found/valid in gym.
        HTTPException 422: Validation error in request body.
    """
    # Service layer handles checking session ownership and performing update
    return await class_session_service.update_session(
        db, session_id=session_id, session_data=session_data, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/sessions/{session_id}/cancel", response_model=ClassSession)
async def cancel_session(
    session_id: int = Path(..., description="ID of the session"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Cancel Class Session

    Marks a scheduled class session as cancelled.

    Args:
        session_id (int): The ID of the session to cancel.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'update:schedules' scope (typically for trainers/admins).

    Returns:
        ClassSessionSchema: The session object with status updated to CANCELLED.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session or Gym not found, or session doesn't belong to this gym.
    """
    # Service layer handles checking session ownership and updating status
    return await class_session_service.cancel_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)


@router.get("/date-range", response_model=List[SessionWithClass])
async def get_sessions_by_date_range(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Sessions by Date Range (with Class)

    Devuelve las sesiones programadas dentro de un rango de fechas **incluyendo**
    la definición completa de la clase asociada. Cada elemento de la lista
    combina:

    • ``session`` – objeto ``ClassSession`` (instancia concreta)
    • ``class_info`` – objeto ``Class`` (plantilla de la clase)

    Args:
        start_date (date): The start date of the range (YYYY-MM-DD).
        end_date (date): The end date of the range (YYYY-MM-DD).
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Timezone
    - `start_date`/`end_date` se interpretan en la zona horaria del gimnasio.
    - La respuesta incluye `session.timezone` y `session.start_time_local`/`end_time_local`.

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[SessionWithClass]: Lista de objetos compuestos ``SessionWithClass``.

    Raises:
        HTTPException 400: Invalid date range (e.g., end_date before start_date).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym not found.
        HTTPException 422: Invalid date format in query parameters.
    """
    sessions = await class_session_service.get_sessions_by_date_range(
        db,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    # Poblar campos timezone en bloque
    from app.services.schedule import populate_sessions_with_timezone
    sessions_with_tz = await populate_sessions_with_timezone(sessions, current_gym.id, db)

    results: List[SessionWithClass] = []
    for i, sess in enumerate(sessions):
        try:
            class_obj = await class_service.get_class(
                db,
                class_id=sess.class_id,
                gym_id=current_gym.id,
                redis_client=redis_client
            )
        except Exception:
            class_obj = None

        session_schema = ClassSession.model_validate(sessions_with_tz[i])
        class_schema = Class.model_validate(class_obj) if class_obj else None
        results.append(SessionWithClass(session=session_schema, class_info=class_schema))

    return results


@router.get("/date-range-with-timezone", response_model=List[SessionWithClassAndTimezone])
async def get_sessions_by_date_range_with_timezone(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Sessions by Date Range with Timezone Information
    
    Devuelve las sesiones programadas dentro de un rango de fechas **incluyendo**
    información completa de timezone y detalles de clase. Mismo formato que 
    /date-range pero con información de timezone.
    
    Args:
        start_date (date): Fecha de inicio del rango (YYYY-MM-DD)
        end_date (date): Fecha de fin del rango (YYYY-MM-DD)
        skip (int): Registros a omitir para paginación
        limit (int): Máximo número de registros
        db: Sesión de base de datos
        current_gym: Contexto del gimnasio actual
        user: Usuario autenticado
        redis_client: Cliente Redis
        
    Timezone
    - Igual que /date-range, pero además añade `session.gym_timezone` y `session.time_info` con
      las representaciones local/UTC de manera explícita.

    Returns:
        List[SessionWithClassAndTimezone]: Sesiones con clase e información de timezone
        
    Response Format:
        [{
            "session": {
                "id": 837,
                "start_time": "2025-07-27T17:00:00",
                "gym_timezone": "America/New_York",
                "time_info": {
                    "local_time": "2025-07-27T17:00:00",
                    "gym_timezone": "America/New_York",
                    "iso_with_timezone": "2025-07-27T17:00:00-04:00",
                    "utc_time": "2025-07-27T21:00:00+00:00"
                }
                // ... otros campos de sesión
            },
            "class_info": {
                "id": 145,
                "name": "Cardio Hit",
                // ... otros campos de clase
            }
        }]
    """
    # Obtener sesiones del rango de fechas
    sessions = await class_session_service.get_sessions_by_date_range(
        db,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Para cada sesión, obtener la clase y formatear con timezone
    results: List[SessionWithClassAndTimezone] = []
    for sess in sessions:
        try:
            class_obj = await class_service.get_class(
                db,
                class_id=sess.class_id,
                gym_id=current_gym.id,
                redis_client=redis_client
            )
        except Exception:
            class_obj = None

        if class_obj:
            session_with_class_tz = format_session_with_class_and_timezone(
                sess, class_obj, current_gym.timezone
            )
            results.append(session_with_class_tz)

    return results


@router.get("/trainer/{trainer_id}", response_model=List[ClassSession])
async def get_trainer_sessions(
    trainer_id: int = Path(..., description="ID of the trainer"),
    upcoming_only: bool = Query(False, description="Only return future sessions"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Sessions by Trainer

    Retrieves class sessions assigned to a specific trainer within the current gym.
    Can optionally filter for only upcoming sessions.

    Timezone
    - Respuesta incluye `timezone` y `start_time_local`/`end_time_local` por sesión.

    Args:
        trainer_id (int): The ID of the trainer whose sessions are requested.
        upcoming_only (bool, optional): If true, only returns sessions starting from now. Defaults to False.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Requires 'read:schedules' or 
                                    'read:trainer_schedules' if viewing another trainer's schedule.
                                    Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.
        - To view another trainer's schedule, requires one of the following:
          * 'read:trainer_schedules' scope
          * User is a SuperAdmin
          * User is an Admin or Owner of the gym
          * User is viewing their own schedule

    Returns:
        List[ClassSessionSchema]: A list of session objects taught by the specified trainer.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Insufficient permissions to view this trainer's schedule.
        HTTPException 404: Gym or Trainer not found, or trainer doesn't belong to this gym.
    """
    # Check permissions: Allow if user is the requested trainer, a SuperAdmin, or has specific permission
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    is_own_schedule = db_user and db_user.id == trainer_id
    is_super_admin = db_user and db_user.role == UserRole.SUPER_ADMIN # Assuming UserRole enum exists
    has_permission = "read:trainer_schedules" in (getattr(user, "permissions", []) or [])
    
    # Verificar si el usuario es ADMIN u OWNER en este gimnasio
    is_gym_admin_or_owner = False
    if db_user:
        # Verificar el rol del usuario en este gimnasio usando el servicio
        user_gym_membership = await user_service.check_user_gym_membership_cached(
            db=db, user_id=db_user.id, gym_id=current_gym.id, redis_client=redis_client
        )
        # Verificar si tiene rol ADMIN u OWNER
        if user_gym_membership:
            # user_gym_membership puede ser un objeto o un diccionario dependiendo de la fuente
            role = user_gym_membership.role if hasattr(user_gym_membership, 'role') else user_gym_membership.get('role')
            if role in [GymRoleType.ADMIN, GymRoleType.OWNER]:
                is_gym_admin_or_owner = True

    if not (is_own_schedule or is_super_admin or has_permission or is_gym_admin_or_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this trainer's schedule"
        )

    # Verify trainer exists in the current gym
    trainer_membership = await user_service.check_user_gym_membership_cached(
        db=db, user_id=trainer_id, gym_id=current_gym.id, redis_client=redis_client
    )
    if not trainer_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trainer not found in this gym"
        )

    base = await class_session_service.get_sessions_by_trainer(
        db,
        trainer_id=trainer_id,
        skip=skip,
        limit=limit,
        upcoming_only=upcoming_only,
        gym_id=current_gym.id,
        redis_client=redis_client
    )
    # Poblar timezone
    from app.services.schedule import populate_sessions_with_timezone
    sessions_with_tz = await populate_sessions_with_timezone(base, current_gym.id, db)
    from app.schemas.schedule import ClassSession
    return [ClassSession.model_validate(s) for s in sessions_with_tz]


@router.get("/my-sessions", response_model=List[ClassSession])
async def get_my_sessions(
    upcoming_only: bool = Query(True, description="Only return future sessions"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get My Sessions (for Trainers)

    Retrieves the calling user's (who must be a trainer) class sessions within the current gym.
    Can optionally filter for only upcoming sessions.

    Timezone
    - Respuesta incluye campos locales (`timezone`, `start_time_local`, `end_time_local`).

    Args:
        upcoming_only (bool, optional): If true, only returns sessions starting from now. Defaults to True.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:own_schedules' scope (intended for trainers).

    Returns:
        List[ClassSessionSchema]: A list of the calling user's session objects.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user is not found/not a trainer in this gym.
        HTTPException 404: Gym not found or User not found.
    """
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Optionally verify the user has a trainer role within the gym if the scope isn't sufficient
    # trainer_membership = await user_service.check_user_gym_membership_cached(...) # Example
    # if not trainer_membership or trainer_membership.role != GymRoleType.TRAINER:
    #    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a trainer in this gym")

    # Obtener sesiones del trainer
    trainer_sessions = await class_session_service.get_sessions_by_trainer(
        db,
        trainer_id=db_user.id,
        skip=skip,
        limit=limit,
        upcoming_only=upcoming_only,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Poblar campos timezone para las sesiones
    from app.services.schedule import populate_sessions_with_timezone
    sessions_with_tz = await populate_sessions_with_timezone(trainer_sessions, current_gym.id, db)

    # Convertir a esquemas ClassSession
    from app.schemas.schedule import ClassSession
    return [ClassSession.model_validate(session_dict) for session_dict in sessions_with_tz]


@router.delete("/sessions/{session_id}", response_model=ClassSession)
async def delete_session(
    session_id: int = Path(..., description="ID of the session"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Delete Class Session

    Deletes a class session. If participants are already registered, the session
    is marked as CANCELLED instead of being deleted.

    Args:
        session_id (int): The ID of the session to delete/cancel.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'delete:schedules' scope (typically for admins).

    Returns:
        ClassSessionSchema: The deleted or cancelled session object.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Session or Gym not found, or session doesn't belong to this gym.
    """
    # Service layer handles checking ownership and deciding whether to delete or cancel
    # Based on the logic in the original endpoint code

    # Get session and verify ownership first
    session = await class_session_service.get_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    if not session:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found in this gym")

    # Check for participants
    participants = await class_participation_service.get_session_participants(db, session_id=session_id, gym_id=current_gym.id, limit=1, redis_client=redis_client)

    if participants:
        # Cancel if participants exist
        return await class_session_service.cancel_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    else:
        # Delete if no participants
        deleted_session = class_session_repository.remove(db, id=session_id)
        # Invalidate cache after deletion (consider adding to service layer)
        await class_session_service._invalidate_session_caches(redis_client, gym_id=current_gym.id, session_id=session_id)
        return deleted_session 
