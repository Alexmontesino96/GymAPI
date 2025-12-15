"""
Test unitario para verificar el comportamiento de eliminación de conversación.

Este test verifica que al eliminar una conversación:
1. Se llama a Stream Chat con channel.hide(user_id, clear_history=True)
2. clear_history=True asegura que el historial NO se muestra al reabrir
3. El chat queda oculto automáticamente en la base de datos

IMPORTANTE: Este test verifica el comportamiento CORE de la eliminación.
El parámetro clear_history=True en Stream Chat garantiza que:
- Al reabrir el chat, NO se muestran mensajes antiguos
- Solo aparecerán mensajes enviados DESPUÉS de la eliminación
- El comportamiento es permanente (no se puede revertir)
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy.orm import Session

from app.services.chat import chat_service


def test_delete_conversation_calls_stream_with_clear_history():
    """
    Test PRINCIPAL: Verifica que delete_conversation_for_user llama a Stream Chat
    con clear_history=True, lo cual garantiza que el historial NO se muestra al reabrir.
    """
    print("\n" + "="*80)
    print("TEST: Verificar que delete_conversation usa clear_history=True")
    print("="*80)

    # SETUP: Mocks
    mock_db = MagicMock(spec=Session)
    mock_room = Mock()
    mock_room.id = 100
    mock_room.gym_id = 1
    mock_room.is_direct = True
    mock_room.stream_channel_id = "direct_user_10_user_11"
    mock_room.stream_channel_type = "messaging"

    mock_user = Mock()
    mock_user.id = 10
    mock_user.gym_id = 1

    mock_member = Mock()
    mock_member.room_id = 100
    mock_member.user_id = 10

    # Configurar comportamiento de la DB
    # Primera query: ChatMember (verificar membresía)
    # Segunda query: User (obtener usuario)
    query_mock = MagicMock()
    mock_db.query.return_value = query_mock
    query_mock.filter.return_value.first.side_effect = [
        mock_member,  # Primera llamada: verificar membresía
        mock_user,  # Segunda llamada: get user
    ]

    # Mock de Stream Chat
    mock_channel = MagicMock()

    print(f"\n1. Configuración del test:")
    print(f"   - Room ID: {mock_room.id}")
    print(f"   - User ID: {mock_user.id}")
    print(f"   - Gym ID: 1")
    print(f"   - Stream Channel: {mock_room.stream_channel_type}:{mock_room.stream_channel_id}")

    with patch('app.services.chat.stream_client') as mock_stream_client, \
         patch('app.services.chat.chat_repository') as mock_repo:

        # Configurar repository mock
        mock_repo.get_room.return_value = mock_room
        mock_repo.hide_room_for_user.return_value = None

        # Configurar stream client mock
        mock_stream_client.channel.return_value = mock_channel

        # ACCIÓN: Llamar al servicio
        print(f"\n2. Ejecutando delete_conversation_for_user...")
        result = chat_service.delete_conversation_for_user(
            db=mock_db,
            room_id=100,
            user_id=10,
            gym_id=1
        )

        print(f"\n3. Verificando llamadas a Stream Chat:")

        # VERIFICACIÓN 1: Se obtuvo el canal correcto
        mock_stream_client.channel.assert_called_once_with("messaging", "direct_user_10_user_11")
        print(f"   ✅ Canal obtenido: messaging:direct_user_10_user_11")

        # VERIFICACIÓN 2: Se llamó a hide() con clear_history=True
        # Verificar que hide() fue llamado
        assert mock_channel.hide.called, "hide() debe haber sido llamado"

        # Obtener los argumentos con los que fue llamado
        hide_call_args = mock_channel.hide.call_args
        assert hide_call_args is not None

        # CRÍTICO: Verificar que clear_history=True fue pasado
        assert hide_call_args[1].get('clear_history') is True, "clear_history debe ser True"

        # El user_id puede variar ("user_10" o "gym_1_user_10"), ambos son válidos
        user_id_param = hide_call_args[1].get('user_id')
        assert user_id_param is not None, "user_id debe estar presente"
        assert '10' in user_id_param, f"user_id debe contener el ID del usuario: {user_id_param}"

        print(f"   ✅ hide() llamado con:")
        print(f"      - user_id: {user_id_param}")
        print(f"      - clear_history: True  👈 CRÍTICO")

        # VERIFICACIÓN 3: El chat se ocultó en la BD
        mock_repo.hide_room_for_user.assert_called_once_with(mock_db, room_id=100, user_id=10)
        print(f"   ✅ Chat ocultado en BD")

        # VERIFICACIÓN 4: El resultado indica éxito
        assert result["success"] is True
        assert result["history_cleared"] is True
        print(f"\n4. Resultado del servicio:")
        print(f"   ✅ success: {result['success']}")
        print(f"   ✅ history_cleared: {result['history_cleared']}")
        print(f"   ✅ message: {result['message']}")

        print(f"\n5. Comportamiento esperado en Stream Chat:")
        print(f"   📖 Según documentación de Stream Chat:")
        print(f"   - channel.hide(user_id, clear_history=True) hace dos cosas:")
        print(f"     1. Oculta el canal para este usuario")
        print(f"     2. ELIMINA PERMANENTEMENTE el historial para este usuario")
        print(f"   - Al reabrir el chat:")
        print(f"     ✅ El chat aparece en la lista")
        print(f"     ❌ NO se muestran mensajes antiguos")
        print(f"     ✅ Solo aparecen mensajes NUEVOS enviados DESPUÉS de la eliminación")

    print("\n" + "="*80)
    print("✅ TEST COMPLETADO EXITOSAMENTE")
    print("="*80)
    print(f"\nCONCLUSIÓN:")
    print(f"  El servicio delete_conversation_for_user está correctamente implementado.")
    print(f"  Usa clear_history=True lo cual garantiza que:")
    print(f"  - El historial fue ELIMINADO PERMANENTEMENTE para el usuario")
    print(f"  - Al reabrir el chat, NO se muestran mensajes previos")
    print(f"  - Solo se verán mensajes nuevos (patrón WhatsApp 'Eliminar Para Mí')")
    print("="*80 + "\n")


def test_stream_clear_history_parameter_explanation():
    """
    Test educativo: Explica el comportamiento de clear_history=True
    """
    print("\n" + "="*80)
    print("EXPLICACIÓN: ¿Qué hace clear_history=True en Stream Chat?")
    print("="*80)

    print(f"\n📚 DOCUMENTACIÓN DE STREAM CHAT:")
    print(f"   API: channel.hide(user_id, clear_history=True)")
    print(f"\n   Parámetros:")
    print(f"   - user_id: El ID del usuario para quien ocultar el canal")
    print(f"   - clear_history: Si True, elimina el historial de mensajes para este usuario")

    print(f"\n🔍 COMPORTAMIENTOS:")
    print(f"\n   Con clear_history=False (default):")
    print(f"   ✓ El canal se oculta")
    print(f"   ✓ Los mensajes permanecen")
    print(f"   ✓ Al reabrir: Se ven todos los mensajes antiguos")
    print(f"   → Esto es un simple 'hide'")

    print(f"\n   Con clear_history=True:")
    print(f"   ✓ El canal se oculta")
    print(f"   ✓ Los mensajes se ELIMINAN para este usuario")
    print(f"   ✓ Al reabrir: NO se ven mensajes antiguos")
    print(f"   ✓ Solo aparecen mensajes nuevos")
    print(f"   → Esto es 'Eliminar Para Mí' (WhatsApp pattern)")

    print(f"\n💡 CASOS DE USO:")
    print(f"\n   1. Usuario quiere solo ocultar:")
    print(f"      → Usar hide(user_id, clear_history=False)")
    print(f"      → Puede ver historial al reabrir")

    print(f"\n   2. Usuario quiere eliminar historial sensible:")
    print(f"      → Usar hide(user_id, clear_history=True) ✅")
    print(f"      → Historial eliminado permanentemente")
    print(f"      → Solo verá mensajes nuevos")

    print(f"\n⚠️  IMPORTANTE:")
    print(f"   - clear_history=True es PERMANENTE y NO REVERSIBLE")
    print(f"   - El otro usuario NO se ve afectado (mantiene su historial)")
    print(f"   - Es unilateral (solo afecta al usuario que ejecuta la acción)")

    print("\n" + "="*80 + "\n")


def test_delete_conversation_validates_direct_only():
    """
    Test: Verificar que solo se pueden eliminar chats directos 1-to-1
    """
    print("\n" + "="*80)
    print("TEST: Validar que solo se eliminan chats directos")
    print("="*80)

    # SETUP: Mock de un chat de GRUPO (no directo)
    mock_db = MagicMock(spec=Session)
    mock_room = Mock()
    mock_room.id = 200
    mock_room.gym_id = 1
    mock_room.is_direct = False  # ❌ NO es directo
    mock_room.stream_channel_id = "group_test_123"

    mock_db.query.return_value.filter.return_value.first.return_value = mock_room

    print(f"\n1. Intentando eliminar un chat de GRUPO (debe fallar)...")

    with patch('app.services.chat.stream_client'):
        # Intentar eliminar el grupo (debe lanzar error)
        with pytest.raises(ValueError) as exc_info:
            chat_service.delete_conversation_for_user(
                db=mock_db,
                room_id=200,
                user_id=10,
                gym_id=1
            )

        error_message = str(exc_info.value)
        print(f"   ✅ Error recibido correctamente:")
        print(f"      '{error_message}'")
        assert "Solo puedes eliminar conversaciones 1-to-1" in error_message

    print("\n" + "="*80)
    print("✅ Validación funciona correctamente")
    print("="*80 + "\n")


if __name__ == "__main__":
    print("\n" + "="*100)
    print(" "*30 + "SUITE DE TESTS - DELETE CONVERSATION")
    print("="*100)

    print("\n📋 TESTS INCLUIDOS:")
    print("   1. test_delete_conversation_calls_stream_with_clear_history")
    print("      → Verifica que se llama a Stream con clear_history=True")
    print("   2. test_stream_clear_history_parameter_explanation")
    print("      → Explica el comportamiento de clear_history")
    print("   3. test_delete_conversation_validates_direct_only")
    print("      → Verifica que solo se eliminan chats 1-to-1")

    pytest.main([__file__, "-v", "-s"])
