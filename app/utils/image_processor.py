"""
Procesador de imágenes con optimización para posts.
Reduce tamaño de storage mediante compresión, conversión a WebP y eliminación de EXIF.

NOTA: Optimizado para bajo consumo de memoria (< 50MB para imágenes típicas).
"""
import io
import logging
from PIL import Image, ImageOps
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Optimiza imágenes antes de subirlas al bucket."""

    # Configuración por defecto
    MAX_DIMENSION = 2048      # Límite máximo de ancho/alto
    WEBP_QUALITY = 80         # Calidad WebP (0-100)
    JPEG_QUALITY = 85         # Calidad JPEG fallback
    MIN_SAVINGS_RATIO = 0.9   # Solo convertir a WebP si ahorra >10%

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

        Procesa la imagen en UNA SOLA PASADA para minimizar uso de memoria.

        Args:
            content: Bytes de la imagen original
            max_dimension: Dimensión máxima (default: 2048)
            webp_quality: Calidad WebP (default: 80)
            min_savings_ratio: Ratio mínimo para convertir a WebP (default: 0.9)

        Returns:
            {
                "content": bytes,
                "format": str,
                "content_type": str,
                "original_size": int,
                "final_size": int,
                "dimensions": (w, h),
                "compression_ratio": float,
                "was_resized": bool,
                "was_converted": bool
            }

        Raises:
            ValueError: Si la imagen es inválida
        """
        max_dim = max_dimension or cls.MAX_DIMENSION
        quality = webp_quality or cls.WEBP_QUALITY
        savings_ratio = min_savings_ratio or cls.MIN_SAVINGS_RATIO

        original_size = len(content)

        # 1. Abrir imagen UNA SOLA VEZ
        try:
            img = Image.open(io.BytesIO(content))
            original_format = img.format or 'JPEG'
        except Exception as e:
            raise ValueError(f"Imagen inválida: {e}")

        # 2. Aplicar rotación EXIF de forma eficiente (sin copiar píxeles)
        # ImageOps.exif_transpose es la forma correcta y eficiente
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass  # Si falla, continuar con la imagen original

        # 3. Redimensionar si es necesario
        was_resized = False
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            was_resized = True
            logger.debug(f"Imagen redimensionada a: {img.size}")

        dimensions = img.size

        # 4. Preparar para guardar (convertir modo si es necesario)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Mantener para WebP que soporta transparencia
            if img.mode == 'P':
                img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # 5. Guardar como WebP y comparar tamaño
        webp_buffer = io.BytesIO()

        # Para WebP con transparencia
        save_img = img
        if img.mode == 'RGBA':
            img.save(webp_buffer, format='WEBP', quality=quality, method=4)
        else:
            # Convertir a RGB para WebP sin transparencia
            if img.mode != 'RGB':
                save_img = img.convert('RGB')
            save_img.save(webp_buffer, format='WEBP', quality=quality, method=4)

        webp_content = webp_buffer.getvalue()
        webp_buffer.close()

        # 6. Decidir formato final
        # Comparar con tamaño original o con JPEG comprimido
        if len(webp_content) < original_size * savings_ratio:
            # WebP es significativamente más pequeño
            final_content = webp_content
            final_format = 'webp'
            was_converted = True
            logger.debug(f"Usando WebP: {len(webp_content)/1024:.0f}KB")
        else:
            # Guardar en formato original comprimido
            orig_buffer = io.BytesIO()

            if original_format.upper() in ('JPEG', 'JPG'):
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(orig_buffer, format='JPEG', quality=cls.JPEG_QUALITY, optimize=True)
                final_format = 'jpeg'
            elif original_format.upper() == 'PNG':
                img.save(orig_buffer, format='PNG', optimize=True)
                final_format = 'png'
            else:
                # Fallback a JPEG
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(orig_buffer, format='JPEG', quality=cls.JPEG_QUALITY, optimize=True)
                final_format = 'jpeg'

            final_content = orig_buffer.getvalue()
            orig_buffer.close()
            was_converted = False

            # Si WebP es más pequeño que el formato original comprimido, usar WebP
            if len(webp_content) < len(final_content):
                final_content = webp_content
                final_format = 'webp'
                was_converted = True
                logger.debug(f"WebP más pequeño que {original_format}: {len(webp_content)/1024:.0f}KB")

        # Liberar memoria
        img.close()

        final_size = len(final_content)
        compression_ratio = final_size / original_size if original_size > 0 else 1.0

        # Determinar content type
        content_type_map = {
            'webp': 'image/webp',
            'jpeg': 'image/jpeg',
            'jpg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif'
        }
        content_type = content_type_map.get(final_format, f'image/{final_format}')

        logger.info(
            f"Imagen optimizada: {original_size/1024:.0f}KB -> {final_size/1024:.0f}KB "
            f"({compression_ratio:.0%}), formato: {final_format}, dims: {dimensions}"
        )

        return {
            "content": final_content,
            "format": final_format,
            "content_type": content_type,
            "original_size": original_size,
            "final_size": final_size,
            "dimensions": dimensions,
            "compression_ratio": compression_ratio,
            "was_resized": was_resized,
            "was_converted": was_converted
        }
