"""
Tests para funcionalidad de salir de grupos.

Tests para la función leave_group del servicio de chat,
que implementa el patrón WhatsApp para salir de grupos.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.chat import chat_service
from app.models.chat import ChatRoom, ChatMember, ChatRoomStatus, ChatMemberHidden
from app.models.user import User


class TestChatLeaveGroup:
    """Tests para salir de grupos."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        db = Mock(spec=Session)
        db.commit = Mock()
        return db

    @pytest.fixture
    def sample_user(self):
        """Usuario de muestra para tests."""
        user = Mock(spec=User)
        user.id = 1
        user.auth0_id = "auth0|test123"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def sample_group_chat(self):
        """Chat de grupo de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 101
        chat.stream_channel_id = "test-group-1"
        chat.stream_channel_type = "messaging"
        chat.name = "Test Group"
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
        chat.id = 102
        chat.stream_channel_id = "test-event-1"
        chat.stream_channel_type = "messaging"
        chat.gym_id = 1
        chat.is_direct = False
        chat.event_id = 1  # Asociado a un evento
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    # Tests de Leave Group - Success Cases

    def test_leave_group_success_with_auto_hide(self, mock_db, sample_user, sample_group_chat):
        """Test salir de grupo exitosamente con auto-hide."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat
            mock_repo.get_room_members_count.return_value = 2  # Quedan 2 miembros
            mock_repo.hide_room_for_user.return_value = True

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            # Mock remove_user_from_channel
            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.return_value = None

                # Act
                result = chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id,
                    auto_hide=True
                )

                # Assert
                assert result["success"] is True
                assert result["room_id"] == sample_group_chat.id
                assert result["remaining_members"] == 2
                assert result["group_deleted"] is False
                assert result["auto_hidden"] is True
                mock_remove.assert_called_once()
                mock_repo.hide_room_for_user.assert_called_once()

    def test_leave_group_success_without_auto_hide(self, mock_db, sample_user, sample_group_chat):
        """Test salir de grupo sin auto-hide."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat
            mock_repo.get_room_members_count.return_value = 3
            mock_repo.hide_room_for_user.return_value = False

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.return_value = None

                # Act
                result = chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id,
                    auto_hide=False
                )

                # Assert
                assert result["success"] is True
                assert result["remaining_members"] == 3
                assert result["auto_hidden"] is False
                mock_repo.hide_room_for_user.assert_not_called()

    def test_leave_group_last_member_closes_group(self, mock_db, sample_user, sample_group_chat):
        """Test que el último miembro al salir cierra el grupo."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat
            mock_repo.get_room_members_count.return_value = 0  # No quedan miembros
            mock_repo.hide_room_for_user.return_value = True

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.return_value = None

                # Act
                result = chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id,
                    auto_hide=True
                )

                # Assert
                assert result["success"] is True
                assert result["remaining_members"] == 0
                assert result["group_deleted"] is True
                assert sample_group_chat.status == ChatRoomStatus.CLOSED
                mock_db.commit.assert_called()

    # Tests de Leave Group - Error Cases

    def test_leave_group_not_found(self, mock_db, sample_user):
        """Test salir de grupo que no existe."""
        # Arrange
        gym_id = 1
        room_id = 999

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.leave_group(
                    mock_db,
                    room_id=room_id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "no encontrada" in str(exc_info.value)

    def test_leave_group_wrong_gym(self, mock_db, sample_user, sample_group_chat):
        """Test salir de grupo de otro gimnasio."""
        # Arrange
        gym_id = 2  # Diferente al gym_id del chat (1)

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No tienes acceso a esta sala" in str(exc_info.value)

    def test_leave_direct_chat_fails(self, mock_db, sample_user, sample_direct_chat):
        """Test que no se puede salir de un chat directo (debe usar hide)."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.leave_group(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No puedes salir de un chat directo 1-to-1" in str(exc_info.value)

    def test_leave_event_chat_fails(self, mock_db, sample_user, sample_event_chat):
        """Test que no se puede salir de un chat de evento."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_event_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.leave_group(
                    mock_db,
                    room_id=sample_event_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No puedes salir manualmente de un chat de evento" in str(exc_info.value)

    def test_leave_group_not_member(self, mock_db, sample_user, sample_group_chat):
        """Test salir de grupo del que no eres miembro."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat

            # Mock no membership
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No eres miembro" in str(exc_info.value)

    def test_leave_group_remove_user_fails(self, mock_db, sample_user, sample_group_chat):
        """Test que falla al remover usuario de Stream."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            # Mock remove_user_from_channel fails
            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.side_effect = Exception("Stream API error")

                # Act & Assert
                with pytest.raises(ValueError) as exc_info:
                    chat_service.leave_group(
                        mock_db,
                        room_id=sample_group_chat.id,
                        user_id=sample_user.id,
                        gym_id=gym_id
                    )

                assert "Error al salir del grupo" in str(exc_info.value)

    # Tests de Auto-Hide Functionality

    def test_leave_group_auto_hide_error_continues(self, mock_db, sample_user, sample_group_chat):
        """Test que errores en auto-hide no impiden salir del grupo."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat
            mock_repo.get_room_members_count.return_value = 1
            mock_repo.hide_room_for_user.side_effect = Exception("Hide error")

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.return_value = None

                # Act
                result = chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id,
                    auto_hide=True
                )

                # Assert - Should succeed despite hide error
                assert result["success"] is True
                assert result["remaining_members"] == 1

    # Tests de Integration

    def test_leave_group_updates_room_status_correctly(self, mock_db, sample_user, sample_group_chat):
        """Test que el status del grupo se actualiza correctamente."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat
            mock_repo.get_room_members_count.return_value = 0

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.return_value = None

                # Act
                result = chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert sample_group_chat.status == ChatRoomStatus.CLOSED
                assert sample_group_chat.updated_at is not None
                mock_db.commit.assert_called()

    def test_leave_group_message_includes_group_name(self, mock_db, sample_user, sample_group_chat):
        """Test que el mensaje de respuesta incluye el nombre del grupo."""
        # Arrange
        gym_id = 1
        sample_group_chat.name = "Team Alpha"

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat
            mock_repo.get_room_members_count.return_value = 5

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            with patch.object(chat_service, 'remove_user_from_channel') as mock_remove:
                mock_remove.return_value = None

                # Act
                result = chat_service.leave_group(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert "Team Alpha" in result["message"]
