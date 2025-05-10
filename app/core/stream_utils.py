"""
Utilidades para la integración con Stream Chat.

Este módulo contiene funciones de ayuda para facilitar la 
interacción entre los IDs internos de la aplicación y los
IDs necesarios para Stream Chat.
"""

def get_stream_id_from_internal(internal_id: int) -> str:
    """
    Convierte un ID interno (número entero) a un ID para Stream Chat (string).
    
    Args:
        internal_id: ID interno de usuario en nuestra base de datos
        
    Returns:
        Un string que representa el ID en formato válido para Stream
    """
    # Stream requiere IDs como strings y permite caracteres: a-z, 0-9, @, _, -
    # Simplemente prefijamos con "user_" para asegurar que es un ID interno
    return f"user_{internal_id}"

def get_internal_id_from_stream(stream_id: str) -> int:
    """
    Extrae el ID interno a partir de un ID de Stream.
    
    Args:
        stream_id: ID de Stream en formato "user_X"
        
    Returns:
        El ID interno como entero
        
    Raises:
        ValueError: Si el ID no tiene el formato esperado
    """
    # Verificar formato correcto
    if not stream_id or not stream_id.startswith("user_"):
        raise ValueError(f"ID de Stream inválido: {stream_id}")
    
    # Extraer parte numérica
    try:
        return int(stream_id.replace("user_", ""))
    except ValueError:
        raise ValueError(f"ID de Stream no contiene un ID interno válido: {stream_id}")

def is_internal_id_format(stream_id: str) -> bool:
    """
    Verifica si un ID de Stream tiene el formato de ID interno.
    
    Args:
        stream_id: ID de Stream a verificar
        
    Returns:
        True si el ID tiene formato de ID interno, False en caso contrario
    """
    if not stream_id:
        return False
    
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