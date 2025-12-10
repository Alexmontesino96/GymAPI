"""
Servicio de almacenamiento para logos de gimnasios.
Extiende el StorageService existente para soportar upload de logos.
"""

import os
import uuid
import logging
from typing import Optional, Dict
from fastapi import UploadFile, HTTPException, status

from app.services.storage import StorageService
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GymLogoService(StorageService):
    """
    Servicio extendido para manejar logos de gimnasios.
    Solo acepta imágenes (sin videos) y no genera thumbnails.
    """

    def __init__(self):
        super().__init__()
        # Bucket dedicado para logos de gimnasios
        self.gym_logo_bucket = settings.GYM_LOGO_BUCKET
        self.max_logo_size = 5 * 1024 * 1024  # 5MB
        # Tipos MIME permitidos para logos
        self.allowed_mime_types = {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp"
        }

    async def upload_gym_logo(
        self,
        gym_id: int,
        file: UploadFile
    ) -> str:
        """
        Sube el logo de un gimnasio.

        Args:
            gym_id: ID del gimnasio
            file: Archivo de imagen del logo

        Returns:
            str: URL pública del logo subido

        Raises:
            HTTPException: Si el servicio no está disponible, el archivo no es válido,
                          o excede el tamaño máximo permitido.
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
            if not self._is_valid_logo_image(file.content_type):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo debe ser una imagen válida (jpg, jpeg, png, webp)"
                )

            # Leer contenido del archivo
            contents = await file.read()

            # Validar tamaño
            if len(contents) > self.max_logo_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo excede el tamaño máximo permitido ({self.max_logo_size // (1024*1024)}MB)"
                )

            # Generar nombre único para el archivo
            file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            # Estructura: gym_{gym_id}/logo_{uuid}.ext
            folder_path = f"gym_{gym_id}"
            filename = f"{folder_path}/logo_{uuid.uuid4().hex}{file_ext}"

            logger.info(f"Subiendo logo de gimnasio {gym_id}: {filename}")

            # Subir archivo
            async def upload_operation():
                result = self.supabase.storage.from_(self.gym_logo_bucket).upload(
                    path=filename,
                    file=contents,
                    file_options={"content-type": file.content_type}
                )
                logger.info(f"Logo subido exitosamente: {result}")
                return result

            await self._execute_with_retry_async(
                f"subida de logo {filename}",
                upload_operation
            )

            # Generar URL pública
            logo_url = self._execute_with_retry_sync(
                "generación de URL pública",
                lambda: self.supabase.storage.from_(self.gym_logo_bucket).get_public_url(filename)
            )

            logger.info(f"Logo del gimnasio {gym_id} subido correctamente: {logo_url}")
            return logo_url

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al procesar logo del gimnasio {gym_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar el logo: {str(e)}"
            )

    async def delete_gym_logo(self, logo_url: str) -> bool:
        """
        Elimina un logo de gimnasio del almacenamiento.

        Args:
            logo_url: URL del logo a eliminar

        Returns:
            bool: True si se eliminó exitosamente, False en caso contrario
        """
        if not self.supabase:
            logger.warning("Cliente Supabase no inicializado, no se puede eliminar logo")
            return False

        try:
            # Extraer el path del archivo desde la URL
            # Formato: https://{host}/storage/v1/object/public/{bucket}/{path}
            path = self._extract_path_from_url(logo_url, self.gym_logo_bucket)

            if not path:
                logger.warning(f"No se pudo extraer el path de la URL: {logo_url}")
                return False

            logger.info(f"Eliminando logo: {path}")

            # Eliminar archivo
            def delete_operation():
                result = self.supabase.storage.from_(self.gym_logo_bucket).remove([path])
                logger.info(f"Logo eliminado: {result}")
                return result

            self._execute_with_retry_sync(
                f"eliminación de logo {path}",
                delete_operation
            )

            return True

        except Exception as e:
            logger.error(f"Error al eliminar logo {logo_url}: {str(e)}")
            return False

    def _is_valid_logo_image(self, content_type: Optional[str]) -> bool:
        """
        Valida que el tipo de contenido sea una imagen válida para logos.

        Args:
            content_type: Tipo MIME del archivo

        Returns:
            bool: True si es un tipo de imagen válido, False en caso contrario
        """
        if not content_type:
            return False

        return content_type.lower() in self.allowed_mime_types

    def _extract_path_from_url(self, url: str, bucket: str) -> Optional[str]:
        """
        Extrae el path del archivo desde una URL de Supabase Storage.

        Args:
            url: URL completa del archivo
            bucket: Nombre del bucket

        Returns:
            str: Path del archivo o None si no se pudo extraer
        """
        try:
            # Formato: https://{host}/storage/v1/object/public/{bucket}/{path}
            bucket_prefix = f"/storage/v1/object/public/{bucket}/"

            if bucket_prefix in url:
                # Extraer todo lo que viene después del bucket
                path = url.split(bucket_prefix)[1]
                return path
            else:
                logger.warning(f"URL no contiene el prefijo esperado del bucket: {url}")
                return None
        except Exception as e:
            logger.error(f"Error extrayendo path de URL {url}: {str(e)}")
            return None


# Instancia global del servicio
gym_logo_service = GymLogoService()
