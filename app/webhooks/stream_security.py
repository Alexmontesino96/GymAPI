"""
Webhooks de seguridad para Stream Chat
Valida acceso a canales y previene ataques cross-gym
"""

import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.chat import chat_service
from app.models.user import User, UserGym

logger = logging.getLogger(__name__)

class StreamSecurityWebhook:
    """
    Clase para manejar webhooks de seguridad de Stream Chat.
    Valida el acceso a canales basándose en la membresía de gimnasio.
    """
    
    @staticmethod
    def validate_channel_access(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida si un usuario puede acceder a un canal específico.
        
        Args:
            payload: Payload del webhook de Stream
            
        Returns:
            Dict con la respuesta de autorización
        """
        try:
            user_id = payload.get("user", {}).get("id", "")
            channel_id = payload.get("channel", {}).get("id", "")
            action = payload.get("type", "")
            
            logger.info(f"Validando acceso: user={user_id}, channel={channel_id}, action={action}")
            
            # Extraer internal_user_id del stream user_id (formato: user_X)
            if not user_id.startswith("user_"):
                logger.error(f"Formato de user_id inválido: {user_id}")
                return {"allow": False, "reason": "ID de usuario inválido"}
                
            try:
                internal_user_id = int(user_id.replace("user_", ""))
            except ValueError:
                logger.error(f"No se pudo extraer user_id numérico de: {user_id}")
                return {"allow": False, "reason": "ID de usuario malformado"}
            
            # Obtener gym_id del usuario desde la base de datos
            with SessionLocal() as db:
                user_gym_id = StreamSecurityWebhook._get_user_gym_id(db, internal_user_id, channel_id)
                
                if not user_gym_id:
                    logger.warning(f"No se pudo determinar gym_id para user {internal_user_id}")
                    return {"allow": False, "reason": "Usuario sin gimnasio válido"}
                
                # Validar acceso al canal
                if chat_service.validate_channel_access(channel_id, user_gym_id):
                    logger.info(f"Acceso permitido: user {user_id} a canal {channel_id}")
                    return {"allow": True}
                else:
                    logger.warning(f"Acceso denegado: user {user_id} a canal {channel_id}")
                    return {"allow": False, "reason": "Acceso no autorizado al canal"}
                    
        except Exception as e:
            logger.error(f"Error en validación de acceso: {str(e)}", exc_info=True)
            return {"allow": False, "reason": "Error interno de validación"}
    
    @staticmethod
    def _get_user_gym_id(db: Session, user_id: int, channel_id: str) -> Optional[int]:
        """
        Obtiene el gym_id de un usuario basándose en el canal al que intenta acceder.
        
        Args:
            db: Sesión de base de datos
            user_id: ID interno del usuario
            channel_id: ID del canal
            
        Returns:
            Optional[int]: gym_id del usuario o None si no se puede determinar
        """
        try:
            # Si el canal ya tiene prefijo de gym, extraerlo
            if channel_id.startswith("gym_"):
                parts = channel_id.split("_")
                if len(parts) >= 2:
                    try:
                        gym_id = int(parts[1])
                        
                        # Verificar que el usuario pertenezca a este gimnasio
                        membership = db.query(UserGym).filter(
                            UserGym.user_id == user_id,
                            UserGym.gym_id == gym_id
                        ).first()
                        
                        if membership:
                            return gym_id
                    except ValueError:
                        pass
            
            # Para canales legacy, obtener el gimnasio principal del usuario
            # (esto debería eliminarse gradualmente)
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == user_id
            ).first()
            
            if user_gym:
                logger.warning(f"Usando gym_id legacy para user {user_id}: {user_gym.gym_id}")
                return user_gym.gym_id
                
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo gym_id para user {user_id}: {str(e)}")
            return None

    @staticmethod
    def log_security_event(event_type: str, user_id: str, channel_id: str, details: Dict[str, Any]):
        """
        Registra eventos de seguridad para auditoría.
        
        Args:
            event_type: Tipo de evento (access_denied, suspicious_activity, etc.)
            user_id: ID del usuario
            channel_id: ID del canal
            details: Detalles adicionales del evento
        """
        logger.warning(f"EVENTO DE SEGURIDAD - {event_type}: user={user_id}, channel={channel_id}, details={details}")
        
        # Aquí se podría integrar con un sistema de alertas o SIEM
        # Por ejemplo, enviar a un webhook de Slack o guardar en base de datos de auditoría


# Instancia del webhook
stream_security_webhook = StreamSecurityWebhook()