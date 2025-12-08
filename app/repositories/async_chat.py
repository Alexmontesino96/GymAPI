"""
AsyncChatRepository - Repositorio async para operaciones de chat con Stream Chat.

Este repositorio gestiona las referencias locales a canales de Stream Chat
y la membresía de usuarios en salas de chat.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from fastapi.encoders import jsonable_encoder
import logging

from app.models.chat import ChatRoom, ChatMember
from app.schemas.chat import ChatRoomCreate, ChatRoomUpdate

# Configurar logger
logger = logging.getLogger("async_chat_repository")


class AsyncChatRepository:
    """
    Repositorio async para operaciones de chat.

    Este repositorio NO hereda de AsyncBaseRepository porque ChatRoom
    tiene una estructura especial vinculada a Stream Chat.

    Métodos principales:
    - create_room() - Crear sala con Stream Chat ID
    - get_room() - Obtener sala por ID
    - get_room_by_stream_id() - Obtener por Stream channel ID
    - get_direct_chat() - Buscar chat directo entre 2 usuarios
    - get_user_rooms() - Todas las salas de un usuario
    - get_event_room() - Sala asociada a un evento
    - update_room() - Actualizar sala
    - add_member_to_room() - Añadir miembro
    - remove_member_from_room() - Eliminar miembro
    """

    async def create_room(
        self,
        db: AsyncSession,
        *,
        stream_channel_id: str,
        stream_channel_type: str,
        room_data: ChatRoomCreate,
        gym_id: int
    ) -> ChatRoom:
        """
        Crea una referencia local a un canal de Stream Chat.

        Args:
            db: Sesión async de base de datos
            stream_channel_id: ID del canal en Stream Chat
            stream_channel_type: Tipo de canal en Stream (messaging, direct, team)
            room_data: Datos de la sala (name, member_ids, event_id, etc.)
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Sala de chat creada con miembros asociados

        Note:
            Crea la sala y añade todos los miembros en la misma transacción.
        """
        logger.info(
            f"Iniciando creación de sala en BD: stream_id={stream_channel_id}, "
            f"event_id={room_data.event_id}, gym_id={gym_id}"
        )
        try:
            db_room = ChatRoom(
                stream_channel_id=stream_channel_id,
                stream_channel_type=stream_channel_type,
                name=room_data.name,
                gym_id=gym_id,  # Multi-tenant
                is_direct=room_data.is_direct,
                event_id=room_data.event_id
            )
            logger.debug(f"Objeto ChatRoom creado con: {db_room.__dict__}")
            db.add(db_room)
            logger.debug("Objeto añadido a la sesión, realizando flush...")
            await db.flush()
            logger.debug("Flush realizado con éxito")
            await db.refresh(db_room)
            logger.debug(
                f"Objeto actualizado después de refresh: id={db_room.id}, "
                f"event_id={db_room.event_id}, gym_id={db_room.gym_id}"
            )

            # Añadir miembros usando IDs internos
            member_count = 0
            for member_id in room_data.member_ids:
                db_member = ChatMember(
                    room_id=db_room.id,
                    user_id=member_id
                )
                db.add(db_member)
                member_count += 1

            logger.debug(f"Añadidos {member_count} miembros, realizando flush final...")
            await db.flush()
            logger.info(
                f"Sala creada exitosamente en BD: id={db_room.id}, "
                f"event_id={db_room.event_id}, gym_id={db_room.gym_id}, "
                f"stream_id={stream_channel_id}"
            )

            return db_room
        except Exception as e:
            logger.error(f"Error al crear sala en BD: {str(e)}", exc_info=True)
            await db.rollback()
            raise

    async def get_room(self, db: AsyncSession, *, room_id: int) -> Optional[ChatRoom]:
        """
        Obtiene una sala por su ID interno.

        Args:
            db: Sesión async de base de datos
            room_id: ID interno de la sala

        Returns:
            Sala encontrada o None
        """
        stmt = select(ChatRoom).where(ChatRoom.id == room_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_room_by_stream_id(
        self,
        db: AsyncSession,
        *,
        stream_channel_id: str
    ) -> Optional[ChatRoom]:
        """
        Obtiene una sala por su ID de Stream Chat.

        Args:
            db: Sesión async de base de datos
            stream_channel_id: ID del canal en Stream Chat

        Returns:
            Sala encontrada o None
        """
        stmt = select(ChatRoom).where(ChatRoom.stream_channel_id == stream_channel_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_direct_chat(
        self,
        db: AsyncSession,
        *,
        user1_id: int,
        user2_id: int
    ) -> Optional[ChatRoom]:
        """
        Obtiene un chat directo entre dos usuarios.

        Args:
            db: Sesión async de base de datos
            user1_id: ID interno del primer usuario
            user2_id: ID interno del segundo usuario

        Returns:
            Sala de chat directo si existe, None en caso contrario

        Note:
            Verifica que la sala sea directa (is_direct=True) y que
            tenga exactamente 2 miembros (ambos usuarios).
        """
        # Buscar habitaciones directas donde ambos usuarios sean miembros
        stmt = (
            select(ChatRoom)
            .join(ChatMember)
            .where(
                and_(
                    ChatRoom.is_direct == True,
                    ChatMember.user_id.in_([user1_id, user2_id])
                )
            )
        )
        result = await db.execute(stmt)
        rooms = list(result.scalars().all())

        # Filtrar para encontrar habitaciones donde ambos usuarios son miembros
        for room in rooms:
            # Cargar members de la sala
            members_stmt = select(ChatMember).where(ChatMember.room_id == room.id)
            members_result = await db.execute(members_stmt)
            members = list(members_result.scalars().all())
            member_ids = [member.user_id for member in members]

            if user1_id in member_ids and user2_id in member_ids and len(member_ids) == 2:
                return room

        return None

    async def get_user_rooms(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> List[ChatRoom]:
        """
        Obtiene todas las salas de chat de un usuario.

        Args:
            db: Sesión async de base de datos
            user_id: ID interno del usuario

        Returns:
            Lista de salas donde el usuario es miembro
        """
        stmt = (
            select(ChatRoom)
            .join(ChatMember)
            .where(ChatMember.user_id == user_id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_event_room(
        self,
        db: AsyncSession,
        *,
        event_id: int
    ) -> Optional[ChatRoom]:
        """
        Obtiene la sala asociada a un evento.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento

        Returns:
            Sala del evento o None

        Note:
            Los eventos tienen salas de chat asociadas automáticamente.
        """
        stmt = select(ChatRoom).where(ChatRoom.event_id == event_id)
        result = await db.execute(stmt)
        room = result.scalar_one_or_none()
        logger.debug(
            f"Búsqueda de sala para evento {event_id}: "
            f"{'encontrada' if room else 'no encontrada'}"
        )
        return room

    async def update_room(
        self,
        db: AsyncSession,
        *,
        db_obj: ChatRoom,
        obj_in: ChatRoomUpdate
    ) -> ChatRoom:
        """
        Actualiza una sala de chat.

        Args:
            db: Sesión async de base de datos
            db_obj: Sala existente a actualizar
            obj_in: Datos de actualización

        Returns:
            Sala actualizada
        """
        update_data = jsonable_encoder(obj_in, exclude_unset=True)

        for field in update_data:
            setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def add_member_to_room(
        self,
        db: AsyncSession,
        *,
        room_id: int,
        user_id: int
    ) -> ChatMember:
        """
        Añade un miembro a una sala de chat.

        Args:
            db: Sesión async de base de datos
            room_id: ID de la sala
            user_id: ID interno del usuario

        Returns:
            Membresía creada o existente

        Note:
            Si el usuario ya es miembro, retorna la membresía existente.
        """
        # Verificar si ya es miembro
        stmt = select(ChatMember).where(
            and_(
                ChatMember.room_id == room_id,
                ChatMember.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Crear nuevo miembro
        db_member = ChatMember(
            room_id=room_id,
            user_id=user_id
        )
        db.add(db_member)
        await db.flush()
        await db.refresh(db_member)
        return db_member

    async def remove_member_from_room(
        self,
        db: AsyncSession,
        *,
        room_id: int,
        user_id: int
    ) -> bool:
        """
        Elimina un miembro de una sala de chat.

        Args:
            db: Sesión async de base de datos
            room_id: ID de la sala
            user_id: ID interno del usuario

        Returns:
            True si se eliminó, False si no existía
        """
        stmt = select(ChatMember).where(
            and_(
                ChatMember.room_id == room_id,
                ChatMember.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        member = result.scalar_one_or_none()

        if member:
            db.delete(member)
            await db.flush()
            return True
        return False


# Instancia singleton del repositorio async
async_chat_repository = AsyncChatRepository()
