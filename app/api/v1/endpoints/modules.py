from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Security, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User, auth
from app.services.module import module_service
from app.services.billing_module import billing_module_service
from app.schemas.module import Module, ModuleCreate, ModuleUpdate, ModuleStatus, GymModuleList
from app.core.tenant import get_tenant_id, verify_gym_admin_access, verify_super_admin_access
from app.schemas.gym import GymSchema
from app.db.redis_client import get_redis_client, Redis
from app.core.tenant_cache import verify_gym_access_cached
from app.models.user import User

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
    super_admin: User = Depends(verify_super_admin_access)
):
    """
    Activar un módulo para el gimnasio actual.

    IMPORTANTE: Solo los administradores de la plataforma (SUPER_ADMIN) pueden activar módulos.
    Los administradores de gimnasio (ADMIN/OWNER) no tienen este permiso.

    Args:
        gym_id: ID del gimnasio (del header X-Gym-ID)
        module_code: Código del módulo a activar (ej: "events", "nutrition")
        super_admin: Usuario verificado con rol SUPER_ADMIN

    Returns:
        Mensaje de éxito si el módulo fue activado correctamente

    Raises:
        HTTPException 403: Si el usuario no es SUPER_ADMIN
        HTTPException 404: Si el módulo no existe
        HTTPException 500: Si hay un error al activar el módulo
    """
    # Verificar que el módulo existe
    module = module_service.get_module_by_code(db, module_code)
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Módulo con código {module_code} no encontrado"
        )

    # Activar módulo (verificación de SUPER_ADMIN ya realizada por verify_super_admin_access)
    if module_service.activate_module_for_gym(db, gym_id, module_code):
        return {"status": "success", "message": f"Módulo {module_code} activado correctamente para gimnasio {gym_id}"}
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
    super_admin: User = Depends(verify_super_admin_access)
):
    """
    Desactivar un módulo para el gimnasio actual.

    IMPORTANTE: Solo los administradores de la plataforma (SUPER_ADMIN) pueden desactivar módulos.
    Los administradores de gimnasio (ADMIN/OWNER) no tienen este permiso.

    Args:
        gym_id: ID del gimnasio (del header X-Gym-ID)
        module_code: Código del módulo a desactivar (ej: "events", "nutrition")
        super_admin: Usuario verificado con rol SUPER_ADMIN

    Returns:
        Mensaje de éxito si el módulo fue desactivado correctamente

    Raises:
        HTTPException 403: Si el usuario no es SUPER_ADMIN
        HTTPException 404: Si el módulo no existe
        HTTPException 500: Si hay un error al desactivar el módulo
    """
    # Verificar que el módulo existe
    module = module_service.get_module_by_code(db, module_code)
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Módulo con código {module_code} no encontrado"
        )

    # Desactivar módulo (verificación de SUPER_ADMIN ya realizada por verify_super_admin_access)
    if module_service.deactivate_module_for_gym(db, gym_id, module_code):
        return {"status": "success", "message": f"Módulo {module_code} desactivado correctamente para gimnasio {gym_id}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar el módulo"
        )


# === Endpoints Específicos para Módulo Billing ===

@router.post("/billing/activate", status_code=status.HTTP_200_OK)
async def activate_billing_module(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:modules"]),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
):
    """
    Activar el módulo de billing para el gimnasio actual.
    
    Este endpoint realiza una activación completa que incluye:
    - Activación del módulo en la base de datos
    - Validación de la configuración de Stripe
    - Sincronización automática de planes existentes
    
    Solo los administradores pueden activar el módulo billing.
    """
    result = await billing_module_service.activate_billing_for_gym(
        db, gym_id, validate_stripe_config=True
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return result


@router.post("/billing/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_billing_module(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    preserve_data: bool = True,
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:modules"]),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
):
    """
    Desactivar el módulo de billing para el gimnasio actual.
    
    Args:
        preserve_data: Si preservar los datos de Stripe (recomendado)
        
    Solo los administradores pueden desactivar el módulo billing.
    """
    result = await billing_module_service.deactivate_billing_for_gym(
        db, gym_id, preserve_stripe_data=preserve_data
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return result


@router.get("/billing/status", status_code=status.HTTP_200_OK)
async def get_billing_module_status(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    current_gym: GymSchema = Depends(verify_gym_access_cached)
):
    """
    Obtener el estado detallado del módulo billing para el gimnasio actual.
    
    Devuelve información sobre:
    - Estado de activación del módulo
    - Validación de configuración de Stripe
    - Estadísticas de planes y suscripciones
    - Capacidades disponibles
    """
    status_info = await billing_module_service.get_billing_status(db, gym_id)
    
    return {
        "gym_id": gym_id,
        "gym_name": current_gym.name,
        **status_info
    }
