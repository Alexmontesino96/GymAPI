from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.models.gym import Gym

router = APIRouter()

@router.post("/register/{session_id}", response_model=ClassParticipation)
async def register_for_class(
    session_id: int = Path(..., description="ID de la sesión"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["register:classes"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Registrar al usuario actual en una sesión de clase.
    Requiere el scope 'register:classes' asignado a todos los usuarios.
    """
    # Obtener ID del usuario actual
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos"
        )
    
    # Verificar que la sesión pertenezca al gimnasio actual
    session = await class_session_service.get_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    return await class_participation_service.register_for_class(
        db, member_id=db_user.id, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/register/{session_id}/{member_id}", response_model=ClassParticipation)
async def register_member_for_class(
    session_id: int = Path(..., description="ID de la sesión"),
    member_id: int = Path(..., description="ID del miembro"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Registrar a un miembro específico en una sesión de clase (para administradores).
    Requiere el scope 'manage:class_registrations' asignado a entrenadores y administradores.
    """
    # Verificar que la sesión pertenezca al gimnasio actual
    session = await class_session_service.get_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    # Verificar que el miembro pertenezca al gimnasio actual
    user_gym = user_service.get_user_gym(db, user_id=member_id, gym_id=current_gym.id)
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado en este gimnasio"
        )
    
    return await class_participation_service.register_for_class(
        db, member_id=member_id, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/cancel-registration/{session_id}", response_model=ClassParticipation)
async def cancel_my_registration(
    session_id: int = Path(..., description="ID de la sesión"),
    reason: Optional[str] = Query(None, description="Razón de la cancelación"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["register:classes"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Cancelar el registro del usuario actual en una sesión.
    Requiere el scope 'register:classes' asignado a todos los usuarios.
    """
    # Obtener ID del usuario actual
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos"
        )
    
    # Verificar que la sesión pertenezca al gimnasio actual
    session = await class_session_service.get_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    return await class_participation_service.cancel_registration(
        db, member_id=db_user.id, session_id=session_id, reason=reason, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/cancel-registration/{session_id}/{member_id}", response_model=ClassParticipation)
async def cancel_member_registration(
    session_id: int = Path(..., description="ID de la sesión"),
    member_id: int = Path(..., description="ID del miembro"),
    reason: Optional[str] = Query(None, description="Razón de la cancelación"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Cancelar el registro de un miembro específico en una sesión (para administradores).
    Requiere el scope 'manage:class_registrations' asignado a entrenadores y administradores.
    """
    # Verificar que la sesión pertenezca al gimnasio actual
    session = await class_session_service.get_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    # Verificar que el miembro pertenezca al gimnasio actual
    user_gym = user_service.get_user_gym(db, user_id=member_id, gym_id=current_gym.id)
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado en este gimnasio"
        )
    
    return await class_participation_service.cancel_registration(
        db, member_id=member_id, session_id=session_id, reason=reason, gym_id=current_gym.id, redis_client=redis_client
    )


@router.post("/attendance/{session_id}/{user_id}", response_model=ClassParticipation)
async def mark_attendance(
    session_id: int,
    user_id: str,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["write:class_registrations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Mark a user as attended for a class session.
    """
    return await class_participation_service.mark_attendance(
        db, 
        session_id=session_id, 
        user_id=user_id, 
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.post("/mark-no-show/{session_id}/{member_id}", response_model=ClassParticipation)
async def mark_no_show(
    session_id: int = Path(..., description="ID de la sesión"),
    member_id: int = Path(..., description="ID del miembro"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Marcar que un miembro no asistió a una sesión.
    Requiere el scope 'manage:class_registrations' asignado a entrenadores y administradores.
    """
    # Verificar que la sesión pertenezca al gimnasio actual
    session = await class_session_service.get_session(db, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada en este gimnasio"
        )
    
    return await class_participation_service.mark_no_show(
        db, member_id=member_id, session_id=session_id, gym_id=current_gym.id, redis_client=redis_client
    )


@router.get("/participants/{session_id}", response_model=List[ClassParticipation])
async def get_session_participants(
    session_id: int,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:class_registrations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get all participants for a specific class session.
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
    
    return await class_participation_service.get_session_participants(
        db, 
        session_id=session_id, 
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
    Obtener las próximas clases del usuario actual.
    Requiere el scope 'read:own_schedules' asignado a todos los usuarios.
    """
    # Obtener ID del usuario actual
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos"
        )
    
    return await class_participation_service.get_member_upcoming_classes(
        db, member_id=db_user.id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    )


@router.get("/member-classes/{member_id}", response_model=List[Dict[str, Any]])
async def get_member_upcoming_classes(
    member_id: int = Path(..., description="ID del miembro"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["manage:class_registrations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtener las próximas clases de un miembro específico.
    Requiere el scope 'manage:class_registrations' asignado a entrenadores y administradores.
    """
    # Verificar que el miembro pertenezca al gimnasio actual
    user_gym = user_service.get_user_gym(db, user_id=member_id, gym_id=current_gym.id)
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado en este gimnasio"
        )
    
    return await class_participation_service.get_member_upcoming_classes(
        db, member_id=member_id, skip=skip, limit=limit, gym_id=current_gym.id, redis_client=redis_client
    ) 