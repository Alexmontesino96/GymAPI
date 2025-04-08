#!/usr/bin/env python3
import requests
import json
import time
import os

# URL base para las pruebas (asegúrate de que el servidor esté en ejecución)
API_URL = "http://localhost:8080"
API_BASE = f"{API_URL}/api/v1"

# Token de autenticación (reemplaza con el tuyo o configura una variable de entorno)
AUTH_TOKEN = os.environ.get("TEST_AUTH_TOKEN", "test_token")

def test_chat_flow():
    """Prueba completa del flujo de chat haciendo solicitudes HTTP reales"""
    print("\n\n================================================================================")
    print("================ INICIANDO PRUEBA DE FLUJO DEL SISTEMA DE CHAT =================")
    print("================================================================================\n\n")
    
    # Headers para autenticación
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # ETAPA 1: Obtener perfil de usuario
    print("\n================================================================================")
    print("================== OBTENIENDO INFORMACIÓN DEL USUARIO ACTUAL ===================")
    print("================================================================================\n")
    
    response = requests.get(f"{API_BASE}/users/profile", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error al obtener usuario actual: {response.status_code}")
        try:
            print(response.text)
        except:
            print("No se pudo mostrar respuesta de error")
        print("❌ No se pudo obtener información del usuario actual. Abortando prueba.")
        print("\n✅ Prueba de chat completada")
        return
    
    user_data = response.json()
    print(f"✅ Usuario actual obtenido: {user_data.get('name', 'Sin nombre')} ({user_data.get('id', 'Sin ID')})")
    user_id = user_data.get("id", "unknown_user")
    
    # ETAPA 2: Obtener token de Stream Chat
    print("\n================================================================================")
    print("======================= OBTENIENDO TOKEN DE STREAM CHAT ========================")
    print("================================================================================\n")
    
    response = requests.get(f"{API_BASE}/chat/token", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error al obtener token de Stream Chat: {response.status_code}")
        try:
            print(response.text)
        except:
            print("No se pudo mostrar respuesta de error")
        print("⚠️ No se pudo obtener el token de Stream Chat. Continuando prueba...")
        stream_token = None
    else:
        token_data = response.json()
        stream_token = token_data["token"]
        print(f"✅ Token de Stream Chat obtenido: {stream_token[:15]}...")
    
    # ETAPA 3: Crear una sala de chat
    print("\n================================================================================")
    print("========================= CREANDO SALA DE CHAT CUSTOM =========================")
    print("================================================================================\n")
    
    room_name = f"Sala-{int(time.time())}"
    room_data = {
        "name": room_name,
        "is_direct": False,
        "member_ids": [user_id]
    }
    
    response = requests.post(f"{API_BASE}/chat/rooms", json=room_data, headers=headers)
    
    if response.status_code != 201:
        print(f"❌ Error al crear sala de chat: {response.status_code}")
        try:
            print(response.text)
        except:
            print("No se pudo mostrar respuesta de error")
        print("⚠️ No se pudo crear la sala de chat. Continuando prueba...")
        custom_room_id = None
    else:
        room_data = response.json()
        custom_room_id = room_data["id"]
        print(f"✅ Sala de chat creada: {room_data['name']} (ID: {custom_room_id})")
    
    # ETAPA 4: Obtener sala de chat de un evento
    print("\n================================================================================")
    print("========================= OBTENIENDO CHAT DE EVENTO ===========================")
    print("================================================================================\n")
    
    # Usar un ID de evento fijo para las pruebas
    event_id = 1
    
    response = requests.get(f"{API_BASE}/chat/rooms/event/{event_id}", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error al obtener chat de evento: {response.status_code}")
        try:
            print(response.text)
        except:
            print("No se pudo mostrar respuesta de error")
        print("⚠️ No se pudo obtener el chat del evento. Continuando prueba...")
        event_room_id = None
    else:
        event_room_data = response.json()
        event_room_id = event_room_data["id"]
        print(f"✅ Chat de evento obtenido: ID {event_room_id}")
    
    # ETAPA 5: Crear chat directo con otro usuario
    print("\n================================================================================")
    print("========================= CREANDO CHAT DIRECTO ================================")
    print("================================================================================\n")
    
    # Para pruebas, usamos un ID fijo de otro usuario
    other_user_id = "7"  # ID corto y simple para pruebas
    
    response = requests.get(f"{API_BASE}/chat/rooms/direct/{other_user_id}", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error al crear chat directo: {response.status_code}")
        try:
            print(response.text)
        except:
            print("No se pudo mostrar respuesta de error")
        print("⚠️ No se pudo crear el chat directo. Continuando prueba...")
        direct_room_id = None
    else:
        direct_room_data = response.json()
        direct_room_id = direct_room_data["id"]
        print(f"✅ Chat directo creado: ID {direct_room_id}")
    
    # Resumen de resultados
    print("\n================================================================================")
    print("====================== RESUMEN DE RESULTADOS DE LA PRUEBA =====================")
    print("================================================================================\n")
    
    print(f"Perfil de usuario: {'✅' if user_id != 'unknown_user' else '❌'}")
    print(f"Token de Stream: {'✅' if stream_token else '❌'}")
    print(f"Creación de sala: {'✅' if custom_room_id else '❌'}")
    print(f"Chat de evento: {'✅' if event_room_id else '❌'}")
    print(f"Chat directo: {'✅' if direct_room_id else '❌'}")
    
    print("\n✅ Prueba de chat completada")

if __name__ == "__main__":
    test_chat_flow() 