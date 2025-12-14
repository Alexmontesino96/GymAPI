"""
Tests para funcionalidad de eliminar conversación (Delete For Me).

Tests para la función delete_conversation_for_user del servicio de chat,
que implementa el patrón "Eliminar Para Mí" de WhatsApp.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.chat import chat_service
from app.models.chat import ChatRoom, ChatMember, ChatRoomStatus
from app.models.user import User


class TestChatDeleteConversation:
    """Tests para eliminar conversación (Delete For Me)."""

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
        chat.stream_channel_id = "test-direct-1"
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

    # Tests de Delete Conversation - Success Cases

    def test_delete_conversation_success(self, mock_db, sample_user, sample_direct_chat):
        """Test eliminar conversación exitosamente."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            # Mock membership
            mock_membership = Mock(spec=ChatMember)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_membership

            # Mock user query - needs to return sample_user for second query
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            # Mock Stream client
            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Mock messages
                mock_messages = {
                    'messages': [
                        {'id': 'msg1', 'text': 'Hello'},
                        {'id': 'msg2', 'text': 'World'},
                        {'id': 'msg3', 'text': 'Test'}
                    ]
                }
                mock_channel.query.return_value = mock_messages

                # Act
                result = chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["success"] is True
                assert result["room_id"] == sample_direct_chat.id
                assert result["messages_deleted"] == 3
                assert "El otro usuario mantiene su historial" in result["message"]

                # Verify messages were deleted
                assert mock_channel.delete_message.call_count == 3
                mock_repo.hide_room_for_user.assert_called_once()

    def test_delete_conversation_with_many_messages(self, mock_db, sample_user, sample_direct_chat):
        """Test eliminar conversación con muchos mensajes."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            # Mock membership and user
            mock_membership = Mock(spec=ChatMember)
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Mock 100 messages
                mock_messages = {
                    'messages': [{'id': f'msg{i}', 'text': f'Message {i}'} for i in range(100)]
                }
                mock_channel.query.return_value = mock_messages

                # Act
                result = chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["messages_deleted"] == 100
                assert mock_channel.delete_message.call_count == 100

    def test_delete_conversation_auto_hides_chat(self, mock_db, sample_user, sample_direct_chat):
        """Test que la conversación se oculta automáticamente al eliminar."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            mock_membership = Mock(spec=ChatMember)
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel
                mock_channel.query.return_value = {'messages': []}

                # Act
                result = chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert
                assert result["success"] is True
                mock_repo.hide_room_for_user.assert_called_once_with(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id
                )

    # Tests de Delete Conversation - Validation Errors

    def test_delete_conversation_not_found(self, mock_db, sample_user):
        """Test eliminar conversación que no existe."""
        # Arrange
        gym_id = 1
        room_id = 999

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=room_id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "no encontrada" in str(exc_info.value)

    def test_delete_conversation_wrong_gym(self, mock_db, sample_user, sample_direct_chat):
        """Test eliminar conversación de otro gimnasio."""
        # Arrange
        gym_id = 2  # Diferente al gym_id del chat (1)

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No tienes acceso a esta sala" in str(exc_info.value)

    def test_delete_group_chat_fails(self, mock_db, sample_user, sample_group_chat):
        """Test que no se puede eliminar un grupo (debe usar leave)."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_group_chat

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_group_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "Solo puedes eliminar conversaciones 1-to-1" in str(exc_info.value)

    def test_delete_conversation_not_member(self, mock_db, sample_user, sample_direct_chat):
        """Test eliminar conversación del que no eres miembro."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat

            # Mock no membership
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

            assert "No eres miembro" in str(exc_info.value)

    # Tests de Stream Chat Integration

    def test_delete_conversation_stream_error_continues(self, mock_db, sample_user, sample_direct_chat):
        """Test que errores de Stream no impiden ocultar el chat."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            mock_membership = Mock(spec=ChatMember)
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            # Mock Stream client error
            with patch('app.services.chat.stream_client') as mock_stream:
                mock_stream.channel.side_effect = Exception("Stream API error")

                # Act
                result = chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert - Should still hide chat even if Stream fails
                assert result["success"] is True
                assert result["messages_deleted"] == 0
                mock_repo.hide_room_for_user.assert_called_once()

    def test_delete_conversation_partial_message_deletion(self, mock_db, sample_user, sample_direct_chat):
        """Test que fallos parciales en eliminación de mensajes continúan."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            mock_membership = Mock(spec=ChatMember)
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                # Mock messages
                mock_messages = {
                    'messages': [
                        {'id': 'msg1', 'text': 'Success'},
                        {'id': 'msg2', 'text': 'Fail'},
                        {'id': 'msg3', 'text': 'Success'}
                    ]
                }
                mock_channel.query.return_value = mock_messages

                # Mock delete_message to fail for msg2
                def delete_side_effect(msg_id, hard=False):
                    if msg_id == 'msg2':
                        raise Exception("Delete failed")

                mock_channel.delete_message.side_effect = delete_side_effect

                # Act
                result = chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert - Should delete 2 out of 3 messages
                assert result["success"] is True
                assert result["messages_deleted"] == 2

    def test_delete_conversation_soft_delete_in_stream(self, mock_db, sample_user, sample_direct_chat):
        """Test que los mensajes se eliminan con soft delete en Stream."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.return_value = True

            mock_membership = Mock(spec=ChatMember)
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel

                mock_messages = {
                    'messages': [{'id': 'msg1', 'text': 'Test'}]
                }
                mock_channel.query.return_value = mock_messages

                # Act
                chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert - Verify soft delete was used
                mock_channel.delete_message.assert_called_once_with(
                    'msg1',
                    hard=False  # Soft delete mantiene para otros usuarios
                )

    def test_delete_conversation_hide_failure_continues(self, mock_db, sample_user, sample_direct_chat):
        """Test que error al ocultar no impide eliminar mensajes."""
        # Arrange
        gym_id = 1

        with patch('app.services.chat.chat_repository') as mock_repo:
            mock_repo.get_room.return_value = sample_direct_chat
            mock_repo.hide_room_for_user.side_effect = Exception("Hide error")

            mock_membership = Mock(spec=ChatMember)
            side_effects = [mock_membership, sample_user]
            mock_db.query.return_value.filter.return_value.first.side_effect = side_effects

            with patch('app.services.chat.stream_client') as mock_stream:
                mock_channel = MagicMock()
                mock_stream.channel.return_value = mock_channel
                mock_channel.query.return_value = {'messages': [{'id': 'msg1'}]}

                # Act
                result = chat_service.delete_conversation_for_user(
                    mock_db,
                    room_id=sample_direct_chat.id,
                    user_id=sample_user.id,
                    gym_id=gym_id
                )

                # Assert - Should still succeed
                assert result["success"] is True
                assert result["messages_deleted"] == 1
