from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import get_settings

# Definimos dónde buscar la clave API (en qué header)
# La Action enviará el secreto en este header
api_key_header = APIKeyHeader(name="X-Auth0-Webhook-Secret", auto_error=False)

async def verify_auth0_webhook_secret(api_key: str = Security(api_key_header)):
    """
    Verifica que la clave API proporcionada en el header X-Auth0-Webhook-Secret
    coincida con el secreto AUTH0_WEBHOOK_SECRET configurado.
    """
    settings = get_settings()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header X-Auth0-Webhook-Secret",
        )
    # Comparamos con la variable de configuración existente AUTH0_WEBHOOK_SECRET
    if api_key != settings.AUTH0_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token secreto inválido o incorrecto",
        )
    # Si la clave es válida, la dependencia no necesita devolver nada explícitamente.
    return True # Opcionalmente devolver True para claridad 