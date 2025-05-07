from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import hmac
import hashlib
import logging

from app.db.session import get_db
from app.core.config import get_settings
from app.services.notification_service import notification_service
from app.services.chat import chat_service
from app.core.stream_client import stream_client
from app.models.user import User

# Valor de webhook secret fijo para pruebas
TEST_WEBHOOK_SECRET = "test_webhook_secret_for_local_testing"

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

async def verify_stream_webhook_signature(request: Request):
    """
    Verify the webhook signature from GetStream.
    """
    # Obtener el secreto de webhook configurado o usar el de prueba
    webhook_secret = settings.STREAM_WEBHOOK_SECRET

    # Si no hay secreto configurado, verificar si es una prueba
    if not webhook_secret:
        logger.warning("STREAM_WEBHOOK_SECRET no configurado, intentando usar secreto de prueba")
        webhook_secret = TEST_WEBHOOK_SECRET
    
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )
    
    # Get raw body
    body = await request.body()
    
    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

@router.post("/stream/new-message", status_code=status.HTTP_200_OK)
async def handle_new_message(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(verify_stream_webhook_signature)
):
    """
    Webhook endpoint for handling new messages from GetStream.
    When a new message is created, this endpoint will be called to send notifications.
    """
    try:
        # Get webhook payload
        payload = await request.json()
        
        # Extract message data
        message = payload.get("message", {})
        channel = payload.get("channel", {})
        
        if not message or not channel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook payload"
            )
        
        # Get channel type and id
        channel_type = channel.get("type")
        channel_id = channel.get("id")
        
        # Get message sender
        user_id = message.get("user", {}).get("id")
        
        if not all([channel_type, channel_id, user_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields"
            )
            
        # Get channel members to notify (excluding sender)
        channel_members = await chat_service.get_channel_members(channel_type, channel_id)
        recipients = [member for member in channel_members if member != user_id]
        
        if not recipients:
            logger.info(f"No recipients to notify for message in channel {channel_id}")
            return {"status": "success", "message": "No recipients to notify"}
        
        # Prepare notification data
        notification_data = {
            "title": f"New message in {channel.get('name', 'chat')}",
            "message": message.get("text", "You have a new message"),
            "data": {
                "channel_id": channel_id,
                "channel_type": channel_type,
                "message_id": message.get("id"),
                "sender_id": user_id
            }
        }
        
        # Send notifications in background
        background_tasks.add_task(
            notification_service.send_notification_to_users,
            db,
            recipients,
            notification_data
        )
        
        # Enviar mensaje de respuesta si es necesario
        try:
            # Obtener el canal de Stream
            stream_channel = stream_client.channel(channel_type, channel_id)
            
            # Buscar el usuario que envió el mensaje original
            sender = db.query(User).filter(User.auth0_id == user_id).first()
            if sender:
                # Crear mensaje de respuesta
                response_message = {
                    "text": "He recibido tu mensaje y lo estoy procesando.",
                    "user_id": sender.auth0_id  # Usar auth0_id para Stream
                }
                
                # Enviar mensaje de respuesta
                stream_channel.send_message(response_message)
                logger.info(f"Mensaje de respuesta enviado en el canal {channel_id}")
        except Exception as msg_error:
            logger.error(f"Error enviando mensaje de respuesta: {str(msg_error)}", exc_info=True)
            # No fallar el webhook si el envío del mensaje falla
        
        return {
            "status": "success",
            "message": f"Notifications queued for {len(recipients)} recipients"
        }
        
    except Exception as e:
        logger.error(f"Error processing stream webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        ) 