"""
AsyncStorageService - Servicio async para almacenamiento de archivos en Supabase.

Este módulo proporciona funcionalidades async para manejar archivos en Supabase Storage
con reintentos automáticos y manejo robusto de errores.

Migrado en FASE 3 de la conversión sync → async.
"""

import os
import uuid
import logging
import re
import asyncio
from typing import Optional, Any, Dict, Callable, Union, Awaitable
from fastapi import UploadFile, HTTPException, status
from supabase import create_client, Client

from app.core.config import get_settings

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos

# Logger
logger = logging.getLogger("async_storage_service")


class AsyncStorageService:
    """
    Servicio async para manejar el almacenamiento de archivos en Supabase Storage.

    Todos los métodos son async y utilizan reintentos automáticos.

    Características:
    - Upload/delete de imágenes de perfil
    - Generación de URLs públicas
    - Reintentos automáticos con backoff progresivo
    - Sanitización de nombres de archivos
    - Validación de tipos de contenido

    Métodos principales:
    - upload_profile_image() - Sube imagen de perfil
    - delete_profile_image() - Elimina imagen de perfil
    - generate_public_url() - Genera URL pública
    """

    def __init__(self):
        """
        Inicializa el cliente de Supabase si las credenciales están disponibles.

        Raises:
            Warning: Si las credenciales no están configuradas
        """
        settings = get_settings()
        self.api_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_ANON_KEY
        self.profile_image_bucket = settings.PROFILE_IMAGE_BUCKET
        self.supabase: Optional[Client] = None

        # Inicializar el cliente de Supabase solo si tenemos las credenciales
        if self.api_url and self.api_key:
            try:
                self.supabase = create_client(self.api_url, self.api_key)
                logger.info("Cliente Supabase async inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar el cliente Supabase: {str(e)}")
                self.supabase = None
        else:
            logger.warning("No se proporcionaron credenciales de Supabase. El servicio de almacenamiento no funcionará.")

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza un nombre de archivo para asegurar que sea válido en Supabase Storage.

        Args:
            filename: Nombre de archivo original

        Returns:
            Nombre de archivo sanitizado

        Note:
            Reemplaza caracteres no válidos: |, /, \\, ?, %, *, :, ", <, >, espacio
        """
        # Reemplazar caracteres no válidos con guiones bajos
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
        # Remover cualquier otro carácter no alfanumérico excepto - y _
        sanitized = re.sub(r'[^\w\-_.]', '_', sanitized)
        return sanitized

    async def _execute_with_retry_async(
        self,
        operation_name: str,
        operation_func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """
        Ejecuta una función asíncrona con reintentos en caso de error.

        Args:
            operation_name: Nombre de la operación para el registro
            operation_func: Función asíncrona a ejecutar
            *args, **kwargs: Argumentos para la función

        Returns:
            El resultado de la función

        Raises:
            HTTPException: Si todos los reintentos fallan

        Note:
            Backoff progresivo: intento 1 = 2s, intento 2 = 4s, intento 3 = 6s
        """
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Intentando {operation_name} (intento {attempt}/{MAX_RETRIES})")
                return await operation_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                logger.warning(f"Error en {operation_name} (intento {attempt}/{MAX_RETRIES}): {error_type} - {str(e)}")

                # Si es el último intento, no esperar
                if attempt < MAX_RETRIES:
                    wait_time = RETRY_DELAY * attempt  # Espera progresiva
                    logger.info(f"Esperando {wait_time}s antes del siguiente intento...")
                    await asyncio.sleep(wait_time)

        # Si llegamos aquí, todos los reintentos fallaron
        logger.error(f"Todos los intentos de {operation_name} fallaron. Último error: {str(last_error)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error de comunicación con el servicio de almacenamiento después de {MAX_RETRIES} intentos: {str(last_error)}"
        )

    def _execute_with_retry_sync(
        self,
        operation_name: str,
        operation_func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Ejecuta una función síncrona con reintentos en caso de error.

        Args:
            operation_name: Nombre de la operación para el registro
            operation_func: Función síncrona a ejecutar
            *args, **kwargs: Argumentos para la función

        Returns:
            El resultado de la función

        Raises:
            HTTPException: Si todos los reintentos fallan

        Note:
            Para operaciones sync del SDK de Supabase (e.g. get_public_url).
            Usa time.sleep en lugar de asyncio.sleep.
        """
        import time
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Intentando {operation_name} (intento {attempt}/{MAX_RETRIES})")
                return operation_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                logger.warning(f"Error en {operation_name} (intento {attempt}/{MAX_RETRIES}): {error_type} - {str(e)}")

                # Si es el último intento, no esperar
                if attempt < MAX_RETRIES:
                    wait_time = RETRY_DELAY * attempt  # Espera progresiva
                    logger.info(f"Esperando {wait_time}s antes del siguiente intento...")
                    time.sleep(wait_time)

        # Si llegamos aquí, todos los reintentos fallaron
        logger.error(f"Todos los intentos de {operation_name} fallaron. Último error: {str(last_error)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error de comunicación con el servicio de almacenamiento después de {MAX_RETRIES} intentos: {str(last_error)}"
        )

    async def upload_profile_image(self, user_id: str, file: UploadFile) -> str:
        """
        Sube una imagen de perfil para un usuario específico.

        Args:
            user_id: ID del usuario
            file: Archivo de imagen a subir

        Returns:
            URL pública del archivo subido

        Raises:
            HTTPException: Si ocurre un error durante la subida o comunicación con Supabase

        Note:
            Genera nombre único: {user_id_sanitized}_{uuid}.{ext}
            Tipos válidos: jpg, png, webp
        """
        # Verificar que Supabase esté configurado
        if not self.supabase:
            logger.error("Cliente Supabase no inicializado. No se puede subir la imagen.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de almacenamiento no disponible"
            )

        try:
            # Validar el tipo de archivo
            if not self._is_valid_image(file.content_type):
                logger.warning(f"Tipo de archivo no válido: {file.content_type}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo debe ser una imagen (jpg, png, webp)"
                )

            # Sanitizar el ID de usuario y generar un nombre único para el archivo
            sanitized_user_id = self._sanitize_filename(user_id)
            file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            filename = f"{sanitized_user_id}_{uuid.uuid4().hex}{file_ext}"

            logger.info(f"ID de usuario original: {user_id}, sanitizado: {sanitized_user_id}")
            logger.info(f"Nombre de archivo generado: {filename}")

            # Leer el contenido del archivo
            contents = await file.read()

            try:
                logger.info(f"Subiendo imagen {filename} a bucket {self.profile_image_bucket}")

                # Función anónima asincrónica para la subida
                async def upload_operation():
                    result = self.supabase.storage.from_(self.profile_image_bucket).upload(
                        path=filename,
                        file=contents,
                        file_options={"content-type": file.content_type}
                    )
                    logger.info(f"Imagen subida exitosamente: {result}")
                    return result

                # Ejecutar la subida con reintentos (método asíncrono)
                await self._execute_with_retry_async(f"subida de imagen {filename}", upload_operation)

                # Obtener la URL pública (método síncrono, no necesita await)
                def get_public_url():
                    url = self.supabase.storage.from_(self.profile_image_bucket).get_public_url(filename)
                    logger.info(f"URL pública generada: {url}")
                    return url

                # Usar la versión síncrona para get_public_url ya que no es una función async
                public_url = self._execute_with_retry_sync("generación de URL pública", get_public_url)
                return public_url

            except HTTPException:
                # Re-lanzar excepciones HTTP generadas por _execute_with_retry
                raise
            except Exception as e:
                logger.error(f"Error inesperado: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error al procesar la imagen: {str(e)}"
                )

        except HTTPException:
            # Re-lanzar excepciones HTTP
            raise
        except Exception as e:
            logger.error(f"Error al procesar la imagen: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar la imagen: {str(e)}"
            )

    def _is_valid_image(self, content_type: str) -> bool:
        """
        Verifica si el tipo de contenido es una imagen válida.

        Args:
            content_type: Tipo MIME del archivo

        Returns:
            True si es imagen válida (jpg, png, webp)
        """
        valid_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
        return content_type in valid_types

    async def delete_profile_image(self, image_url: str) -> bool:
        """
        Elimina una imagen de perfil de Supabase Storage.

        Args:
            image_url: URL de la imagen a eliminar

        Returns:
            True si la eliminación fue exitosa, False en caso contrario

        Note:
            No lanza excepciones, solo retorna False en caso de error.
            Valida que la URL pertenezca al bucket correcto.
        """
        # Verificar si el cliente Supabase está inicializado
        if not self.supabase:
            logger.error("Intento de eliminar imagen sin cliente Supabase configurado.")
            return False

        try:
            # Asegurarse que api_url no sea None antes de usar startswith
            if not self.api_url or not image_url or not image_url.startswith(self.api_url):
                logger.warning(f"URL no válida para eliminar ({image_url}) o api_url no configurado ({self.api_url})")
                return False

            # Extraer el nombre del archivo de la URL
            try:
                # Remover parámetros de consulta si existen
                clean_url = image_url.split('?')[0]

                # La URL será algo como: https://<supabase_url>/storage/v1/object/public/<bucket_name>/filename
                bucket_path_prefix = f'/storage/v1/object/public/{self.profile_image_bucket}/'
                if bucket_path_prefix in clean_url:
                    # Extraer el nombre del archivo correctamente
                    filename = clean_url.split(bucket_path_prefix)[-1]
                    if not filename:
                        logger.error(f"No se pudo extraer el nombre de archivo de la URL: {clean_url}")
                        return False

                    logger.info(f"Eliminando archivo {filename} del bucket {self.profile_image_bucket}")

                    try:
                        # Función para eliminar con reintentos
                        async def remove_operation():
                            result = self.supabase.storage.from_(self.profile_image_bucket).remove([filename])
                            logger.info(f"Archivo eliminado correctamente: {result}")
                            return True

                        # Ejecutar la eliminación con reintentos (método asíncrono)
                        success = await self._execute_with_retry_async(f"eliminación de archivo {filename}", remove_operation)
                        return success
                    except HTTPException:
                        # Capturar HTTPException de _execute_with_retry pero devolver False
                        logger.error("Falló la eliminación después de todos los reintentos")
                        return False
                    except Exception as remove_error:
                        logger.error(f"Error al eliminar archivo de Supabase: {str(remove_error)}")
                        return False
                else:
                    logger.warning(f"URL ({clean_url}) no corresponde al bucket de imágenes de perfil esperado ({bucket_path_prefix})")
                    return False

            except Exception as e:
                logger.error(f"Error al extraer nombre de archivo de URL: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"Error general al eliminar imagen: {str(e)}")
            return False

    def generate_public_url(self, path: str) -> str:
        """
        Genera una URL pública para acceder a un archivo.

        Args:
            path: Ruta del archivo en el bucket

        Returns:
            URL pública del archivo, o string vacío si no está configurado

        Note:
            Formato: {api_url}/storage/v1/object/public/{bucket}/{path}
        """
        if not self.api_url or not self.api_key:
            return ""

        # Formato de URL pública de Supabase Storage
        return f"{self.api_url}/storage/v1/object/public/{self.profile_image_bucket}/{path}"


# Instancia singleton del servicio async
_async_storage_service_instance = None


def get_async_storage_service() -> AsyncStorageService:
    """
    Obtiene la instancia singleton del AsyncStorageService.

    Returns:
        Instancia única de AsyncStorageService
    """
    global _async_storage_service_instance
    if _async_storage_service_instance is None:
        _async_storage_service_instance = AsyncStorageService()
    return _async_storage_service_instance
