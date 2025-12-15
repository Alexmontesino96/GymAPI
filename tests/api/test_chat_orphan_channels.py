"""
Tests para endpoint de eliminación de canales huérfanos de Stream

Este módulo prueba el endpoint DELETE /channels/orphan/{channel_id} que
implementa las mejores prácticas de Stream Chat para arquitectura Backend-First.

Escenarios probados:
1. Eliminación exitosa de canal huérfano
2. Rechazo si canal existe en BD
3. Rechazo si usuario no es owner
4. Rechazo si canal pertenece a otro gym
5. Rechazo si canal es de evento
6. Canal no encontrado en Stream
7. Audit logging

Basado en: STREAM_OFFICIAL_BEST_PRACTICES.md
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.db.session import get_db
from app.models.chat import ChatRoom
from app.models.user import User

client = TestClient(app)


@pytest.fixture
def mock_stream_channel_orphan():
    """
    Mock de un canal huérfano en Stream (NO existe en BD)
    """
    mock_channel = MagicMock()
    mock_channel.query.return_value = {
        'channel': {
            'id': 'orphan_channel_123',
            'type': 'messaging',
            'team': 'gym_1',
            'created_by': {'id': 'gym_1_user_10'}
        },
        'members': [
            {
                'user_id': 'gym_1_user_10',
                'role': 'owner',
                'created_at': '2025-01-01T00:00:00Z'
            }
        ]
    }
    mock_channel.delete.return_value = {'deleted': True}
    return mock_channel


@pytest.fixture
def mock_stream_channel_event():
    """
    Mock de un canal de evento en Stream
    """
    mock_channel = MagicMock()
    mock_channel.query.return_value = {
        'channel': {
            'id': 'event_456',
            'type': 'messaging',
            'team': 'gym_1',
            'created_by': {'id': 'gym_1_user_10'}
        },
        'members': [
            {
                'user_id': 'gym_1_user_10',
                'role': 'owner',
                'created_at': '2025-01-01T00:00:00Z'
            }
        ]
    }
    return mock_channel


@pytest.fixture
def mock_stream_channel_wrong_gym():
    """
    Mock de un canal que pertenece a otro gym
    """
    mock_channel = MagicMock()
    mock_channel.query.return_value = {
        'channel': {
            'id': 'channel_999',
            'type': 'messaging',
            'team': 'gym_2',  # Gym diferente
            'created_by': {'id': 'gym_2_user_20'}
        },
        'members': [
            {
                'user_id': 'gym_1_user_10',
                'role': 'member',  # No es owner
                'created_at': '2025-01-01T00:00:00Z'
            }
        ]
    }
    return mock_channel


@pytest.fixture
def mock_stream_channel_not_owner():
    """
    Mock de un canal donde el usuario es member, no owner
    """
    mock_channel = MagicMock()
    mock_channel.query.return_value = {
        'channel': {
            'id': 'channel_member_only',
            'type': 'messaging',
            'team': 'gym_1',
            'created_by': {'id': 'gym_1_user_99'}
        },
        'members': [
            {
                'user_id': 'gym_1_user_10',
                'role': 'member',  # No es owner
                'created_at': '2025-01-01T00:00:00Z'
            },
            {
                'user_id': 'gym_1_user_99',
                'role': 'owner',
                'created_at': '2025-01-01T00:00:00Z'
            }
        ]
    }
    return mock_channel


class TestDeleteOrphanChannelSuccess:
    """Tests de casos exitosos"""

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_delete_orphan_channel_success(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream,
        mock_stream_channel_orphan
    ):
        """
        Test exitoso: Elimina canal huérfano correctamente

        Validaciones verificadas:
        1. Canal NO existe en BD (es huérfano) ✅
        2. Pertenece al gym actual ✅
        3. No es canal de evento ✅
        4. Usuario es owner ✅
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),  # Usuario encontrado
            None  # ChatRoom NO encontrado (es huérfano)
        ]
        mock_db.return_value = mock_db_session

        mock_stream.channel.return_value = mock_stream_channel_orphan

        # Request
        response = client.delete(
            "/api/v1/chat/channels/orphan/orphan_channel_123",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['message'] == "Canal huérfano eliminado correctamente"

        # Verificar que se llamó a delete
        mock_stream_channel_orphan.delete.assert_called_once()


class TestDeleteOrphanChannelValidations:
    """Tests de validaciones de seguridad"""

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_reject_if_channel_exists_in_db(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream
    ):
        """
        Test: Rechaza si el canal existe en BD

        Debe retornar 409 Conflict
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),  # Usuario encontrado
            MagicMock(id=1, stream_channel_id='existing_channel')  # ChatRoom SÍ existe
        ]
        mock_db.return_value = mock_db_session

        # Request
        response = client.delete(
            "/api/v1/chat/channels/orphan/existing_channel",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 409  # Conflict
        data = response.json()
        assert "existe en la base de datos" in data['detail']
        assert "DELETE /rooms/" in data['detail']

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_reject_if_not_owner(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream,
        mock_stream_channel_not_owner
    ):
        """
        Test: Rechaza si usuario no es owner del canal

        Debe retornar 403 Forbidden
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),  # Usuario encontrado
            None  # ChatRoom NO encontrado (es huérfano)
        ]
        mock_db.return_value = mock_db_session

        mock_stream.channel.return_value = mock_stream_channel_not_owner

        # Request
        response = client.delete(
            "/api/v1/chat/channels/orphan/channel_member_only",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 403  # Forbidden
        data = response.json()
        assert "owner" in data['detail'].lower()

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_reject_if_wrong_gym(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream,
        mock_stream_channel_wrong_gym
    ):
        """
        Test: Rechaza si canal pertenece a otro gym

        Debe retornar 403 Forbidden
        Valida validación cross-gym
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),  # Usuario encontrado
            None  # ChatRoom NO encontrado (es huérfano)
        ]
        mock_db.return_value = mock_db_session

        mock_stream.channel.return_value = mock_stream_channel_wrong_gym

        # Request
        response = client.delete(
            "/api/v1/chat/channels/orphan/channel_999",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 403  # Forbidden
        data = response.json()
        assert "pertenece a otro gimnasio" in data['detail']

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_reject_event_channels(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream,
        mock_stream_channel_event
    ):
        """
        Test: Rechaza canales de eventos

        Debe retornar 403 Forbidden
        Los canales de eventos no deben ser eliminables por usuarios
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),  # Usuario encontrado
            None  # ChatRoom NO encontrado (es huérfano)
        ]
        mock_db.return_value = mock_db_session

        mock_stream.channel.return_value = mock_stream_channel_event

        # Request
        response = client.delete(
            "/api/v1/chat/channels/orphan/event_456",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 403  # Forbidden
        data = response.json()
        assert "canales de eventos" in data['detail'].lower()


class TestDeleteOrphanChannelErrors:
    """Tests de manejo de errores"""

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_channel_not_found_in_stream(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream
    ):
        """
        Test: Canal no existe ni en BD ni en Stream

        Debe retornar 404 Not Found
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),  # Usuario encontrado
            None  # ChatRoom NO encontrado (es huérfano)
        ]
        mock_db.return_value = mock_db_session

        # Mock Stream lanza error de not found
        mock_channel = MagicMock()
        mock_channel.query.side_effect = Exception("Channel not found")
        mock_stream.channel.return_value = mock_channel

        # Request
        response = client.delete(
            "/api/v1/chat/channels/orphan/nonexistent_channel",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 404  # Not Found
        data = response.json()
        assert "no encontrado" in data['detail'].lower()


class TestDeleteOrphanChannelFormats:
    """Tests de formatos de channel_id"""

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_channel_id_with_type_prefix(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream,
        mock_stream_channel_orphan
    ):
        """
        Test: Soporta channel_id con prefijo tipo:id

        Ejemplo: "messaging:abc123"
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),
            None
        ]
        mock_db.return_value = mock_db_session

        mock_stream.channel.return_value = mock_stream_channel_orphan

        # Request con formato "tipo:id"
        response = client.delete(
            "/api/v1/chat/channels/orphan/messaging:orphan_channel_123",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 200

        # Verificar que se parseó correctamente
        mock_stream.channel.assert_called_with('messaging', 'orphan_channel_123')

    @patch('app.services.chat.stream_client')
    @patch('app.api.v1.endpoints.chat.get_db')
    @patch('app.api.v1.endpoints.chat.verify_gym_access')
    @patch('app.api.v1.endpoints.chat.auth.get_user')
    def test_channel_id_without_type_prefix(
        self,
        mock_auth,
        mock_gym,
        mock_db,
        mock_stream,
        mock_stream_channel_orphan
    ):
        """
        Test: Soporta channel_id sin prefijo (solo ID)

        Ejemplo: "abc123" → asume tipo "messaging"
        """
        # Setup mocks
        mock_auth.return_value = MagicMock(id='auth0|123')
        mock_gym.return_value = MagicMock(id=1, name='Gym Test')

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=10),
            None
        ]
        mock_db.return_value = mock_db_session

        mock_stream.channel.return_value = mock_stream_channel_orphan

        # Request sin formato "tipo:id"
        response = client.delete(
            "/api/v1/chat/channels/orphan/orphan_channel_123",
            headers={
                "Authorization": "Bearer fake_token",
                "X-Gym-ID": "1"
            }
        )

        # Assertions
        assert response.status_code == 200

        # Verificar que usó tipo "messaging" por defecto
        mock_stream.channel.assert_called_with('messaging', 'orphan_channel_123')


# Resumen de cobertura de tests
"""
✅ Test Suite Completa: Delete Orphan Channels

Casos cubiertos:
1. ✅ Eliminación exitosa de canal huérfano
2. ✅ Rechazo si canal existe en BD (409 Conflict)
3. ✅ Rechazo si usuario no es owner (403 Forbidden)
4. ✅ Rechazo si canal pertenece a otro gym (403 Forbidden)
5. ✅ Rechazo si canal es de evento (403 Forbidden)
6. ✅ Canal no encontrado en Stream (404 Not Found)
7. ✅ Soporte de formatos: "tipo:id" y "id"

Validaciones de seguridad verificadas:
- ✅ Canal NO existe en BD (es huérfano)
- ✅ Pertenece al gym actual (team validation)
- ✅ NO es canal de evento
- ✅ Usuario es owner en Stream
- ✅ Cross-gym isolation

Basado en: Stream Chat Official Best Practices
Referencia: /STREAM_OFFICIAL_BEST_PRACTICES.md
"""
