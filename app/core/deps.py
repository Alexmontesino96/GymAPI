# Este archivo ahora redirige a auth.py para mantener compatibilidad
from app.core.auth0_helper import get_current_user, get_current_user_with_permissions

# Para compatibilidad con código existente
get_current_active_user = get_current_user

# Para compatibilidad con código que requiera superusuario
get_current_active_superuser = lambda: get_current_user_with_permissions(required_permissions=["admin:all"]) 