"""
AsyncSQSNotificationService - Servicio async para notificaciones vía Amazon SQS.

Este servicio maneja:
- Productor: Encola mensajes de notificación async
- Consumidor: Procesa mensajes y envía notificaciones async
- Dead Letter Queue: Maneja mensajes fallidos
- Multi-tenant: Soporte completo de gym_id

Beneficios:
- Escalabilidad horizontal
- Resiliencia ante fallos
- No bloquea el proceso principal
- Reintentos automáticos
- Monitoreo centralizado
- Soporte async nativo con aioboto3

Migrado en FASE 3 de la conversión sync → async.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import aioboto3
    AIOBOTO3_AVAILABLE = True
except ImportError:
    AIOBOTO3_AVAILABLE = False
    logging.warning("aioboto3 not available - SQS features will be disabled")

from app.core.config import get_settings

logger = logging.getLogger("async_sqs_notification_service")


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

class NotificationMessageType(str, Enum):
    """Tipos de mensajes de notificación"""
    MEAL_REMINDER = "meal_reminder"
    ACHIEVEMENT = "achievement"
    CHALLENGE_UPDATE = "challenge_update"
    STREAK_MILESTONE = "streak_milestone"
    DAILY_PLAN = "daily_plan"


@dataclass
class NotificationMessage:
    """
    Estructura de mensaje para la cola SQS.

    Attributes:
        message_type: Tipo de mensaje (enum NotificationMessageType)
        user_id: ID del usuario
        gym_id: ID del gimnasio
        title: Título de la notificación
        body: Cuerpo del mensaje
        data: Datos adicionales opcionales
        created_at: Timestamp de creación (ISO format)
        retry_count: Contador de reintentos
    """
    message_type: str
    user_id: int
    gym_id: int
    title: str
    body: str
    data: Dict[str, Any]
    created_at: str = None
    retry_count: int = 0

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        """Serializar a JSON string"""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'NotificationMessage':
        """Deserializar desde JSON string"""
        data = json.loads(json_str)
        return cls(**data)


# ============================================================================
# SERVICIO SQS ASYNC
# ============================================================================

class AsyncSQSNotificationService:
    """
    Servicio async para manejar notificaciones de nutrición via Amazon SQS.

    Todos los métodos son async y utilizan aioboto3.

    Funcionalidades:
    - Encolar mensajes async (send_message, send_message_batch)
    - Recibir y procesar mensajes async
    - Integración con AsyncOneSignalService
    - Dead Letter Queue para mensajes fallidos
    - Estadísticas de cola en tiempo real

    Métodos principales:
    - enqueue_meal_reminder() - Recordatorios de comidas
    - enqueue_achievement() - Notificaciones de logros
    - enqueue_batch() - Batch de hasta 10 mensajes
    - process_messages() - Consumir y procesar mensajes

    Note:
        - Usa aioboto3 para operaciones async de SQS
        - Fallback automático si SQS no está configurado
        - Configuración centralizada desde Settings
    """

    def __init__(self):
        """
        Inicializa el servicio SQS async.

        Note:
            - Verifica disponibilidad de aioboto3
            - Valida credenciales AWS desde Settings
            - No crea cliente, usa context manager async
        """
        self.settings = get_settings()
        self.enabled = self._check_sqs_enabled()
        self.queue_url = None
        self.dlq_url = None

        if self.enabled:
            self.queue_url = self.settings.SQS_NUTRITION_QUEUE_URL
            self.dlq_url = self.settings.SQS_NUTRITION_DLQ_URL
            logger.info(f"AsyncSQS Nutrition initialized. Queue: {self.queue_url}")

    def _check_sqs_enabled(self) -> bool:
        """
        Verificar si SQS está configurado y aioboto3 disponible.

        Returns:
            bool: True si SQS está habilitado
        """
        if not AIOBOTO3_AVAILABLE:
            logger.warning("aioboto3 not installed - SQS disabled")
            return False

        return all([
            self.settings.AWS_ACCESS_KEY_ID,
            self.settings.AWS_SECRET_ACCESS_KEY,
            self.settings.SQS_NUTRITION_QUEUE_URL
        ])

    def _get_session(self):
        """
        Obtener sesión de aioboto3 para crear clientes.

        Returns:
            aioboto3.Session configurada con credenciales AWS
        """
        return aioboto3.Session(
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
            region_name=self.settings.AWS_REGION
        )

    # ========================================================================
    # PRODUCTOR - Métodos para encolar mensajes
    # ========================================================================

    async def enqueue_message(self, message: NotificationMessage) -> Optional[str]:
        """
        Encolar un mensaje de notificación en SQS async.

        Args:
            message: NotificationMessage a encolar

        Returns:
            Optional[str]: message_id de SQS si fue exitoso, None si falló

        Note:
            - Usa async context manager para cliente SQS
            - MessageAttributes con MessageType, GymId, UserId
            - DelaySeconds configurable (default: 0)
        """
        if not self.enabled:
            logger.warning("SQS not enabled, skipping enqueue")
            return None

        try:
            session = self._get_session()
            async with session.client('sqs') as sqs_client:
                response = await sqs_client.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=message.to_json(),
                    MessageAttributes={
                        'MessageType': {
                            'DataType': 'String',
                            'StringValue': message.message_type
                        },
                        'GymId': {
                            'DataType': 'Number',
                            'StringValue': str(message.gym_id)
                        },
                        'UserId': {
                            'DataType': 'Number',
                            'StringValue': str(message.user_id)
                        }
                    },
                    # Delay opcional para distribuir carga
                    DelaySeconds=0
                )

            message_id = response.get('MessageId')
            logger.debug(f"Message enqueued: {message_id} for user {message.user_id}")
            return message_id

        except Exception as e:
            logger.error(f"Failed to enqueue message: {e}", exc_info=True)
            return None

    def _create_meal_reminder_message(
        self,
        user_id: int,
        gym_id: int,
        meal_type: str,
        meal_name: str,
        plan_title: str,
        meal_id: Optional[int] = None,
        plan_id: Optional[int] = None
    ) -> NotificationMessage:
        """
        Crear un NotificationMessage para recordatorio de comida.

        No encola directamente, útil para uso con enqueue_batch.

        Args:
            user_id: ID del usuario
            gym_id: ID del gimnasio
            meal_type: Tipo de comida (breakfast, lunch, dinner, etc.)
            meal_name: Nombre de la comida
            plan_title: Título del plan nutricional
            meal_id: ID de la comida (opcional)
            plan_id: ID del plan (opcional)

        Returns:
            NotificationMessage listo para encolar

        Note:
            - Incluye emojis según tipo de comida
            - Textos en español para cada tipo
        """
        meal_emojis = {
            "breakfast": "🌅",
            "mid_morning": "🥤",
            "lunch": "🍽️",
            "afternoon": "☕",
            "dinner": "🌙",
            "post_workout": "💪",
            "late_snack": "🍿"
        }

        meal_texts = {
            "breakfast": "desayuno",
            "mid_morning": "snack de media mañana",
            "lunch": "almuerzo",
            "afternoon": "merienda",
            "dinner": "cena",
            "post_workout": "comida post-entreno",
            "late_snack": "snack nocturno"
        }

        emoji = meal_emojis.get(meal_type, "🍽️")
        meal_text = meal_texts.get(meal_type, "comida")

        return NotificationMessage(
            message_type=NotificationMessageType.MEAL_REMINDER,
            user_id=user_id,
            gym_id=gym_id,
            title=f"{emoji} Hora de tu {meal_text}",
            body=f"{meal_name} - {plan_title}",
            data={
                "type": "meal_reminder",
                "meal_type": meal_type,
                "meal_id": meal_id,
                "plan_id": plan_id,
                "action": "open_meal_plan"
            }
        )

    async def enqueue_meal_reminder(
        self,
        user_id: int,
        gym_id: int,
        meal_type: str,
        meal_name: str,
        plan_title: str,
        meal_id: Optional[int] = None,
        plan_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Encolar recordatorio de comida async.

        Args:
            user_id: ID del usuario
            gym_id: ID del gimnasio
            meal_type: Tipo de comida (breakfast, lunch, dinner)
            meal_name: Nombre de la comida
            plan_title: Título del plan
            meal_id: ID de la comida (opcional)
            plan_id: ID del plan (opcional)

        Returns:
            Optional[str]: message_id si fue exitoso
        """
        message = self._create_meal_reminder_message(
            user_id=user_id,
            gym_id=gym_id,
            meal_type=meal_type,
            meal_name=meal_name,
            plan_title=plan_title,
            meal_id=meal_id,
            plan_id=plan_id
        )
        return await self.enqueue_message(message)

    async def enqueue_achievement(
        self,
        user_id: int,
        gym_id: int,
        achievement_type: str,
        extra_data: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Encolar notificación de logro async.

        Args:
            user_id: ID del usuario
            gym_id: ID del gimnasio
            achievement_type: Tipo de logro (first_meal, week_streak, etc.)
            extra_data: Datos adicionales opcionales

        Returns:
            Optional[str]: message_id si fue exitoso

        Note:
            - Tipos soportados: first_meal, week_streak, month_streak,
              perfect_day, challenge_completed
            - Textos predefinidos con emojis
        """
        achievements = {
            "first_meal": {
                "title": "🎉 ¡Primera comida completada!",
                "body": "Has dado el primer paso en tu viaje nutricional"
            },
            "week_streak": {
                "title": "🔥 ¡Racha de 7 días!",
                "body": "Una semana completa siguiendo tu plan"
            },
            "month_streak": {
                "title": "🏆 ¡Racha de 30 días!",
                "body": "Un mes entero de consistencia. ¡Eres imparable!"
            },
            "perfect_day": {
                "title": "⭐ ¡Día perfecto!",
                "body": "Completaste todas las comidas del día"
            },
            "challenge_completed": {
                "title": "🥇 ¡Challenge completado!",
                "body": f"Has terminado el challenge: {extra_data.get('challenge_name', '') if extra_data else ''}"
            }
        }

        achievement = achievements.get(achievement_type)
        if not achievement:
            return None

        message = NotificationMessage(
            message_type=NotificationMessageType.ACHIEVEMENT,
            user_id=user_id,
            gym_id=gym_id,
            title=achievement["title"],
            body=achievement["body"],
            data={
                "type": "achievement",
                "achievement_type": achievement_type,
                "extra": extra_data or {}
            }
        )

        return await self.enqueue_message(message)

    async def enqueue_challenge_update(
        self,
        user_ids: List[int],
        gym_id: int,
        plan_id: int,
        plan_title: str,
        update_type: str
    ) -> int:
        """
        Encolar actualizaciones de challenge para múltiples usuarios async.

        Args:
            user_ids: Lista de IDs de usuarios
            gym_id: ID del gimnasio
            plan_id: ID del plan
            plan_title: Título del plan
            update_type: Tipo de actualización (started, halfway, ending_soon, completed)

        Returns:
            int: Número de mensajes encolados exitosamente

        Note:
            - Itera sobre usuarios y encola mensajes individuales
            - Usa await para cada enqueue_message
        """
        messages = {
            "started": {
                "title": "🚀 ¡El challenge ha comenzado!",
                "body": f"{plan_title} está en marcha. ¡A por ello!"
            },
            "halfway": {
                "title": "🎯 ¡Mitad del challenge!",
                "body": f"Llevas la mitad de {plan_title}. ¡Sigue así!"
            },
            "ending_soon": {
                "title": "⏰ ¡Últimos 3 días!",
                "body": f"{plan_title} está por terminar. ¡Sprint final!"
            },
            "completed": {
                "title": "🎊 ¡Challenge completado!",
                "body": f"¡Felicidades! Has completado {plan_title}"
            }
        }

        msg_content = messages.get(update_type)
        if not msg_content:
            return 0

        enqueued_count = 0
        for user_id in user_ids:
            message = NotificationMessage(
                message_type=NotificationMessageType.CHALLENGE_UPDATE,
                user_id=user_id,
                gym_id=gym_id,
                title=msg_content["title"],
                body=msg_content["body"],
                data={
                    "type": "challenge_update",
                    "update_type": update_type,
                    "plan_id": plan_id,
                    "plan_title": plan_title
                }
            )

            if await self.enqueue_message(message):
                enqueued_count += 1

        logger.info(f"Enqueued {enqueued_count}/{len(user_ids)} challenge updates")
        return enqueued_count

    async def enqueue_batch(self, messages: List[NotificationMessage]) -> Dict[str, int]:
        """
        Encolar múltiples mensajes en batch async (más eficiente).

        SQS permite hasta 10 mensajes por batch.

        Args:
            messages: Lista de NotificationMessage

        Returns:
            Dict con successful y failed counts

        Note:
            - Procesa en batches de 10 (límite de SQS)
            - Usa send_message_batch async
            - Retorna contadores de éxito/fallo
        """
        if not self.enabled:
            return {"successful": 0, "failed": len(messages)}

        results = {"successful": 0, "failed": 0}
        session = self._get_session()

        # Procesar en batches de 10 (límite de SQS)
        for i in range(0, len(messages), 10):
            batch = messages[i:i + 10]

            entries = []
            for idx, msg in enumerate(batch):
                entries.append({
                    'Id': str(idx),
                    'MessageBody': msg.to_json(),
                    'MessageAttributes': {
                        'MessageType': {
                            'DataType': 'String',
                            'StringValue': msg.message_type
                        },
                        'GymId': {
                            'DataType': 'Number',
                            'StringValue': str(msg.gym_id)
                        }
                    }
                })

            try:
                async with session.client('sqs') as sqs_client:
                    response = await sqs_client.send_message_batch(
                        QueueUrl=self.queue_url,
                        Entries=entries
                    )

                results["successful"] += len(response.get('Successful', []))
                results["failed"] += len(response.get('Failed', []))

            except Exception as e:
                logger.error(f"Batch enqueue failed: {e}", exc_info=True)
                results["failed"] += len(batch)

        return results

    # ========================================================================
    # CONSUMIDOR - Métodos para procesar mensajes
    # ========================================================================

    async def receive_messages(self, max_messages: int = 10, wait_time: int = 20) -> List[Dict]:
        """
        Recibir mensajes de la cola SQS async.

        Args:
            max_messages: Máximo de mensajes a recibir (1-10)
            wait_time: Tiempo de long polling en segundos (0-20)

        Returns:
            List[Dict]: Lista de mensajes con receipt_handle para eliminar después

        Note:
            - Usa long polling para reducir costos
            - MaxNumberOfMessages limitado a 10
            - Incluye MessageAttributeNames y AttributeNames
        """
        if not self.enabled:
            return []

        try:
            session = self._get_session()
            async with session.client('sqs') as sqs_client:
                response = await sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=min(max_messages, 10),
                    WaitTimeSeconds=wait_time,
                    MessageAttributeNames=['All'],
                    AttributeNames=['All']
                )

            messages = response.get('Messages', [])
            logger.debug(f"Received {len(messages)} messages from SQS")
            return messages

        except Exception as e:
            logger.error(f"Failed to receive messages: {e}", exc_info=True)
            return []

    async def delete_message(self, receipt_handle: str) -> bool:
        """
        Eliminar un mensaje procesado de la cola async.

        Args:
            receipt_handle: Handle del mensaje recibido

        Returns:
            bool: True si se eliminó correctamente

        Note:
            - Llamar después de procesar exitosamente
            - Si no se elimina, mensaje vuelve a la cola después de visibility timeout
        """
        if not self.enabled:
            return False

        try:
            session = self._get_session()
            async with session.client('sqs') as sqs_client:
                await sqs_client.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle
                )
            return True

        except Exception as e:
            logger.error(f"Failed to delete message: {e}", exc_info=True)
            return False

    async def process_single_message(self, sqs_message: Dict) -> bool:
        """
        Procesar un mensaje individual de SQS async.

        Args:
            sqs_message: Mensaje de SQS con Body y ReceiptHandle

        Returns:
            bool: True si se procesó correctamente

        Note:
            - Parsea NotificationMessage desde JSON
            - Usa async_notification_service para enviar push
            - No elimina mensaje, lo hace el caller
        """
        try:
            # Parsear el mensaje
            body = sqs_message.get('Body', '{}')
            notification = NotificationMessage.from_json(body)

            # Importar el servicio async aquí para evitar circular imports
            from app.services.async_notification_service import async_notification_service

            # Enviar la notificación via OneSignal (async)
            result = await async_notification_service.send_to_users(
                user_ids=[str(notification.user_id)],
                title=notification.title,
                message=notification.body,
                data=notification.data,
                db=None  # Sin DB para SQS worker
            )

            if result.get('success'):
                logger.info(
                    f"Notification sent: type={notification.message_type}, "
                    f"user={notification.user_id}"
                )
                return True
            else:
                logger.warning(
                    f"Notification failed: type={notification.message_type}, "
                    f"user={notification.user_id}, errors={result.get('errors')}"
                )
                return False

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return False

    async def process_messages(self, max_messages: int = 10) -> Dict[str, int]:
        """
        Procesar un batch de mensajes de la cola async.

        Args:
            max_messages: Máximo de mensajes a procesar

        Returns:
            Dict con processed y failed counts

        Note:
            - Recibe mensajes con receive_messages
            - Procesa cada uno con process_single_message
            - Elimina mensajes exitosos con delete_message
            - Mensajes fallidos vuelven a la cola tras visibility timeout
        """
        results = {"processed": 0, "failed": 0}

        messages = await self.receive_messages(max_messages)

        for sqs_message in messages:
            receipt_handle = sqs_message.get('ReceiptHandle')

            if await self.process_single_message(sqs_message):
                # Eliminar mensaje exitoso de la cola (async)
                await self.delete_message(receipt_handle)
                results["processed"] += 1
            else:
                # El mensaje volverá a estar disponible después del visibility timeout
                # Después de N intentos fallidos, irá a la DLQ
                results["failed"] += 1

        return results

    # ========================================================================
    # UTILIDADES
    # ========================================================================

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas de la cola async.

        Returns:
            Dict con estadísticas:
            - enabled: bool
            - queue_url: str
            - messages_available: int
            - messages_in_flight: int
            - messages_delayed: int

        Note:
            - Usa get_queue_attributes async
            - Valores aproximados (eventual consistency de SQS)
        """
        if not self.enabled:
            return {"enabled": False}

        try:
            session = self._get_session()
            async with session.client('sqs') as sqs_client:
                response = await sqs_client.get_queue_attributes(
                    QueueUrl=self.queue_url,
                    AttributeNames=[
                        'ApproximateNumberOfMessages',
                        'ApproximateNumberOfMessagesNotVisible',
                        'ApproximateNumberOfMessagesDelayed'
                    ]
                )

            attrs = response.get('Attributes', {})

            return {
                "enabled": True,
                "queue_url": self.queue_url,
                "messages_available": int(attrs.get('ApproximateNumberOfMessages', 0)),
                "messages_in_flight": int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
                "messages_delayed": int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
            }

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            return {"enabled": True, "error": str(e)}

    async def purge_queue(self) -> bool:
        """
        Purgar todos los mensajes de la cola async (CUIDADO: elimina todo).

        Solo usar en desarrollo/testing.

        Returns:
            bool: True si se purgó correctamente

        Warning:
            - Elimina TODOS los mensajes de la cola
            - No reversible
            - Solo para desarrollo/testing
        """
        if not self.enabled:
            return False

        try:
            session = self._get_session()
            async with session.client('sqs') as sqs_client:
                await sqs_client.purge_queue(QueueUrl=self.queue_url)

            logger.warning("Queue purged!")
            return True

        except Exception as e:
            logger.error(f"Failed to purge queue: {e}", exc_info=True)
            return False


# Instancia singleton del servicio async
async_sqs_notification_service = AsyncSQSNotificationService()
