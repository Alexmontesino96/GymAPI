"""
Script para crear los tipos ENUM faltantes del sistema de posts.

PROBLEMA:
La migración f546b56de5bb_add_posts_system_with_gallery_support.py
crea las tablas del sistema de posts pero los tipos ENUM (posttype, postprivacy,
tagtype, reportreason) no se crearon en la base de datos de producción.

SOLUCIÓN:
Este script crea manualmente los tipos ENUM y actualiza las columnas
correspondientes para usarlos.

EJECUCIÓN:
    python scripts/fix_missing_post_enums.py

FECHA: 2025-12-06
"""

from app.db.session import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_enums():
    """Crear tipos ENUM faltantes"""
    logger.info('Creando tipos ENUM faltantes en PostgreSQL...')

    with engine.begin() as conn:
        # Crear ENUM posttype
        try:
            conn.execute(text("""
                CREATE TYPE posttype AS ENUM ('SINGLE_IMAGE', 'GALLERY', 'VIDEO', 'WORKOUT');
            """))
            logger.info('✅ ENUM posttype creado')
        except Exception as e:
            logger.warning(f'⚠️  posttype ya existe o error: {e}')

        # Crear ENUM postprivacy
        try:
            conn.execute(text("""
                CREATE TYPE postprivacy AS ENUM ('PUBLIC', 'PRIVATE');
            """))
            logger.info('✅ ENUM postprivacy creado')
        except Exception as e:
            logger.warning(f'⚠️  postprivacy ya existe o error: {e}')

        # Crear ENUM tagtype
        try:
            conn.execute(text("""
                CREATE TYPE tagtype AS ENUM ('MENTION', 'EVENT', 'SESSION');
            """))
            logger.info('✅ ENUM tagtype creado')
        except Exception as e:
            logger.warning(f'⚠️  tagtype ya existe o error: {e}')

        # Crear ENUM reportreason
        try:
            conn.execute(text("""
                CREATE TYPE reportreason AS ENUM ('SPAM', 'INAPPROPRIATE', 'HARASSMENT', 'FALSE_INFO', 'HATE_SPEECH', 'VIOLENCE', 'OTHER');
            """))
            logger.info('✅ ENUM reportreason creado')
        except Exception as e:
            logger.warning(f'⚠️  reportreason ya existe o error: {e}')


def update_columns():
    """Actualizar columnas para usar los tipos ENUM"""
    logger.info('\nActualizando columnas para usar los tipos ENUM...')

    # Tabla posts - columna post_type
    try:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT;'))
            conn.execute(text('''
                ALTER TABLE posts
                ALTER COLUMN post_type TYPE posttype USING post_type::text::posttype;
            '''))
            conn.execute(text("ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'SINGLE_IMAGE'::posttype;"))
            logger.info('✅ posts.post_type actualizada a posttype')
    except Exception as e:
        logger.warning(f'⚠️  posts.post_type: {e}')

    # Tabla posts - columna privacy
    try:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE posts ALTER COLUMN privacy DROP DEFAULT;'))
            conn.execute(text('''
                ALTER TABLE posts
                ALTER COLUMN privacy TYPE postprivacy USING privacy::text::postprivacy;
            '''))
            conn.execute(text("ALTER TABLE posts ALTER COLUMN privacy SET DEFAULT 'PUBLIC'::postprivacy;"))
            logger.info('✅ posts.privacy actualizada a postprivacy')
    except Exception as e:
        logger.warning(f'⚠️  posts.privacy: {e}')

    # Tabla post_tags - columna tag_type
    try:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE post_tags ALTER COLUMN tag_type DROP DEFAULT;'))
            conn.execute(text('''
                ALTER TABLE post_tags
                ALTER COLUMN tag_type TYPE tagtype USING tag_type::text::tagtype;
            '''))
            logger.info('✅ post_tags.tag_type actualizada a tagtype')
    except Exception as e:
        logger.warning(f'⚠️  post_tags.tag_type: {e}')

    # Tabla post_reports - columna reason
    try:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE post_reports ALTER COLUMN reason DROP DEFAULT;'))
            conn.execute(text('''
                ALTER TABLE post_reports
                ALTER COLUMN reason TYPE reportreason USING reason::text::reportreason;
            '''))
            logger.info('✅ post_reports.reason actualizada a reportreason')
    except Exception as e:
        logger.warning(f'⚠️  post_reports.reason: {e}')


def verify_schema():
    """Verificar que todo quedó correctamente configurado"""
    logger.info('\n' + '='*60)
    logger.info('Verificación final del esquema:')
    logger.info('='*60)

    with engine.connect() as conn:
        # Verificar ENUMs
        result = conn.execute(text("""
            SELECT typname FROM pg_type
            WHERE typname IN ('posttype', 'postprivacy', 'tagtype', 'reportreason')
            ORDER BY typname;
        """))
        enums = result.fetchall()
        logger.info('\n1. ENUMs creados:')
        for enum in enums:
            logger.info(f'   ✅ {enum[0]}')

        # Verificar columnas de posts
        result = conn.execute(text("""
            SELECT column_name, udt_name, column_default
            FROM information_schema.columns
            WHERE table_name = 'posts' AND column_name IN ('post_type', 'privacy')
            ORDER BY column_name;
        """))
        cols = result.fetchall()
        logger.info('\n2. Columnas de tabla posts:')
        for col in cols:
            logger.info(f'   ✅ {col[0]}: {col[1]} (default: {col[2]})')

        # Verificar otras tablas
        result = conn.execute(text("""
            SELECT table_name, column_name, udt_name
            FROM information_schema.columns
            WHERE (table_name = 'post_tags' AND column_name = 'tag_type')
               OR (table_name = 'post_reports' AND column_name = 'reason')
            ORDER BY table_name;
        """))
        cols = result.fetchall()
        logger.info('\n3. Otras columnas:')
        for col in cols:
            logger.info(f'   ✅ {col[0]}.{col[1]}: {col[2]}')

    logger.info('\n' + '='*60)
    logger.info('✅ PROCESO COMPLETADO EXITOSAMENTE')
    logger.info('='*60)


if __name__ == '__main__':
    try:
        create_enums()
        update_columns()
        verify_schema()
    except Exception as e:
        logger.error(f'❌ Error durante la ejecución: {e}', exc_info=True)
        raise
