from app.api.v1.endpoints.schedule.common import *
from app.models.schedule import ClassCategoryCustom, Class
from app.schemas.schedule import ClassCategoryCustomCreate, ClassCategoryCustomUpdate, ClassCategoryCustom as ClassCategoryCustomSchema
from app.models.gym import Gym
from app.models.user_gym import GymRoleType
from app.core.tenant import verify_gym_access, verify_trainer_role, verify_admin_role, GymSchema
from fastapi import APIRouter, Depends, Body, Path, Security, HTTPException, status, Request
from typing import List, Optional, Any
from app.services.schedule import category_service
from app.db.session import get_db
from app.core.auth0_fastapi import Auth0User, auth
from app.services.user import user_service
from app.db.redis_client import get_redis_client
from redis.asyncio import Redis

router = APIRouter()

@router.get("/categories", response_model=List[ClassCategoryCustomSchema])
async def get_categories(
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
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
    return await category_service.get_categories_by_gym(db, gym_id=current_gym.id, active_only=active_only, redis_client=redis_client)


@router.get("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def get_category(
    request: Request,
    category_id: int = Path(..., description="ID de la categoría"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
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
    return await category_service.get_category(db, category_id=category_id, gym_id=current_gym.id, redis_client=redis_client)


@router.post("/categories", response_model=ClassCategoryCustomSchema)
async def create_category(
    request: Request,
    category_data: ClassCategoryCustomCreate = Body(...),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_trainer_role),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Crear una nueva categoría de clase personalizada.
    
    Esta ruta permite crear nuevas categorías de clases para el gimnasio actual.
    Las categorías son específicas del gimnasio y no serán visibles para otros.
    
    Requiere:
    - Scope 'create:schedules' en Auth0
    - Rol de TRAINER, ADMIN o OWNER en el gimnasio actual
    """
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)
    
    created_by_id = db_user.id if db_user else None
    
    return await category_service.create_category(
        db, category_data=category_data, gym_id=current_gym.id, created_by_id=created_by_id, redis_client=redis_client
    )


@router.put("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def update_category(
    request: Request,
    category_id: int = Path(..., description="ID de la categoría"),
    category_data: ClassCategoryCustomUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_trainer_role),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
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
    return await category_service.update_category(
        db, category_id=category_id, category_data=category_data, gym_id=current_gym.id, redis_client=redis_client
    )


@router.delete(
    "/categories/{category_id}", 
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_category(
    request: Request,
    category_id: int = Path(..., description="ID de la categoría"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_admin_role),
    user: Auth0User = Security(auth.get_user, scopes=["delete:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> None:
    """
    Eliminar una categoría.
    
    Esta ruta permite eliminar una categoría existente,
    verificando que pertenezca al gimnasio actual para garantizar
    la separación de datos entre diferentes gimnasios.
    
    Si hay clases usando esta categoría, se marcará como inactiva en lugar de eliminarla.
    Devuelve 204 No Content en caso de éxito.
    
    Requiere:
    - Scope 'delete:schedules' en Auth0
    - Rol de ADMIN o OWNER en el gimnasio actual
    """
    await category_service.delete_category(db, category_id=category_id, gym_id=current_gym.id, redis_client=redis_client)
    return None 