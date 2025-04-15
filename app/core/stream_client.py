from stream_chat import StreamChat
from app.core.config import get_settings

# Inicializar el cliente Stream con las credenciales obtenidas de get_settings()
_settings = get_settings()
stream_client = StreamChat(
    api_key=_settings.STREAM_API_KEY,
    api_secret=_settings.STREAM_API_SECRET
) 