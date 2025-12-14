"""
Tests para funcionalidad de eliminar grupos.

Tests para la función delete_group del servicio de chat,
que permite a admins/creadores eliminar grupos completamente.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.chat import chat_service
from app.models.chat import ChatRoom, ChatMember, ChatRoomStatus
from app.models.user import User
from app.models.user_gym import GymRoleType


class TestChatDeleteGroup:
    """Tests para eliminar grupos."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        db = Mock(spec=Session)
        db.commit = Mock()
        return db

    @pytest.fixture
    def sample_user_member(self):
        """Usuario miembro de muestra."""
        user = Mock(spec=User)
        user.id = 1
        user.auth0_id = "auth0|member123"
        user.email = "member@example.com"
        return user

    @pytest.fixture
    def sample_user_trainer(self):
        """Usuario entrenador de muestra."""
        user = Mock(spec=User)
        user.id = 2
        user.auth0_id = "auth0|trainer123"
        user.email = "trainer@example.com"
        return user

    @pytest.fixture
    def sample_user_admin(self):
        """Usuario admin de muestra."""
        user = Mock(spec=User)
        user.id = 3
        user.auth0_id = "auth0|admin123"
        user.email = "admin@example.com"
        return user

    @pytest.fixture
    def sample_empty_group(self):
        """Grupo vacío de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 101
        chat.stream_channel_id = "test-group-1"
        chat.stream_channel_type = "messaging"
        chat.name = "Empty Group"
        chat.gym_id = 1
        chat.is_direct = False
        chat.event_id = None
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    @pytest.fixture
    def sample_group_with_members(self):
        """Grupo con miembros de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 102
        chat.stream_channel_id = "test-group-2"
        chat.stream_channel_type = "messaging"
        chat.name = "Active Group"
        chat.gym_id = 1
        chat.is_direct = False
        chat.event_id = None
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    @pytest.fixture
    def sample_direct_chat(self):
        """Chat directo de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 100
        chat.stream_channel_id = "test-direct-1"
        chat.stream_channel_type = "messaging"
        chat.gym_id = 1
        chat.is_direct = True
        chat.event_id = None
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    @pytest.fixture
    def sample_event_chat(self):
        """Chat de evento de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 103
        chat.stream_channel_id = "test-event-1"
        chat.stream_channel_type = "messaging"
        chat.gym_id = 1
        chat.is_direct = False
        chat.event_id = 1
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    # Tests de Delete Group - Success Cases

    def test_delete_empty_group_as_admin(self, mock_db, sample_user_admin, sample_empty_group):
        """Test eliminar grupo vacío como admin."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.return_value = True

                # Act
                result = chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role,
                    hard_delete=True
                )

                # Assert
                assert result["success"] is True
                assert result["room_id"] == sample_empty_group.id
                assert result["deleted_from_stream"] is True
                assert sample_empty_group.status == ChatRoomStatus.CLOSED
                mock_db.commit.assert_called()
                mock_delete_stream.assert_called_once()

    def test_delete_empty_group_as_creator_trainer(self, mock_db, sample_user_trainer, sample_empty_group):
        """Test eliminar grupo vacío como entrenador creador."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.TRAINER.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = True  # Es el creador

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.return_value = True

                # Act
                result = chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_trainer.id,
                    gym_id=gym_id,
                    user_role=user_role,
                    hard_delete=True
                )

                # Assert
                assert result["success"] is True
                assert sample_empty_group.status == ChatRoomStatus.CLOSED

    def test_delete_group_soft_delete(self, mock_db, sample_user_admin, sample_empty_group):
        """Test eliminar grupo con soft delete (solo marca como CLOSED)."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            # Act - hard_delete=False
            result = chat_service.delete_group(
                mock_db,
                room_id=sample_empty_group.id,
                user_id=sample_user_admin.id,
                gym_id=gym_id,
                user_role=user_role,
                hard_delete=False
            )

            # Assert
            assert result["success"] is True
            assert result["deleted_from_stream"] is False
            assert sample_empty_group.status == ChatRoomStatus.CLOSED

    def test_delete_group_as_owner(self, mock_db, sample_user_admin, sample_empty_group):
        """Test eliminar grupo como owner."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.OWNER.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.return_value = True

                # Act
                result = chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role,
                    hard_delete=True
                )

                # Assert
                assert result["success"] is True

    # Tests de Delete Group - Permission Errors

    def test_delete_group_as_member_fails(self, mock_db, sample_user_member, sample_empty_group):
        """Test que member no puede eliminar grupos."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.MEMBER.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_member.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "No tienes permisos para eliminar este grupo" in str(exc_info.value)

    def test_delete_group_as_non_creator_trainer_fails(self, mock_db, sample_user_trainer, sample_empty_group):
        """Test que entrenador no-creador no puede eliminar grupo."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.TRAINER.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False  # NO es el creador

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_trainer.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "Los entrenadores solo pueden eliminar grupos que ellos crearon" in str(exc_info.value)

    # Tests de Delete Group - Validation Errors

    def test_delete_group_not_found(self, mock_db, sample_user_admin):
        """Test eliminar grupo que no existe."""
        # Arrange
        gym_id = 1
        room_id = 999
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=room_id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "no encontrada" in str(exc_info.value)

    def test_delete_group_wrong_gym(self, mock_db, sample_user_admin, sample_empty_group):
        """Test eliminar grupo de otro gimnasio."""
        # Arrange
        gym_id = 2  # Diferente al gym_id del chat (1)
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "No tienes acceso a esta sala" in str(exc_info.value)

    def test_delete_direct_chat_fails(self, mock_db, sample_user_admin, sample_direct_chat):
        """Test que no se puede eliminar chat directo."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "No puedes eliminar un chat directo 1-to-1" in str(exc_info.value)

    def test_delete_event_chat_fails(self, mock_db, sample_user_admin, sample_event_chat):
        """Test que no se puede eliminar chat de evento."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_event_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_event_chat.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "Los chats de eventos se eliminan automáticamente" in str(exc_info.value)

    def test_delete_group_with_members_fails(self, mock_db, sample_user_admin, sample_group_with_members):
        """Test que no se puede eliminar grupo con miembros."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value
        member_count = 3

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_with_members
            mock_repo.get_room_members_count.return_value = member_count
            mock_repo.is_user_room_creator.return_value = False

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_group_with_members.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

            assert "Debes remover a todos los miembros" in str(exc_info.value)
            assert str(member_count) in str(exc_info.value)

    # Tests de Stream Integration

    def test_delete_group_stream_error_handling(self, mock_db, sample_user_admin, sample_empty_group):
        """Test que errores de Stream no impiden marcar como CLOSED en BD."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.side_effect = Exception("Stream API error")

                # Act
                result = chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role,
                    hard_delete=True
                )

                # Assert - Should still mark as CLOSED even if Stream fails
                assert result["success"] is True
                assert result["deleted_from_stream"] is False
                assert sample_empty_group.status == ChatRoomStatus.CLOSED
                mock_db.commit.assert_called()

    def test_delete_group_stream_success_indicator(self, mock_db, sample_user_admin, sample_empty_group):
        """Test que deleted_from_stream indica correctamente el resultado."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.return_value = True

                # Act
                result = chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role,
                    hard_delete=True
                )

                # Assert
                assert result["deleted_from_stream"] is True

    # Tests de Response Messages

    def test_delete_group_message_includes_group_name(self, mock_db, sample_user_admin, sample_empty_group):
        """Test que el mensaje de respuesta incluye el nombre del grupo."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value
        sample_empty_group.name = "Test Group Name"

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.return_value = True

                # Act
                result = chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

                # Assert
                assert "Test Group Name" in result["message"]

    def test_delete_group_updates_timestamp(self, mock_db, sample_user_admin, sample_empty_group):
        """Test que se actualiza el timestamp del grupo."""
        # Arrange
        gym_id = 1
        user_role = GymRoleType.ADMIN.value

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_empty_group
            mock_repo.get_room_members_count.return_value = 0
            mock_repo.is_user_room_creator.return_value = False

            with patch('app.core.scheduler.delete_stream_channel') as mock_delete_stream:
                mock_delete_stream.return_value = True

                # Act
                chat_service.delete_group(
                    mock_db,
                    room_id=sample_empty_group.id,
                    user_id=sample_user_admin.id,
                    gym_id=gym_id,
                    user_role=user_role
                )

                # Assert
                assert sample_empty_group.updated_at is not None
                mock_db.commit.assert_called()
