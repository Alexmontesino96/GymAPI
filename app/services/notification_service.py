import requests
import logging
import json
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.repositories.notification_repository import notification_repository

logger = logging.getLogger(__name__)

# Obtener directamente las credenciales de las variables de entorno
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "57c2285f-1a1a-4431-a5db-7ecd0bab4c5f")
ONESIGNAL_REST_API_KEY = os.environ.get("ONESIGNAL_REST_API_KEY", "os_v2_app_k7bcqxy2djcddjo3p3gqxk2ml5yilwxkkezur7mhf2ofworqrxvejkvtmywal5lniukbix5ugvyqoka5adzapeuu5f5nxzfparez6lq")

class OneSignalService:
    def __init__(self, app_id: str, api_key: str):
        self.app_id = app_id
        self.api_key = api_key
        self.base_url = "https://onesignal.com/api/v1/notifications"
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }
    
    def send_to_users(self, user_ids: List[str], title: str, message: str, 
                      data: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Envía notificación a múltiples usuarios por su user_id
        """
        if not user_ids:
            return {"success": False, "errors": ["No user IDs provided"]}
        
        try:
            payload = {
                "app_id": self.app_id,
                "include_external_user_ids": user_ids,
                "channel_for_external_user_ids": "push",
                "headings": {"en": title, "es": title},
                "contents": {"en": message, "es": message},
                "data": data or {}
            }
            
            logger.info(f"Sending notification to {len(user_ids)} users: {title}")
            response = requests.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            logger.debug(f"OneSignal response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Actualizar último uso en BD si se proporciona sesión
                if db and result.get("id"):
                    if "errors" not in result or not result["errors"]:
                        self._update_tokens_last_used(db, user_ids)
                
                return {
                    "success": True,
                    "notification_id": result.get("id"),
                    "recipients": result.get("recipients")
                }
            else:
                error_msg = f"OneSignal error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "errors": [error_msg]}
                
        except Exception as e:
            error_msg = f"Error sending notification: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "errors": [error_msg]}
    
    def send_to_segment(self, segment: str, title: str, message: str, 
                        data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Envía notificación a un segmento de usuarios
        """
        try:
            payload = {
                "app_id": self.app_id,
                "included_segments": [segment],
                "headings": {"en": title, "es": title},
                "contents": {"en": message, "es": message},
                "data": data or {}
            }
            
            logger.info(f"Sending notification to segment {segment}: {title}")
            response = requests.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "notification_id": result.get("id"),
                    "recipients": result.get("recipients")
                }
            else:
                error_msg = f"OneSignal error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "errors": [error_msg]}
                
        except Exception as e:
            error_msg = f"Error sending notification: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "errors": [error_msg]}
    
    def schedule_notification(self, user_ids: List[str], title: str, message: str, 
                              send_after: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Programa una notificación para enviar en el futuro
        send_after: formato ISO8601 "2023-04-07T15:00:00Z"
        """
        if not user_ids:
            return {"success": False, "errors": ["No user IDs provided"]}
            
        try:
            payload = {
                "app_id": self.app_id,
                "include_external_user_ids": user_ids,
                "channel_for_external_user_ids": "push",
                "headings": {"en": title, "es": title},
                "contents": {"en": message, "es": message},
                "data": data or {},
                "send_after": send_after
            }
            
            logger.info(f"Scheduling notification for {len(user_ids)} users at {send_after}: {title}")
            response = requests.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "notification_id": result.get("id"),
                    "recipients": result.get("recipients")
                }
            else:
                error_msg = f"OneSignal error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "errors": [error_msg]}
                
        except Exception as e:
            error_msg = f"Error scheduling notification: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "errors": [error_msg]}
    
    def _update_tokens_last_used(self, db: Session, user_ids: List[str]) -> None:
        """
        Actualiza la última fecha de uso para los tokens de los usuarios
        """
        try:
            tokens = notification_repository.get_active_tokens_by_user_ids(db, user_ids)
            device_tokens = [token.device_token for token in tokens]
            if device_tokens:
                notification_repository.update_last_used(db, device_tokens)
        except Exception as e:
            logger.error(f"Error updating tokens last_used: {str(e)}", exc_info=True)

# Instancia global
notification_service = OneSignalService(
    app_id=ONESIGNAL_APP_ID,
    api_key=ONESIGNAL_REST_API_KEY
) 