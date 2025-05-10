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
from app.models.chat import ChatRoom

# Valor de webhook secret fijo para pruebas
TEST_WEBHOOK_SECRET = "test_webhook_secret_for_local_testing"

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

async def verify_stream_webhook_signature(request: Request):
    """
    Verifica la firma del webhook de Stream Chat usando HMAC-SHA256.
    
    Esta implementación usa directamente el STREAM_API_SECRET para calcular y verificar
    la firma, igual que lo hace el script de prueba.
    """
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )
    
    # Obtener el cuerpo del request
    body = await request.body()
    
    # Obtener el API_SECRET de la configuración
    api_secret = settings.STREAM_API_SECRET
    
    # Calcular la firma esperada
    expected_signature = hmac.new(
        api_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Comparar firmas de manera segura
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning(f"Firma del webhook inválida. Esperada: {expected_signature}, Recibida: {signature}")
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
        
        # Get message sender (Stream user_id)
        stream_user_id = message.get("user", {}).get("id")
        
        # Log para diagnóstico
        logger.info(f"Webhook recibido - Canal: {channel_id}, Tipo: {channel_type}, Remitente Stream: {stream_user_id}")
        logger.info(f"Mensaje: {message.get('text', '(sin texto)')}")
        
        if not all([channel_type, channel_id, stream_user_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields"
            )
            
        # Inicializar ID interno del remitente
        sender_internal_id = None
        
        # Manejar mensajes del system explícitamente
        if stream_user_id == "system":
            # No intentar buscar usuario, procesar como mensaje de sistema
            logger.info("Procesando mensaje de System")
            return {"status": "success", "message": "System message processed"}
        
        # Intentar obtener ID interno usando formato user_X o buscar por auth0_id (legacy)
        try:
            from app.core.stream_utils import is_internal_id_format, get_internal_id_from_stream, is_legacy_id_format
            
            if is_internal_id_format(stream_user_id):
                # Nuevo formato de ID interno
                sender_internal_id = get_internal_id_from_stream(stream_user_id)
                logger.info(f"ID interno extraído de Stream: {sender_internal_id}")
                
                # Verificar que el usuario existe
                sender = db.query(User).filter(User.id == sender_internal_id).first()
                if not sender:
                    logger.warning(f"Usuario con ID interno {sender_internal_id} no encontrado en la BD. Posible inconsistencia.")
                    # Esto no debería ocurrir, pero si ocurre, registrarlo como éxito
                    # ya que el mensaje ya está enviado en Stream
                    return {"status": "success", "message": "Message processed, user not found in DB"}
            elif is_legacy_id_format(stream_user_id):
                # Formato legacy (auth0_id)
                sender = db.query(User).filter(User.auth0_id == stream_user_id).first()
                if not sender:
                    logger.warning(f"Usuario remitente no encontrado en la BD: {stream_user_id}")
                    # Para mensajes normales, registramos éxito aunque no encontremos el usuario
                    return {"status": "success", "message": "Message processed, legacy user not found"}
                sender_internal_id = sender.id
            else:
                logger.warning(f"Formato de ID de Stream desconocido: {stream_user_id}")
                return {"status": "success", "message": "Message processed, unknown ID format"}
        
        except Exception as e:
            logger.error(f"Error procesando ID de usuario: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"Error processing user ID: {str(e)}"}
        
        # Procesar el mensaje aquí según sea necesario
        try:
            # Obtener la sala de chat
            chat_room = db.query(ChatRoom).filter(ChatRoom.stream_channel_id == channel_id).first()
            if not chat_room:
                logger.warning(f"Sala de chat no encontrada para canal {channel_id}")
                return {"status": "success", "message": "Message processed, chat room not found in DB"}
                
            # Aquí puedes implementar la lógica para procesar el mensaje
            # Por ejemplo: enviar notificaciones, actualizar contadores, etc.
            
            return {"status": "success", "message": "Message processed successfully"}
            
        except Exception as e:
            logger.error(f"Error processing stream webhook: {e}", exc_info=True)
            # No lanzar excepción para devolver 200 OK a Stream (evitar reintentos)
            return {"status": "error", "message": f"Error processing webhook: {str(e)}"}
        
    except Exception as e:
        logger.error(f"Error processing stream webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        ) 