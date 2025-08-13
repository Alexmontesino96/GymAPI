"""
Utilidades para el manejo de zonas horarias en el sistema.
"""
from datetime import datetime, timezone
from typing import Optional
import pytz


def convert_naive_to_gym_timezone(naive_dt: datetime, gym_timezone: str) -> datetime:
    """
    Convierte un datetime naive (sin timezone) interpretándolo como hora local del gimnasio
    y lo convierte a un datetime aware en la zona horaria del gimnasio.
    
    Args:
        naive_dt: Datetime naive que representa la hora local del gimnasio
        gym_timezone: Zona horaria del gimnasio (ej: 'America/Mexico_City')
        
    Returns:
        Datetime aware en la zona horaria del gimnasio
    """
    if naive_dt.tzinfo is not None:
        raise ValueError("El datetime debe ser naive (sin timezone)")
    
    tz = pytz.timezone(gym_timezone)
    return tz.localize(naive_dt)


def convert_gym_time_to_utc(naive_dt: datetime, gym_timezone: str) -> datetime:
    """
    Convierte un datetime naive (hora local del gimnasio) a UTC.
    
    Args:
        naive_dt: Datetime naive que representa la hora local del gimnasio
        gym_timezone: Zona horaria del gimnasio
        
    Returns:
        Datetime aware en UTC
    """
    gym_aware = convert_naive_to_gym_timezone(naive_dt, gym_timezone)
    return gym_aware.astimezone(timezone.utc)


def normalize_to_utc(dt: datetime, gym_timezone: str) -> datetime:
    """
    Normaliza un datetime a UTC manejando entradas naive o aware.

    - Si `dt` es naive, se interpreta en la timezone del gimnasio y se convierte a UTC.
    - Si `dt` es aware, se convierte directamente a UTC preservando la hora exacta.

    Args:
        dt: datetime a normalizar
        gym_timezone: zona horaria del gimnasio

    Returns:
        datetime aware en UTC
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return convert_gym_time_to_utc(dt, gym_timezone)
    return dt.astimezone(timezone.utc)


def get_current_time_in_gym_timezone(gym_timezone: str) -> datetime:
    """
    Obtiene la hora actual en la zona horaria del gimnasio.
    
    Args:
        gym_timezone: Zona horaria del gimnasio
        
    Returns:
        Datetime aware representando la hora actual en la zona horaria del gimnasio
    """
    utc_now = datetime.now(timezone.utc)
    tz = pytz.timezone(gym_timezone)
    return utc_now.astimezone(tz)


def is_session_in_future(session_start_time: datetime, gym_timezone: str) -> bool:
    """
    Verifica si una sesión está en el futuro considerando la zona horaria del gimnasio.

    Acepta tanto datetimes naive (interpretados en la zona del gimnasio) como aware.
    Si es aware, se convierte a la zona del gimnasio antes de comparar.
    """
    current_time_gym = get_current_time_in_gym_timezone(gym_timezone)
    if session_start_time.tzinfo is None:
        session_aware = convert_naive_to_gym_timezone(session_start_time, gym_timezone)
    else:
        session_aware = convert_utc_to_local(session_start_time, gym_timezone)
    return session_aware > current_time_gym


def format_session_time_with_timezone(session_start_time: datetime, gym_timezone: str) -> dict:
    """
    Formatea la hora de una sesión incluyendo información de zona horaria.
    
    Args:
        session_start_time: Hora de inicio de la sesión (datetime naive)
        gym_timezone: Zona horaria del gimnasio
        
    Returns:
        Diccionario con información formateada de la hora
    """
    session_aware = convert_naive_to_gym_timezone(session_start_time, gym_timezone)
    
    return {
        "local_time": session_start_time,  # Hora naive (como se almacena)
        "gym_timezone": gym_timezone,
        "iso_with_timezone": session_aware.isoformat(),
        "utc_time": session_aware.astimezone(timezone.utc).isoformat()
    }


def convert_utc_to_local(utc_dt: datetime, gym_timezone: str) -> datetime:
    """
    Convierte un datetime UTC a hora local del gimnasio.
    
    Args:
        utc_dt: Datetime aware en UTC
        gym_timezone: Zona horaria del gimnasio
        
    Returns:
        Datetime aware en la zona horaria del gimnasio
    """
    if utc_dt.tzinfo is None:
        # Si es naive, asumimos que es UTC
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    
    tz = pytz.timezone(gym_timezone)
    return utc_dt.astimezone(tz)


def populate_session_timezone_fields(session_dict: dict, gym_timezone: str) -> dict:
    """
    Puebla los campos timezone de una sesión para la respuesta.
    
    Args:
        session_dict: Diccionario con datos de la sesión
        gym_timezone: Zona horaria del gimnasio
        
    Returns:
        Diccionario actualizado con campos timezone poblados
    """
    # Copiar el diccionario para no modificar el original
    result = session_dict.copy()
    
    # Poblar timezone del gimnasio
    result["timezone"] = gym_timezone
    
    # Convertir start_time de UTC a local si existe
    if "start_time" in result and result["start_time"]:
        start_time_utc = result["start_time"]
        if isinstance(start_time_utc, str):
            start_time_utc = datetime.fromisoformat(start_time_utc.replace('Z', '+00:00'))
        
        start_time_local = convert_utc_to_local(start_time_utc, gym_timezone)
        result["start_time_local"] = start_time_local.replace(tzinfo=None)  # Retornar como naive para compatibilidad
    
    # Convertir end_time de UTC a local si existe
    if "end_time" in result and result["end_time"]:
        end_time_utc = result["end_time"]
        if isinstance(end_time_utc, str):
            end_time_utc = datetime.fromisoformat(end_time_utc.replace('Z', '+00:00'))
        
        end_time_local = convert_utc_to_local(end_time_utc, gym_timezone)
        result["end_time_local"] = end_time_local.replace(tzinfo=None)  # Retornar como naive para compatibilidad
    
    return result
