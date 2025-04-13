from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.models.gym import Gym
from app.services.gym import gym_service

router = APIRouter()

@router.get("/sessions", response_model=List[ClassSession])
async def get_upcoming_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener las próximas sesiones de clase programadas.
    Requiere el scope 'read:schedules'.
    """
    return class_session_service.get_upcoming_sessions(
        db, 
        skip=skip, 
        limit=limit, 
        gym_id=current_gym.id
    )


@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session_with_details(
    session_id: int = Path(..., description="ID de la sesión"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener una sesión específica con detalles de clase y disponibilidad.
    Requiere el scope 'read:schedules'.
    """
    # Verificar que la sesión pertenezca al gimnasio actual
    session = class_session_service.get_session(db, session_id=session_id)
    if not session or session.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    return class_session_service.get_session_with_details(db, session_id=session_id)


@router.post("/sessions", response_model=ClassSession)
async def create_session(
    session_data: ClassSessionCreate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"])
) -> Any:
    """
    Crear una nueva sesión de clase.
    
    Esta ruta permite crear una sesión específica para una clase.
    Una sesión representa una instancia concreta de la clase en un momento
    y lugar determinado.
    
    Requiere:
    - Scope 'create:schedules' en Auth0
    - Pertenencia al gimnasio actual
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    # Verificar que la clase existe y pertenece al gimnasio actual
    class_obj = class_service.get_class(db, class_id=session_data.class_id)
    if not class_obj or class_obj.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada en este gimnasio"
        )
    
    # Si el entrenador es diferente al usuario actual, verificar que existe
    # y pertenece al gimnasio
    if db_user and session_data.trainer_id != db_user.id:
        print(f"DEBUG: Verificando entrenador {session_data.trainer_id} en gimnasio {current_gym.id}")
        trainer_exists = gym_service.check_user_in_gym(
            db, user_id=session_data.trainer_id, gym_id=current_gym.id
        )
        print(f"DEBUG: Resultado de verificación: {trainer_exists}")
        if not trainer_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrenador no encontrado en este gimnasio"
            )
    
    # Asignar el gimnasio actual de forma explícita 
    session_dict = session_data.model_dump()
    session_dict["gym_id"] = current_gym.id
    
    # Forzar el gym_id - mostrar para depuración
    print(f"DEBUG: Asignando gym_id={current_gym.id} a la sesión")
    
    # Crear un nuevo objeto con el gym_id explícitamente asignado
    complete_session_data = ClassSessionCreate(**session_dict)
    
    # Doble verificación para asegurar que no se pierde
    assert complete_session_data.gym_id == current_gym.id, "Error: gym_id no se estableció correctamente"
    
    # Crear la sesión
    created_by_id = db_user.id if db_user else None
    return class_session_service.create_session(
        db, session_data=complete_session_data, created_by_id=created_by_id
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
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"]),
    current_gym: Gym = Depends(verify_gym_access)
) -> Any:
    """
    Crear sesiones recurrentes en un rango de fechas.
    Requiere el scope 'create:schedules' asignado a entrenadores y administradores.
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    # Asignar el gym_id desde el tenant actual
    session_obj = base_session.model_dump()
    session_obj["gym_id"] = current_gym.id
    
    # Crear un nuevo objeto ClassSessionCreate con el gym_id establecido
    updated_base_session = ClassSessionCreate(**session_obj)
    
    return class_session_service.create_recurring_sessions(
        db, 
        base_session_data=updated_base_session,
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
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Actualizar una sesión existente.
    Requiere el scope 'update:schedules' asignado a entrenadores y administradores.
    """
    # Verificar que la sesión pertenezca al gimnasio actual
    session = class_session_service.get_session(db, session_id=session_id)
    if not session or session.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    return class_session_service.update_session(
        db, session_id=session_id, session_data=session_data
    )


@router.post("/sessions/{session_id}/cancel", response_model=ClassSession)
async def cancel_session(
    session_id: int = Path(..., description="ID de la sesión"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Cancelar una sesión.
    Requiere el scope 'update:schedules' asignado a entrenadores y administradores.
    """
    # Verificar que la sesión pertenezca al gimnasio actual
    session = class_session_service.get_session(db, session_id=session_id)
    if not session or session.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    return class_session_service.cancel_session(db, session_id=session_id)


@router.get("/sessions/date-range", response_model=List[ClassSession])
async def get_sessions_by_date_range(
    start_date: date = Query(..., description="Fecha de inicio"),
    end_date: date = Query(..., description="Fecha de fin"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener sesiones en un rango de fechas.
    Requiere el scope 'read:schedules'.
    """
    return class_session_service.get_sessions_by_date_range(
        db, 
        start_date=start_date, 
        end_date=end_date, 
        skip=skip, 
        limit=limit,
        gym_id=current_gym.id
    )


@router.get("/sessions/trainer/{trainer_id}", response_model=List[ClassSession])
async def get_trainer_sessions(
    trainer_id: int = Path(..., description="ID del entrenador"),
    upcoming_only: bool = Query(False, description="Solo sesiones futuras"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
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
            db, 
            trainer_id=trainer_id, 
            skip=skip, 
            limit=limit, 
            upcoming_only=upcoming_only,
            gym_id=current_gym.id
        )
    
    # Si no es el propio entrenador o un administrador, verificar los permisos adicionales
    user_permissions = getattr(user, "permissions", []) or []
    if "read:trainer_schedules" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las sesiones de este entrenador"
        )
    
    return class_session_service.get_sessions_by_trainer(
        db, 
        trainer_id=trainer_id, 
        skip=skip, 
        limit=limit, 
        upcoming_only=upcoming_only,
        gym_id=current_gym.id
    )


@router.get("/my-sessions", response_model=List[ClassSession])
async def get_my_sessions(
    upcoming_only: bool = Query(True, description="Solo sesiones futuras"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
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
        db, 
        trainer_id=db_user.id, 
        skip=skip, 
        limit=limit, 
        upcoming_only=upcoming_only,
        gym_id=current_gym.id
    )


@router.delete("/sessions/{session_id}", response_model=ClassSession)
async def delete_session(
    session_id: int = Path(..., description="ID de la sesión"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["delete:schedules"])
) -> Any:
    """
    Eliminar una sesión.
    Requiere el scope 'delete:schedules' asignado a administradores.
    """
    # Obtener la sesión
    session = class_session_service.get_session(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada"
        )
    
    # Verificar que la sesión pertenezca al gimnasio actual
    if session.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    # Verificar si ya hay participantes registrados
    participants = class_participation_service.get_session_participants(db, session_id=session_id)
    if participants:
        # Si hay participantes, marcar como cancelada en lugar de eliminar
        return class_session_service.cancel_session(db, session_id=session_id)
    
    # Si no hay participantes, eliminar la sesión
    return class_session_repository.remove(db, id=session_id) 