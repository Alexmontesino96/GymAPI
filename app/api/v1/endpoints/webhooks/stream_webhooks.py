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
from app.webhooks.stream_security import stream_security_webhook

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
    # Log detallado de la verificación
    logger.info("🔐 Iniciando verificación de firma de webhook Stream")
    
    signature = request.headers.get("X-Signature")
    logger.info(f"🔐 Signature recibida: {signature}")
    
    if not signature:
        logger.error("🔐 ERROR: Signature faltante en headers")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )
    
    # Obtener el cuerpo del request
    body = await request.body()
    logger.info(f"🔐 Body size: {len(body)} bytes")
    
    # Obtener el API_SECRET de la configuración
    api_secret = settings.STREAM_API_SECRET
    logger.info(f"🔐 API Secret configurado: {api_secret[:8]}...")
    
    # Calcular la firma esperada
    expected_signature = hmac.new(
        api_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    logger.info(f"🔐 Signature esperada: {expected_signature}")
    logger.info(f"🔐 Signature recibida: {signature}")
    
    # Comparar firmas de manera segura
    if not hmac.compare_digest(signature, expected_signature):
        logger.error(f"🔐 ERROR: Firma del webhook inválida. Esperada: {expected_signature}, Recibida: {signature}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    logger.info("🔐 ✅ Firma verificada exitosamente")

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
    # LOGGING COMPLETO - Log antes de cualquier procesamiento
    logger.info("🔔 ========== WEBHOOK STREAM NEW MESSAGE RECIBIDO ==========")
    logger.info(f"📡 Headers completos: {dict(request.headers)}")
    logger.info(f"🌐 Client host: {request.client.host if request.client else 'unknown'}")
    logger.info(f"🌐 URL path: {request.url.path}")
    logger.info(f"📊 Method: {request.method}")
    
    try:
        # Get webhook payload
        payload = await request.json()
        logger.info(f"📦 Payload completo: {payload}")
        
        # Extract message data
        message = payload.get("message", {})
        channel = payload.get("channel", {})
        
        logger.info(f"✉️  Mensaje extraído: {message}")
        logger.info(f"📺 Canal extraído: {channel}")
        
        if not message or not channel:
            logger.error("❌ ERROR: Payload de webhook inválido: falta message o channel")
            return {"status": "error", "message": "Invalid webhook payload"}
        
        # Get channel type and id
        channel_type = channel.get("type")
        channel_id = channel.get("id")
        
        # Get message sender (Stream user_id)
        stream_user_id = message.get("user", {}).get("id")
        
        # Log detallado para diagnóstico
        logger.info(f"📋 DATOS PROCESADOS:")
        logger.info(f"   📺 Canal ID: {channel_id}")
        logger.info(f"   📺 Canal tipo: {channel_type}")
        logger.info(f"   👤 Remitente Stream: {stream_user_id}")
        logger.info(f"   ✉️  Texto mensaje: {message.get('text', '(sin texto)')}")
        logger.info(f"   🕐 Timestamp: {message.get('created_at', 'N/A')}")
        logger.info(f"   🆔 Message ID: {message.get('id', 'N/A')}")
        
        if not all([channel_type, channel_id, stream_user_id]):
            logger.error(f"❌ ERROR: Campos faltantes en webhook:")
            logger.error(f"   channel_type: {channel_type}")
            logger.error(f"   channel_id: {channel_id}")
            logger.error(f"   stream_user_id: {stream_user_id}")
            return {"status": "error", "message": "Missing required fields"}
            
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
            
            # Obtener el texto del mensaje
            message_text = message.get("text", "")
            
            # Ejecutar tareas en segundo plano para no bloquear la respuesta del webhook
            if sender_internal_id and message_text:
                # Determinar tipo de contenido basado en el canal y mensaje
                content_type = determine_content_type(chat_room, message_text)
                
                # 1. Enviar notificaciones push inteligentes con lógica basada en roles
                members_with_unread = payload.get("members", [])
                background_tasks.add_task(
                    send_smart_notifications_with_role_logic_async,
                    db,
                    sender_internal_id,
                    chat_room,
                    message_text,
                    members_with_unread,
                    content_type
                )
                
                # 2. Procesar menciones
                background_tasks.add_task(
                    process_mentions_async,
                    db,
                    message_text,
                    chat_room,
                    sender_internal_id
                )
                
                # 3. Actualizar actividad del chat
                background_tasks.add_task(
                    update_chat_activity_async,
                    db,
                    chat_room,
                    sender_internal_id
                )
                
                # 4. Procesar eventos especiales (si es necesario)
                if message.get("type") == "system" or "bienvenido" in message_text.lower():
                    background_tasks.add_task(
                        process_special_events_async,
                        db,
                        message,
                        chat_room,
                        sender_internal_id
                    )
            
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


# Funciones asíncronas para procesamiento en segundo plano
async def send_smart_notifications_with_role_logic_async(
    db: Session, 
    sender_id: int, 
    chat_room: ChatRoom, 
    message_text: str,
    members_with_unread: list,
    content_type: str = "chat"
):
    """
    Envía notificaciones push inteligentes con lógica basada en roles según el tipo de contenido.
    
    - Para EVENTOS: Solo notifica si el remitente tiene autoridad (TRAINER/ADMIN/OWNER)
    - Para CHAT: Notificación normal a usuarios offline con mensajes no leídos
    """
    try:
        # Crear nueva sesión de DB para el hilo de background
        from app.db.session import SessionLocal
        async_db = SessionLocal()
        
        try:
            # Filtrar usuarios que NO son el remitente y que tienen mensajes no leídos
            sender_stream_id = f"user_{sender_id}"
            users_to_notify = []
            
            logger.info(f"📊 Analizando {len(members_with_unread)} miembros para notificaciones ({content_type})")
            
            for member in members_with_unread:
                member_stream_id = member.get("user_id", "")
                member_user_data = member.get("user", {})
                unread_count = member.get("channel_unread_count", 0)
                is_online = member_user_data.get("online", False)
                
                # Lógica de notificación inteligente (igual para ambos tipos)
                should_notify = (
                    member_stream_id != sender_stream_id and  # No notificar al remitente
                    unread_count > 0 and                     # Tiene mensajes no leídos
                    not is_online                            # No está online actualmente
                )
                
                logger.info(f"👤 {member_stream_id}: unread={unread_count}, online={is_online}, notify={should_notify}")
                
                if should_notify:
                    # Extraer ID interno del formato user_X
                    try:
                        internal_id = int(member_stream_id.replace("user_", ""))
                        users_to_notify.append({
                            "internal_id": internal_id,
                            "stream_id": member_stream_id,
                            "unread_count": unread_count,
                            "name": member_user_data.get("name", "Usuario"),
                            "email": member_user_data.get("email", "")
                        })
                    except ValueError:
                        logger.warning(f"⚠️ No se pudo extraer ID interno de {member_stream_id}")
            
            logger.info(f"🎯 Usuarios elegibles antes del filtro por roles: {len(users_to_notify)}")
            
            if users_to_notify:
                # Enviar notificaciones usando la nueva lógica basada en roles
                await send_targeted_notifications(
                    async_db,
                    users_to_notify,
                    chat_room,
                    message_text,
                    sender_id,
                    content_type  # Pasar el tipo de contenido
                )
            else:
                logger.info("📭 No hay usuarios elegibles para notificación")
                
        finally:
            async_db.close()
            
    except Exception as e:
        logger.error(f"Error en notificaciones inteligentes con roles: {str(e)}", exc_info=True)


async def send_smart_chat_notifications_async(
    db: Session, 
    sender_id: int, 
    chat_room: ChatRoom, 
    message_text: str,
    members_with_unread: list
):
    """
    Envía notificaciones push inteligentes solo a usuarios con mensajes no leídos (función legacy).
    """
    try:
        # Crear nueva sesión de DB para el hilo de background
        from app.db.session import SessionLocal
        async_db = SessionLocal()
        
        try:
            # Filtrar usuarios que NO son el remitente y que tienen mensajes no leídos
            sender_stream_id = f"user_{sender_id}"
            users_to_notify = []
            
            logger.info(f"📊 Analizando {len(members_with_unread)} miembros para notificaciones")
            
            for member in members_with_unread:
                member_stream_id = member.get("user_id", "")
                member_user_data = member.get("user", {})
                unread_count = member.get("channel_unread_count", 0)
                is_online = member_user_data.get("online", False)
                
                # Lógica de notificación inteligente
                should_notify = (
                    member_stream_id != sender_stream_id and  # No notificar al remitente
                    unread_count > 0 and                     # Tiene mensajes no leídos
                    not is_online                            # No está online actualmente
                )
                
                logger.info(f"👤 {member_stream_id}: unread={unread_count}, online={is_online}, notify={should_notify}")
                
                if should_notify:
                    # Extraer ID interno del formato user_X
                    try:
                        internal_id = int(member_stream_id.replace("user_", ""))
                        users_to_notify.append({
                            "internal_id": internal_id,
                            "stream_id": member_stream_id,
                            "unread_count": unread_count,
                            "name": member_user_data.get("name", "Usuario"),
                            "email": member_user_data.get("email", "")
                        })
                    except ValueError:
                        logger.warning(f"⚠️ No se pudo extraer ID interno de {member_stream_id}")
            
            logger.info(f"🎯 Enviando notificaciones a {len(users_to_notify)} usuarios")
            
            if users_to_notify:
                # Enviar notificaciones usando OneSignal (sin filtro por roles)
                await send_targeted_notifications(
                    async_db,
                    users_to_notify,
                    chat_room,
                    message_text,
                    sender_id
                )
            else:
                logger.info("📭 No hay usuarios elegibles para notificación")
                
        finally:
            async_db.close()
            
    except Exception as e:
        logger.error(f"Error en notificaciones inteligentes: {str(e)}", exc_info=True)


def determine_content_type(chat_room: ChatRoom, message_text: str) -> str:
    """
    Determina el tipo de contenido del mensaje para aplicar lógica de notificación correcta.
    
    Args:
        chat_room: Sala de chat donde se envió el mensaje
        message_text: Texto del mensaje
        
    Returns:
        str: "event" si es relacionado con eventos, "chat" para mensajes normales
    """
    try:
        # Indicadores de que el mensaje es relacionado con eventos/clases
        event_keywords = [
            "clase", "sesion", "session", "entrenamiento", "training",
            "evento", "event", "reserva", "booking", "cancelar", "cancel",
            "horario", "schedule", "gimnasio", "gym", "instructor", "trainer"
        ]
        
        # Verificar si el nombre del canal indica que es de eventos
        channel_name = chat_room.name.lower() if chat_room.name else ""
        is_event_channel = any(keyword in channel_name for keyword in ["evento", "event", "clase", "class", "schedule"])
        
        # Verificar si el mensaje contiene palabras clave de eventos
        message_lower = message_text.lower()
        has_event_keywords = any(keyword in message_lower for keyword in event_keywords)
        
        # Determinar tipo basado en canal y contenido
        if is_event_channel or has_event_keywords:
            logger.info(f"🎭 Mensaje detectado como EVENTO: canal='{channel_name}', keywords={has_event_keywords}")
            return "event"
        else:
            logger.info(f"💬 Mensaje detectado como CHAT normal")
            return "chat"
            
    except Exception as e:
        logger.error(f"Error determinando tipo de contenido: {str(e)}")
        # En caso de error, asumir chat normal
        return "chat"


async def check_user_authority_in_gym(db: Session, user_id: int, gym_id: int) -> bool:
    """
    Verifica si un usuario tiene autoridad en el gimnasio (TRAINER, ADMIN, o OWNER).
    
    Args:
        db: Sesión de base de datos
        user_id: ID interno del usuario
        gym_id: ID del gimnasio
        
    Returns:
        bool: True si el usuario tiene autoridad (TRAINER+), False si es MEMBER o no existe
    """
    try:
        from app.models.user_gym import UserGym, GymRoleType
        
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id,
            UserGym.is_active == True
        ).first()
        
        if not user_gym:
            logger.info(f"👤 Usuario {user_id} no encontrado en gym {gym_id}")
            return False
        
        has_authority = user_gym.role in [GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER]
        
        logger.info(f"🎭 Usuario {user_id} role: {user_gym.role}, autoridad: {has_authority}")
        return has_authority
        
    except Exception as e:
        logger.error(f"Error verificando autoridad del usuario: {str(e)}", exc_info=True)
        return False


async def send_targeted_notifications(
    db: Session,
    users_to_notify: list,
    chat_room: ChatRoom,
    message_text: str,
    sender_id: int,
    content_type: str = "chat"
):
    """
    Envía notificaciones específicas a usuarios seleccionados según el tipo de contenido.
    
    Args:
        content_type: "chat" (normal) o "event" (requiere autoridad del remitente)
    """
    try:
        # Obtener información del remitente
        from app.models.user import User
        sender = db.query(User).filter(User.id == sender_id).first()
        sender_name = sender.name if sender else "Alguien"
        
        # LÓGICA BASADA EN TIPO DE CONTENIDO
        if content_type == "event":
            # Para eventos: verificar que el remitente tenga autoridad
            gym_id = chat_room.gym_id
            has_authority = await check_user_authority_in_gym(db, sender_id, gym_id)
            
            if not has_authority:
                logger.info(f"🚫 Evento NO notificado: {sender_name} (ID: {sender_id}) no tiene autoridad en gym {gym_id}")
                return
            else:
                logger.info(f"✅ Evento SÍ notificado: {sender_name} tiene autoridad ({has_authority})")
        
        # Para chat: notificación normal (ya filtrado previamente)
        
        # Preparar IDs para OneSignal (usando user_id como external_user_id)
        user_ids_for_onesignal = [str(user["internal_id"]) for user in users_to_notify]
        
        # Personalizar mensaje según el contexto
        chat_name = chat_room.name or "chat"
        
        # Personalizar título según tipo de contenido
        if content_type == "event":
            notification_title = f"📅 {sender_name} - Evento en {chat_name}"
        else:
            notification_title = f"💬 {sender_name} en {chat_name}"
        
        # Truncar mensaje si es muy largo
        truncated_message = message_text[:100] + "..." if len(message_text) > 100 else message_text
        
        # Datos adicionales para deep linking
        notification_data = {
            "type": "chat_message" if content_type == "chat" else "event_notification",
            "content_type": content_type,
            "chat_room_id": str(chat_room.id),
            "channel_id": chat_room.stream_channel_id,
            "sender_id": str(sender_id),
            "message_preview": truncated_message
        }
        
        logger.info(f"📤 Enviando notificación {content_type} a {len(user_ids_for_onesignal)} usuarios:")
        for user in users_to_notify:
            logger.info(f"   👤 {user['name']} (ID: {user['internal_id']}, unread: {user['unread_count']})")
        
        # Enviar via OneSignal
        result = notification_service.send_to_users(
            user_ids=user_ids_for_onesignal,
            title=notification_title,
            message=truncated_message,
            data=notification_data,
            db=db
        )
        
        if result.get("success"):
            logger.info(f"✅ Notificación {content_type} enviada exitosamente: {result.get('recipients', 0)} destinatarios")
        else:
            logger.error(f"❌ Error enviando notificación {content_type}: {result.get('errors', [])}")
            
    except Exception as e:
        logger.error(f"Error enviando notificaciones dirigidas: {str(e)}", exc_info=True)


async def send_chat_notifications_async(
    db: Session, 
    sender_id: int, 
    chat_room: ChatRoom, 
    message_text: str
):
    """
    Envía notificaciones push en segundo plano (función legacy).
    """
    try:
        # Crear nueva sesión de DB para el hilo de background
        from app.db.session import SessionLocal
        async_db = SessionLocal()
        
        try:
            await chat_service.send_chat_notification(
                async_db,
                sender_id,
                chat_room,
                message_text,
                notification_service
            )
        finally:
            async_db.close()
            
    except Exception as e:
        logger.error(f"Error en notificaciones async: {str(e)}", exc_info=True)


async def process_mentions_async(
    db: Session,
    message_text: str,
    chat_room: ChatRoom,
    sender_id: int
):
    """
    Procesa menciones en segundo plano.
    """
    try:
        # Crear nueva sesión de DB para el hilo de background
        from app.db.session import SessionLocal
        async_db = SessionLocal()
        
        try:
            await chat_service.process_message_mentions(
                async_db,
                message_text,
                chat_room,
                sender_id,
                notification_service
            )
        finally:
            async_db.close()
            
    except Exception as e:
        logger.error(f"Error procesando menciones async: {str(e)}", exc_info=True)


async def update_chat_activity_async(
    db: Session,
    chat_room: ChatRoom,
    sender_id: int
):
    """
    Actualiza la actividad del chat en segundo plano.
    """
    try:
        # Crear nueva sesión de DB para el hilo de background
        from app.db.session import SessionLocal
        async_db = SessionLocal()
        
        try:
            await chat_service.update_chat_activity(
                async_db,
                chat_room,
                sender_id
            )
        finally:
            async_db.close()
            
    except Exception as e:
        logger.error(f"Error actualizando actividad async: {str(e)}", exc_info=True)


async def process_special_events_async(
    db: Session,
    message: Dict[Any, Any],
    chat_room: ChatRoom,
    sender_id: int
):
    """
    Procesa eventos especiales en segundo plano.
    """
    try:
        # Crear nueva sesión de DB para el hilo de background
        from app.db.session import SessionLocal
        async_db = SessionLocal()
        
        try:
            message_text = message.get("text", "").lower()
            
            # Procesar mensajes de bienvenida
            if "bienvenido" in message_text or "welcome" in message_text:
                logger.info(f"Procesando mensaje de bienvenida en chat {chat_room.id}")
                
                # Aquí puedes agregar lógica específica para mensajes de bienvenida
                # Por ejemplo: enviar información adicional, activar funciones especiales, etc.
                
            # Procesar comandos especiales (si los hay)
            if message_text.startswith("/"):
                await process_chat_commands_async(async_db, message_text, chat_room, sender_id)
                
        finally:
            async_db.close()
            
    except Exception as e:
        logger.error(f"Error procesando eventos especiales async: {str(e)}", exc_info=True)


async def process_chat_commands_async(
    db: Session,
    message_text: str,
    chat_room: ChatRoom,
    sender_id: int
):
    """
    Procesa comandos de chat como /help, /stats, etc.
    """
    try:
        command = message_text.split()[0].lower()
        
        if command == "/stats":
            # Obtener estadísticas del chat
            stats = chat_service.get_chat_statistics(db, chat_room.id)
            logger.info(f"Estadísticas solicitadas para chat {chat_room.id}: {stats}")
            
        elif command == "/help":
            logger.info(f"Ayuda solicitada en chat {chat_room.id} por usuario {sender_id}")
            
        # Agregar más comandos según necesidad
        
    except Exception as e:
        logger.error(f"Error procesando comandos de chat: {str(e)}", exc_info=True)


@router.post("/stream/channel-deleted", status_code=status.HTTP_200_OK)
async def handle_channel_deleted(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(verify_stream_webhook_signature)
):
    """
    Webhook endpoint for handling channel deletion from GetStream.
    """
    try:
        payload = await request.json()
        channel = payload.get("channel", {})
        
        channel_id = channel.get("id")
        if not channel_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing channel ID"
            )
        
        # Buscar y limpiar la sala en la base de datos local
        chat_room = db.query(ChatRoom).filter(ChatRoom.stream_channel_id == channel_id).first()
        if chat_room:
            # Eliminar miembros y la sala
            from app.repositories.chat import chat_repository
            chat_repository.delete_room(db, chat_room.id)
            logger.info(f"Sala de chat {chat_room.id} eliminada tras eliminación del canal {channel_id}")
        
        return {"status": "success", "message": "Channel deletion processed"}
        
    except Exception as e:
        logger.error(f"Error processing channel deletion webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )


@router.post("/stream/user-banned", status_code=status.HTTP_200_OK)
async def handle_user_banned(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(verify_stream_webhook_signature)
):
    """
    Webhook endpoint for handling user bans from GetStream.
    """
    try:
        payload = await request.json()
        user_data = payload.get("user", {})
        channel = payload.get("channel", {})
        
        stream_user_id = user_data.get("id")
        channel_id = channel.get("id")
        
        if not all([stream_user_id, channel_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields"
            )
        
        logger.info(f"Usuario {stream_user_id} baneado del canal {channel_id}")
        
        # Aquí puedes agregar lógica adicional para manejar el baneo
        # Por ejemplo: actualizar estado en BD local, enviar notificaciones, etc.
        
        return {"status": "success", "message": "User ban processed"}
        
    except Exception as e:
        logger.error(f"Error processing user ban webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )


@router.post("/stream/auth", status_code=status.HTTP_200_OK)
async def stream_auth_webhook(request: Request):
    """
    Webhook de autorización para Stream Chat.
    Valida el acceso de usuarios a canales específicos basándose en membresía de gimnasio.
    
    Este webhook se ejecuta cada vez que un usuario intenta:
    - Unirse a un canal
    - Leer mensajes de un canal  
    - Enviar mensajes a un canal
    
    Returns:
        Dict: {"allow": true/false, "reason": "..."}
    """
    try:
        # Obtener el payload del webhook
        payload = await request.json()
        
        # Obtener información del webhook
        webhook_type = payload.get("type", "")
        user_data = payload.get("user", {})
        channel_data = payload.get("channel", {})
        
        logger.info(f"🔐 Stream auth webhook: type={webhook_type}, user={user_data.get('id')}, channel={channel_data.get('id')}")
        
        # Validar acceso según el tipo de webhook
        if webhook_type in ["channel.join", "message.new", "channel.read", "channel.query"]:
            result = stream_security_webhook.validate_channel_access(payload)
            
            # Registrar eventos de seguridad si el acceso es denegado
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
                
            logger.info(f"🔐 Auth result: {result}")
            return result
        
        # Para otros tipos de webhook, permitir por defecto pero logear
        logger.info(f"🔐 Webhook type {webhook_type} permitido por defecto")
        return {"allow": True}
        
    except Exception as e:
        logger.error(f"🔐 Error procesando webhook de autorización: {str(e)}", exc_info=True)
        
        # En caso de error, denegar acceso por seguridad
        return {"allow": False, "reason": "Error interno del servidor"}


@router.post("/stream/events", status_code=status.HTTP_200_OK)
async def stream_events_webhook(request: Request):
    """
    Webhook para eventos generales de Stream Chat.
    Usado para auditoría y monitoreo adicional.
    """
    try:
        payload = await request.json()
        event_type = payload.get("type", "")
        
        # Log de eventos para auditoría
        logger.info(f"📊 Stream event recibido: {event_type}")
        
        # Procesar eventos específicos que requieren atención
        if event_type in ["user.banned", "user.muted", "channel.truncated"]:
            logger.warning(f"⚠️  Evento de moderación detectado: {event_type}")
            # Aquí se pueden agregar alertas adicionales
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"📊 Error procesando evento de Stream: {str(e)}")
        return {"status": "error"}


# ========== ENDPOINTS DE DIAGNÓSTICO ==========

@router.post("/stream/test", status_code=status.HTTP_200_OK)
async def stream_test_webhook(request: Request):
    """
    Endpoint de diagnóstico para probar conectividad con Stream.
    NO requiere verificación de firma para testing inicial.
    """
    logger.info("🧪 ========== TEST WEBHOOK STREAM ==========")
    logger.info(f"📡 Headers: {dict(request.headers)}")
    logger.info(f"🌐 Client: {request.client.host if request.client else 'unknown'}")
    logger.info(f"📊 Method: {request.method}")
    logger.info(f"🌐 URL: {request.url}")
    
    try:
        body = await request.body()
        logger.info(f"📦 Body size: {len(body)} bytes")
        
        if body:
            payload = await request.json()
            logger.info(f"📦 Payload: {payload}")
        else:
            logger.info("📦 Body vacío")
            
        return {
            "status": "success", 
            "message": "Test webhook recibido correctamente",
            "timestamp": "2025-07-28",
            "endpoint": "/stream/test"
        }
        
    except Exception as e:
        logger.error(f"🧪 Error en test webhook: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }


@router.get("/stream/health", status_code=status.HTTP_200_OK)
async def stream_health_check():
    """
    Health check simple para verificar que el endpoint está disponible.
    """
    logger.info("❤️  Health check de Stream webhooks")
    return {
        "status": "healthy",
        "service": "stream-webhooks",
        "timestamp": "2025-07-28",
        "endpoints": [
            "/stream/new-message",
            "/stream/test", 
            "/stream/health",
            "/stream/auth",
            "/stream/events"
        ]
    }


@router.post("/stream/debug", status_code=status.HTTP_200_OK)
async def stream_debug_webhook(request: Request):
    """
    Endpoint de debug que loggea TODO sin procesar nada.
    Útil para ver exactamente qué está enviando Stream.
    """
    logger.info("🐛 ========== DEBUG WEBHOOK STREAM ==========")
    
    # Log de TODOS los headers
    for header_name, header_value in request.headers.items():
        logger.info(f"🏷️  Header {header_name}: {header_value}")
    
    # Log del body raw
    body = await request.body()
    logger.info(f"📦 Raw body: {body}")
    
    # Log del JSON parseado
    try:
        if body:
            payload = await request.json()
            logger.info(f"📋 Parsed JSON: {payload}")
    except Exception as e:
        logger.error(f"🐛 Error parsing JSON: {str(e)}")
    
    logger.info("🐛 ========== FIN DEBUG WEBHOOK ==========")
    
    return {"status": "debug_complete", "logged": True} 