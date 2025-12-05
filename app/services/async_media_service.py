"""
AsyncMediaService - Servicio async para manejar media de historias.

Este módulo extiende AsyncStorageService para soportar upload/delete de media
de historias (imágenes y videos) con generación automática de thumbnails.

Migrado en FASE 3 de la conversión sync → async.
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import io

from app.services.async_storage import AsyncStorageService
from app.core.config import get_settings

logger = logging.getLogger("async_media_service")
settings = get_settings()


class AsyncMediaService(AsyncStorageService):
    """
    Servicio async extendido para manejar media de historias (imágenes y videos).

    Todos los métodos son async y utilizan AsyncSession.

    Hereda de AsyncStorageService y añade:
    - Upload de media para historias
    - Generación automática de thumbnails
    - Validación de tipos de archivo
    - Procesamiento de imágenes con PIL

    Métodos principales:
    - upload_story_media() - Sube imagen o video para historia
    - delete_story_media() - Elimina media de historia
    - validate_media_url() - Valida URLs de media
    """

    def __init__(self):
        """
        Inicializa el servicio con bucket dedicado para historias.

        Note:
            Limites de tamaño:
            - Imágenes: 10MB
            - Videos: 50MB
        """
        super().__init__()
        # Bucket dedicado para historias
        self.stories_bucket = settings.STORIES_BUCKET
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.max_video_size = 50 * 1024 * 1024  # 50MB

    async def upload_story_media(
        self,
        gym_id: int,
        user_id: int,
        file: UploadFile,
        media_type: str = "image"
    ) -> Dict[str, str]:
        """
        Sube media para una historia (imagen o video).

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            file: Archivo a subir
            media_type: Tipo de media ("image" o "video")

        Returns:
            Dict con URLs de media y thumbnail:
            - media_url: URL del archivo principal
            - thumbnail_url: URL del thumbnail (None para videos)

        Raises:
            HTTPException: Si el tipo de archivo no es válido o excede tamaño máximo

        Note:
            Thumbnails:
            - Imágenes grandes: thumbnail 400x400 con aspect ratio
            - Videos: thumbnail pendiente de implementación (None)
        """
        # Verificar que Supabase esté configurado
        if not self.supabase:
            logger.error("Cliente Supabase no inicializado")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de almacenamiento no disponible"
            )

        try:
            # Validar tipo de archivo
            if media_type == "image":
                if not self._is_valid_story_image(file.content_type):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El archivo debe ser una imagen (jpg, png, webp, gif)"
                    )
                max_size = self.max_image_size
            elif media_type == "video":
                if not self._is_valid_story_video(file.content_type):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El archivo debe ser un video (mp4, mov, avi)"
                    )
                max_size = self.max_video_size
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tipo de media no soportado"
                )

            # Leer contenido del archivo
            contents = await file.read()

            # Validar tamaño
            if len(contents) > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo excede el tamaño máximo permitido ({max_size // (1024*1024)}MB)"
                )

            # Generar nombre único para el archivo
            file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            folder_path = f"gym_{gym_id}/user_{user_id}/stories"
            filename = f"{folder_path}/{uuid.uuid4().hex}{file_ext}"

            logger.info(f"Subiendo media de historia: {filename}")

            # Subir archivo principal
            async def upload_operation():
                result = self.supabase.storage.from_(self.stories_bucket).upload(
                    path=filename,
                    file=contents,
                    file_options={"content-type": file.content_type}
                )
                logger.info(f"Media subida exitosamente: {result}")
                return result

            await self._execute_with_retry_async(
                f"subida de media {filename}",
                upload_operation
            )

            # Generar URL pública
            media_url = self._execute_with_retry_sync(
                "generación de URL pública",
                lambda: self.supabase.storage.from_(self.stories_bucket).get_public_url(filename)
            )

            result = {"media_url": media_url}

            # Para videos, generar thumbnail
            if media_type == "video":
                # Por ahora, usar una imagen placeholder
                # En producción, usar un servicio de procesamiento de video
                result["thumbnail_url"] = None
                logger.info("Thumbnail de video pendiente de implementación")

            # Para imágenes grandes, generar thumbnail
            elif media_type == "image":
                try:
                    thumbnail_url = await self._generate_image_thumbnail(
                        contents=contents,
                        gym_id=gym_id,
                        user_id=user_id,
                        original_filename=file.filename
                    )
                    result["thumbnail_url"] = thumbnail_url
                except Exception as e:
                    logger.error(f"Error generando thumbnail: {e}")
                    result["thumbnail_url"] = media_url  # Usar imagen original como fallback

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al procesar media de historia: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar el archivo: {str(e)}"
            )

    async def _generate_image_thumbnail(
        self,
        contents: bytes,
        gym_id: int,
        user_id: int,
        original_filename: str
    ) -> Optional[str]:
        """
        Genera un thumbnail para una imagen.

        Args:
            contents: Contenido de la imagen original
            gym_id: ID del gimnasio
            user_id: ID del usuario
            original_filename: Nombre del archivo original

        Returns:
            URL del thumbnail generado, o None si la imagen es pequeña

        Note:
            - Tamaño thumbnail: 400x400 manteniendo aspect ratio
            - Formato: JPEG con calidad 85%
            - Convierte RGBA/LA/P a RGB automáticamente
        """
        try:
            # Abrir imagen con PIL
            img = Image.open(io.BytesIO(contents))

            # Si la imagen es pequeña, no generar thumbnail
            if img.width <= 400 and img.height <= 400:
                return None

            # Redimensionar manteniendo aspect ratio
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)

            # Convertir a RGB si es necesario (para evitar problemas con PNG con transparencia)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img

            # Guardar en buffer
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            thumbnail_contents = buffer.getvalue()

            # Generar nombre para thumbnail
            folder_path = f"gym_{gym_id}/user_{user_id}/stories/thumbnails"
            thumbnail_filename = f"{folder_path}/{uuid.uuid4().hex}_thumb.jpg"

            # Subir thumbnail
            async def upload_thumbnail():
                result = self.supabase.storage.from_(self.stories_bucket).upload(
                    path=thumbnail_filename,
                    file=thumbnail_contents,
                    file_options={"content-type": "image/jpeg"}
                )
                return result

            await self._execute_with_retry_async(
                f"subida de thumbnail {thumbnail_filename}",
                upload_thumbnail
            )

            # Generar URL pública
            thumbnail_url = self._execute_with_retry_sync(
                "generación de URL de thumbnail",
                lambda: self.supabase.storage.from_(self.stories_bucket).get_public_url(thumbnail_filename)
            )

            return thumbnail_url

        except Exception as e:
            logger.error(f"Error generando thumbnail: {str(e)}")
            return None

    def _is_valid_story_image(self, content_type: str) -> bool:
        """
        Verifica si el tipo de contenido es una imagen válida para historias.

        Args:
            content_type: Tipo MIME del archivo

        Returns:
            True si es imagen válida (jpg, png, webp, gif)
        """
        valid_types = [
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/jpg",
            "image/gif"
        ]
        return content_type in valid_types

    def _is_valid_story_video(self, content_type: str) -> bool:
        """
        Verifica si el tipo de contenido es un video válido para historias.

        Args:
            content_type: Tipo MIME del archivo

        Returns:
            True si es video válido (mp4, mov, avi, webm)
        """
        valid_types = [
            "video/mp4",
            "video/quicktime",  # .mov
            "video/x-msvideo",  # .avi
            "video/webm"
        ]
        return content_type in valid_types

    async def delete_story_media(self, media_url: str) -> bool:
        """
        Elimina media de una historia.

        Args:
            media_url: URL de la media a eliminar

        Returns:
            True si se eliminó exitosamente, False en caso contrario

        Note:
            - Valida que la URL pertenezca al bucket de historias
            - No lanza excepciones, solo retorna False en caso de error
        """
        if not self.supabase:
            logger.error("Cliente Supabase no inicializado")
            return False

        try:
            # Verificar que la URL pertenece a nuestro bucket
            if not media_url or not media_url.startswith(self.api_url):
                logger.warning(f"URL no válida para eliminar: {media_url}")
                return False

            # Extraer nombre del archivo de la URL
            clean_url = media_url.split('?')[0]
            bucket_path_prefix = f'/storage/v1/object/public/{self.stories_bucket}/'

            if bucket_path_prefix in clean_url:
                filename = clean_url.split(bucket_path_prefix)[-1]

                if not filename:
                    logger.error(f"No se pudo extraer nombre de archivo de URL: {clean_url}")
                    return False

                logger.info(f"Eliminando archivo {filename} del bucket {self.stories_bucket}")

                async def remove_operation():
                    result = self.supabase.storage.from_(self.stories_bucket).remove([filename])
                    logger.info(f"Archivo eliminado: {result}")
                    return True

                success = await self._execute_with_retry_async(
                    f"eliminación de archivo {filename}",
                    remove_operation
                )
                return success

            else:
                logger.warning(f"URL no corresponde al bucket de historias: {clean_url}")
                return False

        except Exception as e:
            logger.error(f"Error al eliminar media de historia: {str(e)}")
            return False

    def validate_media_url(self, url: str) -> bool:
        """
        Valida si una URL es válida y accesible.

        Args:
            url: URL a validar

        Returns:
            True si la URL es válida

        Note:
            Permite:
            - URLs de nuestro servicio (Supabase)
            - URLs externas (YouTube, etc.)
        """
        if not url:
            return False

        # Verificar que sea una URL de nuestro servicio
        if self.api_url and url.startswith(self.api_url):
            return True

        # También permitir URLs externas (YouTube, etc.)
        if url.startswith(('http://', 'https://')):
            return True

        return False


# Instancia singleton del servicio async
_async_media_service_instance = None


def get_async_media_service() -> AsyncMediaService:
    """
    Obtiene la instancia singleton del AsyncMediaService.

    Returns:
        Instancia única de AsyncMediaService
    """
    global _async_media_service_instance
    if _async_media_service_instance is None:
        _async_media_service_instance = AsyncMediaService()
    return _async_media_service_instance


# Instancia exportada para uso directo (compatible con imports existentes)
async_media_service = get_async_media_service()
