from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import SessionLocal, get_async_db
from app.schemas.notification import DeviceTokenCreate, DeviceTokenResponse, NotificationSend, NotificationResponse, GymNotificationRequest
from app.repositories.notification_repository import notification_repository
from app.services.notification_service import notification_service
from app.core.auth0_fastapi import auth, Auth0User
from fastapi import Security
from app.core.tenant import verify_gym_access, verify_admin_role, get_tenant_id
from app.models.gym import Gym
from app.services.user import user_service


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
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user),
    gym: Gym = Depends(verify_gym_access),
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
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user),
    gym: Gym = Depends(verify_gym_access),
):
    """
    Obtiene todos los dispositivos registrados del usuario actual
    """
    return notification_repository.get_user_device_tokens(db, current_user.id)

@router.delete("/devices")
def logout_all_devices(
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user),
    gym: Gym = Depends(verify_gym_access),
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
    db: AsyncSession = Depends(get_async_db),
    gym: Gym = Depends(verify_admin_role)
):
    """
    Envía una notificación a usuarios específicos (solo para admins del gym actual)
    """
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

@router.post("/send-to-gym", response_model=NotificationResponse)
async def send_notification_to_gym_users(
    notification_data: GymNotificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Depends(get_tenant_id),
    gym: Gym = Depends(verify_admin_role)
):
    """
    Envía una notificación a todos los usuarios del gimnasio actual (solo para admins)
    """
    # Obtener todos los IDs de usuarios del gimnasio
    user_ids = user_service.get_all_gym_user_ids(db, gym_id)
    
    if not user_ids:
        return {"success": False, "errors": ["No hay usuarios registrados en este gimnasio"]}
    
    # Enviar en segundo plano para no bloquear la respuesta
    background_tasks.add_task(
        notification_service.send_to_users,
        user_ids=user_ids,
        title=notification_data.title,
        message=notification_data.message,
        data=notification_data.data,
        db=db
    )
    
    return {
        "success": True,
        "message": f"Notificación programada para {len(user_ids)} usuarios del gimnasio"
    } 