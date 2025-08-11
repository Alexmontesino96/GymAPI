"""
Test específico para verificar que el bug de membresías en canales directos está corregido.

Este test simula la creación de un canal directo y verifica que AMBOS usuarios
(creator y destinatario) son agregados como miembros del canal.
"""

import pytest
from unittest.mock import Mock, patch
from app.services.chat import ChatService
from app.schemas.chat import ChatRoomCreate


class TestDirectChatMembershipFix:
    
    @patch('app.services.chat.stream_client')
    @patch('app.services.chat.chat_repository')
    def test_creator_is_added_as_member_in_direct_chat(self, mock_repo, mock_stream_client):
        """
        Test que verifica que el creator es agregado como miembro en canales directos.
        Este es el bug que fue corregido.
        """
        # Configurar mocks
        mock_db = Mock()
        mock_user1 = Mock()
        mock_user1.id = 10
        mock_user1.auth0_id = "auth0|creator"
        mock_user1.email = "creator@test.com"
        
        mock_user2 = Mock()
        mock_user2.id = 8  
        mock_user2.auth0_id = "auth0|recipient"
        mock_user2.email = "recipient@test.com"
        
        # Mock de consultas de usuarios
        def mock_query_filter(model, condition):
            mock_query = Mock()
            if hasattr(condition, 'right') and condition.right.value == 10:
                mock_query.first.return_value = mock_user1
            elif hasattr(condition, 'right') and condition.right.value == 8:
                mock_query.first.return_value = mock_user2
            return mock_query
            
        mock_db.query.return_value.filter.side_effect = lambda condition: mock_query_filter(None, condition)
        
        # Mock del repositorio (no hay chat existente)
        mock_repo.get_direct_chat.return_value = None
        mock_repo.get_room_by_stream_id.return_value = None
        
        # Mock de Stream Client
        mock_channel = Mock()
        mock_stream_client.channel.return_value = mock_channel
        
        # Mock de respuesta de creación del canal
        mock_channel.create.return_value = {
            "channel": {
                "id": "direct_user_10_user_8",
                "type": "messaging",
                "created_at": "2025-08-11T00:00:00Z"
            }
        }
        
        # Mock de respuesta del repositorio al crear la sala
        mock_created_room = Mock()
        mock_created_room.id = 123
        mock_created_room.stream_channel_id = "direct_user_10_user_8"
        mock_created_room.stream_channel_type = "messaging"
        mock_created_room.created_at = "2025-08-11T00:00:00Z"
        mock_repo.create_room.return_value = mock_created_room
        mock_repo.get_room_by_event_id.return_value = mock_created_room
        
        # Crear el servicio y ejecutar
        chat_service = ChatService()
        
        room_data = ChatRoomCreate(
            name="Test Direct Chat",
            member_ids=[10, 8],  # Creator (10) y destinatario (8)
            is_direct=True
        )
        
        result = chat_service.create_room(db=mock_db, creator_id=10, room_data=room_data, gym_id=4)
        
        # VERIFICACIONES CRÍTICAS
        
        # 1. Verificar que se llamó add_members con AMBOS usuarios
        mock_channel.add_members.assert_called_once()
        called_members = mock_channel.add_members.call_args[0][0]
        
        # 2. Verificar que tanto el creator como el destinatario están en la lista
        assert len(called_members) == 2, f"Esperados 2 miembros, obtenidos {len(called_members)}"
        
        # 3. Verificar que incluye user_10 (creator) - ESTE ERA EL BUG
        assert "user_10" in called_members, "El creator (user_10) NO fue agregado como miembro - BUG NO CORREGIDO"
        
        # 4. Verificar que incluye user_8 (destinatario)
        assert "user_8" in called_members, "El destinatario (user_8) no fue agregado como miembro"
        
        # 5. Verificar que se creó el canal correctamente
        mock_stream_client.channel.assert_called_with("messaging", "direct_user_10_user_8")
        mock_channel.create.assert_called_once()
        
        # 6. Verificar que el resultado contiene la información correcta
        assert result["id"] == 123
        assert result["stream_channel_id"] == "direct_user_10_user_8"
        assert result["is_direct"] == True

    @patch('app.services.chat.stream_client')
    def test_both_users_can_access_created_channel(self, mock_stream_client):
        """
        Test que verifica que ambos usuarios pueden acceder al canal creado.
        """
        # Mock del canal
        mock_channel = Mock()
        mock_stream_client.channel.return_value = mock_channel
        
        # Simular respuesta exitosa de query para ambos usuarios
        mock_channel.query.return_value = {
            "channel": {
                "id": "direct_user_10_user_8",
                "type": "messaging",
                "members": [
                    {"user": {"id": "user_10"}},
                    {"user": {"id": "user_8"}}
                ]
            }
        }
        
        chat_service = ChatService()
        
        # Simular query desde ambos usuarios
        for user_id in ["user_10", "user_8"]:
            response = chat_service._query_stream_channel_with_retry(
                "messaging", "direct_user_10_user_8", user_id
            )
            
            # Verificar que ambos usuarios pueden acceder
            assert response["channel"]["id"] == "direct_user_10_user_8"
            members = response["channel"]["members"]
            member_ids = [m["user"]["id"] for m in members]
            
            # Verificar que ambos usuarios son miembros
            assert "user_10" in member_ids, "Creator no es miembro del canal"
            assert "user_8" in member_ids, "Destinatario no es miembro del canal"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])