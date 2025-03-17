from stream_chat import StreamChat
from app.core.config import settings

# Inicializar el cliente Stream con las credenciales desde las variables de entorno
stream_client = StreamChat(
    api_key=settings.STREAM_API_KEY,
    api_secret=settings.STREAM_API_SECRET
) 