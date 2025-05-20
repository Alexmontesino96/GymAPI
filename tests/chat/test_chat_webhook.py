import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
import hmac
import hashlib
import time

from app.main import app
from app.core.config import get_settings
from app.services.chat import chat_service
from app.core.stream_client import stream_client

settings = get_settings()

def test_chat_webhook_flow():
    """
    Prueba el flujo completo de chat con webhook:
    1. Crear chat directo entre dos usuarios
    2. Enviar mensajes
    3. Verificar que el webhook recibe las notificaciones
    """
    client = TestClient(app)
    
    # 1. Crear chat directo entre usuarios 4 y 6
    response = client.get("/api/v1/chat/rooms/direct/6", headers={"Authorization": f"Bearer {get_test_token()}"})
    assert response.status_code == 200
    chat_data = response.json()
    channel_id = chat_data["stream_channel_id"]
    
    # 2. Enviar 3 mensajes como usuario 4
    messages = [
        "¡Hola! Este es el primer mensaje de prueba",
        "Este es el segundo mensaje para probar el webhook",
        "Y este es el tercer mensaje para completar la prueba"
    ]
    
    for message in messages:
        # Enviar mensaje a través de Stream
        channel = stream_client.channel("messaging", channel_id)
        response = channel.send_message({
            "text": message,
            "user_id": "auth0_67d5d64d64ccf1c522a6950b"  # ID de Stream del usuario 4
        })
        
        # Simular el webhook de Stream
        webhook_payload = {
            "message": {
                "id": response["message"]["id"],
                "text": message,
                "user": {
                    "id": "auth0_67d5d64d64ccf1c522a6950b"
                }
            },
            "channel": {
                "id": channel_id,
                "type": "messaging",
                "name": chat_data["name"]
            }
        }
        
        # Calcular firma del webhook
        body = json.dumps(webhook_payload).encode()
        signature = hmac.new(
            settings.STREAM_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Enviar webhook
        webhook_response = client.post(
            "/api/v1/webhooks/stream/new-message",
            json=webhook_payload,
            headers={"X-Signature": signature}
        )
        
        assert webhook_response.status_code == 200
        webhook_data = webhook_response.json()
        assert webhook_data["status"] == "success"
        
        # Esperar un momento para que se procesen las notificaciones
        time.sleep(1)

def get_test_token():
    """
    Obtiene un token de prueba para el usuario 4
    """
    # Aquí deberías implementar la lógica para obtener un token válido
    # Por ahora, retornamos un token de prueba
    return "test_token" 