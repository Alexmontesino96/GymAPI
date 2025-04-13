from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.models.gym import Gym

router = APIRouter()

@router.get("/classes", response_model=List[Class])
async def get_classes(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener todas las clases del gimnasio actual.
    Requiere el scope 'read:schedules'.
    """
    return class_service.get_classes(
        db, 
        skip=skip, 
        limit=limit, 
        active_only=active_only,
        gym_id=current_gym.id
    )


@router.get("/classes/{class_id}", response_model=ClassWithSessions)
async def get_class(
    class_id: int = Path(..., description="ID de la clase"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener una clase específica con sus sesiones.
    Requiere el scope 'read:schedules'.
    """
    class_obj = class_service.get_class(db, class_id=class_id)
    
    # Verificar que la clase pertenezca al gimnasio actual
    if not class_obj or class_obj.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada en este gimnasio"
        )
    
    # Obtener sesiones de la clase (solo las del gimnasio actual)
    sessions = class_session_service.get_sessions_by_class(db, class_id=class_id, gym_id=current_gym.id)
    
    # Crear respuesta con sesiones
    response = class_obj.__dict__.copy()
    response["sessions"] = sessions
    
    return response


@router.post("/classes", response_model=Class)
async def create_class(
    class_data: ClassCreate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"])
) -> Any:
    """
    Crear una nueva clase.
    
    Esta ruta permite crear una definición de clase que luego puede ser utilizada
    para programar sesiones específicas. La clase será asociada automáticamente
    al gimnasio actual y solo será visible para miembros de ese gimnasio.
    
    Requiere:
    - Scope 'create:schedules' en Auth0
    - Pertenencia al gimnasio actual
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    # Procesar los datos de entrada
    input_dict = class_data.model_dump(exclude_unset=True)
    
    # Eliminar 'category' si existe, ya ha sido procesado por el validador
    if 'category' in input_dict:
        del input_dict['category']
    
    # Verificar si usa una categoría personalizada del gimnasio
    if class_data.category_id:
        # Verificar que la categoría pertenezca al gimnasio actual
        from app.models.schedule import ClassCategoryCustom
        category = db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.id == class_data.category_id,
            ClassCategoryCustom.gym_id == current_gym.id
        ).first()
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La categoría seleccionada no pertenece a este gimnasio"
            )
    
    # Crear la clase con los datos procesados
    class_obj = ClassCreate(**input_dict)
    return class_service.create_class(
        db, 
        class_data=class_obj, 
        created_by_id=created_by_id,
        gym_id=current_gym.id  # Pasar explícitamente el ID del gimnasio
    )


@router.put("/classes/{class_id}", response_model=Class)
async def update_class(
    class_id: int = Path(..., description="ID de la clase"),
    class_data: ClassUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Actualizar una clase existente.
    Requiere el scope 'update:schedules' asignado a entrenadores y administradores.
    """
    # Obtener la clase
    class_obj = class_service.get_class(db, class_id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada"
        )
    
    # Verificar que la clase pertenezca al gimnasio actual
    if class_obj.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada en este gimnasio"
        )
    
    # Verificar si está actualizando la categoría
    if class_data.category_id:
        # Verificar que la nueva categoría pertenezca al gimnasio actual
        from app.models.schedule import ClassCategoryCustom
        category = db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.id == class_data.category_id
        ).first()
        
        if not category or category.gym_id != current_gym.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La categoría seleccionada no pertenece a este gimnasio"
            )
    
    return class_service.update_class(db, class_id=class_id, class_data=class_data)


@router.delete("/classes/{class_id}", response_model=Class)
async def delete_class(
    class_id: int = Path(..., description="ID de la clase"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["delete:schedules"])
) -> Any:
    """
    Eliminar una clase.
    Requiere el scope 'delete:schedules' asignado a administradores.
    
    Nota: Si la clase tiene sesiones programadas, se marcará como inactiva en lugar de eliminarla.
    """
    # Obtener la clase
    class_obj = class_service.get_class(db, class_id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada"
        )
    
    # Verificar que la clase pertenezca al gimnasio actual
    if class_obj.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada en este gimnasio"
        )
    
    return class_service.delete_class(db, class_id=class_id)


@router.get("/classes/category/{category}", response_model=List[Class])
async def get_classes_by_category(
    category: ClassCategory = Path(..., description="Categoría de la clase"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener clases por categoría.
    Requiere el scope 'read:schedules'.
    """
    return class_service.get_classes_by_category(
        db, 
        category=category, 
        skip=skip, 
        limit=limit,
        gym_id=current_gym.id
    )


@router.get("/classes/difficulty/{difficulty}", response_model=List[Class])
async def get_classes_by_difficulty(
    difficulty: ClassDifficultyLevel = Path(..., description="Nivel de dificultad de la clase"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener clases por nivel de dificultad.
    Requiere el scope 'read:schedules'.
    """
    return class_service.get_classes_by_difficulty(
        db, 
        difficulty=difficulty, 
        skip=skip, 
        limit=limit,
        gym_id=current_gym.id
    )


@router.get("/classes/search", response_model=List[Class])
async def search_classes(
    query: str = Query(..., description="Texto a buscar"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Buscar clases por nombre o descripción.
    Requiere el scope 'read:schedules'.
    """
    return class_service.search_classes(
        db, 
        search=query, 
        skip=skip, 
        limit=limit,
        gym_id=current_gym.id
    ) 