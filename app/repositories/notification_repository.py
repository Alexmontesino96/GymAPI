from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.notification import DeviceToken

class NotificationRepository:
    def create_device_token(self, db: Session, user_id: str, device_token: str, platform: str) -> DeviceToken:
        """Crea o actualiza un token de dispositivo"""
        existing_token = db.query(DeviceToken).filter(
            DeviceToken.user_id == user_id,
            DeviceToken.device_token == device_token
        ).first()
        
        if existing_token:
            # Actualizar token existente
            existing_token.platform = platform
            existing_token.is_active = True
            existing_token.updated_at = datetime.now()
            db.commit()
            db.refresh(existing_token)
            return existing_token
        
        # Crear nuevo token
        db_token = DeviceToken(
            user_id=user_id,
            device_token=device_token,
            platform=platform,
            is_active=True
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        return db_token
    
    def get_active_tokens_by_user_ids(self, db: Session, user_ids: List[str]) -> List[DeviceToken]:
        """Obtiene tokens activos para una lista de usuarios"""
        return db.query(DeviceToken).filter(
            DeviceToken.user_id.in_(user_ids),
            DeviceToken.is_active == True
        ).all()
    
    def get_user_device_tokens(self, db: Session, user_id: str) -> List[DeviceToken]:
        """Obtiene todos los tokens activos de un usuario"""
        return db.query(DeviceToken).filter(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True
        ).all()
    
    def deactivate_token(self, db: Session, device_token: str) -> bool:
        """Desactiva un token específico"""
        result = db.query(DeviceToken).filter(
            DeviceToken.device_token == device_token
        ).update({
            DeviceToken.is_active: False,
            DeviceToken.updated_at: datetime.now()
        })
        db.commit()
        return result > 0
    
    def deactivate_user_tokens(self, db: Session, user_id: str) -> int:
        """Desactiva todos los tokens de un usuario (para logout)"""
        result = db.query(DeviceToken).filter(
            DeviceToken.user_id == user_id
        ).update({
            DeviceToken.is_active: False,
            DeviceToken.updated_at: datetime.now()
        })
        db.commit()
        return result
    
    def update_last_used(self, db: Session, device_tokens: List[str]) -> int:
        """Actualiza la fecha de último uso para varios tokens"""
        result = db.query(DeviceToken).filter(
            DeviceToken.device_token.in_(device_tokens)
        ).update({
            DeviceToken.last_used: datetime.now()
        })
        db.commit()
        return result
    
    def cleanup_old_tokens(self, db: Session, days: int = 90) -> int:
        """Elimina tokens inactivos antiguos"""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = db.query(DeviceToken).filter(
            and_(
                DeviceToken.is_active == False,
                or_(
                    DeviceToken.updated_at <= cutoff_date,
                    DeviceToken.last_used <= cutoff_date
                )
            )
        ).delete(synchronize_session=False)
        
        db.commit()
        return result

notification_repository = NotificationRepository() 