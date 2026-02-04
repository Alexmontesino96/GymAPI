"""
Procesador de imágenes con optimización para posts.
Reduce tamaño de storage mediante compresión, conversión a WebP y eliminación de EXIF.
"""
import io
import logging
from PIL import Image, ExifTags
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Optimiza imágenes antes de subirlas al bucket."""

    # Configuración por defecto
    MAX_DIMENSION = 2048      # Límite máximo de ancho/alto
    WEBP_QUALITY = 85         # Calidad WebP (0-100)
    JPEG_QUALITY = 85         # Calidad JPEG fallback
    MIN_SAVINGS_RATIO = 0.9   # Solo convertir a WebP si ahorra >10%

    @staticmethod
    def validate(content: bytes) -> Tuple[bool, Optional[str]]:
        """
        Valida que el contenido sea una imagen válida.

        Args:
            content: Bytes de la imagen

        Returns:
            Tuple[is_valid, error_message]
        """
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def strip_exif(content: bytes) -> Tuple[bytes, str, Tuple[int, int]]:
        """
        Elimina metadata EXIF preservando la orientación correcta.

        Args:
            content: Bytes de la imagen original

        Returns:
            Tuple[bytes_procesados, formato_original, (width, height)]
        """
        img = Image.open(io.BytesIO(content))
        original_format = img.format or 'JPEG'

        # Aplicar rotación EXIF antes de eliminar metadata
        try:
            exif = img._getexif()
            if exif:
                orientation_key = next(
                    (k for k, v in ExifTags.TAGS.items() if v == 'Orientation'),
                    None
                )
                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    rotations = {3: 180, 6: 270, 8: 90}
                    if orientation in rotations:
                        img = img.rotate(rotations[orientation], expand=True)
                        logger.debug(f"Aplicada rotación EXIF: {rotations[orientation]}°")
        except (AttributeError, KeyError, TypeError):
            pass

        # Crear imagen nueva sin EXIF copiando los datos de píxeles
        if img.mode in ('RGBA', 'LA', 'P'):
            # Preservar canal alpha si existe
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))
        else:
            # Para RGB/L, convertir y copiar
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))

        buffer = io.BytesIO()

        # Guardar en formato original
        save_kwargs = {}
        if original_format.upper() in ('JPEG', 'JPG'):
            save_kwargs['quality'] = 95  # Alta calidad para paso intermedio
            save_kwargs['optimize'] = True
            if clean_img.mode == 'RGBA':
                clean_img = clean_img.convert('RGB')
        elif original_format.upper() == 'PNG':
            save_kwargs['optimize'] = True

        clean_img.save(buffer, format=original_format, **save_kwargs)
        return buffer.getvalue(), original_format, clean_img.size

    @staticmethod
    def resize_if_needed(
        content: bytes,
        max_dim: int = 2048
    ) -> Tuple[bytes, Tuple[int, int], bool]:
        """
        Redimensiona la imagen si excede el límite máximo.

        Args:
            content: Bytes de la imagen
            max_dim: Dimensión máxima permitida

        Returns:
            Tuple[bytes_procesados, (width, height), fue_redimensionada]
        """
        img = Image.open(io.BytesIO(content))
        original_format = img.format or 'JPEG'
        original_size = img.size

        if max(img.size) <= max_dim:
            return content, original_size, False

        # Redimensionar manteniendo aspect ratio
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()

        save_kwargs = {'quality': 95, 'optimize': True}
        if original_format.upper() == 'PNG':
            save_kwargs = {'optimize': True}
        elif img.mode == 'RGBA' and original_format.upper() in ('JPEG', 'JPG'):
            img = img.convert('RGB')

        img.save(buffer, format=original_format, **save_kwargs)

        logger.debug(f"Imagen redimensionada: {original_size} -> {img.size}")
        return buffer.getvalue(), img.size, True

    @staticmethod
    def convert_to_webp(
        content: bytes,
        quality: int = 85,
        min_savings_ratio: float = 0.9
    ) -> Tuple[bytes, bool, str]:
        """
        Convierte a WebP si reduce el tamaño significativamente.

        Args:
            content: Bytes de la imagen
            quality: Calidad WebP (0-100)
            min_savings_ratio: Ratio mínimo de ahorro para convertir

        Returns:
            Tuple[bytes_procesados, fue_convertido, formato_final]
        """
        img = Image.open(io.BytesIO(content))
        original_format = img.format or 'JPEG'

        # Manejar transparencia
        if img.mode in ('RGBA', 'LA', 'P'):
            # WebP soporta transparencia
            if img.mode == 'P':
                img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        buffer = io.BytesIO()
        img.save(
            buffer,
            format='WEBP',
            quality=quality,
            method=4,  # Balance entre velocidad y compresión
            lossless=False
        )
        webp_content = buffer.getvalue()

        # Solo usar WebP si ahorra más del umbral configurado
        if len(webp_content) < len(content) * min_savings_ratio:
            savings_percent = (1 - len(webp_content) / len(content)) * 100
            logger.debug(f"Convertido a WebP: {savings_percent:.1f}% ahorro")
            return webp_content, True, 'webp'

        logger.debug("WebP no ofrece suficiente ahorro, manteniendo formato original")
        return content, False, original_format.lower()

    @classmethod
    def optimize(
        cls,
        content: bytes,
        max_dimension: int = None,
        webp_quality: int = None,
        min_savings_ratio: float = None
    ) -> Dict[str, Any]:
        """
        Pipeline completo de optimización de imagen.

        Args:
            content: Bytes de la imagen original
            max_dimension: Dimensión máxima (default: 2048)
            webp_quality: Calidad WebP (default: 85)
            min_savings_ratio: Ratio mínimo para convertir a WebP (default: 0.9)

        Returns:
            {
                "content": bytes,           # Imagen optimizada
                "format": str,              # "webp" o formato original
                "content_type": str,        # MIME type
                "original_size": int,       # Tamaño original en bytes
                "final_size": int,          # Tamaño final en bytes
                "dimensions": (w, h),       # Dimensiones finales
                "compression_ratio": float, # Ratio final/original
                "was_resized": bool,        # Si se redimensionó
                "was_converted": bool       # Si se convirtió a WebP
            }

        Raises:
            ValueError: Si la imagen es inválida
        """
        # Usar valores por defecto si no se especifican
        max_dim = max_dimension or cls.MAX_DIMENSION
        quality = webp_quality or cls.WEBP_QUALITY
        savings_ratio = min_savings_ratio or cls.MIN_SAVINGS_RATIO

        original_size = len(content)

        # 1. Validar imagen
        is_valid, error = cls.validate(content)
        if not is_valid:
            raise ValueError(f"Imagen inválida: {error}")

        # 2. Eliminar EXIF (preservando orientación)
        content, original_format, dimensions = cls.strip_exif(content)
        logger.debug(f"EXIF eliminado, formato: {original_format}, dims: {dimensions}")

        # 3. Redimensionar si es muy grande
        content, dimensions, was_resized = cls.resize_if_needed(content, max_dim)

        # 4. Convertir a WebP si es beneficioso
        content, was_converted, final_format = cls.convert_to_webp(
            content,
            quality,
            savings_ratio
        )

        # Determinar content type
        content_type_map = {
            'webp': 'image/webp',
            'jpeg': 'image/jpeg',
            'jpg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif'
        }
        content_type = content_type_map.get(final_format, f'image/{final_format}')

        final_size = len(content)
        compression_ratio = final_size / original_size if original_size > 0 else 1.0

        logger.info(
            f"Imagen optimizada: {original_size/1024:.0f}KB -> {final_size/1024:.0f}KB "
            f"({compression_ratio:.0%}), formato: {final_format}, dims: {dimensions}"
        )

        return {
            "content": content,
            "format": final_format,
            "content_type": content_type,
            "original_size": original_size,
            "final_size": final_size,
            "dimensions": dimensions,
            "compression_ratio": compression_ratio,
            "was_resized": was_resized,
            "was_converted": was_converted
        }
