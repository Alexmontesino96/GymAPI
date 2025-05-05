from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Security, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User, auth
from app.services.module import module_service
from app.schemas.module import Module, ModuleCreate, ModuleUpdate, ModuleStatus, GymModuleList
from app.core.tenant import get_tenant_id
from app.schemas.gym import GymSchema
from app.db.redis_client import get_redis_client, Redis
from app.core.tenant_cache import verify_gym_access_cached
from app.core.auth0_fastapi import get_current_user

router = APIRouter()

@router.get("", response_model=GymModuleList)
async def get_active_modules(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    current_user: Auth0User = Security(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access_cached),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Obtener la lista de módulos activos para el gimnasio actual.
    
    Esta endpoint permite al frontend saber qué funcionalidades están disponibles
    para mostrar en la interfaz.
    """
    # Obtener todos los módulos y su estado para este gimnasio
    all_modules = module_service.get_modules(db)
    active_modules = module_service.get_active_modules_for_gym(db, gym_id)
    active_module_ids = {m.id for m in active_modules}
    
    # Construir respuesta
    module_statuses = []
    for module in all_modules:
        module_statuses.append(
            ModuleStatus(
                code=module.code,
                name=module.name,
                active=module.id in active_module_ids,
                is_premium=module.is_premium
            )
        )
    
    return GymModuleList(modules=module_statuses)

@router.patch("/{module_code}/activate", status_code=status.HTTP_200_OK)
async def activate_module(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    module_code: str = Path(..., title="Código del módulo a activar"),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:modules"])
):
    """
    Activar un módulo para el gimnasio actual.
    
    Solo los administradores pueden activar módulos.
    """
    # Verificar que el módulo existe
    module = module_service.get_module_by_code(db, module_code)
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Módulo con código {module_code} no encontrado"
        )
    
    # Activar módulo - Verificación de admin ya realizada por verify_gym_admin_access
    if module_service.activate_module_for_gym(db, gym_id, module_code):
        return {"status": "success", "message": f"Módulo {module_code} activado correctamente"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al activar el módulo"
        )

@router.patch("/{module_code}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_module(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    module_code: str = Path(..., title="Código del módulo a desactivar"),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:modules"])
):
    """
    Desactivar un módulo para el gimnasio actual.
    
    Solo los administradores pueden desactivar módulos.
    """
    # Verificar que el módulo existe
    module = module_service.get_module_by_code(db, module_code)
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Módulo con código {module_code} no encontrado"
        )
    
    # Desactivar módulo - Verificación de admin ya realizada por verify_gym_admin_access
    if module_service.deactivate_module_for_gym(db, gym_id, module_code):
        return {"status": "success", "message": f"Módulo {module_code} desactivado correctamente"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar el módulo"
        )
