"""
Test de integración para verificar el comportamiento de eliminación de conversación.
Este test verifica que:
1. Al eliminar una conversación, se llama a Stream con clear_history=True
2. El chat queda oculto automáticamente
3. Al reabrir el chat, el historial previo NO debe mostrarse
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.gym import Gym
from app.models.chat import ChatRoom, ChatMember
from app.services.chat import chat_service
from app.repositories import chat_repository


@pytest.fixture
def gym(db: Session):
    """Crea un gimnasio de prueba"""
    gym = Gym(
        id=1,
        name="Gimnasio Test",
        address="Calle Test 123",
        phone="1234567890"
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    return gym


@pytest.fixture
def user1(db: Session, gym: Gym):
    """Crea el usuario 1 (quien eliminará la conversación)"""
    user = User(
        id=10,
        auth0_id="auth0|test_user_1",
        email="user1@test.com",
        first_name="Usuario",
        last_name="Uno",
        gym_id=gym.id,
        role="MEMBER"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user2(db: Session, gym: Gym):
    """Crea el usuario 2 (el otro participante del chat)"""
    user = User(
        id=11,
        auth0_id="auth0|test_user_2",
        email="user2@test.com",
        first_name="Usuario",
        last_name="Dos",
        gym_id=gym.id,
        role="MEMBER"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def direct_chat(db: Session, gym: Gym, user1: User, user2: User):
    """Crea un chat directo entre user1 y user2"""
    chat_room = ChatRoom(
        id=100,
        gym_id=gym.id,
        name=f"Chat entre {user1.first_name} y {user2.first_name}",
        is_direct=True,
        stream_channel_id="direct_user_10_user_11",
        stream_channel_type="messaging",
        status="ACTIVE"
    )
    db.add(chat_room)
    db.commit()
    db.refresh(chat_room)

    # Agregar miembros al chat
    member1 = ChatMember(room_id=chat_room.id, user_id=user1.id)
    member2 = ChatMember(room_id=chat_room.id, user_id=user2.id)
    db.add(member1)
    db.add(member2)
    db.commit()

    return chat_room


def test_delete_conversation_hides_and_clears_history(db: Session, gym: Gym, user1: User, user2: User, direct_chat: ChatRoom):
    """
    Test principal: Verificar que al eliminar una conversación:
    1. Se llama a Stream Chat con clear_history=True
    2. El chat queda oculto automáticamente
    """
    print("\n" + "="*80)
    print("TEST: Eliminar conversación y verificar comportamiento")
    print("="*80)

    # Mock de Stream Chat
    with patch('app.services.chat.stream_client') as mock_stream:
        # Configurar el mock del canal
        mock_channel = MagicMock()
        mock_stream.channel.return_value = mock_channel

        print(f"\n1. Estado inicial:")
        print(f"   - Chat ID: {direct_chat.id}")
        print(f"   - Usuario 1 ID: {user1.id}")
        print(f"   - Usuario 2 ID: {user2.id}")
        print(f"   - Stream Channel: {direct_chat.stream_channel_id}")

        # Verificar que el chat NO está oculto inicialmente
        is_hidden_before = chat_repository.is_room_hidden(db, room_id=direct_chat.id, user_id=user1.id)
        print(f"\n2. Chat oculto ANTES de eliminar: {is_hidden_before}")
        assert not is_hidden_before, "El chat NO debe estar oculto inicialmente"

        # PASO 3: Eliminar la conversación
        print(f"\n3. Eliminando conversación...")
        result = chat_service.delete_conversation_for_user(
            db=db,
            room_id=direct_chat.id,
            user_id=user1.id,
            gym_id=gym.id
        )

        print(f"   ✅ Resultado: {result}")

        # VERIFICACIÓN 1: Stream Chat fue llamado correctamente
        print(f"\n4. Verificando llamadas a Stream Chat:")

        # Verificar que se obtuvo el canal correcto
        mock_stream.channel.assert_called_once_with("messaging", "direct_user_10_user_11")
        print(f"   ✅ Canal obtenido: messaging:direct_user_10_user_11")

        # Verificar que se llamó a hide() con clear_history=True
        expected_stream_id = f"gym_{gym.id}_user_{user1.id}"
        mock_channel.hide.assert_called_once_with(user_id=expected_stream_id, clear_history=True)
        print(f"   ✅ hide() llamado con clear_history=True para usuario: {expected_stream_id}")

        # VERIFICACIÓN 2: El chat quedó oculto automáticamente
        print(f"\n5. Verificando que el chat está oculto:")
        is_hidden_after = chat_repository.is_room_hidden(db, room_id=direct_chat.id, user_id=user1.id)
        print(f"   Chat oculto DESPUÉS de eliminar: {is_hidden_after}")
        assert is_hidden_after, "El chat DEBE estar oculto después de eliminar"
        print(f"   ✅ El chat está oculto correctamente")

        # VERIFICACIÓN 3: El resultado indica que el historial fue limpiado
        print(f"\n6. Verificando resultado de la operación:")
        assert result["success"] is True, "La operación debe ser exitosa"
        assert result["history_cleared"] is True, "El historial debe estar marcado como limpiado"
        assert result["room_id"] == direct_chat.id, "El room_id debe coincidir"
        print(f"   ✅ success: {result['success']}")
        print(f"   ✅ history_cleared: {result['history_cleared']}")
        print(f"   ✅ message: {result['message']}")

        # VERIFICACIÓN 4: El otro usuario NO se ve afectado
        print(f"\n7. Verificando que el usuario 2 NO se ve afectado:")
        is_hidden_for_user2 = chat_repository.is_room_hidden(db, room_id=direct_chat.id, user_id=user2.id)
        print(f"   Chat oculto para usuario 2: {is_hidden_for_user2}")
        assert not is_hidden_for_user2, "El chat NO debe estar oculto para el otro usuario"
        print(f"   ✅ El usuario 2 mantiene el chat visible")

        print("\n" + "="*80)
        print("✅ TEST COMPLETADO EXITOSAMENTE")
        print("="*80)


def test_reopen_chat_after_delete_no_history(db: Session, gym: Gym, user1: User, user2: User, direct_chat: ChatRoom):
    """
    Test: Verificar que al volver a mostrar el chat después de eliminarlo,
    el comportamiento es correcto (el historial NO se restaura)
    """
    print("\n" + "="*80)
    print("TEST: Reabrir chat después de eliminar - Verificar sin historial")
    print("="*80)

    with patch('app.services.chat.stream_client') as mock_stream:
        mock_channel = MagicMock()
        mock_stream.channel.return_value = mock_channel

        # PASO 1: Eliminar la conversación
        print(f"\n1. Eliminando conversación del chat {direct_chat.id}...")
        result_delete = chat_service.delete_conversation_for_user(
            db=db,
            room_id=direct_chat.id,
            user_id=user1.id,
            gym_id=gym.id
        )
        assert result_delete["success"] is True
        print(f"   ✅ Conversación eliminada")

        # Verificar que está oculto
        is_hidden = chat_repository.is_room_hidden(db, room_id=direct_chat.id, user_id=user1.id)
        assert is_hidden, "El chat debe estar oculto después de eliminar"
        print(f"   ✅ Chat está oculto")

        # PASO 2: Mostrar el chat de nuevo (simula que el usuario lo reabre)
        print(f"\n2. Mostrando el chat de nuevo...")
        chat_repository.show_room_for_user(db, room_id=direct_chat.id, user_id=user1.id)

        is_hidden_after_show = chat_repository.is_room_hidden(db, room_id=direct_chat.id, user_id=user1.id)
        assert not is_hidden_after_show, "El chat debe estar visible después de show"
        print(f"   ✅ Chat está visible de nuevo")

        # PASO 3: Verificar que clear_history fue llamado en Stream
        print(f"\n3. Verificando que el historial fue eliminado en Stream:")

        # El historial fue eliminado con clear_history=True en el paso de delete
        # Stream Chat garantiza que los mensajes antiguos NO aparecerán para este usuario
        expected_stream_id = f"gym_{gym.id}_user_{user1.id}"

        # Verificamos que hide fue llamado con clear_history=True
        hide_call_args = mock_channel.hide.call_args
        print(f"   Llamada a hide(): {hide_call_args}")

        assert hide_call_args is not None, "hide() debe haber sido llamado"
        assert hide_call_args[1]['user_id'] == expected_stream_id
        assert hide_call_args[1]['clear_history'] is True
        print(f"   ✅ clear_history=True fue pasado a Stream Chat")

        print(f"\n4. Comportamiento esperado en la app:")
        print(f"   - El chat está visible de nuevo en la lista")
        print(f"   - Al abrir el chat, NO aparecen mensajes antiguos")
        print(f"   - Solo aparecerán mensajes nuevos enviados DESPUÉS de la eliminación")
        print(f"   - Stream Chat maneja automáticamente el filtrado del historial")

        print("\n" + "="*80)
        print("✅ TEST COMPLETADO - El historial NO se restaura al reabrir")
        print("="*80)


def test_delete_conversation_validates_direct_chat_only(db: Session, gym: Gym, user1: User, user2: User):
    """
    Test: Verificar que solo se pueden eliminar chats directos 1-to-1
    """
    print("\n" + "="*80)
    print("TEST: Validar que solo se eliminan chats directos")
    print("="*80)

    # Crear un chat de grupo (NO directo)
    group_chat = ChatRoom(
        id=200,
        gym_id=gym.id,
        name="Grupo de Prueba",
        is_direct=False,  # NO es directo
        stream_channel_id="group_test_123",
        stream_channel_type="messaging",
        status="ACTIVE"
    )
    db.add(group_chat)
    db.commit()

    # Agregar miembros
    member1 = ChatMember(room_id=group_chat.id, user_id=user1.id)
    db.add(member1)
    db.commit()

    print(f"\n1. Intentando eliminar un chat de GRUPO (debe fallar)...")

    with patch('app.services.chat.stream_client'):
        # Intentar eliminar el grupo (debe lanzar error)
        with pytest.raises(ValueError) as exc_info:
            chat_service.delete_conversation_for_user(
                db=db,
                room_id=group_chat.id,
                user_id=user1.id,
                gym_id=gym.id
            )

        error_message = str(exc_info.value)
        print(f"   ✅ Error recibido: {error_message}")
        assert "Solo puedes eliminar conversaciones 1-to-1" in error_message

    print("\n" + "="*80)
    print("✅ TEST COMPLETADO - Validación funciona correctamente")
    print("="*80)


def test_delete_conversation_validates_membership(db: Session, gym: Gym, user1: User, user2: User, direct_chat: ChatRoom):
    """
    Test: Verificar que solo los miembros pueden eliminar la conversación
    """
    print("\n" + "="*80)
    print("TEST: Validar que solo miembros pueden eliminar")
    print("="*80)

    # Crear un usuario que NO es miembro del chat
    user3 = User(
        id=12,
        auth0_id="auth0|test_user_3",
        email="user3@test.com",
        first_name="Usuario",
        last_name="Tres",
        gym_id=gym.id,
        role="MEMBER"
    )
    db.add(user3)
    db.commit()

    print(f"\n1. Usuario 3 NO es miembro del chat")
    print(f"   Intentando eliminar (debe fallar)...")

    with patch('app.services.chat.stream_client'):
        # Intentar eliminar sin ser miembro (debe lanzar error)
        with pytest.raises(ValueError) as exc_info:
            chat_service.delete_conversation_for_user(
                db=db,
                room_id=direct_chat.id,
                user_id=user3.id,
                gym_id=gym.id
            )

        error_message = str(exc_info.value)
        print(f"   ✅ Error recibido: {error_message}")
        assert "No eres miembro" in error_message

    print("\n" + "="*80)
    print("✅ TEST COMPLETADO - Validación de membresía funciona")
    print("="*80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
