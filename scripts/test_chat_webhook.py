import requests
import json
import hmac
import hashlib
import time
from app.core.config import get_settings
from app.core.stream_client import stream_client

# Usar un valor de webhook secret fijo para pruebas
WEBHOOK_SECRET = "test_webhook_secret_for_local_testing"

def test_chat_webhook():
    """
    Prueba manual del webhook de chat:
    1. Crear chat directo entre usuarios 4 y 6
    2. Enviar mensajes
    3. Verificar que el webhook recibe las notificaciones
    """
    # Configurar la URL base y headers
    base_url = "https://gymapi-eh6m.onrender.com/api/v1"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ2NTg3NjUzLCJleHAiOjE3NDY2NzQwNTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.iSV8FKwBFg65i2LFghbW7vVykMTqhsvPeND9fYKzcfwaEAFhIqjfUPr3eALTFtt-tjV0SNDeuywP5RcO5WsIlMoErK2zCHF191ZxGizWfXVtUq2GkADOhIf9s7UF2itnAnxfhgMCGqDdYpQZFl-3yB1Yl_1eBNDGM_VBFcbJP_B1ReSC2f7m18S86SUEYNf3Lh6lvOt4D5YQri-t_hO6OszI4ZrcIETueL2NWXfC-JXATpCQ_S3YgdPONlTljs3ryMqWhZWJN5vESlAsUlB9ao9rpFU4WirjS8CldVYaHhXu7QUbK1pcRc8L14x67AcJZKMHTgGaIhPLU9JskImzlg",
        "x-gym-id": "1"
    }
    
    # 1. Crear chat directo entre usuarios 4 y 6
    print(f"\nCreando chat directo...")
    print(f"URL: {base_url}/chat/rooms/direct/6")
    print(f"Headers: {headers}")
    
    response = requests.get(
        f"{base_url}/chat/rooms/direct/6",
        headers=headers
    )
    print(f"Status: {response.status_code}")
    print(f"Response text: {response.text}")
    
    if response.status_code != 200:
        print("Error creando el chat directo. Abortando prueba.")
        return
        
    chat_data = response.json()
    channel_id = chat_data["stream_channel_id"]
    channel_type = chat_data["stream_channel_type"]
    print(f"Canal creado: {channel_id}, tipo: {channel_type}")
    
    # 2. Enviar 3 mensajes como usuario 4
    messages = [
        "¡Hola! Este es el primer mensaje de prueba",
        "Este es el segundo mensaje para probar el webhook",
        "Y este es el tercer mensaje para completar la prueba"
    ]
    
    # ID de Auth0 del usuario que envía los mensajes
    user_auth0_id = "auth0_67d5d64d64ccf1c522a6950b"
    
    # Obtener token de Stream para el usuario 4 (no es necesario para enviar mensajes en este caso)
    token = stream_client.create_token(user_auth0_id)
    
    for i, message in enumerate(messages, 1):
        print(f"\nEnviando mensaje {i}: {message}")
        
        # Enviar mensaje a través de Stream
        channel = stream_client.channel(channel_type, channel_id)
        
        # Basado en cómo se usa en chat.py en close_event_chat:
        # channel.send_message(system_message, user_id="system")
        message_data = {"text": message}
        message_response = channel.send_message(message_data, user_id=user_auth0_id)
        print(f"Mensaje enviado - ID: {message_response['message']['id']}")
        
        # Simular el webhook de Stream
        webhook_payload = {
            "message": {
                "id": message_response["message"]["id"],
                "text": message,
                "user": {
                    "id": user_auth0_id
                }
            },
            "channel": {
                "id": channel_id,
                "type": channel_type,
                "name": chat_data["name"]
            }
        }
        
        # Calcular firma del webhook usando el secreto fijo
        body = json.dumps(webhook_payload).encode()
        signature = hmac.new(
            WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        print(f"Enviando webhook con firma: {signature}")
        # Enviar webhook
        webhook_response = requests.post(
            f"{base_url}/webhooks/stream/new-message",
            json=webhook_payload,
            headers={
                "X-Signature": signature,
                "x-gym-id": "2"
            }
        )
        
        print(f"Webhook response - Status: {webhook_response.status_code}")
        print(f"Webhook response - Body: {webhook_response.json()}")
        
        # Esperar un momento para que se procesen las notificaciones
        time.sleep(1)

if __name__ == "__main__":
    test_chat_webhook() 