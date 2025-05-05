from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.module import module_service
from app.core.tenant import get_tenant_id


def module_enabled(module_code: str):
    """
    Factoría de dependencia para verificar si un módulo está activo para el gimnasio actual.
    
    Ejemplo de uso:
        schedule_router = APIRouter(
            prefix="/schedule",
            dependencies=[Depends(module_enabled("schedule"))]
        )
    
    Args:
        module_code: Código del módulo a verificar
        
    Returns:
        Dependencia FastAPI que verifica si el módulo está activo
    """
    def dependency(db: Session = Depends(get_db), gym_id: int = Depends(get_tenant_id)) -> None:
        is_active = module_service.get_gym_module_status(db, gym_id, module_code)
        
        if is_active is None:
            # Módulo no existe
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Módulo {module_code} no encontrado"
            )
        
        if not is_active:
            # Módulo existe pero no está activo para este gimnasio
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El módulo {module_code} no está disponible en este gimnasio"
            )
    
    return Depends(dependency)
