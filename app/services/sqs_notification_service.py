"""
Amazon SQS Service para notificaciones de nutrición.

Este servicio maneja:
- Productor: Encola mensajes de notificación
- Consumidor: Procesa mensajes y envía notificaciones
- Dead Letter Queue: Maneja mensajes fallidos

Beneficios:
- Escalabilidad horizontal
- Resiliencia ante fallos
- No bloquea el proceso principal
- Reintentos automáticos
- Monitoreo centralizado
"""

import boto3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.config import get_settings

logger = logging.getLogger(__name__)


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
    """Estructura de mensaje para la cola SQS"""
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
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'NotificationMessage':
        data = json.loads(json_str)
        return cls(**data)


# ============================================================================
# SERVICIO SQS
# ============================================================================

class SQSNotificationService:
    """
    Servicio para manejar notificaciones de nutrición via Amazon SQS.

    Usa la configuración centralizada de Settings (mismas credenciales AWS
    que el servicio de eventos, pero cola separada para notificaciones).

    Uso:
        # Productor (desde scheduler o endpoints)
        sqs_service.enqueue_meal_reminder(user_id=123, meal_type="lunch", ...)

        # Consumidor (desde worker)
        sqs_service.process_messages(max_messages=10)
    """

    def __init__(self):
        self.settings = get_settings()
        self.enabled = self._check_sqs_enabled()
        self.sqs_client = None
        self.queue_url = None
        self.dlq_url = None

        if self.enabled:
            self._initialize_client()

    def _check_sqs_enabled(self) -> bool:
        """Verificar si SQS está configurado para notificaciones de nutrición"""
        return all([
            self.settings.AWS_ACCESS_KEY_ID,
            self.settings.AWS_SECRET_ACCESS_KEY,
            self.settings.SQS_NUTRITION_QUEUE_URL
        ])

    def _initialize_client(self):
        """Inicializar cliente SQS de boto3 usando configuración centralizada"""
        try:
            self.sqs_client = boto3.client(
                'sqs',
                region_name=self.settings.AWS_REGION,
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY
            )
            self.queue_url = self.settings.SQS_NUTRITION_QUEUE_URL
            self.dlq_url = self.settings.SQS_NUTRITION_DLQ_URL

            logger.info(f"SQS Nutrition client initialized. Queue: {self.queue_url}")

        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {e}")
            self.enabled = False

    # ========================================================================
    # PRODUCTOR - Métodos para encolar mensajes
    # ========================================================================

    def enqueue_message(self, message: NotificationMessage) -> Optional[str]:
        """
        Encolar un mensaje de notificación en SQS.

        Args:
            message: NotificationMessage a encolar

        Returns:
            message_id de SQS si fue exitoso, None si falló
        """
        if not self.enabled:
            logger.warning("SQS not enabled, skipping enqueue")
            return None

        try:
            response = self.sqs_client.send_message(
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
            logger.error(f"Failed to enqueue message: {e}")
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
        Crear un NotificationMessage para recordatorio de comida (sin encolar).
        Útil para uso con enqueue_batch.

        Args:
            user_id: ID del usuario
            gym_id: ID del gimnasio
            meal_type: Tipo de comida
            meal_name: Nombre de la comida
            plan_title: Título del plan
            meal_id: ID de la comida (opcional)
            plan_id: ID del plan (opcional)

        Returns:
            NotificationMessage listo para encolar
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

    def enqueue_meal_reminder(
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
        Encolar recordatorio de comida.

        Args:
            user_id: ID del usuario
            gym_id: ID del gimnasio
            meal_type: Tipo de comida (breakfast, lunch, dinner)
            meal_name: Nombre de la comida
            plan_title: Título del plan
            meal_id: ID de la comida (opcional)
            plan_id: ID del plan (opcional)

        Returns:
            message_id si fue exitoso
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
        return self.enqueue_message(message)

    def enqueue_achievement(
        self,
        user_id: int,
        gym_id: int,
        achievement_type: str,
        extra_data: Optional[Dict] = None
    ) -> Optional[str]:
        """Encolar notificación de logro"""
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

        return self.enqueue_message(message)

    def enqueue_challenge_update(
        self,
        user_ids: List[int],
        gym_id: int,
        plan_id: int,
        plan_title: str,
        update_type: str
    ) -> int:
        """
        Encolar actualizaciones de challenge para múltiples usuarios.

        Args:
            user_ids: Lista de IDs de usuarios
            gym_id: ID del gimnasio
            plan_id: ID del plan
            plan_title: Título del plan
            update_type: Tipo de actualización (started, halfway, ending_soon, completed)

        Returns:
            Número de mensajes encolados exitosamente
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

            if self.enqueue_message(message):
                enqueued_count += 1

        logger.info(f"Enqueued {enqueued_count}/{len(user_ids)} challenge updates")
        return enqueued_count

    def enqueue_batch(self, messages: List[NotificationMessage]) -> Dict[str, int]:
        """
        Encolar múltiples mensajes en batch (más eficiente).
        SQS permite hasta 10 mensajes por batch.

        Args:
            messages: Lista de NotificationMessage

        Returns:
            Dict con successful y failed counts
        """
        if not self.enabled:
            return {"successful": 0, "failed": len(messages)}

        results = {"successful": 0, "failed": 0}

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
                response = self.sqs_client.send_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries
                )

                results["successful"] += len(response.get('Successful', []))
                results["failed"] += len(response.get('Failed', []))

            except Exception as e:
                logger.error(f"Batch enqueue failed: {e}")
                results["failed"] += len(batch)

        return results

    # ========================================================================
    # CONSUMIDOR - Métodos para procesar mensajes
    # ========================================================================

    def receive_messages(self, max_messages: int = 10, wait_time: int = 20) -> List[Dict]:
        """
        Recibir mensajes de la cola SQS.

        Args:
            max_messages: Máximo de mensajes a recibir (1-10)
            wait_time: Tiempo de long polling en segundos (0-20)

        Returns:
            Lista de mensajes con su receipt_handle para eliminar después
        """
        if not self.enabled:
            return []

        try:
            response = self.sqs_client.receive_message(
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
            logger.error(f"Failed to receive messages: {e}")
            return []

    def delete_message(self, receipt_handle: str) -> bool:
        """
        Eliminar un mensaje procesado de la cola.

        Args:
            receipt_handle: Handle del mensaje recibido

        Returns:
            True si se eliminó correctamente
        """
        if not self.enabled:
            return False

        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            return True

        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    def process_single_message(self, sqs_message: Dict) -> bool:
        """
        Procesar un mensaje individual de SQS.

        Args:
            sqs_message: Mensaje de SQS con Body y ReceiptHandle

        Returns:
            True si se procesó correctamente
        """
        try:
            # Parsear el mensaje
            body = sqs_message.get('Body', '{}')
            notification = NotificationMessage.from_json(body)

            # Importar el servicio de notificaciones aquí para evitar circular imports
            from app.services.notification_service import notification_service

            # Enviar la notificación via OneSignal
            result = notification_service.send_to_users(
                user_ids=[str(notification.user_id)],
                title=notification.title,
                message=notification.body,
                data=notification.data
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
            logger.error(f"Error processing message: {e}")
            return False

    def process_messages(self, max_messages: int = 10) -> Dict[str, int]:
        """
        Procesar un batch de mensajes de la cola.

        Args:
            max_messages: Máximo de mensajes a procesar

        Returns:
            Dict con processed y failed counts
        """
        results = {"processed": 0, "failed": 0}

        messages = self.receive_messages(max_messages)

        for sqs_message in messages:
            receipt_handle = sqs_message.get('ReceiptHandle')

            if self.process_single_message(sqs_message):
                # Eliminar mensaje exitoso de la cola
                self.delete_message(receipt_handle)
                results["processed"] += 1
            else:
                # El mensaje volverá a estar disponible después del visibility timeout
                # Después de N intentos fallidos, irá a la DLQ
                results["failed"] += 1

        return results

    # ========================================================================
    # UTILIDADES
    # ========================================================================

    def get_queue_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de la cola"""
        if not self.enabled:
            return {"enabled": False}

        try:
            response = self.sqs_client.get_queue_attributes(
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
            logger.error(f"Failed to get queue stats: {e}")
            return {"enabled": True, "error": str(e)}

    def purge_queue(self) -> bool:
        """
        Purgar todos los mensajes de la cola (CUIDADO: elimina todo).
        Solo usar en desarrollo/testing.
        """
        if not self.enabled:
            return False

        try:
            self.sqs_client.purge_queue(QueueUrl=self.queue_url)
            logger.warning("Queue purged!")
            return True

        except Exception as e:
            logger.error(f"Failed to purge queue: {e}")
            return False


# Instancia global del servicio
sqs_notification_service = SQSNotificationService()