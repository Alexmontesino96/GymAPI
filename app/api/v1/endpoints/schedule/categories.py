from app.api.v1.endpoints.schedule.common import *
from app.models.schedule import ClassCategoryCustom, Class
from app.schemas.schedule import ClassCategoryCustomCreate, ClassCategoryCustomUpdate, ClassCategoryCustom as ClassCategoryCustomSchema
from app.repositories.base import BaseRepository
from app.models.gym import Gym
from app.models.user_gym import GymRoleType
from app.core.tenant import verify_gym_access, verify_trainer_role, verify_admin_role

# Crear un repositorio para ClassCategoryCustom
class ClassCategoryCustomRepository(BaseRepository[ClassCategoryCustom, ClassCategoryCustomCreate, ClassCategoryCustomUpdate]):
    def get_by_gym(self, db: Session, *, gym_id: int) -> List[ClassCategoryCustom]:
        """Obtener categorías de clase personalizadas para un gimnasio específico"""
        return db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.gym_id == gym_id
        ).all()
    
    def get_active_categories(self, db: Session, *, gym_id: int) -> List[ClassCategoryCustom]:
        """Obtener categorías activas para un gimnasio específico"""
        return db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.gym_id == gym_id,
            ClassCategoryCustom.is_active == True
        ).all()
    
    def get_by_name_and_gym(self, db: Session, *, name: str, gym_id: int) -> Optional[ClassCategoryCustom]:
        """Verificar si existe una categoría con el mismo nombre en el mismo gimnasio"""
        return db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.name == name,
            ClassCategoryCustom.gym_id == gym_id
        ).first()

# Instanciar el repositorio
class_category_repository = ClassCategoryCustomRepository(ClassCategoryCustom)

# Crear un servicio para ClassCategoryCustom
class ClassCategoryService:
    def get_category(self, db: Session, category_id: int, gym_id: int) -> Any:
        """Obtener una categoría por ID asegurando que pertenece al gimnasio correcto"""
        category = class_category_repository.get(db, id=category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada"
            )
        
        # Verificar que la categoría pertenece al gimnasio actual
        if category.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta categoría"
            )
            
        return category
    
    def get_categories_by_gym(self, db: Session, gym_id: int, active_only: bool = True) -> List[Any]:
        """Obtener categorías para un gimnasio específico"""
        if active_only:
            return class_category_repository.get_active_categories(db, gym_id=gym_id)
        return class_category_repository.get_by_gym(db, gym_id=gym_id)
    
    def create_category(self, db: Session, category_data: ClassCategoryCustomCreate, gym_id: int, created_by_id: Optional[int] = None) -> Any:
        """Crear una nueva categoría personalizada"""
        # Verificar si ya existe una categoría con el mismo nombre en este gimnasio
        existing_category = class_category_repository.get_by_name_and_gym(
            db, name=category_data.name, gym_id=gym_id
        )
        if existing_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una categoría con este nombre en este gimnasio"
            )
        
        # Agregar ID del gimnasio y creador si se proporciona
        obj_in_data = category_data.model_dump()
        obj_in_data["gym_id"] = gym_id
        if created_by_id:
            obj_in_data["created_by"] = created_by_id
        
        return class_category_repository.create(db, obj_in=ClassCategoryCustomCreate(**obj_in_data))
    
    def update_category(self, db: Session, category_id: int, category_data: ClassCategoryCustomUpdate, gym_id: int) -> Any:
        """Actualizar una categoría existente"""
        # Obtener la categoría y verificar que pertenece al gimnasio correcto
        category = self.get_category(db, category_id=category_id, gym_id=gym_id)
        
        # Si se está actualizando el nombre, verificar que no exista otra categoría con ese nombre
        if category_data.name and category_data.name != category.name:
            existing_category = class_category_repository.get_by_name_and_gym(
                db, name=category_data.name, gym_id=gym_id
            )
            if existing_category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otra categoría con este nombre en este gimnasio"
                )
        
        return class_category_repository.update(db, db_obj=category, obj_in=category_data)
    
    def delete_category(self, db: Session, category_id: int, gym_id: int) -> Any:
        """Eliminar una categoría"""
        # Obtener la categoría y verificar que pertenece al gimnasio correcto
        category = self.get_category(db, category_id=category_id, gym_id=gym_id)
        
        # Verificar si hay clases usando esta categoría
        classes_with_category = db.query(Class).filter(Class.category_id == category_id).count()
        if classes_with_category > 0:
            # Si hay clases usando esta categoría, solo marcarla como inactiva
            return class_category_repository.update(
                db, db_obj=category, obj_in={"is_active": False}
            )
        
        return class_category_repository.remove(db, id=category_id)

# Instanciar el servicio
category_service = ClassCategoryService()

router = APIRouter()

@router.get("/categories", response_model=List[ClassCategoryCustomSchema])
async def get_categories(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener todas las categorías de clases personalizadas del gimnasio actual.
    
    Esta ruta devuelve la lista de categorías personalizadas disponibles,
    filtrando por el gimnasio actual para garantizar la separación de datos
    entre diferentes gimnasios.
    
    Parámetros:
    - active_only: Si es true (por defecto), solo muestra categorías activas
    
    Requiere:
    - Scope 'read:schedules' en Auth0
    - Pertenencia al gimnasio actual
    """
    return category_service.get_categories_by_gym(db, gym_id=current_gym.id, active_only=active_only)


@router.get("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def get_category(
    category_id: int = Path(..., description="ID de la categoría"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Obtener una categoría específica.
    
    Esta ruta devuelve los detalles de una categoría específica,
    verificando que pertenezca al gimnasio actual para garantizar
    la separación de datos entre diferentes gimnasios.
    
    Requiere:
    - Scope 'read:schedules' en Auth0
    - Pertenencia al gimnasio actual
    """
    return category_service.get_category(db, category_id=category_id, gym_id=current_gym.id)


@router.post("/categories", response_model=ClassCategoryCustomSchema)
async def create_category(
    category_data: ClassCategoryCustomCreate = Body(...),
    db: Session = Depends(get_db),
    # Verificar que el usuario tiene rol de entrenador o administrador en este gimnasio
    current_gym: Gym = Depends(verify_trainer_role),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"])
) -> Any:
    """
    Crear una nueva categoría de clase personalizada.
    
    Esta ruta permite crear nuevas categorías de clases para el gimnasio actual.
    Las categorías son específicas del gimnasio y no serán visibles para otros.
    
    Requiere:
    - Scope 'create:schedules' en Auth0
    - Rol de TRAINER, ADMIN o OWNER en el gimnasio actual
    """
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    return category_service.create_category(
        db, category_data=category_data, gym_id=current_gym.id, created_by_id=created_by_id
    )


@router.put("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def update_category(
    category_id: int = Path(..., description="ID de la categoría"),
    category_data: ClassCategoryCustomUpdate = Body(...),
    db: Session = Depends(get_db),
    # Verificar que el usuario tiene rol de entrenador o administrador en este gimnasio
    current_gym: Gym = Depends(verify_trainer_role),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Actualizar una categoría existente.
    
    Esta ruta permite actualizar una categoría existente,
    verificando que pertenezca al gimnasio actual para garantizar
    la separación de datos entre diferentes gimnasios.
    
    Requiere:
    - Scope 'update:schedules' en Auth0
    - Rol de TRAINER, ADMIN o OWNER en el gimnasio actual
    """
    return category_service.update_category(
        db, category_id=category_id, category_data=category_data, gym_id=current_gym.id
    )


@router.delete("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def delete_category(
    category_id: int = Path(..., description="ID de la categoría"),
    db: Session = Depends(get_db),
    # Verificar que el usuario tiene rol de administrador en este gimnasio
    current_gym: Gym = Depends(verify_admin_role),
    user: Auth0User = Security(auth.get_user, scopes=["delete:schedules"])
) -> Any:
    """
    Eliminar una categoría.
    
    Esta ruta permite eliminar una categoría existente,
    verificando que pertenezca al gimnasio actual para garantizar
    la separación de datos entre diferentes gimnasios.
    
    Si hay clases usando esta categoría, se marcará como inactiva en lugar de eliminarla.
    
    Requiere:
    - Scope 'delete:schedules' en Auth0
    - Rol de ADMIN o OWNER en el gimnasio actual
    """
    return category_service.delete_category(db, category_id=category_id, gym_id=current_gym.id) 