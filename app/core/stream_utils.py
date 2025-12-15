"""
Utilidades para la integración con Stream Chat.

Este módulo contiene funciones de ayuda para facilitar la 
interacción entre los IDs internos de la aplicación y los
IDs necesarios para Stream Chat.
"""

def get_stream_id_from_internal(internal_id: int, gym_id: int = None) -> str:
    """
    Convierte un ID interno (número entero) a un ID para Stream Chat (string).
    Soporta formato multi-tenant con gym_id.

    Args:
        internal_id: ID interno de usuario en nuestra base de datos
        gym_id: ID del gimnasio (requerido para multi-tenant). Si es None, usa formato legacy.

    Returns:
        Un string que representa el ID en formato válido para Stream.
        - Con gym_id: "gym_{gym_id}_user_{internal_id}" (multi-tenant)
        - Sin gym_id: "user_{internal_id}" (legacy, deprecado)
    """
    import logging

    # Stream requiere IDs como strings y permite caracteres: a-z, 0-9, @, _, -
    if gym_id is not None:
        # Formato multi-tenant: gym_{gym_id}_user_{user_id}
        return f"gym_{gym_id}_user_{internal_id}"
    else:
        # Fallback a formato legacy (sin gym_id) - DEPRECADO
        # Solo debe usarse para compatibilidad con datos existentes
        logging.warning(
            f"get_stream_id_from_internal llamado sin gym_id para user {internal_id}. "
            f"Usando formato legacy 'user_{id}' - DEPRECADO. "
            f"Por favor actualiza el código para pasar gym_id."
        )
        return f"user_{internal_id}"

def get_internal_id_from_stream(stream_id: str) -> int:
    """
    Extrae el ID interno a partir de un ID de Stream.
    Soporta tanto formato multi-tenant como legacy.

    Args:
        stream_id: ID de Stream en formato:
            - Multi-tenant: "gym_{gym_id}_user_{user_id}"
            - Legacy: "user_{user_id}"

    Returns:
        El ID interno del usuario como entero

    Raises:
        ValueError: Si el ID no tiene el formato esperado
    """
    if not stream_id:
        raise ValueError("ID de Stream vacío")

    # Formato multi-tenant: gym_{gym_id}_user_{user_id}
    if stream_id.startswith("gym_") and "_user_" in stream_id:
        try:
            # Extraer la parte después de "_user_"
            user_part = stream_id.split("_user_")[-1]
            return int(user_part)
        except (ValueError, IndexError):
            raise ValueError(f"ID de Stream multi-tenant inválido: {stream_id}")

    # Formato legacy: user_{user_id}
    elif stream_id.startswith("user_"):
        try:
            return int(stream_id.replace("user_", ""))
        except ValueError:
            raise ValueError(f"ID de Stream legacy inválido: {stream_id}")

    else:
        raise ValueError(f"Formato de ID de Stream no reconocido: {stream_id}")

def is_internal_id_format(stream_id: str) -> bool:
    """
    Verifica si un ID de Stream tiene el formato de ID interno.
    Reconoce tanto formato multi-tenant como legacy.

    Args:
        stream_id: ID de Stream a verificar

    Returns:
        True si el ID tiene formato de ID interno (multi-tenant o legacy), False en caso contrario
    """
    if not stream_id:
        return False

    # Formato multi-tenant: gym_{gym_id}_user_{user_id}
    if stream_id.startswith("gym_") and "_user_" in stream_id:
        try:
            user_part = stream_id.split("_user_")[-1]
            return user_part.isdigit()
        except:
            return False

    # Formato legacy: user_{user_id}
    return stream_id.startswith("user_") and stream_id[5:].isdigit()

def is_legacy_id_format(stream_id: str) -> bool:
    """
    Verifica si un ID de Stream tiene el formato legacy (auth0_id).
    
    Args:
        stream_id: ID de Stream a verificar
        
    Returns:
        True si el ID tiene formato legacy, False en caso contrario
    """
    if not stream_id:
        return False
    
    # Los IDs de Auth0 generalmente comienzan con "auth0|"
    return stream_id.startswith("auth0") or "|" in stream_id 