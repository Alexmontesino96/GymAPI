"""
AsyncGymChatService - Servicio async para gestionar el canal general del gimnasio.

Este módulo proporciona funcionalidades async para la creación automática del canal
general y la adición de nuevos miembros con mensajes de bienvenida.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging

from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.schemas.chat import ChatRoomCreate
from app.repositories.async_chat import async_chat_repository
from app.services.chat import chat_service
from app.core.stream_client import stream_client

logger = logging.getLogger("async_gym_chat_service")


class AsyncGymChatService:
    """
    Servicio async para gestionar el canal general del gimnasio.

    Todos los métodos son async y utilizan AsyncSession.

    Canal General:
    - Creación automática al inicializar gimnasio
    - Auto-adición de todos los miembros del gimnasio
    - Mensajes de bienvenida automatizados
    - Gestión de membresías del canal

    Métodos principales:
    - get_or_create_general_channel() - Obtiene o crea canal general
    - add_user_to_general_channel() - Agrega usuario al canal
    - remove_user_from_general_channel() - Remueve usuario del canal
    - send_welcome_message() - Envía mensaje de bienvenida
    """

    GENERAL_CHANNEL_NAME = "General"
    GENERAL_CHANNEL_DESCRIPTION = "Canal general del gimnasio para comunicaciones importantes y bienvenida"

    async def get_or_create_general_channel(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Optional[ChatRoom]:
        """
        Obtiene o crea el canal general del gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            ChatRoom del canal general, o None si hay error

        Note:
            El canal general se crea automáticamente si no existe.
            Todos los miembros del gimnasio son agregados automáticamente.
        """
        try:
            # Buscar canal general existente
            result = await db.execute(
                select(ChatRoom).where(
                    and_(
                        ChatRoom.gym_id == gym_id,
                        ChatRoom.name == self.GENERAL_CHANNEL_NAME,
                        ChatRoom.is_direct == False,
                        ChatRoom.event_id.is_(None)
                    )
                )
            )
            general_channel = result.scalar_one_or_none()

            if general_channel:
                logger.info(f"Canal general encontrado para gym {gym_id}: {general_channel.id}")
                return general_channel

            # Si no existe, crearlo
            logger.info(f"Creando canal general para gym {gym_id}")
            return await self._create_general_channel(db, gym_id)

        except Exception as e:
            logger.error(f"Error obteniendo/creando canal general para gym {gym_id}: {str(e)}")
            return None

    async def _create_general_channel(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Optional[ChatRoom]:
        """
        Crea el canal general del gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            ChatRoom creado, o None si hay error

        Note:
            - Busca un admin/owner como creador
            - Si no hay admin, usa el primer usuario del gimnasio
            - Agrega todos los miembros del gimnasio automáticamente
        """
        try:
            # Obtener el gimnasio
            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()

            if not gym:
                logger.error(f"Gimnasio {gym_id} no encontrado")
                return None

            # Buscar un admin/owner del gimnasio para ser el creador
            result = await db.execute(
                select(UserGym).where(
                    and_(
                        UserGym.gym_id == gym_id,
                        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
                    )
                )
            )
            admin_membership = result.scalar_one_or_none()

            # Si no hay admin/owner, buscar cualquier usuario del gimnasio
            if not admin_membership:
                result = await db.execute(
                    select(UserGym).where(UserGym.gym_id == gym_id)
                )
                admin_membership = result.scalar_one_or_none()

            if not admin_membership:
                logger.warning(f"No hay usuarios en el gimnasio {gym_id} para crear canal general")
                return None

            creator_id = admin_membership.user_id

            # Obtener todos los miembros del gimnasio
            result = await db.execute(
                select(UserGym).where(UserGym.gym_id == gym_id)
            )
            gym_members = result.scalars().all()
            member_ids = [member.user_id for member in gym_members]

            # Crear datos del canal
            room_data = ChatRoomCreate(
                name=self.GENERAL_CHANNEL_NAME,
                is_direct=False,
                member_ids=member_ids,
                event_id=None
            )

            # Crear el canal usando el servicio de chat (sync)
            # TODO: Migrar chat_service.create_room a async
            result = chat_service.create_room(db, creator_id, room_data, gym_id)

            # Obtener el objeto ChatRoom creado
            result_query = await db.execute(
                select(ChatRoom).where(ChatRoom.id == result["id"])
            )
            general_channel = result_query.scalar_one_or_none()

            logger.info(f"Canal general creado para gym {gym_id}: {general_channel.id} con {len(member_ids)} miembros")
            return general_channel

        except Exception as e:
            logger.error(f"Error creando canal general para gym {gym_id}: {str(e)}")
            return None

    async def add_user_to_general_channel(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Agrega un usuario al canal general del gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario a agregar

        Returns:
            True si se agregó exitosamente, False en caso contrario

        Note:
            - Crea el canal general si no existe
            - Idempotente: no falla si el usuario ya es miembro
        """
        try:
            # Obtener o crear el canal general
            general_channel = await self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                logger.error(f"No se pudo obtener/crear canal general para gym {gym_id}")
                return False

            # Verificar si el usuario ya es miembro
            result = await db.execute(
                select(ChatMember).where(
                    and_(
                        ChatMember.room_id == general_channel.id,
                        ChatMember.user_id == user_id
                    )
                )
            )
            existing_member = result.scalar_one_or_none()

            if existing_member:
                logger.info(f"Usuario {user_id} ya es miembro del canal general de gym {gym_id}")
                return True

            # Agregar el usuario al canal (sync - TODO: migrar a async)
            chat_service.add_user_to_channel(db, general_channel.id, user_id)

            logger.info(f"Usuario {user_id} agregado al canal general de gym {gym_id}")
            return True

        except Exception as e:
            logger.error(f"Error agregando usuario {user_id} al canal general de gym {gym_id}: {str(e)}")
            return False

    async def remove_user_from_general_channel(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: int
    ) -> bool:
        """
        Remueve un usuario del canal general del gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario a remover

        Returns:
            True si se removió exitosamente, False en caso contrario
        """
        try:
            # Obtener el canal general
            general_channel = await self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                logger.warning(f"Canal general no encontrado para gym {gym_id}")
                return False

            # Remover el usuario del canal (sync - TODO: migrar a async)
            chat_service.remove_user_from_channel(db, general_channel.id, user_id)

            logger.info(f"Usuario {user_id} removido del canal general de gym {gym_id}")
            return True

        except Exception as e:
            logger.error(f"Error removiendo usuario {user_id} del canal general de gym {gym_id}: {str(e)}")
            return False

    async def get_general_channel_info(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del canal general del gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con información del canal:
            - id, name, stream_channel_id, stream_channel_type
            - member_count, created_at, updated_at
        """
        try:
            general_channel = await self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                return None

            # Contar miembros
            result = await db.execute(
                select(func.count(ChatMember.id)).where(
                    ChatMember.room_id == general_channel.id
                )
            )
            member_count = result.scalar()

            return {
                "id": general_channel.id,
                "name": general_channel.name,
                "stream_channel_id": general_channel.stream_channel_id,
                "stream_channel_type": general_channel.stream_channel_type,
                "member_count": member_count,
                "created_at": general_channel.created_at,
                "updated_at": general_channel.updated_at
            }

        except Exception as e:
            logger.error(f"Error obteniendo info del canal general de gym {gym_id}: {str(e)}")
            return None

    async def send_welcome_message(
        self,
        db: AsyncSession,
        gym_id: int,
        new_user_id: int
    ) -> bool:
        """
        Envía un mensaje de bienvenida al canal general cuando se une un nuevo usuario.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            new_user_id: ID del nuevo usuario

        Returns:
            True si se envió el mensaje exitosamente

        Note:
            - Mensaje enviado por usuario bot del gimnasio
            - Incluye nombre del usuario y del gimnasio
            - Usa Stream Chat API para enviar mensaje
        """
        try:
            # Obtener información del usuario y gimnasio
            result = await db.execute(
                select(User).where(User.id == new_user_id)
            )
            user = result.scalar_one_or_none()

            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()

            if not user or not gym:
                logger.error(f"Usuario {new_user_id} o gimnasio {gym_id} no encontrado")
                return False

            general_channel = await self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                logger.error(f"Canal general no disponible para gym {gym_id}")
                return False

            # Crear mensaje de bienvenida
            user_name = user.email.split('@')[0] if user.email else f"Usuario {new_user_id}"
            welcome_message = f"¡Bienvenido/a {user_name} a {gym.name}! 🎉\n\nEste es el canal general donde compartimos información importante del gimnasio. ¡Esperamos que disfrutes tu experiencia con nosotros!"

            # Enviar mensaje usando Stream Chat API
            try:
                # Crear un ID de usuario oficial del gimnasio
                gym_bot_user_id = f"gym_{gym_id}_bot"

                # Asegurar que el usuario del gimnasio existe en Stream
                try:
                    stream_client.update_user({
                        "id": gym_bot_user_id,
                        "name": f"{gym.name} - Equipo",
                        "image": gym.logo_url or "https://via.placeholder.com/150",
                        "role": "admin",
                        "teams": [f"gym_{gym_id}"]  # Asignar bot al team del gimnasio
                    })
                except Exception as user_error:
                    logger.warning(f"No se pudo crear/actualizar usuario bot del gimnasio: {user_error}")

                channel = stream_client.channel(
                    general_channel.stream_channel_type,
                    general_channel.stream_channel_id
                )

                # Enviar mensaje como el perfil oficial del gimnasio
                channel.send_message({
                    "text": welcome_message
                }, gym_bot_user_id)

                logger.info(f"Mensaje de bienvenida enviado para usuario {new_user_id} en gym {gym_id} por perfil oficial del gimnasio")
                return True

            except Exception as stream_error:
                logger.error(f"Error enviando mensaje de bienvenida via Stream: {stream_error}")
                return False

        except Exception as e:
            logger.error(f"Error enviando mensaje de bienvenida para usuario {new_user_id} en gym {gym_id}: {str(e)}")
            return False


# Instancia singleton del servicio async
async_gym_chat_service = AsyncGymChatService()
