from app.api.v1.endpoints.schedule.common import *

router = APIRouter()

@router.get("/classes", response_model=List[Class])
async def get_classes(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener todas las clases.
    Requiere el scope 'read:schedules'.
    """
    return class_service.get_classes(db, skip=skip, limit=limit, active_only=active_only)


@router.get("/classes/{class_id}", response_model=ClassWithSessions)
async def get_class(
    class_id: int = Path(..., description="ID de la clase"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener una clase específica con sus sesiones.
    Requiere el scope 'read:schedules'.
    """
    class_obj = class_service.get_class(db, class_id=class_id)
    
    # Obtener sesiones de la clase
    sessions = class_session_service.get_sessions_by_class(db, class_id=class_id)
    
    # Crear respuesta con sesiones
    response = class_obj.__dict__.copy()
    response["sessions"] = sessions
    
    return response


@router.post("/classes", response_model=Class)
async def create_class(
    class_data: ClassCreate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"])
) -> Any:
    """
    Crear una nueva clase.
    Requiere el scope 'create:schedules' asignado a entrenadores y administradores.
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    return class_service.create_class(
        db, class_data=class_data, created_by_id=created_by_id
    )


@router.put("/classes/{class_id}", response_model=Class)
async def update_class(
    class_id: int = Path(..., description="ID de la clase"),
    class_data: ClassUpdate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Actualizar una clase existente.
    Requiere el scope 'update:schedules' asignado a entrenadores y administradores.
    """
    return class_service.update_class(db, class_id=class_id, class_data=class_data)


@router.delete("/classes/{class_id}", response_model=Class)
async def delete_class(
    class_id: int = Path(..., description="ID de la clase"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["delete:schedules"])
) -> Any:
    """
    Eliminar una clase.
    Requiere el scope 'delete:schedules' asignado a administradores.
    
    Nota: Si la clase tiene sesiones programadas, se marcará como inactiva en lugar de eliminarla.
    """
    return class_service.delete_class(db, class_id=class_id)


@router.get("/classes/category/{category}", response_model=List[Class])
async def get_classes_by_category(
    category: ClassCategory = Path(..., description="Categoría de la clase"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener clases por categoría.
    Requiere el scope 'read:schedules'.
    """
    return class_service.get_classes_by_category(
        db, category=category, skip=skip, limit=limit
    )


@router.get("/classes/difficulty/{difficulty}", response_model=List[Class])
async def get_classes_by_difficulty(
    difficulty: ClassDifficultyLevel = Path(..., description="Nivel de dificultad de la clase"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener clases por nivel de dificultad.
    Requiere el scope 'read:schedules'.
    """
    return class_service.get_classes_by_difficulty(
        db, difficulty=difficulty, skip=skip, limit=limit
    )


@router.get("/classes/search", response_model=List[Class])
async def search_classes(
    query: str = Query(..., description="Texto a buscar"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Buscar clases por nombre o descripción.
    Requiere el scope 'read:schedules'.
    """
    return class_service.search_classes(
        db, search=query, skip=skip, limit=limit
    ) 