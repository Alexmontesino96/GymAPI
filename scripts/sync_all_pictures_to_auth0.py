"""
Script para sincronizar todas las fotos de perfil de Supabase hacia Auth0.

Este script actualiza el campo 'picture' en Auth0 para todos los usuarios
que tienen una foto almacenada en Supabase Storage.

IMPORTANTE: Solo sincroniza fotos que sean de Supabase Storage,
no sobrescribe fotos de proveedores sociales (Google, Facebook, etc.)
a menos que ya fueron reemplazadas por fotos de Supabase en la BD.

Uso:
    python scripts/sync_all_pictures_to_auth0.py [--dry-run] [--limit N]

Argumentos:
    --dry-run: Solo muestra qué se sincronizaría sin hacer cambios
    --limit N: Limita a los primeros N usuarios (útil para testing)
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from app.db.session import SessionLocal
from app.core.auth0_mgmt import auth0_mgmt_service
from app.core.config import get_settings
import logging

# Importar todos los modelos para que SQLAlchemy resuelva las relaciones
from app.db.base import Base  # Esto importa todos los modelos
from app.models.user import User

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PictureSyncService:
    """
    Servicio para sincronizar fotos de perfil hacia Auth0.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.settings = get_settings()
        self.stats = {
            'total_users': 0,
            'with_picture': 0,
            'supabase_pictures': 0,
            'synced_success': 0,
            'synced_failed': 0,
            'skipped': 0
        }

    def is_supabase_url(self, picture_url: str) -> bool:
        """
        Verifica si una URL es de Supabase Storage.

        Args:
            picture_url: URL de la imagen

        Returns:
            bool: True si es de Supabase, False si es de otro proveedor
        """
        if not picture_url:
            return False

        # Patrones comunes de Supabase Storage
        supabase_patterns = [
            'supabase.co/storage',
            'supabase.in/storage',
            '.supabase.',
        ]

        return any(pattern in picture_url.lower() for pattern in supabase_patterns)

    async def sync_user_picture(self, user: User) -> bool:
        """
        Sincroniza la foto de un usuario hacia Auth0.

        Args:
            user: Modelo de usuario

        Returns:
            bool: True si se sincronizó exitosamente, False si falló
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Se sincronizaría: {user.email} ({user.auth0_id}) → {user.picture}")
                return True

            # Sincronizar con Auth0
            auth0_mgmt_service.update_user_picture(user.auth0_id, user.picture)
            logger.info(f"✓ Sincronizado: {user.email} ({user.auth0_id})")
            return True

        except Exception as e:
            logger.error(f"✗ Error al sincronizar {user.email} ({user.auth0_id}): {str(e)}")
            return False

    async def sync_all_pictures(self, limit: int = None):
        """
        Sincroniza todas las fotos de usuarios hacia Auth0.

        Args:
            limit: Limitar a los primeros N usuarios (opcional)
        """
        db = SessionLocal()

        try:
            logger.info("=" * 80)
            logger.info("SINCRONIZACIÓN DE FOTOS DE PERFIL: SUPABASE → AUTH0")
            logger.info("=" * 80)

            if self.dry_run:
                logger.warning("⚠️  MODO DRY-RUN ACTIVADO - No se harán cambios reales")

            logger.info("")

            # 1. Obtener todos los usuarios con foto
            query = select(User).where(
                User.picture.isnot(None),
                User.auth0_id.isnot(None)
            )

            if limit:
                query = query.limit(limit)
                logger.info(f"🔍 Limitando a los primeros {limit} usuarios")

            result = db.execute(query)
            users = result.scalars().all()

            self.stats['total_users'] = len(users)
            logger.info(f"📊 Usuarios encontrados con foto: {self.stats['total_users']}")
            logger.info("")

            # 2. Filtrar solo usuarios con fotos de Supabase
            supabase_users = []
            for user in users:
                self.stats['with_picture'] += 1

                if self.is_supabase_url(user.picture):
                    supabase_users.append(user)
                    self.stats['supabase_pictures'] += 1
                else:
                    self.stats['skipped'] += 1
                    logger.debug(f"⊘ Omitido (no es Supabase): {user.email} → {user.picture}")

            logger.info(f"🎯 Usuarios con fotos de Supabase: {self.stats['supabase_pictures']}")
            logger.info(f"⊘  Usuarios omitidos (fotos de proveedores sociales): {self.stats['skipped']}")
            logger.info("")

            if not supabase_users:
                logger.warning("No hay usuarios con fotos de Supabase para sincronizar.")
                return

            # 3. Sincronizar cada usuario
            logger.info("🚀 Iniciando sincronización...")
            logger.info("")

            for idx, user in enumerate(supabase_users, 1):
                logger.info(f"[{idx}/{len(supabase_users)}] Procesando: {user.email}")

                success = await self.sync_user_picture(user)

                if success:
                    self.stats['synced_success'] += 1
                else:
                    self.stats['synced_failed'] += 1

                # Pequeña pausa para no saturar Auth0 API
                if not self.dry_run and idx < len(supabase_users):
                    await asyncio.sleep(0.5)  # 500ms entre cada request

            # 4. Mostrar resumen
            logger.info("")
            logger.info("=" * 80)
            logger.info("RESUMEN DE SINCRONIZACIÓN")
            logger.info("=" * 80)
            logger.info(f"Total de usuarios analizados:        {self.stats['total_users']}")
            logger.info(f"Usuarios con foto:                   {self.stats['with_picture']}")
            logger.info(f"Fotos de Supabase:                   {self.stats['supabase_pictures']}")
            logger.info(f"Fotos omitidas (proveedores social): {self.stats['skipped']}")
            logger.info(f"")
            logger.info(f"✓ Sincronizadas exitosamente:        {self.stats['synced_success']}")
            logger.info(f"✗ Fallos al sincronizar:             {self.stats['synced_failed']}")
            logger.info("=" * 80)

            if self.dry_run:
                logger.warning("")
                logger.warning("⚠️  MODO DRY-RUN: No se realizaron cambios reales")
                logger.warning("    Ejecuta sin --dry-run para sincronizar")

        except Exception as e:
            logger.error(f"Error crítico durante la sincronización: {str(e)}", exc_info=True)
            raise

        finally:
            db.close()


async def main():
    """
    Punto de entrada del script.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Sincroniza fotos de perfil de Supabase hacia Auth0"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo dry-run: muestra qué se haría sin hacer cambios"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limitar a los primeros N usuarios (útil para testing)"
    )

    args = parser.parse_args()

    # Verificar que las variables de entorno estén configuradas
    settings = get_settings()
    if not all([settings.AUTH0_MGMT_CLIENT_ID, settings.AUTH0_MGMT_CLIENT_SECRET]):
        logger.error("❌ Variables de entorno AUTH0_MGMT_* no configuradas")
        logger.error("   Verifica que .env tenga:")
        logger.error("   - AUTH0_MGMT_CLIENT_ID")
        logger.error("   - AUTH0_MGMT_CLIENT_SECRET")
        logger.error("   - AUTH0_MGMT_AUDIENCE")
        sys.exit(1)

    # Ejecutar sincronización
    sync_service = PictureSyncService(dry_run=args.dry_run)
    await sync_service.sync_all_pictures(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
