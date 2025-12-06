# Fix: PostgreSQL ENUM Types Missing for Posts System

**Fecha:** 2025-12-06
**Problema:** `type "postprivacy" does not exist`
**Migración afectada:** `f546b56de5bb_add_posts_system_with_gallery_support.py`

## Descripción del Problema

Durante el deployment de la fase async (fase 2), se detectó un error crítico en el sistema de posts:

```
sqlalchemy.exc.ProgrammingError: type "postprivacy" does not exist
```

El error ocurría en `/api/v1/posts/feed/timeline` en `async_post_service.py:363`.

## Causa Raíz

La migración `f546b56de5bb_add_posts_system_with_gallery_support.py` debería haber creado los siguientes tipos ENUM en PostgreSQL:

- `posttype`: Tipos de posts (SINGLE_IMAGE, GALLERY, VIDEO, WORKOUT)
- `postprivacy`: Niveles de privacidad (PUBLIC, PRIVATE)
- `tagtype`: Tipos de tags (MENTION, EVENT, SESSION)
- `reportreason`: Razones de reporte (SPAM, INAPPROPRIATE, etc.)

Sin embargo, **NINGUNO de estos tipos ENUM fue creado** en la base de datos de producción, aunque las tablas SÍ fueron creadas.

### Verificación

```python
# ENUMs esperados según migración (línea 27, 31, 78, 157):
sa.Column('post_type', sa.Enum('SINGLE_IMAGE', 'GALLERY', 'VIDEO', 'WORKOUT', name='posttype'))
sa.Column('privacy', sa.Enum('PUBLIC', 'PRIVATE', name='postprivacy'))
sa.Column('tag_type', sa.Enum('MENTION', 'EVENT', 'SESSION', name='tagtype'))
sa.Column('reason', sa.Enum('SPAM', 'INAPPROPRIATE', ..., name='reportreason'))

# Estado real de la BD:
- posttype: ❌ NO EXISTE
- postprivacy: ❌ NO EXISTE
- tagtype: ❌ NO EXISTE
- reportreason: ❌ NO EXISTE
- Tabla posts: ✅ EXISTE (pero con columnas VARCHAR en lugar de ENUM)
```

## Solución Implementada

Se creó el script `scripts/fix_missing_post_enums.py` que:

1. **Crea los tipos ENUM en PostgreSQL:**
   ```sql
   CREATE TYPE posttype AS ENUM ('SINGLE_IMAGE', 'GALLERY', 'VIDEO', 'WORKOUT');
   CREATE TYPE postprivacy AS ENUM ('PUBLIC', 'PRIVATE');
   CREATE TYPE tagtype AS ENUM ('MENTION', 'EVENT', 'SESSION');
   CREATE TYPE reportreason AS ENUM ('SPAM', 'INAPPROPRIATE', 'HARASSMENT', 'FALSE_INFO', 'HATE_SPEECH', 'VIOLENCE', 'OTHER');
   ```

2. **Actualiza las columnas para usar los ENUMs:**
   ```sql
   -- posts.post_type: VARCHAR → posttype
   ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT;
   ALTER TABLE posts ALTER COLUMN post_type TYPE posttype USING post_type::text::posttype;
   ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'SINGLE_IMAGE'::posttype;

   -- posts.privacy: VARCHAR → postprivacy
   ALTER TABLE posts ALTER COLUMN privacy DROP DEFAULT;
   ALTER TABLE posts ALTER COLUMN privacy TYPE postprivacy USING privacy::text::postprivacy;
   ALTER TABLE posts ALTER COLUMN privacy SET DEFAULT 'PUBLIC'::postprivacy;

   -- post_tags.tag_type: VARCHAR → tagtype
   ALTER TABLE post_tags ALTER COLUMN tag_type TYPE tagtype USING tag_type::text::tagtype;

   -- post_reports.reason: VARCHAR → reportreason
   ALTER TABLE post_reports ALTER COLUMN reason TYPE reportreason USING reason::text::reportreason;
   ```

## Ejecución del Fix

```bash
# En desarrollo local (ya ejecutado):
python scripts/fix_missing_post_enums.py

# En producción (ejecutar cuando sea necesario):
python scripts/fix_missing_post_enums.py
```

## Verificación Post-Fix

```bash
# Verificar ENUMs creados:
psql -c "SELECT typname FROM pg_type WHERE typname IN ('posttype', 'postprivacy', 'tagtype', 'reportreason');"

# Resultado esperado:
#   typname
# --------------
#  postprivacy
#  posttype
#  reportreason
#  tagtype
```

## Estado Final

✅ **Todos los ENUMs correctamente creados:**
- `posttype` con valores: SINGLE_IMAGE, GALLERY, VIDEO, WORKOUT
- `postprivacy` con valores: PUBLIC, PRIVATE
- `tagtype` con valores: MENTION, EVENT, SESSION
- `reportreason` con valores: SPAM, INAPPROPRIATE, HARASSMENT, FALSE_INFO, HATE_SPEECH, VIOLENCE, OTHER

✅ **Columnas actualizadas:**
- `posts.post_type`: posttype (default: 'SINGLE_IMAGE'::posttype)
- `posts.privacy`: postprivacy (default: 'PUBLIC'::postprivacy)
- `post_tags.tag_type`: tagtype
- `post_reports.reason`: reportreason

## Relación con Migración Async

Este problema NO está relacionado con la migración async (fase 2), sino que es un **issue previo de la base de datos** que se manifestó durante las pruebas de la fase async.

La versión sincrónica (sync) tenía el **MISMO problema** (los ENUMs no existían), pero probablemente no se había probado el módulo de posts en producción anteriormente.

## Commits Relacionados

- Script de fix: `scripts/fix_missing_post_enums.py`
- Documentación: `POST_ENUMS_FIX.md`

## Lecciones Aprendidas

1. **Verificar estado real de la BD:** No asumir que las migraciones de Alembic se aplicaron correctamente
2. **Test de esquema:** Agregar tests que verifiquen la existencia de tipos ENUM
3. **Sincronización Alembic:** El registro de Alembic (`alembic_version`) puede estar desincronizado con el estado real de la BD

## Prevención Futura

1. Agregar verificación de ENUMs en health checks:
   ```python
   # app/api/v1/endpoints/health.py
   async def check_database_schema():
       # Verificar existencia de ENUMs críticos
       result = await db.execute(text(
           "SELECT typname FROM pg_type WHERE typname IN ('posttype', 'postprivacy', ...)"
       ))
       # Alertar si faltan ENUMs
   ```

2. Considerar usar `checkfirst=True` en Alembic para ENUMs:
   ```python
   sa.Enum(..., name='posttype').create(op.get_bind(), checkfirst=True)
   ```
