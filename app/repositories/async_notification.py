"""
AsyncNotificationRepository - Repositorio async para notificaciones y device tokens.

Este repositorio NO hereda de AsyncBaseRepository porque DeviceToken
no tiene gym_id (los tokens son globales a nivel usuario).

Gestiona tokens de dispositivos para notificaciones push con OneSignal.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, update, delete

from app.models.notification import DeviceToken


class AsyncNotificationRepository:
    """
    Repositorio async para gestión de device tokens.

    Este repositorio NO hereda de AsyncBaseRepository porque DeviceToken
    es un modelo global sin gym_id (los tokens están asociados a usuarios,
    no a gimnasios específicos).

    Métodos principales:
    - create_device_token() - Crear o actualizar token
    - get_active_tokens_by_user_ids() - Tokens activos de múltiples usuarios
    - get_user_device_tokens() - Tokens de un usuario específico
    - deactivate_token() - Desactivar token específico
    - deactivate_user_tokens() - Desactivar todos los tokens de usuario
    - update_last_used() - Actualizar última fecha de uso
    - cleanup_old_tokens() - Limpiar tokens antiguos inactivos
    """

    async def create_device_token(
        self,
        db: AsyncSession,
        user_id: str,
        device_token: str,
        platform: str
    ) -> DeviceToken:
        """
        Crea o actualiza un token de dispositivo.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario (auth0_id)
            device_token: Token del dispositivo (OneSignal player_id)
            platform: Plataforma del dispositivo (ios, android, web)

        Returns:
            Token creado o actualizado

        Note:
            Si el token ya existe para el usuario, solo actualiza platform
            y marca como activo.
        """
        # Buscar token existente
        stmt = select(DeviceToken).where(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.device_token == device_token
            )
        )
        result = await db.execute(stmt)
        existing_token = result.scalar_one_or_none()

        if existing_token:
            # Actualizar token existente
            existing_token.platform = platform
            existing_token.is_active = True
            existing_token.updated_at = datetime.now()
            db.add(existing_token)
            await db.flush()
            await db.refresh(existing_token)
            return existing_token

        # Crear nuevo token
        db_token = DeviceToken(
            user_id=user_id,
            device_token=device_token,
            platform=platform,
            is_active=True
        )
        db.add(db_token)
        await db.flush()
        await db.refresh(db_token)
        return db_token

    async def get_active_tokens_by_user_ids(
        self,
        db: AsyncSession,
        user_ids: List[str]
    ) -> List[DeviceToken]:
        """
        Obtiene tokens activos para una lista de usuarios.

        Args:
            db: Sesión async de base de datos
            user_ids: Lista de IDs de usuarios (auth0_id)

        Returns:
            Lista de tokens activos de los usuarios especificados

        Note:
            Útil para enviar notificaciones a múltiples usuarios
            (ej: todos los miembros de un evento)
        """
        stmt = select(DeviceToken).where(
            and_(
                DeviceToken.user_id.in_(user_ids),
                DeviceToken.is_active == True
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_device_tokens(
        self,
        db: AsyncSession,
        user_id: str
    ) -> List[DeviceToken]:
        """
        Obtiene todos los tokens activos de un usuario.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario (auth0_id)

        Returns:
            Lista de tokens activos del usuario

        Note:
            Un usuario puede tener múltiples tokens activos
            (ej: iPhone + iPad + Web)
        """
        stmt = select(DeviceToken).where(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.is_active == True
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_token(
        self,
        db: AsyncSession,
        device_token: str
    ) -> bool:
        """
        Desactiva un token específico.

        Args:
            db: Sesión async de base de datos
            device_token: Token del dispositivo a desactivar

        Returns:
            True si se desactivó algún token, False si no existía

        Note:
            Usado cuando el usuario cierra sesión en un dispositivo específico
            o cuando OneSignal reporta un token inválido
        """
        stmt = (
            update(DeviceToken)
            .where(DeviceToken.device_token == device_token)
            .values(
                is_active=False,
                updated_at=datetime.now()
            )
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount > 0

    async def deactivate_user_tokens(
        self,
        db: AsyncSession,
        user_id: str
    ) -> int:
        """
        Desactiva todos los tokens de un usuario.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario (auth0_id)

        Returns:
            Número de tokens desactivados

        Note:
            Usado cuando el usuario cierra sesión en todos los dispositivos
            o cuando se elimina la cuenta
        """
        stmt = (
            update(DeviceToken)
            .where(DeviceToken.user_id == user_id)
            .values(
                is_active=False,
                updated_at=datetime.now()
            )
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount

    async def update_last_used(
        self,
        db: AsyncSession,
        device_tokens: List[str]
    ) -> int:
        """
        Actualiza la fecha de último uso para varios tokens.

        Args:
            db: Sesión async de base de datos
            device_tokens: Lista de tokens a actualizar

        Returns:
            Número de tokens actualizados

        Note:
            Usado para tracking de actividad de dispositivos
            y para cleanup de tokens obsoletos
        """
        stmt = (
            update(DeviceToken)
            .where(DeviceToken.device_token.in_(device_tokens))
            .values(last_used=datetime.now())
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount

    async def cleanup_old_tokens(
        self,
        db: AsyncSession,
        days: int = 90
    ) -> int:
        """
        Elimina tokens inactivos antiguos.

        Args:
            db: Sesión async de base de datos
            days: Días de antigüedad para considerar un token obsoleto

        Returns:
            Número de tokens eliminados

        Note:
            Ejecutado periódicamente (ej: job de APScheduler)
            para mantener la tabla limpia y evitar enviar
            notificaciones a dispositivos desinstalados
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        stmt = delete(DeviceToken).where(
            and_(
                DeviceToken.is_active == False,
                or_(
                    DeviceToken.updated_at <= cutoff_date,
                    DeviceToken.last_used <= cutoff_date
                )
            )
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount


# Instancia singleton del repositorio async
async_notification_repository = AsyncNotificationRepository()
