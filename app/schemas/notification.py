from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator

class DeviceTokenBase(BaseModel):
    device_token: str = Field(..., description="Token único del dispositivo")
    platform: str = Field(..., description="Plataforma (ios/android/web)")
    
    @validator('platform')
    def validate_platform(cls, v):
        allowed = ['ios', 'android', 'web']
        if v.lower() not in allowed:
            raise ValueError(f'Platform must be one of: {", ".join(allowed)}')
        return v.lower()

class DeviceTokenCreate(DeviceTokenBase):
    pass

class DeviceTokenResponse(DeviceTokenBase):
    id: UUID
    user_id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationSend(BaseModel):
    user_ids: List[str] = Field(..., description="Lista de IDs de usuario")
    title: str = Field(..., description="Título de la notificación")
    message: str = Field(..., description="Mensaje de la notificación")
    data: Optional[dict] = Field(None, description="Datos adicionales para la notificación")

class NotificationResponse(BaseModel):
    success: bool
    notification_id: Optional[str] = None
    recipients: Optional[int] = None
    errors: Optional[List[str]] = None

class GymNotificationRequest(BaseModel):
    title: str = Field(..., description="Título de la notificación")
    message: str = Field(..., description="Mensaje de la notificación")
    data: Optional[dict] = Field(None, description="Datos adicionales para la notificación") 