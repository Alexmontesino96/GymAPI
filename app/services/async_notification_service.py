"""
AsyncOneSignalService - Servicio async para notificaciones push con OneSignal.

Este módulo maneja el envío de notificaciones push a usuarios y segmentos
usando OneSignal API de forma asíncrona.

Migrado en FASE 3 de la conversión sync → async.
"""

import httpx
import logging
import json
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.async_notification import async_notification_repository

logger = logging.getLogger("async_onesignal_service")

# Obtener credenciales de las variables de entorno (SIN defaults por seguridad)
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.environ.get("ONESIGNAL_REST_API_KEY")

# Validación en tiempo de importación
if not ONESIGNAL_APP_ID:
    logger.warning("⚠️  ONESIGNAL_APP_ID no configurado - las notificaciones push estarán deshabilitadas")
if not ONESIGNAL_REST_API_KEY:
    logger.warning("⚠️  ONESIGNAL_REST_API_KEY no configurado - las notificaciones push estarán deshabilitadas")


class AsyncOneSignalService:
    """
    Servicio async para notificaciones push con OneSignal.

    Todos los métodos HTTP son async usando httpx.AsyncClient.

    Funcionalidades:
    - Envío de notificaciones a usuarios por external_user_id
    - Envío de notificaciones a segmentos
    - Programación de notificaciones futuras
    - Notificaciones multi-canal para eventos cancelados
    - Actualización de tokens last_used

    Métodos principales:
    - send_to_users() - Enviar a lista de usuarios
    - send_to_segment() - Enviar a segmento
    - schedule_notification() - Programar para el futuro
    - notify_event_cancellation() - Multi-canal para eventos
    """

    def __init__(self, app_id: str, api_key: str):
        """
        Inicializa el servicio con credenciales de OneSignal.

        Args:
            app_id: OneSignal App ID
            api_key: OneSignal REST API Key

        Note:
            - Usa httpx.AsyncClient para llamadas async
        """
        self.app_id = app_id
        self.api_key = api_key
        self.base_url = "https://onesignal.com/api/v1/notifications"
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }

    async def send_to_users(
        self,
        user_ids: List[str],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Envía notificación a múltiples usuarios por su user_id.

        Args:
            user_ids: Lista de IDs externos de usuarios
            title: Título de la notificación
            message: Mensaje de la notificación
            data: Datos adicionales opcionales
            db: Sesión async de BD (opcional, para actualizar last_used)

        Returns:
            Dict con resultado:
            - success: bool
            - notification_id: str (si exitoso)
            - recipients: int (si exitoso)
            - errors: List[str] (si falla)

        Note:
            - Usa httpx.AsyncClient para llamada HTTP async
            - Actualiza tokens last_used si db se proporciona
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

            # Usar httpx.AsyncClient para llamada async
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    content=json.dumps(payload),
                    timeout=30.0
                )

            logger.debug(f"OneSignal response: {response.status_code} - {response.text}")

            if response.status_code == 200:
                result = response.json()

                # Actualizar último uso en BD si se proporciona sesión
                if db and result.get("id"):
                    if "errors" not in result or not result["errors"]:
                        await self._update_tokens_last_used(db, user_ids)

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

    async def send_to_segment(
        self,
        segment: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Envía notificación a un segmento de usuarios.

        Args:
            segment: Nombre del segmento en OneSignal
            title: Título de la notificación
            message: Mensaje de la notificación
            data: Datos adicionales opcionales

        Returns:
            Dict con resultado:
            - success: bool
            - notification_id: str (si exitoso)
            - recipients: int (si exitoso)
            - errors: List[str] (si falla)
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

            # Usar httpx.AsyncClient para llamada async
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    content=json.dumps(payload),
                    timeout=30.0
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

    async def schedule_notification(
        self,
        user_ids: List[str],
        title: str,
        message: str,
        send_after: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Programa una notificación para enviar en el futuro.

        Args:
            user_ids: Lista de IDs externos de usuarios
            title: Título de la notificación
            message: Mensaje de la notificación
            send_after: Timestamp ISO8601 (ej: "2023-04-07T15:00:00Z")
            data: Datos adicionales opcionales

        Returns:
            Dict con resultado:
            - success: bool
            - notification_id: str (si exitoso)
            - recipients: int (si exitoso)
            - errors: List[str] (si falla)
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

            # Usar httpx.AsyncClient para llamada async
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    content=json.dumps(payload),
                    timeout=30.0
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

    async def _update_tokens_last_used(self, db: AsyncSession, user_ids: List[str]) -> None:
        """
        Actualiza la última fecha de uso para los tokens de los usuarios.

        Args:
            db: Sesión async de base de datos
            user_ids: Lista de IDs de usuarios

        Note:
            - Usa async_notification_repository
            - No lanza excepciones, solo registra errores
        """
        try:
            tokens = await async_notification_repository.get_active_tokens_by_user_ids(db, user_ids)
            device_tokens = [token.device_token for token in tokens]
            if device_tokens:
                await async_notification_repository.update_last_used(db, device_tokens)
        except Exception as e:
            logger.error(f"Error updating tokens last_used: {str(e)}", exc_info=True)

    async def notify_event_cancellation(
        self,
        db: AsyncSession,
        event_title: str,
        event_id: int,
        gym_id: int,
        participant_user_ids: List[int],
        total_refunded_cents: int = 0,
        currency: str = "EUR",
        cancellation_reason: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Enviar notificaciones multi-canal sobre la cancelación de un evento.

        Canales de notificación:
        - Push (OneSignal): Notificación inmediata en dispositivos móviles
        - Email: Correo detallado sobre la cancelación (TODO: implementar)
        - Chat (Stream): Mensaje en el canal del evento si existe (TODO: implementar)

        Args:
            db: Sesión async de base de datos
            event_title: Título del evento cancelado
            event_id: ID del evento
            gym_id: ID del gimnasio
            participant_user_ids: Lista de IDs de usuarios participantes
            total_refunded_cents: Total reembolsado en centavos
            currency: Moneda del reembolso (default: EUR)
            cancellation_reason: Razón de la cancelación

        Returns:
            Dict con contadores de notificaciones enviadas:
            - push: Cantidad de notificaciones push enviadas
            - email: Cantidad de emails enviados (TODO)
            - chat: Cantidad de mensajes en chat enviados (TODO)
        """
        stats = {
            "push": 0,
            "email": 0,
            "chat": 0
        }

        if not participant_user_ids:
            logger.warning(f"No hay participantes para notificar sobre cancelación de evento {event_id}")
            return stats

        # Formatear monto reembolsado
        refund_text = ""
        if total_refunded_cents > 0:
            amount_display = total_refunded_cents / 100
            refund_text = f"Reembolso: {amount_display:.2f} {currency}"

        # Preparar mensaje
        title = f"Evento Cancelado: {event_title}"
        message_parts = [
            f"El evento '{event_title}' ha sido cancelado."
        ]

        if cancellation_reason:
            message_parts.append(f"Razón: {cancellation_reason}")

        if refund_text:
            message_parts.append(f"{refund_text} (procesado automáticamente)")

        message = " ".join(message_parts)

        # Convertir IDs a strings para OneSignal
        user_ids_str = [str(uid) for uid in participant_user_ids]

        # 1. NOTIFICACIÓN PUSH (OneSignal)
        try:
            push_result = await self.send_to_users(
                user_ids=user_ids_str,
                title=title,
                message=message,
                data={
                    "type": "event_cancelled",
                    "event_id": event_id,
                    "gym_id": gym_id,
                    "refund_cents": total_refunded_cents,
                    "currency": currency
                },
                db=db
            )

            if push_result.get("success"):
                stats["push"] = push_result.get("recipients", len(user_ids_str))
                logger.info(f"Notificación push enviada a {stats['push']} usuarios sobre cancelación de evento {event_id}")
            else:
                logger.error(f"Error enviando notificación push: {push_result.get('errors')}")

        except Exception as e:
            logger.error(f"Error al enviar notificación push de cancelación: {e}", exc_info=True)

        # 2. EMAIL (TODO: Implementar servicio de email)
        try:
            # TODO: Implementar envío de email con template de cancelación
            # Debería incluir:
            # - Detalles del evento cancelado
            # - Razón de la cancelación
            # - Información del reembolso (monto, método, tiempo estimado)
            # - Contacto de soporte

            logger.info(f"TODO: Enviar email de cancelación a {len(participant_user_ids)} usuarios")
            # stats["email"] = len(participant_user_ids)

        except Exception as e:
            logger.error(f"Error al enviar email de cancelación: {e}", exc_info=True)

        # 3. CHAT (Stream) - Mensaje automático en canal del evento
        try:
            # TODO: Verificar si el evento tiene chat_room asociado
            # Enviar mensaje automático al canal informando de la cancelación
            # Usar Stream Chat SDK para enviar mensaje como "system"

            logger.info(f"TODO: Enviar mensaje de cancelación en chat del evento {event_id}")
            # stats["chat"] = 1  # Un mensaje en el canal del evento

        except Exception as e:
            logger.error(f"Error al enviar mensaje de chat de cancelación: {e}", exc_info=True)

        return stats


# Instancia singleton del servicio async
async_notification_service = AsyncOneSignalService(
    app_id=ONESIGNAL_APP_ID,
    api_key=ONESIGNAL_REST_API_KEY
)
