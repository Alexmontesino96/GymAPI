import requests
import json
import hmac
import hashlib
import time
import re
from app.core.config import get_settings
from app.core.stream_client import stream_client
from app.db.session import SessionLocal
from app.models.user import User

# Necesitamos el API_SECRET para firmar los mensajes en el lado del cliente
# Esto simula lo que Stream hace cuando envía un webhook
settings = get_settings()
API_SECRET = settings.STREAM_API_SECRET

def test_chat_webhook():
    """
    Prueba manual del webhook de chat:
    1. Crear chat directo entre usuarios (usando IDs internos)
    2. Enviar mensajes
    3. Verificar que el webhook recibe las notificaciones
    """
    # Obtener una sesión de base de datos
    db = SessionLocal()
    
    try:
        # Primero, obtener los IDs internos de algunos usuarios para la prueba
        # Por ejemplo, usando los IDs 4 y 6 (ajustar según los usuarios disponibles)
        user1 = db.query(User).filter(User.id == 4).first()
        user2 = db.query(User).filter(User.id == 6).first()
        
        if not user1 or not user2:
            print("No se encontraron los usuarios con IDs 4 y 6. Prueba con otros IDs.")
            return
            
        user1_id = user1.id
        user2_id = user2.id
        
        # Obtener los auth0_ids de los usuarios (necesarios para Stream)
        auth0_id_user1 = user1.auth0_id
        auth0_id_user2 = user2.auth0_id
        
        # Sanitizar IDs para Stream
        user1_id_stream = re.sub(r'[^a-zA-Z0-9@_\-]', '_', auth0_id_user1)
        user2_id_stream = re.sub(r'[^a-zA-Z0-9@_\-]', '_', auth0_id_user2)
        
        print(f"IDs internos: usuario1={user1_id}, usuario2={user2_id}")
        print(f"IDs de Stream: usuario1={user1_id_stream}, usuario2={user2_id_stream}")
    finally:
        db.close()
    
    # Configurar la URL base y headers
    base_url = "https://gymapi-eh6m.onrender.com/api/v1"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ2NTg3NjUzLCJleHAiOjE3NDY2NzQwNTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.iSV8FKwBFg65i2LFghbW7vVykMTqhsvPeND9fYKzcfwaEAFhIqjfUPr3eALTFtt-tjV0SNDeuywP5RcO5WsIlMoErK2zCHF191ZxGizWfXVtUq2GkADOhIf9s7UF2itnAnxfhgMCGqDdYpQZFl-3yB1Yl_1eBNDGM_VBFcbJP_B1ReSC2f7m18S86SUEYNf3Lh6lvOt4D5YQri-t_hO6OszI4ZrcIETueL2NWXfC-JXATpCQ_S3YgdPONlTljs3ryMqWhZWJN5vESlAsUlB9ao9rpFU4WirjS8CldVYaHhXu7QUbK1pcRc8L14x67AcJZKMHTgGaIhPLU9JskImzlg",
        "x-gym-id": "1"
    }
    
    # 1. Crear chat directo usando el endpoint actualizado (ahora usando IDs internos)
    print("\nCreando chat directo...")
    direct_chat_url = f"{base_url}/chat/rooms/direct/{user2_id}"  # usuario_id=6
    
    response = requests.get(direct_chat_url, headers=headers)
    print(f"URL: {direct_chat_url}")
    print(f"Headers: {headers}")
    print(f"Status: {response.status_code}")
    print(f"Response text: {response.text}")
    
    # Si la creación del chat fue exitosa, continuar
    if response.status_code == 200:
        chat_data = response.json()
        channel_id = chat_data["stream_channel_id"]
        channel_type = chat_data["stream_channel_type"]
        print(f"Canal creado: {channel_id}, tipo: {channel_type}")
        
        # Obtener información del canal para verificar los miembros
        try:
            channel = stream_client.channel(channel_type, channel_id)
            channel_info = channel.query(members={"limit": 10})
            print(f"\nInformación del canal:")
            print(f"Miembros: {channel_info.get('members', [])}")
            print(f"Número de miembros: {len(channel_info.get('members', []))}")
            
            # Extraer los IDs de Stream de los miembros
            stream_member_ids = [member.get('user_id') for member in channel_info.get('members', [])]
            print(f"IDs de Stream de los miembros: {stream_member_ids}")
            
            # Verificar si el usuario actual está en los miembros
            if user1_id_stream not in stream_member_ids:
                print(f"El usuario {user1_id_stream} no está en el canal, intentando añadirlo")
                try:
                    # Asegurarse de que el usuario existe en Stream
                    stream_client.update_user({
                        "id": user1_id_stream,
                        "name": "Usuario de prueba"
                    })
                    
                    # Añadir el usuario al canal
                    channel.add_members([user1_id_stream])
                    print(f"Usuario {user1_id_stream} añadido al canal")
                    
                    # Verificar miembros de nuevo
                    channel_info = channel.query(members={"limit": 10})
                    print(f"Miembros actualizados: {channel_info.get('members', [])}")
                    print(f"Número de miembros actualizados: {len(channel_info.get('members', []))}")
                except Exception as e:
                    print(f"Error añadiendo usuario al canal: {e}")
            
        except Exception as e:
            print(f"Error obteniendo información del canal: {e}")
        
        # 2. Enviar algunos mensajes de prueba y simular el webhook
        messages = [
            "¡Hola! Este es el primer mensaje de prueba usando IDs internos",
            "Este es el segundo mensaje para probar el webhook actualizado",
            "Y este es el tercer mensaje para completar la prueba con IDs internos"
        ]
        
        for i, msg_text in enumerate(messages):
            print(f"\nEnviando mensaje {i+1}: {msg_text}")
            
            # Enviar mensaje usando la API de Stream
            message_data = {
                "text": msg_text
            }
            
            # Enviar mensaje
            try:
                # Crear y enviar mensaje directamente con stream_client
                response = channel.send_message(
                    message=message_data,
                    user_id=user1_id_stream  # Usar el ID de Stream de usuario 1
                )
                
                # Verificar respuesta de stream
                if response and "message" in response:
                    message_id = response["message"]["id"]
                    print(f"Mensaje enviado - ID: {message_id}")
                    
                    # Construir payload del webhook (similar a lo que Stream enviaría)
                    # Usar el ID del otro usuario como remitente para el webhook
                    webhook_sender_id = user2_id_stream  # ID de Stream del otro usuario
                    print(f"Usando {webhook_sender_id} como remitente para el webhook")
                    
                    webhook_payload = {
                        "message": {
                            "id": message_id,
                            "text": msg_text,
                            "user": {
                                "id": webhook_sender_id  # Usar el ID de Stream del usuario
                            }
                        },
                        "channel": {
                            "id": channel_id,
                            "type": channel_type
                        }
                    }
                    
                    # Convertir payload a JSON y generar firma HMAC
                    webhook_payload_json = json.dumps(webhook_payload)
                    
                    # Generar firma usando HMAC-SHA256 con API_SECRET
                    signature = hmac.new(
                        API_SECRET.encode(),
                        webhook_payload_json.encode(),
                        hashlib.sha256
                    ).hexdigest()
                    
                    print(f"Firma generada: {signature}")
                    print(f"Payload del webhook: {webhook_payload_json}")
                    
                    # Enviar webhook al endpoint
                    webhook_headers = {
                        "X-Signature": signature,
                        "Content-Type": "application/json"
                    }
                    webhook_url = f"{base_url}/webhooks/stream/new-message"
                    
                    print(f"Enviando webhook con firma: {signature}")
                    webhook_response = requests.post(
                        webhook_url,
                        headers=webhook_headers,
                        data=webhook_payload_json
                    )
                    
                    print(f"Webhook response - Status: {webhook_response.status_code}")
                    print(f"Webhook response - Headers: {webhook_response.headers}")
                    print(f"Webhook response - Body: {webhook_response.json()}")
                    
                    # Esperar un poco entre mensajes
                    time.sleep(1)
                else:
                    print(f"Error enviando mensaje: {response}")
            except Exception as e:
                print(f"Error enviando mensaje: {e}")
    else:
        print(f"Error creando chat directo: {response.text}")

if __name__ == "__main__":
    test_chat_webhook() 