"""
Utilidades para generar previews de mensajes de Stream Chat.
"""

from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def generate_message_preview(message: Dict[str, Any]) -> Tuple[str, str]:
    """
    Genera un preview inteligente del mensaje basado en su contenido.
    
    Args:
        message: Diccionario con datos del mensaje de Stream Chat
        
    Returns:
        Tuple[str, str]: (preview_text, message_type)
        
    Examples:
        - Texto normal: ("Hola, ¿cómo están?", "text")
        - Con imagen: ("📷 Imagen: Miren esta foto", "image") 
        - Solo imagen: ("📷 Imagen", "image")
        - Archivo: ("📎 Archivo: documento.pdf", "file")
        - Sistema: ("ℹ️ Mensaje del sistema", "system")
    """
    try:
        text = message.get("text", "").strip()
        attachments = message.get("attachments", [])
        message_type = message.get("type", "regular")
        
        # Mensajes de sistema
        if message_type == "system" or message_type != "regular":
            return "ℹ️ Mensaje del sistema", "system"
        
        # Procesar attachments si existen
        if attachments:
            preview_text, attachment_type = _process_attachments(attachments, text)
            return preview_text, attachment_type
        
        # Texto normal
        if text:
            # Truncar texto si es muy largo
            if len(text) > 200:
                preview = text[:197] + "..."
            else:
                preview = text
            return preview, "text"
        
        # Mensaje vacío (fallback)
        return "Mensaje", "text"
        
    except Exception as e:
        logger.error(f"Error generando preview de mensaje: {e}")
        return "Mensaje", "text"


def _process_attachments(attachments: list, text: str) -> Tuple[str, str]:
    """
    Procesa attachments y genera preview apropiado.
    
    Args:
        attachments: Lista de attachments del mensaje
        text: Texto del mensaje (puede estar vacío)
        
    Returns:
        Tuple[str, str]: (preview_text, attachment_type)
    """
    if not attachments:
        return text or "Mensaje", "text"
    
    # Contar tipos de attachments
    attachment_types = [att.get("type", "").lower() for att in attachments]
    attachment_count = len(attachments)
    
    # Determinar tipo principal y generar preview
    if "image" in attachment_types:
        return _generate_image_preview(attachment_count, text), "image"
    elif "file" in attachment_types:
        return _generate_file_preview(attachments, text), "file"
    elif "video" in attachment_types:
        return _generate_video_preview(attachment_count, text), "video"
    elif "audio" in attachment_types:
        return _generate_audio_preview(attachment_count, text), "audio"
    else:
        # Attachment genérico o desconocido
        return _generate_generic_attachment_preview(attachment_count, text), "attachment"


def _generate_image_preview(count: int, text: str) -> str:
    """Genera preview para imágenes."""
    if count == 1:
        emoji = "📷"
        label = "Imagen"
    else:
        emoji = "🖼️"
        label = f"{count} imágenes"
    
    if text:
        # Limitar texto a 150 chars si hay attachment
        text_preview = text[:147] + "..." if len(text) > 150 else text
        return f"{emoji} {label}: {text_preview}"
    else:
        return f"{emoji} {label}"


def _generate_file_preview(attachments: list, text: str) -> str:
    """Genera preview para archivos."""
    count = len(attachments)
    
    if count == 1:
        # Intentar obtener nombre del archivo
        filename = attachments[0].get("title") or attachments[0].get("name") or "archivo"
        emoji = "📎"
        label = f"Archivo: {filename}"
    else:
        emoji = "📎"
        label = f"{count} archivos"
    
    if text:
        text_preview = text[:147] + "..." if len(text) > 150 else text
        return f"{emoji} {label}: {text_preview}"
    else:
        return f"{emoji} {label}"


def _generate_video_preview(count: int, text: str) -> str:
    """Genera preview para videos."""
    if count == 1:
        emoji = "🎥"
        label = "Video"
    else:
        emoji = "🎬"
        label = f"{count} videos"
    
    if text:
        text_preview = text[:147] + "..." if len(text) > 150 else text
        return f"{emoji} {label}: {text_preview}"
    else:
        return f"{emoji} {label}"


def _generate_audio_preview(count: int, text: str) -> str:
    """Genera preview para audios."""
    if count == 1:
        emoji = "🎵"
        label = "Audio"
    else:
        emoji = "🎶"
        label = f"{count} audios"
    
    if text:
        text_preview = text[:147] + "..." if len(text) > 150 else text
        return f"{emoji} {label}: {text_preview}"
    else:
        return f"{emoji} {label}"


def _generate_generic_attachment_preview(count: int, text: str) -> str:
    """Genera preview para attachments genéricos."""
    if count == 1:
        emoji = "📎"
        label = "Adjunto"
    else:
        emoji = "📎"
        label = f"{count} adjuntos"
    
    if text:
        text_preview = text[:147] + "..." if len(text) > 150 else text
        return f"{emoji} {label}: {text_preview}"
    else:
        return f"{emoji} {label}"


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    Trunca texto a la longitud máxima especificada.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima (default: 200)
        
    Returns:
        str: Texto truncado con "..." si es necesario
    """
    if not text:
        return ""
    
    text = text.strip()
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."