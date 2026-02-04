"""
Servicio de media para manejar archivos de posts.
Extiende el MediaService para soportar galerías de hasta 10 archivos.
"""

import os
import uuid
import logging
from typing import List, Optional, Dict, Any
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import io
import asyncio

from app.services.storage import StorageService
from app.core.config import get_settings
from app.models.post import PostMedia
from app.utils.image_processor import ImageProcessor
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()


class PostMediaService(StorageService):
    """
    Servicio para manejar media de posts (imágenes y videos con soporte de galería).
    """

    def __init__(self):
        super().__init__()
        # Bucket dedicado para posts
        self.posts_bucket = getattr(settings, 'POSTS_BUCKET', 'gym-posts')
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.max_video_size = 100 * 1024 * 1024  # 100MB
        self.max_files_per_post = 10

    async def upload_post_media(
        self,
        gym_id: int,
        user_id: int,
        file: UploadFile,
        media_type: str = "image",
        display_order: int = 0
    ) -> Dict[str, Any]:
        """
        Sube un archivo de media para un post.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            file: Archivo a subir
            media_type: Tipo de media ("image" o "video")
            display_order: Orden de visualización en galería

        Returns:
            Dict con URLs y metadata del archivo
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
                if not self._is_valid_post_image(file.content_type):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El archivo debe ser una imagen (jpg, png, webp, gif)"
                    )
                max_size = self.max_image_size
            elif media_type == "video":
                if not self._is_valid_post_video(file.content_type):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El archivo debe ser un video (mp4, mov, avi, webm)"
                    )
                max_size = self.max_video_size
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tipo de media no soportado"
                )

            # Leer contenido del archivo
            contents = await file.read()

            # Validar tamaño ANTES de optimización (rechazar archivos muy grandes)
            if len(contents) > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo excede el tamaño máximo permitido ({max_size // (1024*1024)}MB)"
                )

            # Variables para el upload
            upload_content_type = file.content_type
            width, height = None, None

            # Optimizar imagen antes de subir
            if media_type == "image":
                try:
                    optimized = ImageProcessor.optimize(contents)
                    contents = optimized["content"]
                    upload_content_type = optimized["content_type"]
                    width, height = optimized["dimensions"]

                    # Usar extensión del formato optimizado
                    file_ext = f".{optimized['format']}"

                    logger.info(
                        f"Imagen optimizada: {optimized['original_size']/1024:.0f}KB -> "
                        f"{optimized['final_size']/1024:.0f}KB "
                        f"({optimized['compression_ratio']:.0%}), "
                        f"formato: {optimized['format']}, dims: {optimized['dimensions']}"
                    )
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=str(e)
                    )
            else:
                # Para videos, mantener extensión original
                file_ext = os.path.splitext(file.filename)[1] if file.filename else ".mp4"

            # Generar nombre único para el archivo
            folder_path = f"gym_{gym_id}/user_{user_id}/posts"
            filename = f"{folder_path}/{uuid.uuid4().hex}{file_ext}"

            logger.info(f"Subiendo media de post: {filename}")

            # Subir archivo principal (ya optimizado si es imagen)
            async def upload_operation():
                result = self.supabase.storage.from_(self.posts_bucket).upload(
                    path=filename,
                    file=contents,
                    file_options={"content-type": upload_content_type}
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
                lambda: self.supabase.storage.from_(self.posts_bucket).get_public_url(filename)
            )

            # Obtener dimensiones de la imagen (si no se obtuvieron durante optimización)
            if media_type == "image" and width is None:
                try:
                    img = Image.open(io.BytesIO(contents))
                    width, height = img.size
                except Exception as e:
                    logger.warning(f"No se pudieron obtener dimensiones de imagen: {e}")

            result = {
                "media_url": media_url,
                "media_type": media_type,
                "display_order": display_order,
                "width": width,
                "height": height,
                # La imagen optimizada ya está comprimida, usar como thumbnail
                "thumbnail_url": media_url if media_type == "image" else None
            }

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al procesar media de post: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar el archivo: {str(e)}"
            )

    async def upload_gallery(
        self,
        gym_id: int,
        user_id: int,
        files: List[UploadFile]
    ) -> List[Dict[str, Any]]:
        """
        Sube múltiples archivos para crear una galería en un post.

        Args:
            gym_id: ID del gimnasio
            user_id: ID del usuario
            files: Lista de archivos a subir (máximo 10)

        Returns:
            Lista de dicts con URLs y metadata de cada archivo
        """
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe proporcionar al menos un archivo"
            )

        if len(files) > self.max_files_per_post:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Máximo {self.max_files_per_post} archivos por post"
            )

        # Detectar tipo de media de cada archivo
        media_items = []
        for idx, file in enumerate(files):
            # Determinar tipo basado en content_type
            if file.content_type and file.content_type.startswith('image/'):
                media_type = "image"
            elif file.content_type and file.content_type.startswith('video/'):
                media_type = "video"
            else:
                # Intentar detectar por extensión
                ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    media_type = "image"
                elif ext in ['.mp4', '.mov', '.avi', '.webm']:
                    media_type = "video"
                else:
                    logger.warning(f"Tipo de archivo no reconocido: {file.filename}, asumiendo imagen")
                    media_type = "image"

            media_items.append({
                "file": file,
                "media_type": media_type,
                "display_order": idx
            })

        # Subir archivos en paralelo
        tasks = []
        for item in media_items:
            task = self.upload_post_media(
                gym_id=gym_id,
                user_id=user_id,
                file=item["file"],
                media_type=item["media_type"],
                display_order=item["display_order"]
            )
            tasks.append(task)

        # Ejecutar uploads en paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verificar si hubo errores
        uploaded_media = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error subiendo archivo {idx}: {result}")
                # Limpiar archivos ya subidos si hay error
                for uploaded in uploaded_media:
                    try:
                        await self.delete_post_media(uploaded["media_url"])
                    except:
                        pass
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error subiendo archivo {idx + 1}"
                )
            uploaded_media.append(result)

        logger.info(f"Galería subida exitosamente: {len(uploaded_media)} archivos")
        return uploaded_media

    async def delete_post_media(self, media_url: str):
        """
        Elimina un archivo de media del storage.

        Args:
            media_url: URL del archivo a eliminar
        """
        try:
            # Extraer path del archivo de la URL
            # Formato esperado: https://...supabase.co/storage/v1/object/public/{bucket}/{path}
            if '/object/public/' in media_url:
                parts = media_url.split('/object/public/')
                if len(parts) == 2:
                    bucket_and_path = parts[1].split('/', 1)
                    if len(bucket_and_path) == 2:
                        path = bucket_and_path[1]

                        def delete_operation():
                            return self.supabase.storage.from_(self.posts_bucket).remove([path])

                        self._execute_with_retry_sync(
                            f"eliminación de media {path}",
                            delete_operation
                        )
                        logger.info(f"Media eliminada: {path}")
                        return

            logger.warning(f"No se pudo extraer path de URL: {media_url}")

        except Exception as e:
            logger.error(f"Error eliminando media: {e}")
            # No lanzar excepción, solo log

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
            URL del thumbnail generado o None
        """
        try:
            # Abrir imagen con PIL
            img = Image.open(io.BytesIO(contents))

            # Si la imagen es pequeña, no generar thumbnail
            if img.width <= 800 and img.height <= 800:
                return None

            # Redimensionar manteniendo aspect ratio
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)

            # Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img

            # Guardar en buffer
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            thumbnail_contents = buffer.getvalue()

            # Generar nombre para thumbnail
            folder_path = f"gym_{gym_id}/user_{user_id}/posts/thumbnails"
            thumbnail_filename = f"{folder_path}/{uuid.uuid4().hex}_thumb.jpg"

            # Subir thumbnail
            async def upload_thumb():
                return self.supabase.storage.from_(self.posts_bucket).upload(
                    path=thumbnail_filename,
                    file=thumbnail_contents,
                    file_options={"content-type": "image/jpeg"}
                )

            await self._execute_with_retry_async(
                f"subida de thumbnail {thumbnail_filename}",
                upload_thumb
            )

            # Generar URL pública
            thumbnail_url = self._execute_with_retry_sync(
                "generación de URL de thumbnail",
                lambda: self.supabase.storage.from_(self.posts_bucket).get_public_url(thumbnail_filename)
            )

            return thumbnail_url

        except Exception as e:
            logger.error(f"Error generando thumbnail: {e}")
            return None

    def _is_valid_post_image(self, content_type: Optional[str]) -> bool:
        """Valida si el content type es una imagen válida para posts"""
        if not content_type:
            return False
        valid_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        return content_type.lower() in valid_types

    def _is_valid_post_video(self, content_type: Optional[str]) -> bool:
        """Valida si el content type es un video válido para posts"""
        if not content_type:
            return False
        valid_types = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm']
        return content_type.lower() in valid_types
