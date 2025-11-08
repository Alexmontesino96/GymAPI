"""
Cliente de Stream Activity Feeds para el sistema de historias.

Este módulo configura el cliente de Stream Activity Feeds usando las mismas
credenciales que Stream Chat, ya que ambos servicios comparten las API keys.
"""

import logging
from typing import Optional
from stream import Stream
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Obtener configuración
_settings = get_settings()

# Validar configuración requerida
if not _settings.STREAM_API_KEY or not _settings.STREAM_API_SECRET:
    logger.warning("Stream Feeds credentials not configured")
    stream_feeds_client = None
else:
    try:
        # Inicializar cliente de Stream Activity Feeds
        # Nota: Usamos las MISMAS credenciales que Stream Chat
        stream_feeds_client = Stream(
            api_key=_settings.STREAM_API_KEY,
            api_secret=_settings.STREAM_API_SECRET,
            app_id=_settings.STREAM_APP_ID if _settings.STREAM_APP_ID else None,
            location=_settings.STREAM_LOCATION
        )

        logger.info(
            f"Stream Feeds client initialized successfully "
            f"(location: {_settings.STREAM_LOCATION}, "
            f"app_id: {'configured' if _settings.STREAM_APP_ID else 'not set'})"
        )

    except Exception as e:
        logger.error(f"Failed to initialize Stream Feeds client: {str(e)}")
        stream_feeds_client = None


def get_stream_feeds_client() -> Optional[Stream]:
    """
    Obtiene el cliente de Stream Activity Feeds.

    Returns:
        Stream client si está configurado, None en caso contrario
    """
    if not stream_feeds_client:
        logger.warning("Stream Feeds client not available")

    return stream_feeds_client


def is_stream_feeds_available() -> bool:
    """
    Verifica si Stream Activity Feeds está disponible y configurado.

    Returns:
        True si el cliente está configurado, False en caso contrario
    """
    return stream_feeds_client is not None


def create_user_token(user_id: str, **extra_data) -> Optional[str]:
    """
    Crea un token de usuario para Stream Activity Feeds.

    IMPORTANTE: Los tokens de Feeds son DIFERENTES a los de Chat.
    Cada producto de Stream requiere su propio token.

    Args:
        user_id: ID del usuario en formato gym_{gym_id}_user_{user_id}
        **extra_data: Datos adicionales para incluir en el token

    Returns:
        Token JWT para el usuario o None si no está configurado
    """
    if not stream_feeds_client:
        logger.warning("Cannot create user token: Stream Feeds not configured")
        return None

    try:
        # Crear token para Activity Feeds
        # Este token es diferente al de Chat aunque use las mismas credenciales
        token = stream_feeds_client.create_user_token(user_id, **extra_data)

        logger.debug(f"Created Stream Feeds token for user: {user_id}")
        return token

    except Exception as e:
        logger.error(f"Failed to create Stream Feeds token for {user_id}: {str(e)}")
        return None


def get_feed(feed_slug: str, user_id: str):
    """
    Obtiene un feed específico para un usuario.

    Args:
        feed_slug: Tipo de feed (user, timeline, notification, etc.)
        user_id: ID del usuario

    Returns:
        Feed object o None si no está configurado
    """
    if not stream_feeds_client:
        return None

    try:
        return stream_feeds_client.feed(feed_slug, user_id)
    except Exception as e:
        logger.error(f"Failed to get feed {feed_slug} for {user_id}: {str(e)}")
        return None


# Exportar cliente para uso directo si es necesario
__all__ = [
    'stream_feeds_client',
    'get_stream_feeds_client',
    'is_stream_feeds_available',
    'create_user_token',
    'get_feed'
]