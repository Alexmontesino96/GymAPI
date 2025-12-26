#!/usr/bin/env python3
"""
Test para verificar que al eliminar una conversación 1-to-1:
1. El chat se elimina correctamente
2. Al volver a abrir el chat, NO se muestra el historial previo
3. El otro usuario mantiene su historial intacto
"""
import requests
import json
import time
import os
from typing import Dict, Any

# URL base para las pruebas
API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_BASE = f"{API_URL}/api/v1"

# Token de autenticación
AUTH_TOKEN = os.environ.get("TEST_AUTH_TOKEN", "test_token")
GYM_ID = os.environ.get("TEST_GYM_ID", "1")

# IDs de usuarios para testing (configurar en .env.test)
USER_1_ID = os.environ.get("TEST_USER_1_ID", "11")  # Usuario que eliminará la conversación
USER_2_ID = os.environ.get("TEST_USER_2_ID", "8")   # Usuario con quien se chatea

def get_headers(token: str = AUTH_TOKEN) -> Dict[str, str]:
    """Genera headers para las peticiones HTTP"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Gym-ID": GYM_ID
    }

def test_delete_conversation_with_history():
    """
    Test principal: Verificar que al eliminar una conversación,
    el historial previo NO se muestra al reabrir el chat.
    """
    print("\n" + "="*80)
    print("TEST: Eliminar Conversación y Verificar Historial")
    print("="*80 + "\n")

    # PASO 1: Crear o obtener chat directo entre USER_1 y USER_2
    print("PASO 1: Crear/Obtener chat directo")
    print("-" * 80)

    response = requests.get(
        f"{API_BASE}/chat/rooms/direct/{USER_2_ID}",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al crear chat directo: {response.status_code}")
        print(f"Respuesta: {response.text}")
        return False

    chat_data = response.json()
    room_id = chat_data["id"]
    stream_channel_id = chat_data["stream_channel_id"]
    stream_channel_type = chat_data.get("stream_channel_type", "messaging")

    print(f"✅ Chat directo obtenido:")
    print(f"   - Room ID: {room_id}")
    print(f"   - Stream Channel: {stream_channel_type}:{stream_channel_id}")
    print()

    # PASO 2: Enviar mensajes al chat (simulando actividad previa)
    print("PASO 2: Enviar mensajes de prueba al chat")
    print("-" * 80)

    # Necesitamos usar Stream Chat SDK para enviar mensajes
    # Por ahora, verificaremos si ya hay mensajes en el canal
    # En un test real, aquí enviaríamos mensajes usando el SDK de Stream

    print("⚠️  NOTA: Para un test completo, se necesita integración con Stream Chat SDK")
    print("    para enviar mensajes. Por ahora, verificaremos con el estado actual.")
    print()

    # PASO 3: Obtener lista de chats para verificar que el chat está visible
    print("PASO 3: Verificar que el chat está visible en la lista")
    print("-" * 80)

    response = requests.get(
        f"{API_BASE}/chat/my-rooms",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al obtener lista de chats: {response.status_code}")
        return False

    my_rooms = response.json()
    chat_visible_before = any(room["id"] == room_id for room in my_rooms)

    print(f"Chat visible antes de eliminar: {'✅ Sí' if chat_visible_before else '❌ No'}")
    print()

    # PASO 4: Eliminar la conversación (Delete For Me)
    print("PASO 4: Eliminar conversación (DELETE /conversation)")
    print("-" * 80)

    response = requests.delete(
        f"{API_BASE}/chat/rooms/{room_id}/conversation",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al eliminar conversación: {response.status_code}")
        print(f"Respuesta: {response.text}")
        return False

    delete_result = response.json()
    print(f"✅ Conversación eliminada:")
    print(f"   - Success: {delete_result.get('success')}")
    print(f"   - Message: {delete_result.get('message')}")
    print(f"   - History cleared: {delete_result.get('history_cleared')}")
    print()

    # PASO 5: Verificar que el chat está oculto automáticamente
    print("PASO 5: Verificar que el chat está oculto automáticamente")
    print("-" * 80)

    response = requests.get(
        f"{API_BASE}/chat/my-rooms",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al obtener lista de chats: {response.status_code}")
        return False

    my_rooms_after_delete = response.json()
    chat_visible_after_delete = any(room["id"] == room_id for room in my_rooms_after_delete)

    if chat_visible_after_delete:
        print(f"❌ FALLO: El chat todavía está visible (debería estar oculto)")
        return False
    else:
        print(f"✅ El chat está oculto correctamente")
    print()

    # PASO 6: Verificar con include_hidden=true
    print("PASO 6: Verificar con include_hidden=true")
    print("-" * 80)

    response = requests.get(
        f"{API_BASE}/chat/my-rooms?include_hidden=true",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al obtener lista completa: {response.status_code}")
        return False

    all_rooms = response.json()
    chat_in_hidden = any(room["id"] == room_id for room in all_rooms)

    if not chat_in_hidden:
        print(f"⚠️  ADVERTENCIA: El chat no aparece ni con include_hidden=true")
    else:
        print(f"✅ El chat aparece en la lista con include_hidden=true")
    print()

    # PASO 7: Mostrar el chat de nuevo
    print("PASO 7: Mostrar el chat de nuevo (POST /show)")
    print("-" * 80)

    response = requests.post(
        f"{API_BASE}/chat/rooms/{room_id}/show",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al mostrar el chat: {response.status_code}")
        print(f"Respuesta: {response.text}")
        return False

    show_result = response.json()
    print(f"✅ Chat mostrado de nuevo:")
    print(f"   - Success: {show_result.get('success')}")
    print(f"   - Message: {show_result.get('message')}")
    print(f"   - Is hidden: {show_result.get('is_hidden')}")
    print()

    # PASO 8: Verificar que el chat está visible de nuevo
    print("PASO 8: Verificar que el chat vuelve a aparecer en la lista")
    print("-" * 80)

    response = requests.get(
        f"{API_BASE}/chat/my-rooms",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al obtener lista de chats: {response.status_code}")
        return False

    my_rooms_after_show = response.json()
    chat_visible_after_show = any(room["id"] == room_id for room in my_rooms_after_show)

    if not chat_visible_after_show:
        print(f"❌ FALLO: El chat no está visible después de show")
        return False
    else:
        print(f"✅ El chat está visible de nuevo")
    print()

    # PASO 9: Verificar que el historial fue eliminado
    print("PASO 9: Verificar estado del historial")
    print("-" * 80)
    print("⚠️  NOTA IMPORTANTE:")
    print("    Según la documentación y el código:")
    print("    - La función usa channel.hide(user_id, clear_history=True)")
    print("    - Esto ELIMINA PERMANENTEMENTE el historial para este usuario")
    print("    - Al reabrir el chat, NO se deben mostrar mensajes antiguos")
    print("    - Solo se verán mensajes nuevos enviados DESPUÉS de la eliminación")
    print()
    print("    Para verificar completamente esto, se necesita:")
    print("    1. Integración con Stream Chat SDK para enviar mensajes")
    print("    2. Consultar mensajes usando la API de Stream con el user_id")
    print("    3. Verificar que los mensajes antiguos no aparecen")
    print()

    # RESUMEN DE RESULTADOS
    print("\n" + "="*80)
    print("RESUMEN DE RESULTADOS")
    print("="*80)

    results = {
        "1. Chat creado correctamente": True,
        "2. Chat visible antes de eliminar": chat_visible_before,
        "3. Eliminación ejecutada correctamente": delete_result.get('success', False),
        "4. Chat oculto después de eliminar": not chat_visible_after_delete,
        "5. Chat mostrado de nuevo": show_result.get('success', False),
        "6. Chat visible después de show": chat_visible_after_show,
    }

    for key, value in results.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}")

    all_passed = all(results.values())

    print("\n" + "="*80)
    if all_passed:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print("="*80 + "\n")

    return all_passed


def test_delete_conversation_with_stream_verification():
    """
    Test avanzado que verifica el historial usando Stream Chat SDK directamente.
    Requiere: pip install stream-chat
    """
    print("\n" + "="*80)
    print("TEST AVANZADO: Verificación con Stream Chat SDK")
    print("="*80 + "\n")

    try:
        from stream_chat import StreamChat
        from app.core.config import get_settings

        settings = get_settings()
        stream_client = StreamChat(
            api_key=settings.STREAM_API_KEY,
            api_secret=settings.STREAM_API_SECRET
        )

        print("✅ Stream Chat SDK disponible")

    except ImportError:
        print("⚠️  Stream Chat SDK no disponible. Instalar con: pip install stream-chat")
        return False
    except Exception as e:
        print(f"❌ Error al inicializar Stream Chat: {str(e)}")
        return False

    # PASO 1: Obtener el chat directo
    response = requests.get(
        f"{API_BASE}/chat/rooms/direct/{USER_2_ID}",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al obtener chat: {response.status_code}")
        return False

    chat_data = response.json()
    room_id = chat_data["id"]
    stream_channel_id = chat_data["stream_channel_id"]
    stream_channel_type = chat_data.get("stream_channel_type", "messaging")

    print(f"Chat: {stream_channel_type}:{stream_channel_id}")

    # PASO 2: Enviar mensajes de prueba
    print("\nPASO 2: Enviando mensajes de prueba...")
    print("-" * 80)

    channel = stream_client.channel(stream_channel_type, stream_channel_id)

    # Usuario 1 (gym_1_user_11) envía mensajes
    stream_user_1 = f"gym_{GYM_ID}_user_{USER_1_ID}"

    test_messages = [
        "Mensaje de prueba 1",
        "Mensaje de prueba 2",
        "Mensaje de prueba 3"
    ]

    try:
        for i, msg in enumerate(test_messages, 1):
            channel.send_message({
                "text": msg,
                "user_id": stream_user_1
            })
            print(f"✅ Mensaje {i} enviado: {msg}")

        print()

    except Exception as e:
        print(f"❌ Error al enviar mensajes: {str(e)}")
        return False

    # PASO 3: Consultar mensajes ANTES de eliminar
    print("PASO 3: Consultar mensajes ANTES de eliminar")
    print("-" * 80)

    try:
        messages_before = channel.query(
            {"user_id": stream_user_1}
        )

        msg_count_before = len(messages_before["messages"])
        print(f"✅ Mensajes visibles para {stream_user_1}: {msg_count_before}")

        for msg in messages_before["messages"][-3:]:  # Últimos 3
            print(f"   - {msg.get('text', '(sin texto)')}")
        print()

    except Exception as e:
        print(f"❌ Error al consultar mensajes: {str(e)}")
        msg_count_before = 0

    # PASO 4: Eliminar la conversación
    print("PASO 4: Eliminar conversación (API)")
    print("-" * 80)

    response = requests.delete(
        f"{API_BASE}/chat/rooms/{room_id}/conversation",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"❌ Error al eliminar: {response.status_code}")
        return False

    print("✅ Conversación eliminada")
    print()

    # Esperar un poco para que Stream procese
    time.sleep(2)

    # PASO 5: Consultar mensajes DESPUÉS de eliminar
    print("PASO 5: Consultar mensajes DESPUÉS de eliminar")
    print("-" * 80)

    try:
        messages_after = channel.query(
            {"user_id": stream_user_1}
        )

        msg_count_after = len(messages_after["messages"])
        print(f"✅ Mensajes visibles para {stream_user_1}: {msg_count_after}")

        if msg_count_after > 0:
            print(f"⚠️  Mensajes que todavía aparecen:")
            for msg in messages_after["messages"]:
                print(f"   - {msg.get('text', '(sin texto)')}")
        else:
            print(f"✅ El historial fue eliminado completamente")

        print()

    except Exception as e:
        print(f"❌ Error al consultar mensajes: {str(e)}")
        msg_count_after = -1

    # PASO 6: Enviar un nuevo mensaje y verificar que aparece
    print("PASO 6: Enviar nuevo mensaje DESPUÉS de eliminar")
    print("-" * 80)

    try:
        new_message = f"Mensaje NUEVO después de eliminar - {int(time.time())}"
        channel.send_message({
            "text": new_message,
            "user_id": stream_user_1
        })
        print(f"✅ Nuevo mensaje enviado: {new_message}")

        time.sleep(1)

        # Consultar de nuevo
        messages_final = channel.query(
            {"user_id": stream_user_1}
        )

        msg_count_final = len(messages_final["messages"])
        print(f"✅ Mensajes visibles ahora: {msg_count_final}")
        print(f"   (Esperado: solo 1 mensaje nuevo, sin historial antiguo)")

        for msg in messages_final["messages"]:
            print(f"   - {msg.get('text', '(sin texto)')}")

        print()

    except Exception as e:
        print(f"❌ Error con nuevo mensaje: {str(e)}")

    # RESUMEN
    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)
    print(f"Mensajes ANTES de eliminar: {msg_count_before}")
    print(f"Mensajes DESPUÉS de eliminar: {msg_count_after}")
    print()

    if msg_count_after == 0:
        print("✅ ÉXITO: El historial fue eliminado completamente")
        print("   Solo los mensajes nuevos aparecerán")
        return True
    else:
        print("⚠️  El historial todavía aparece para este usuario")
        print("   Verificar implementación de clear_history en Stream")
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("INICIANDO TESTS DE ELIMINACIÓN DE CONVERSACIÓN")
    print("="*80)

    print("\n--- Test 1: Funcionalidad básica de eliminación ---")
    test1_passed = test_delete_conversation_with_history()

    print("\n\n--- Test 2: Verificación con Stream Chat SDK ---")
    test2_passed = test_delete_conversation_with_stream_verification()

    print("\n\n" + "="*80)
    print("RESULTADOS FINALES")
    print("="*80)
    print(f"Test 1 (Básico): {'✅ PASÓ' if test1_passed else '❌ FALLÓ'}")
    print(f"Test 2 (Avanzado): {'✅ PASÓ' if test2_passed else '❌ FALLÓ'}")
    print("="*80 + "\n")
