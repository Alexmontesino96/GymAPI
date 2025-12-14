"""
Tests for Chat Management API Endpoints

Tests para los endpoints de gestión de chats:
- POST /rooms/{room_id}/hide
- POST /rooms/{room_id}/show
- POST /rooms/{room_id}/leave
- DELETE /rooms/{room_id}
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.models.chat import ChatRoom, ChatMember, ChatRoomStatus, ChatMemberHidden
from app.models.gym import Gym
from app.models.user import User
from app.models.user_gym import UserGym, GymRoleType
from app.models.event import Event


@pytest.fixture
def test_gym(db):
    """Fixture para crear un gimnasio de prueba."""
    gym = Gym(
        name="Test Gym",
        description="Gimnasio de prueba",
        created_by_id=1
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    return gym


@pytest.fixture
def test_users(db, test_gym):
    """Fixture para crear usuarios de prueba con diferentes roles."""
    users = {}

    # Member
    member = User(
        email="member@test.com",
        auth0_id="auth0|member123",
        full_name="Test Member"
    )
    db.add(member)

    # Trainer
    trainer = User(
        email="trainer@test.com",
        auth0_id="auth0|trainer123",
        full_name="Test Trainer"
    )
    db.add(trainer)

    # Admin
    admin = User(
        email="admin@test.com",
        auth0_id="auth0|admin123",
        full_name="Test Admin"
    )
    db.add(admin)

    db.commit()
    db.refresh(member)
    db.refresh(trainer)
    db.refresh(admin)

    # Create gym associations
    for user, role in [(member, GymRoleType.MEMBER), (trainer, GymRoleType.TRAINER), (admin, GymRoleType.ADMIN)]:
        user_gym = UserGym(
            user_id=user.id,
            gym_id=test_gym.id,
            role=role
        )
        db.add(user_gym)

    db.commit()

    users['member'] = member
    users['trainer'] = trainer
    users['admin'] = admin

    return users


@pytest.fixture
def direct_chat(db, test_gym, test_users):
    """Fixture para crear un chat directo 1-to-1."""
    chat = ChatRoom(
        stream_channel_id="test-direct-1",
        stream_channel_type="messaging",
        gym_id=test_gym.id,
        is_direct=True,
        status=ChatRoomStatus.ACTIVE
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)

    # Add members
    for user in [test_users['member'], test_users['trainer']]:
        member = ChatMember(
            room_id=chat.id,
            user_id=user.id
        )
        db.add(member)

    db.commit()
    return chat


@pytest.fixture
def group_chat(db, test_gym, test_users):
    """Fixture para crear un chat de grupo."""
    chat = ChatRoom(
        stream_channel_id="test-group-1",
        stream_channel_type="messaging",
        name="Test Group",
        gym_id=test_gym.id,
        is_direct=False,
        status=ChatRoomStatus.ACTIVE
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)

    # Add members
    for user in test_users.values():
        member = ChatMember(
            room_id=chat.id,
            user_id=user.id
        )
        db.add(member)

    db.commit()
    return chat


@pytest.fixture
def empty_group_chat(db, test_gym):
    """Fixture para crear un grupo vacío."""
    chat = ChatRoom(
        stream_channel_id="test-empty-group-1",
        stream_channel_type="messaging",
        name="Empty Group",
        gym_id=test_gym.id,
        is_direct=False,
        status=ChatRoomStatus.ACTIVE
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


# Tests para POST /rooms/{room_id}/hide

def test_hide_direct_chat_success(client, db, test_gym, test_users, direct_chat):
    """Test ocultar un chat directo exitosamente."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.hide_channel_for_user.return_value = {
            "success": True,
            "message": "Chat ocultado exitosamente",
            "room_id": direct_chat.id,
            "is_hidden": True
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{direct_chat.id}/hide",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["room_id"] == direct_chat.id
    assert data["is_hidden"] is True


def test_hide_group_chat_fails(client, db, test_gym, test_users, group_chat):
    """Test que ocultar un grupo falla (debe usar leave)."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.hide_channel_for_user.side_effect = ValueError(
            "Solo puedes ocultar chats directos 1-to-1"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{group_chat.id}/hide",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 400
    assert "Solo puedes ocultar chats directos" in response.json()["detail"]


def test_hide_chat_not_member(client, db, test_gym, test_users, direct_chat):
    """Test ocultar chat del que no eres miembro."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.hide_channel_for_user.side_effect = ValueError(
            "No eres miembro de esta sala de chat"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{direct_chat.id}/hide",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 403


# Tests para POST /rooms/{room_id}/show

def test_show_hidden_chat_success(client, db, test_gym, test_users, direct_chat):
    """Test mostrar un chat oculto exitosamente."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.show_channel_for_user.return_value = {
            "success": True,
            "message": "Chat mostrado exitosamente",
            "room_id": direct_chat.id,
            "is_hidden": False
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{direct_chat.id}/show",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_hidden"] is False


def test_show_chat_not_found(client, db, test_gym, test_users):
    """Test mostrar chat que no existe."""
    user = test_users['member']
    room_id = 999

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.show_channel_for_user.side_effect = ValueError(
            "Sala de chat no encontrada"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{room_id}/show",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 404


# Tests para POST /rooms/{room_id}/leave

def test_leave_group_success(client, db, test_gym, test_users, group_chat):
    """Test salir de un grupo exitosamente."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.leave_group.return_value = {
            "success": True,
            "message": "Has salido del grupo 'Test Group'",
            "room_id": group_chat.id,
            "remaining_members": 2,
            "group_deleted": False,
            "auto_hidden": True
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{group_chat.id}/leave?auto_hide=true",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["remaining_members"] == 2
    assert data["group_deleted"] is False
    assert data["auto_hidden"] is True


def test_leave_group_last_member(client, db, test_gym, test_users, group_chat):
    """Test que el último miembro al salir cierra el grupo."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.leave_group.return_value = {
            "success": True,
            "message": "Has salido del grupo 'Test Group'",
            "room_id": group_chat.id,
            "remaining_members": 0,
            "group_deleted": True,
            "auto_hidden": True
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{group_chat.id}/leave",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["group_deleted"] is True
    assert data["remaining_members"] == 0


def test_leave_direct_chat_fails(client, db, test_gym, test_users, direct_chat):
    """Test que salir de chat directo falla (debe usar hide)."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.leave_group.side_effect = ValueError(
            "No puedes salir de un chat directo 1-to-1"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{direct_chat.id}/leave",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 400


def test_leave_group_without_auto_hide(client, db, test_gym, test_users, group_chat):
    """Test salir de grupo sin auto-hide."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.leave_group.return_value = {
            "success": True,
            "message": "Has salido del grupo 'Test Group'",
            "room_id": group_chat.id,
            "remaining_members": 2,
            "group_deleted": False,
            "auto_hidden": False
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.post(
                f"/api/v1/chat/rooms/{group_chat.id}/leave?auto_hide=false",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["auto_hidden"] is False


# Tests para DELETE /rooms/{room_id}

def test_delete_empty_group_as_admin(client, db, test_gym, test_users, empty_group_chat):
    """Test eliminar grupo vacío como admin."""
    user = test_users['admin']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_group.return_value = {
            "success": True,
            "message": "Grupo 'Empty Group' eliminado exitosamente",
            "room_id": empty_group_chat.id,
            "deleted_from_stream": True
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{empty_group_chat.id}?hard_delete=true",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["deleted_from_stream"] is True


def test_delete_group_with_members_fails(client, db, test_gym, test_users, group_chat):
    """Test que no se puede eliminar grupo con miembros."""
    user = test_users['admin']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_group.side_effect = ValueError(
            "Debes remover a todos los miembros (3 restantes) antes de eliminar el grupo"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{group_chat.id}",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 400
    assert "Debes remover a todos los miembros" in response.json()["detail"]


def test_delete_group_as_member_fails(client, db, test_gym, test_users, empty_group_chat):
    """Test que member no puede eliminar grupos."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_group.side_effect = ValueError(
            "No tienes permisos para eliminar este grupo"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{empty_group_chat.id}",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 403


def test_delete_group_as_non_creator_trainer_fails(client, db, test_gym, test_users, empty_group_chat):
    """Test que trainer no-creador no puede eliminar grupo."""
    user = test_users['trainer']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_group.side_effect = ValueError(
            "Los entrenadores solo pueden eliminar grupos que ellos crearon"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{empty_group_chat.id}",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 403


def test_delete_direct_chat_fails(client, db, test_gym, test_users, direct_chat):
    """Test que no se puede eliminar un chat directo."""
    user = test_users['admin']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_group.side_effect = ValueError(
            "No puedes eliminar un chat directo 1-to-1"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{direct_chat.id}",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 400


def test_delete_group_soft_delete(client, db, test_gym, test_users, empty_group_chat):
    """Test eliminar grupo con soft delete (solo marca como CLOSED)."""
    user = test_users['admin']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_group.return_value = {
            "success": True,
            "message": "Grupo 'Empty Group' eliminado exitosamente",
            "room_id": empty_group_chat.id,
            "deleted_from_stream": False
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{empty_group_chat.id}?hard_delete=false",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["deleted_from_stream"] is False


# Tests para GET /my-rooms con filtro de chats ocultos

def test_list_rooms_excludes_hidden_by_default(client, db, test_gym, test_users, direct_chat):
    """Test que el listado excluye chats ocultos por defecto."""
    user = test_users['member']

    # Ocultar el chat
    hidden = ChatMemberHidden(
        user_id=user.id,
        room_id=direct_chat.id
    )
    db.add(hidden)
    db.commit()

    with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
        mock_auth_user = Mock()
        mock_auth_user.id = user.auth0_id
        mock_auth.get_user.return_value = mock_auth_user

        response = client.get(
            "/api/v1/chat/my-rooms",
            headers={"X-Gym-ID": str(test_gym.id)}
        )

    assert response.status_code == 200
    rooms = response.json()
    # El chat oculto no debería aparecer
    room_ids = [room["id"] for room in rooms]
    assert direct_chat.id not in room_ids


def test_list_rooms_includes_hidden_when_requested(client, db, test_gym, test_users, direct_chat):
    """Test que el listado incluye chats ocultos cuando se solicita."""
    user = test_users['member']

    # Ocultar el chat
    hidden = ChatMemberHidden(
        user_id=user.id,
        room_id=direct_chat.id
    )
    db.add(hidden)
    db.commit()

    with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
        mock_auth_user = Mock()
        mock_auth_user.id = user.auth0_id
        mock_auth.get_user.return_value = mock_auth_user

        response = client.get(
            "/api/v1/chat/my-rooms?include_hidden=true",
            headers={"X-Gym-ID": str(test_gym.id)}
        )

    assert response.status_code == 200
    rooms = response.json()
    # El chat oculto debería aparecer
    room_ids = [room["id"] for room in rooms]
    assert direct_chat.id in room_ids


# Tests para DELETE /rooms/{id}/conversation

def test_delete_conversation_success(client, db, test_gym, test_users, direct_chat):
    """Test eliminar conversación exitosamente."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_conversation_for_user.return_value = {
            "success": True,
            "message": "Conversación eliminada para ti. El otro usuario mantiene su historial.",
            "room_id": direct_chat.id,
            "messages_deleted": 15
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{direct_chat.id}/conversation",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["room_id"] == direct_chat.id
    assert data["messages_deleted"] == 15
    assert "El otro usuario mantiene su historial" in data["message"]


def test_delete_conversation_for_group_fails(client, db, test_gym, test_users, group_chat):
    """Test que no se puede eliminar conversación de grupo."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_conversation_for_user.side_effect = ValueError(
            "Solo puedes eliminar conversaciones 1-to-1"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{group_chat.id}/conversation",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 400
    assert "Solo puedes eliminar conversaciones 1-to-1" in response.json()["detail"]


def test_delete_conversation_not_member(client, db, test_gym, test_users, direct_chat):
    """Test eliminar conversación del que no eres miembro."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_conversation_for_user.side_effect = ValueError(
            "No eres miembro de esta conversación"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{direct_chat.id}/conversation",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 403


def test_delete_conversation_not_found(client, db, test_gym, test_users):
    """Test eliminar conversación que no existe."""
    user = test_users['member']
    room_id = 999

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_conversation_for_user.side_effect = ValueError(
            "Sala de chat no encontrada"
        )

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{room_id}/conversation",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 404


def test_delete_conversation_with_no_messages(client, db, test_gym, test_users, direct_chat):
    """Test eliminar conversación sin mensajes."""
    user = test_users['member']

    with patch('app.api.v1.endpoints.chat.chat_service') as mock_service:
        mock_service.delete_conversation_for_user.return_value = {
            "success": True,
            "message": "Conversación eliminada para ti. El otro usuario mantiene su historial.",
            "room_id": direct_chat.id,
            "messages_deleted": 0
        }

        with patch('app.api.v1.endpoints.chat.auth') as mock_auth:
            mock_auth_user = Mock()
            mock_auth_user.id = user.auth0_id
            mock_auth.get_user.return_value = mock_auth_user

            response = client.delete(
                f"/api/v1/chat/rooms/{direct_chat.id}/conversation",
                headers={"X-Gym-ID": str(test_gym.id)}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["messages_deleted"] == 0
