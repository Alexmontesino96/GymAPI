"""
Tests para funcionalidad de ocultar/mostrar chats.

Tests para las funciones hide_channel_for_user y show_channel_for_user
del servicio de chat, que implementan el patrón WhatsApp para ocultar chats 1-to-1.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.chat import chat_service
from app.models.chat import ChatRoom, ChatMember, ChatRoomStatus, ChatMemberHidden
from app.models.user import User


class TestChatHideShow:
    """Tests para ocultar/mostrar chats."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        return Mock(spec=Session)

    @pytest.fixture
    def sample_user(self):
        """Usuario de muestra para tests."""
        user = Mock(spec=User)
        user.id = 1
        user.auth0_id = "auth0|test123"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def sample_direct_chat(self):
        """Chat directo 1-to-1 de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 100
        chat.stream_channel_id = "test-channel-1"
        chat.stream_channel_type = "messaging"
        chat.gym_id = 1
        chat.is_direct = True
        chat.event_id = None
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    @pytest.fixture
    def sample_group_chat(self):
        """Chat de grupo de muestra."""
        chat = Mock(spec=ChatRoom)
        chat.id = 101
        chat.stream_channel_id = "test-group-1"
        chat.stream_channel_type = "messaging"
        chat.gym_id = 1
        chat.is_direct = False
        chat.event_id = None
        chat.status = ChatRoomStatus.ACTIVE
        return chat

    # Tests de Hide Channel

    def test_hide_direct_chat_success(self, mock_db, sample_user, sample_direct_chat):
        """Test ocultar chat directo exitosamente."""
        # Arrange
        gym_id = 1

        # Mock repository responses
        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            # Mock membership check
            mock_membership = Mock(spec=ChatMember)
            mock_membership.room_id = sample_direct_chat.id
            mock_membership.user_id = sample_user.id
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            # Mock user query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user

            # Mock Stream client
            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Act
                result = chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["success"] is True
                assert result["room_id"] == sample_direct_chat.id
                assert result["is_hidden"] is True
                mock_channel.hide.assert_called_once()
                mock_repo.hide_room_for_user.assert_called_once()

    def test_hide_group_chat_fails(self, mock_db, sample_user, sample_group_chat):
        """Test que ocultar un grupo falla (debe usar leave)."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "Solo puedes ocultar chats directos 1-to-1" in str(exc_info.value)

    def test_hide_chat_not_found(self, mock_db, sample_user):
        """Test ocultar chat que no existe."""
        # Arrange
        gym_id = 1
        room_id = 999

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=room_id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "no encontrada" in str(exc_info.value)

    def test_hide_chat_wrong_gym(self, mock_db, sample_user, sample_direct_chat):
        """Test ocultar chat de otro gimnasio."""
        # Arrange
        gym_id = 2  # Diferente al gym_id del chat (1)

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No tienes acceso a esta sala" in str(exc_info.value)

    def test_hide_chat_not_member(self, mock_db, sample_user, sample_direct_chat):
        """Test ocultar chat del que no eres miembro."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Mock no membership
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No eres miembro" in str(exc_info.value)

    def test_hide_chat_already_hidden(self, mock_db, sample_user, sample_direct_chat):
        """Test ocultar chat que ya estaba oculto."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = False  # Ya estaba oculto

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            # Mock user query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Act
                result = chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["success"] is True
                assert "ya estaba oculto" in result["message"]
                assert result["is_hidden"] is True

    # Tests de Show Channel

    def test_show_hidden_chat_success(self, mock_db, sample_user, sample_direct_chat):
        """Test mostrar chat oculto exitosamente."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.show_room_for_user.return_value = True

            # Mock user query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Act
                result = chat_service.show_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["success"] is True
                assert result["room_id"] == sample_direct_chat.id
                assert result["is_hidden"] is False
                mock_channel.show.assert_called_once()
                mock_repo.show_room_for_user.assert_called_once()

    def test_show_chat_already_visible(self, mock_db, sample_user, sample_direct_chat):
        """Test mostrar chat que ya estaba visible."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.show_room_for_user.return_value = False  # Ya estaba visible

            # Mock user query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Act
                result = chat_service.show_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["success"] is True
                assert "ya estaba visible" in result["message"]
                assert result["is_hidden"] is False

    def test_show_chat_not_found(self, mock_db, sample_user):
        """Test mostrar chat que no existe."""
        # Arrange
        gym_id = 1
        room_id = 999

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.show_channel_for_user(
                    mock_db,
                    room_id=room_id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "no encontrada" in str(exc_info.value)

    def test_show_chat_wrong_gym(self, mock_db, sample_user, sample_direct_chat):
        """Test mostrar chat de otro gimnasio."""
        # Arrange
        gym_id = 2  # Diferente al gym_id del chat (1)

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.show_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No tienes acceso a esta sala" in str(exc_info.value)

    # Tests de Stream Chat Integration

    def test_hide_chat_stream_error_handling(self, mock_db, sample_user, sample_direct_chat):
        """Test que errores de Stream no impiden guardar en BD."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            # Mock user query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user

            # Mock Stream client error
            with patch('app.services.chat.stream_client') as mock_stream:
                mock_stream.channel.side_effect = Exception("Stream API error")

                # Act
                result = chat_service.hide_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert - Should still save to DB even if Stream fails
                assert result["success"] is True
                mock_repo.hide_room_for_user.assert_called_once()

    def test_show_chat_stream_error_handling(self, mock_db, sample_user, sample_direct_chat):
        """Test que errores de Stream no impiden actualizar BD."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.show_room_for_user.return_value = True

            # Mock user query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user

            # Mock Stream client error
            with patch('app.services.chat.stream_client') as mock_stream:
                mock_stream.channel.side_effect = Exception("Stream API error")

                # Act
                result = chat_service.show_channel_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert - Should still update DB even if Stream fails
                assert result["success"] is True
                mock_repo.show_room_for_user.assert_called_once()
