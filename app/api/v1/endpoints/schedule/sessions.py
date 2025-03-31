from app.api.v1.endpoints.schedule.common import *

router = APIRouter()

@router.get("/sessions", response_model=List[ClassSession])
async def get_upcoming_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener las próximas sesiones de clase programadas.
    Requiere el scope 'read:schedules'.
    """
    return class_session_service.get_upcoming_sessions(db, skip=skip, limit=limit)


@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session_with_details(
    session_id: int = Path(..., description="ID de la sesión"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener una sesión específica con detalles de clase y disponibilidad.
    Requiere el scope 'read:schedules'.
    """
    return class_session_service.get_session_with_details(db, session_id=session_id)


@router.post("/sessions", response_model=ClassSession)
async def create_session(
    session_data: ClassSessionCreate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"])
) -> Any:
    """
    Crear una nueva sesión de clase.
    Requiere el scope 'create:schedules' asignado a entrenadores y administradores.
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    return class_session_service.create_session(
        db, session_data=session_data, created_by_id=created_by_id
    )


@router.post("/sessions/recurring", response_model=List[ClassSession])
async def create_recurring_sessions(
    base_session: ClassSessionCreate = Body(...),
    start_date: date = Body(..., description="Fecha de inicio"),
    end_date: date = Body(..., description="Fecha de fin"),
    days_of_week: List[int] = Body(
        ..., description="Días de la semana (0=Lunes, 6=Domingo)"
    ),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"])
) -> Any:
    """
    Crear sesiones recurrentes en un rango de fechas.
    Requiere el scope 'create:schedules' asignado a entrenadores y administradores.
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    return class_session_service.create_recurring_sessions(
        db, 
        base_session_data=base_session,
        start_date=start_date,
        end_date=end_date,
        days_of_week=days_of_week,
        created_by_id=created_by_id
    )


@router.put("/sessions/{session_id}", response_model=ClassSession)
async def update_session(
    session_id: int = Path(..., description="ID de la sesión"),
    session_data: ClassSessionUpdate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Actualizar una sesión existente.
    Requiere el scope 'update:schedules' asignado a entrenadores y administradores.
    """
    return class_session_service.update_session(
        db, session_id=session_id, session_data=session_data
    )


@router.post("/sessions/{session_id}/cancel", response_model=ClassSession)
async def cancel_session(
    session_id: int = Path(..., description="ID de la sesión"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Cancelar una sesión.
    Requiere el scope 'update:schedules' asignado a entrenadores y administradores.
    """
    return class_session_service.cancel_session(db, session_id=session_id)


@router.get("/sessions/date-range", response_model=List[ClassSession])
async def get_sessions_by_date_range(
    start_date: date = Query(..., description="Fecha de inicio"),
    end_date: date = Query(..., description="Fecha de fin"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener sesiones en un rango de fechas.
    Requiere el scope 'read:schedules'.
    """
    return class_session_service.get_sessions_by_date_range(
        db, start_date=start_date, end_date=end_date, skip=skip, limit=limit
    )


@router.get("/sessions/trainer/{trainer_id}", response_model=List[ClassSession])
async def get_trainer_sessions(
    trainer_id: int = Path(..., description="ID del entrenador"),
    upcoming_only: bool = Query(False, description="Solo sesiones futuras"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener sesiones de un entrenador específico.
    Requiere el scope 'read:schedules'.
    """
    # Verificar si el usuario actual es el entrenador o un administrador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if db_user and (db_user.id == trainer_id or db_user.is_superuser):
        return class_session_service.get_sessions_by_trainer(
            db, trainer_id=trainer_id, skip=skip, limit=limit, upcoming_only=upcoming_only
        )
    
    # Si no es el propio entrenador o un administrador, verificar los permisos adicionales
    user_permissions = getattr(user, "permissions", []) or []
    if "read:trainer_schedules" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las sesiones de este entrenador"
        )
    
    return class_session_service.get_sessions_by_trainer(
        db, trainer_id=trainer_id, skip=skip, limit=limit, upcoming_only=upcoming_only
    )


@router.get("/my-sessions", response_model=List[ClassSession])
async def get_my_sessions(
    upcoming_only: bool = Query(True, description="Solo sesiones futuras"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:own_schedules"])
) -> Any:
    """
    Obtener las sesiones del entrenador actual.
    Requiere el scope 'read:own_schedules' asignado a entrenadores.
    """
    # Obtener ID del usuario actual
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos"
        )
    
    return class_session_service.get_sessions_by_trainer(
        db, trainer_id=db_user.id, skip=skip, limit=limit, upcoming_only=upcoming_only
    ) 