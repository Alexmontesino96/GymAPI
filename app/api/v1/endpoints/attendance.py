from fastapi import APIRouter, Depends, Security, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_access
from app.models.gym import Gym
from app.services.attendance import attendance_service
from app.services.user import user_service
from app.db.redis_client import get_redis_client
from redis.asyncio import Redis

router = APIRouter()

class QRCheckInRequest(BaseModel):
    qr_code: str
    session_id: Optional[int] = None  # Si se provee, hace check-in a esta sesión específica

@router.post("/check-in", response_model=Dict[str, Any])
async def check_in(
    check_in_data: QRCheckInRequest,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Procesa el check-in de un usuario usando su código QR.
    
    Args:
        check_in_data: Datos del check-in (código QR)
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        user: Usuario autenticado
        redis_client: Cliente Redis
        
    Returns:
        Dict con el resultado del check-in
        
    Raises:
        HTTPException: Si hay algún error en el proceso
    """
    # Procesar el check-in
    result = await attendance_service.process_check_in(
        db,
        qr_code=check_in_data.qr_code,
        gym_id=current_gym.id,
        redis_client=redis_client,
        session_id=check_in_data.session_id
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result 