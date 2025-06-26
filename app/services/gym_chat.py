"""
Servicio para gestionar el canal general del gimnasio.
Maneja la creación automática del canal general y la adición de nuevos miembros.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.models.gym import Gym
from app.schemas.chat import ChatRoomCreate
from app.repositories.chat import chat_repository
from app.services.chat import chat_service

logger = logging.getLogger(__name__)

class GymChatService:
    """
    Servicio para gestionar el canal general del gimnasio.
    """
    
    GENERAL_CHANNEL_NAME = "General"
    GENERAL_CHANNEL_DESCRIPTION = "Canal general del gimnasio para comunicaciones importantes y bienvenida"
    
    def get_or_create_general_channel(self, db: Session, gym_id: int) -> Optional[ChatRoom]:
        """
        Obtiene o crea el canal general del gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            ChatRoom: El canal general del gimnasio
        """
        try:
            # Buscar canal general existente
            general_channel = db.query(ChatRoom).filter(
                and_(
                    ChatRoom.gym_id == gym_id,
                    ChatRoom.name == self.GENERAL_CHANNEL_NAME,
                    ChatRoom.is_direct == False,
                    ChatRoom.event_id.is_(None)
                )
            ).first()
            
            if general_channel:
                logger.info(f"Canal general encontrado para gym {gym_id}: {general_channel.id}")
                return general_channel
            
            # Si no existe, crearlo
            logger.info(f"Creando canal general para gym {gym_id}")
            return self._create_general_channel(db, gym_id)
            
        except Exception as e:
            logger.error(f"Error obteniendo/creando canal general para gym {gym_id}: {str(e)}")
            return None
    
    def _create_general_channel(self, db: Session, gym_id: int) -> Optional[ChatRoom]:
        """
        Crea el canal general del gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            ChatRoom: El canal general creado
        """
        try:
            # Obtener el gimnasio
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
            if not gym:
                logger.error(f"Gimnasio {gym_id} no encontrado")
                return None
            
            # Buscar un admin/owner del gimnasio para ser el creador
            from app.models.user_gym import UserGym, GymRoleType
            admin_membership = db.query(UserGym).filter(
                and_(
                    UserGym.gym_id == gym_id,
                    UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
                )
            ).first()
            
            # Si no hay admin/owner, buscar cualquier usuario del gimnasio
            if not admin_membership:
                admin_membership = db.query(UserGym).filter(UserGym.gym_id == gym_id).first()
            
            if not admin_membership:
                logger.warning(f"No hay usuarios en el gimnasio {gym_id} para crear canal general")
                return None
            
            creator_id = admin_membership.user_id
            
            # Obtener todos los miembros del gimnasio
            gym_members = db.query(UserGym).filter(UserGym.gym_id == gym_id).all()
            member_ids = [member.user_id for member in gym_members]
            
            # Crear datos del canal
            room_data = ChatRoomCreate(
                name=self.GENERAL_CHANNEL_NAME,
                is_direct=False,
                member_ids=member_ids,
                event_id=None
            )
            
            # Crear el canal usando el servicio de chat
            result = chat_service.create_room(db, creator_id, room_data, gym_id)
            
            # Obtener el objeto ChatRoom creado
            general_channel = db.query(ChatRoom).filter(ChatRoom.id == result["id"]).first()
            
            logger.info(f"Canal general creado para gym {gym_id}: {general_channel.id} con {len(member_ids)} miembros")
            return general_channel
            
        except Exception as e:
            logger.error(f"Error creando canal general para gym {gym_id}: {str(e)}")
            return None
    
    def add_user_to_general_channel(self, db: Session, gym_id: int, user_id: int) -> bool:
        """
        Agrega un usuario al canal general del gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario a agregar
            
        Returns:
            bool: True si se agregó exitosamente, False en caso contrario
        """
        try:
            # Obtener o crear el canal general
            general_channel = self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                logger.error(f"No se pudo obtener/crear canal general para gym {gym_id}")
                return False
            
            # Verificar si el usuario ya es miembro
            existing_member = db.query(ChatMember).filter(
                and_(
                    ChatMember.room_id == general_channel.id,
                    ChatMember.user_id == user_id
                )
            ).first()
            
            if existing_member:
                logger.info(f"Usuario {user_id} ya es miembro del canal general de gym {gym_id}")
                return True
            
            # Agregar el usuario al canal
            chat_service.add_user_to_channel(db, general_channel.id, user_id)
            
            logger.info(f"Usuario {user_id} agregado al canal general de gym {gym_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error agregando usuario {user_id} al canal general de gym {gym_id}: {str(e)}")
            return False
    
    def remove_user_from_general_channel(self, db: Session, gym_id: int, user_id: int) -> bool:
        """
        Remueve un usuario del canal general del gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario a remover
            
        Returns:
            bool: True si se removió exitosamente, False en caso contrario
        """
        try:
            # Obtener el canal general
            general_channel = self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                logger.warning(f"Canal general no encontrado para gym {gym_id}")
                return False
            
            # Remover el usuario del canal
            chat_service.remove_user_from_channel(db, general_channel.id, user_id)
            
            logger.info(f"Usuario {user_id} removido del canal general de gym {gym_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removiendo usuario {user_id} del canal general de gym {gym_id}: {str(e)}")
            return False
    
    def get_general_channel_info(self, db: Session, gym_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del canal general del gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Dict con información del canal general
        """
        try:
            general_channel = self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                return None
            
            # Contar miembros
            member_count = db.query(ChatMember).filter(ChatMember.room_id == general_channel.id).count()
            
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
    
    def send_welcome_message(self, db: Session, gym_id: int, new_user_id: int) -> bool:
        """
        Envía un mensaje de bienvenida al canal general cuando se une un nuevo usuario.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            new_user_id: ID del nuevo usuario
            
        Returns:
            bool: True si se envió el mensaje exitosamente
        """
        try:
            # Obtener información del usuario y gimnasio
            user = db.query(User).filter(User.id == new_user_id).first()
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
            
            if not user or not gym:
                logger.error(f"Usuario {new_user_id} o gimnasio {gym_id} no encontrado")
                return False
            
            general_channel = self.get_or_create_general_channel(db, gym_id)
            if not general_channel:
                logger.error(f"Canal general no disponible para gym {gym_id}")
                return False
            
            # Crear mensaje de bienvenida
            user_name = user.email.split('@')[0] if user.email else f"Usuario {new_user_id}"
            welcome_message = f"¡Bienvenido/a {user_name} a {gym.name}! 🎉\n\nEste es el canal general donde compartimos información importante del gimnasio. ¡Esperamos que disfrutes tu experiencia con nosotros!"
            
            # Enviar mensaje usando Stream Chat API
            from app.core.stream_client import stream_client
            
            try:
                # Crear un ID de usuario oficial del gimnasio
                gym_bot_user_id = f"gym_{gym_id}_bot"
                
                # Asegurar que el usuario del gimnasio existe en Stream
                try:
                    stream_client.update_user({
                        "id": gym_bot_user_id,
                        "name": f"{gym.name} - Equipo",
                        "image": gym.logo_url or "https://via.placeholder.com/150",
                        "role": "admin"
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

# Instancia global del servicio
gym_chat_service = GymChatService() 