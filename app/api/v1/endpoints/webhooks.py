"""
Endpoints para webhooks externos (Stream Chat, Stripe, etc.)
"""

import logging
import hmac
import hashlib
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status, Header
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.webhooks.stream_security import stream_security_webhook

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/stream/auth")
async def stream_auth_webhook(
    request: Request,
    x_signature: str = Header(None, alias="x-signature")
):
    """
    Webhook de autorización para Stream Chat.
    Valida el acceso de usuarios a canales específicos.
    
    Este webhook se ejecuta cada vez que un usuario intenta:
    - Unirse a un canal
    - Leer mensajes de un canal  
    - Enviar mensajes a un canal
    
    Returns:
        JSONResponse: {"allow": true/false, "reason": "..."}
    """
    try:
        # Obtener el body del request
        body = await request.body()
        payload = await request.json()
        
        # Verificar la firma del webhook (opcional pero recomendado)
        settings = get_settings()
        if settings.STREAM_WEBHOOK_SECRET and x_signature:
            if not _verify_stream_signature(body, x_signature, settings.STREAM_WEBHOOK_SECRET):
                logger.error("Firma de webhook inválida")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Firma inválida"
                )
        
        # Obtener información del webhook
        webhook_type = payload.get("type", "")
        user_data = payload.get("user", {})
        channel_data = payload.get("channel", {})
        
        logger.info(f"Stream webhook recibido: type={webhook_type}, user={user_data.get('id')}, channel={channel_data.get('id')}")
        
        # Validar acceso según el tipo de webhook
        if webhook_type in ["channel.join", "message.new", "channel.read"]:
            result = stream_security_webhook.validate_channel_access(payload)
            
            # Registrar eventos de seguridad si es necesario
            if not result.get("allow", False):
                stream_security_webhook.log_security_event(
                    event_type="access_denied",
                    user_id=user_data.get("id", ""),
                    channel_id=channel_data.get("id", ""),
                    details={
                        "webhook_type": webhook_type,
                        "reason": result.get("reason", "Unknown"),
                        "user_agent": request.headers.get("user-agent", ""),
                        "ip": request.client.host if request.client else "unknown"
                    }
                )
            
            return JSONResponse(content=result)
        
        # Para otros tipos de webhook, permitir por defecto
        logger.info(f"Webhook type {webhook_type} permitido por defecto")
        return JSONResponse(content={"allow": True})
        
    except Exception as e:
        logger.error(f"Error procesando webhook de Stream: {str(e)}", exc_info=True)
        
        # En caso de error, denegar acceso por seguridad
        return JSONResponse(
            content={"allow": False, "reason": "Error interno del servidor"},
            status_code=500
        )

def _verify_stream_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Verifica la firma del webhook de Stream Chat.
    
    Args:
        body: Cuerpo del request en bytes
        signature: Firma recibida en el header
        secret: Secret configurado en Stream
        
    Returns:
        bool: True si la firma es válida
    """
    try:
        # Stream usa HMAC-SHA256
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Comparar firmas de forma segura
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error(f"Error verificando firma: {str(e)}")
        return False

@router.post("/stream/events")
async def stream_events_webhook(request: Request):
    """
    Webhook para eventos generales de Stream Chat.
    Usado para auditoría y monitoreo, no para autorización.
    """
    try:
        payload = await request.json()
        event_type = payload.get("type", "")
        
        # Log de eventos para auditoría
        logger.info(f"Stream event recibido: {event_type}")
        
        # Aquí se pueden procesar eventos como:
        # - message.new (nuevos mensajes)
        # - user.presence.changed (cambios de presencia)
        # - channel.created (canales creados)
        
        return JSONResponse(content={"status": "received"})
        
    except Exception as e:
        logger.error(f"Error procesando evento de Stream: {str(e)}")
        return JSONResponse(content={"status": "error"}, status_code=500)