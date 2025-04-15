import os
import uuid
import logging
import re
import time
from typing import Optional, Any, Dict, Callable, Union, Awaitable
from fastapi import UploadFile, HTTPException, status
from supabase import create_client, Client
# Eliminar dotenv si ya no se usa directamente aquí
# from dotenv import load_dotenv

# Importar settings
from app.core.config import settings 

# load_dotenv() # Ya no es necesario si config.py lo maneja

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos

# Logger
logger = logging.getLogger("storage_service")

class StorageService:
    """
    Servicio para manejar el almacenamiento de archivos en Supabase Storage
    usando el SDK oficial
    """
    
    # Usar settings para los valores por defecto
    def __init__(self, api_url: str = settings.SUPABASE_URL, anon_key: str = settings.SUPABASE_ANON_KEY):
        """
        Inicializa el cliente de Supabase
        
        Args:
            api_url: URL de la API de Supabase
            anon_key: Clave anónima de Supabase (no confundir con las credenciales S3)
        """
        self.api_url = api_url
        self.anon_key = anon_key
        
        # Inicializar cliente de Supabase
        try:
            logger.info(f"Inicializando cliente de Supabase para {api_url}")
            self.supabase: Client = create_client(api_url, anon_key)
            logger.info(f"Cliente de Supabase inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar cliente de Supabase: {str(e)}")
            raise

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza un nombre de archivo para asegurar que sea válido en Supabase Storage
        
        Args:
            filename: Nombre de archivo original
            
        Returns:
            Nombre de archivo sanitizado
        """
        # Reemplazar caracteres no válidos con guiones bajos
        # Esto incluye: |, /, \, ?, %, *, :, |, ", <, >, espacio, etc.
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
        # Remover cualquier otro carácter no alfanumérico excepto - y _
        sanitized = re.sub(r'[^\w\-_.]', '_', sanitized)
        return sanitized
        
    async def _execute_with_retry_async(self, operation_name: str, operation_func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Ejecuta una función asíncrona con reintentos en caso de error
        
        Args:
            operation_name: Nombre de la operación para el registro
            operation_func: Función asíncrona a ejecutar
            *args, **kwargs: Argumentos para la función
            
        Returns:
            El resultado de la función
            
        Raises:
            HTTPException: Si todos los reintentos fallan
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
                    time.sleep(wait_time)
        
        # Si llegamos aquí, todos los reintentos fallaron
        logger.error(f"Todos los intentos de {operation_name} fallaron. Último error: {str(last_error)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error de comunicación con el servicio de almacenamiento después de {MAX_RETRIES} intentos: {str(last_error)}"
        )
        
    def _execute_with_retry_sync(self, operation_name: str, operation_func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Ejecuta una función síncrona con reintentos en caso de error
        
        Args:
            operation_name: Nombre de la operación para el registro
            operation_func: Función síncrona a ejecutar
            *args, **kwargs: Argumentos para la función
            
        Returns:
            El resultado de la función
            
        Raises:
            HTTPException: Si todos los reintentos fallan
        """
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

    async def upload_profile_image(self, file: UploadFile, user_id: str) -> str:
        """
        Sube una imagen de perfil a Supabase Storage usando el SDK
        
        Args:
            file: Archivo a subir
            user_id: ID del usuario
            
        Returns:
            URL de la imagen subida
        """
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
                logger.info(f"Subiendo imagen {filename} a bucket {settings.PROFILE_IMAGE_BUCKET}")
                
                # Función anónima asincrónica para la subida
                async def upload_operation():
                    result = self.supabase.storage.from_(settings.PROFILE_IMAGE_BUCKET).upload(
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
                    url = self.supabase.storage.from_(settings.PROFILE_IMAGE_BUCKET).get_public_url(filename)
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
        Verifica si el tipo de contenido es una imagen válida
        """
        valid_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
        return content_type in valid_types
    
    async def delete_profile_image(self, image_url: str) -> bool:
        """
        Elimina una imagen de perfil de Supabase Storage
        
        Args:
            image_url: URL de la imagen a eliminar
            
        Returns:
            True si la eliminación fue exitosa, False en caso contrario
        """
        try:
            if not image_url or not image_url.startswith(self.api_url):
                logger.warning(f"URL no válida para eliminar: {image_url}")
                return False
            
            # Extraer el nombre del archivo de la URL
            try:
                # Remover parámetros de consulta si existen
                clean_url = image_url.split('?')[0]
                
                # La URL será algo como: https://ueijlkythlkqadxymzqd.supabase.co/storage/v1/object/public/userphotoprofile/filename
                if f'public/{settings.PROFILE_IMAGE_BUCKET}/' in clean_url:
                    parts = clean_url.split(f'public/{settings.PROFILE_IMAGE_BUCKET}/')
                    if len(parts) != 2:
                        logger.error(f"Formato de URL no reconocido: {clean_url}")
                        return False
                        
                    filename = parts[1]
                    logger.info(f"Eliminando archivo {filename} del bucket {settings.PROFILE_IMAGE_BUCKET}")
                    
                    try:
                        # Función para eliminar con reintentos
                        async def remove_operation():
                            result = self.supabase.storage.from_(settings.PROFILE_IMAGE_BUCKET).remove([filename])
                            logger.info(f"Archivo eliminado correctamente: {result}")
                            return True
                        
                        # Ejecutar la eliminación con reintentos (método asíncrono)
                        success = await self._execute_with_retry_async(f"eliminación de archivo {filename}", remove_operation)
                        return success
                    except HTTPException:
                        # Capturar HTTPException de _execute_with_retry pero devolver False
                        # ya que este método debe devolver un booleano
                        logger.error("Falló la eliminación después de todos los reintentos")
                        return False
                    except Exception as remove_error:
                        logger.error(f"Error al eliminar archivo de Supabase: {str(remove_error)}")
                        return False
                else:
                    logger.warning(f"URL no corresponde al bucket de imágenes de perfil: {clean_url}")
                    return False
                
            except Exception as e:
                logger.error(f"Error al extraer nombre de archivo de URL: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error al eliminar imagen: {str(e)}")
            return False


# Instancia del servicio para uso global
storage_service = StorageService() 