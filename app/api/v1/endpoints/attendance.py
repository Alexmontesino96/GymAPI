from fastapi import APIRouter, Depends, Security, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any
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

@router.post("/check-in", response_model=Dict[str, Any])
async def check_in(
    check_in_data: QRCheckInRequest,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Procesa el check-in de un usuario usando su código QR.
    Este endpoint debe ser llamado por el personal del gimnasio o un sistema autorizado.
    """
    result = await attendance_service.process_check_in(
        db=db,
        qr_code=check_in_data.qr_code,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

    return result 