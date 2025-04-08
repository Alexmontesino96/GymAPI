from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.db.session import SessionLocal
from app.schemas.notification import DeviceTokenCreate, DeviceTokenResponse, NotificationSend, NotificationResponse
from app.repositories.notification_repository import notification_repository
from app.services.notification_service import notification_service
from app.core.auth0_fastapi import auth, Auth0User
from fastapi import Security
from app.core.tenant import get_current_gym
from app.models.gym import Gym


router = APIRouter()

# Dependencia para obtener la sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/devices", response_model=DeviceTokenResponse)
def register_device(
    token_data: DeviceTokenCreate,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user),
    current_gym: Gym = Depends(get_current_gym),
):
    """
    Registra un nuevo dispositivo para recibir notificaciones push
    """
    return notification_repository.create_device_token(
        db=db,
        user_id=current_user.id,
        device_token=token_data.device_token,
        platform=token_data.platform
    )

@router.get("/devices", response_model=List[DeviceTokenResponse])
def get_user_devices(
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user),
    current_gym: Gym = Depends(get_current_gym),
):
    """
    Obtiene todos los dispositivos registrados del usuario actual
    """
    return notification_repository.get_user_device_tokens(db, current_user.id)

@router.delete("/devices")
def logout_all_devices(
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user),
    current_gym: Gym = Depends(get_current_gym),
):
    """
    Desactiva todos los dispositivos del usuario (para logout)
    """
    count = notification_repository.deactivate_user_tokens(db, current_user.id)
    return {"message": f"Successfully deactivated {count} devices"}

@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification_data: NotificationSend,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user),
    current_gym: Gym = Depends(get_current_gym)
):
    """
    Envía una notificación a usuarios específicos (solo para admins)
    """
    # Verificar permisos (ajusta según tus roles/permisos)
    if "admin:users" not in (current_user.permissions or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send notifications"
        )
    
    # Enviar en segundo plano para no bloquear la respuesta
    background_tasks.add_task(
        notification_service.send_to_users,
        user_ids=notification_data.user_ids,
        title=notification_data.title,
        message=notification_data.message,
        data=notification_data.data,
        db=db
    )
    
    return {
        "success": True,
        "message": f"Notification queued for {len(notification_data.user_ids)} recipients"
    } 