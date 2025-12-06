# Fix: pgbouncer Prepared Statements Errors (CRÍTICO)

**Fecha:** 2025-12-06
**Severidad:** CRÍTICA - Afecta TODA la funcionalidad async en producción
**Plataforma:** Supabase con pgbouncer en modo transaction pooling

## Síntomas del Problema

```
asyncpg.exceptions.DuplicatePreparedStatementError: prepared statement "__asyncpg_stmt_37__" already exists

HINT: pgbouncer with pool_mode set to "transaction" or "statement" does not support prepared statements properly.
```

### Errores Observados en Producción

1. **Primera ocurrencia:** Múltiples endpoints afectados (eventos, posts, users)
2. **Segunda ocurrencia:** Mismo error después de aplicar fix parcial
3. **Endpoints afectados:**
   - `/api/v1/events/participation/me`
   - `/api/v1/posts/feed/timeline`
   - Cualquier endpoint que use AsyncSession con pgbouncer

## Causa Raíz

### ¿Por qué ocurre este error?

**pgbouncer en modo transaction pooling:**
- Cada transacción puede obtener una conexión DIFERENTE del pool
- Las prepared statements se crean en la conexión específica
- Si una segunda petición obtiene la MISMA conexión física del pool pero intenta crear un prepared statement con el mismo nombre, ocurre el error

**asyncpg por defecto:**
- Cachea prepared statements para optimizar performance
- Usa nombres como `__asyncpg_stmt_N__` para identificar statements
- NO sabe que la conexión puede cambiar de manos entre peticiones (pgbouncer)

### Configuración Problemática

```python
# ❌ CONFIGURACIÓN INCORRECTA (solo deshabilita 1 de 3 parámetros)
async_engine = create_async_engine(
    db_url_async,
    connect_args={
        "statement_cache_size": 0,  # Solo este NO es suficiente
    }
)
```

## Solución Completa

### Parámetros de asyncpg a Deshabilitar

asyncpg tiene **3 parámetros** de caching de prepared statements que TODOS deben configurarse a 0:

1. **`statement_cache_size`**: Número máximo de prepared statements en cache (default: 100)
2. **`max_cached_statement_lifetime`**: Tiempo de vida en segundos del cache (default: 300)
3. **`max_cacheable_statement_size`**: Tamaño máximo en bytes de statements cacheables (default: 15360)

### Configuración Correcta en app/db/session.py

```python
from sqlalchemy.pool import NullPool

async_engine = create_async_engine(
    db_url_async,
    echo=False,

    # ✅ CRÍTICO: NullPool deshabilita connection pooling
    # Cada request obtiene una conexión fresca sin prepared statements previos
    poolclass=NullPool,

    connect_args={
        # ✅ CRÍTICO: Deshabilitar TODOS los parámetros de prepared statements
        "statement_cache_size": 0,              # Deshabilitar cache de statements
        "max_cached_statement_lifetime": 0,     # Deshabilitar lifetime del cache
        "max_cacheable_statement_size": 0,      # Deshabilitar tamaño máximo

        "server_settings": {
            "search_path": "public",
            "application_name": "gymapi_async",
            "statement_timeout": "30000"
        }
    },

    # ✅ IMPORTANTE: Deshabilitar cache de SQLAlchemy también
    execution_options={
        "compiled_cache": None,           # Deshabilitar compiled cache
        "schema_translate_map": None      # Evitar caching adicional
    }
)
```

## Historial de Intentos de Fix

### Intento 1: compiled_cache=None (INSUFICIENTE)
**Commit:** `5f6bc09`
```python
execution_options={"compiled_cache": None}
```
**Resultado:** ❌ Error persistió

### Intento 2: NullPool + statement_cache_size=0 (PARCIAL)
**Commit:** `2cad36f`
```python
poolclass=NullPool,
connect_args={"statement_cache_size": 0}
```
**Resultado:** ⚠️ Mejoró pero no resolvió completamente

### Intento 3: TODOS los parámetros de caching (SOLUCIÓN FINAL)
**Commit:** `a15f9b9`
```python
poolclass=NullPool,
connect_args={
    "statement_cache_size": 0,
    "max_cached_statement_lifetime": 0,
    "max_cacheable_statement_size": 0
}
```
**Resultado:** ✅ Esperado: Resolución completa

## Trade-offs de la Solución

### Desventajas

1. **Performance:**
   - Sin prepared statements: ~5-15% más lento por query
   - Sin connection pooling (NullPool): ~10-50ms overhead por request
   - Total estimado: ~15-65ms adicionales por request

2. **Carga en PostgreSQL:**
   - Cada query se parsea y planifica en cada ejecución
   - Mayor uso de CPU en el servidor de BD

### Ventajas

1. **Estabilidad:** Elimina errores críticos de prepared statements
2. **Compatibilidad:** Funciona perfectamente con pgbouncer
3. **Simplicidad:** No requiere configuración especial de pgbouncer

### ¿Es Aceptable el Trade-off?

**SÍ**, porque:
- La estabilidad es más importante que 50ms de latencia adicional
- Redis cache compensa la mayoría de la latencia perdida
- Los errores de prepared statements causan 500 errors (peor UX)

## Alternativas Consideradas

### Alternativa 1: Cambiar pgbouncer a session mode
**Ventaja:** Permite prepared statements
**Desventaja:** Supabase no permite cambiar el modo de pgbouncer
**Viabilidad:** ❌ NO POSIBLE

### Alternativa 2: Usar Direct Connection URL (sin pgbouncer)
**Ventaja:** Sin restricciones de pgbouncer
**Desventaja:** Límite de conexiones muy bajo (~20 en Supabase Free)
**Viabilidad:** ⚠️ Solo para desarrollo local

### Alternativa 3: Migrar a otro proveedor (no Supabase)
**Ventaja:** Control total sobre configuración
**Desventaja:** Costo y tiempo de migración
**Viabilidad:** 🔄 Para considerar a futuro

## Verificación del Fix

### En Desarrollo Local
```bash
# 1. Verificar configuración en session.py
grep -A 3 "statement_cache_size" app/db/session.py

# 2. Iniciar servidor
python app_wrapper.py

# 3. Verificar logs de startup
# Debería mostrar: "✅ Async engine creado con NullPool + TODOS los caches..."
```

### En Producción (Render)

1. **Deploy automático:** Push a GitHub activa redeploy
2. **Verificar logs de startup en Render:**
   ```
   ✅ Async engine creado con NullPool + TODOS los caches de prepared statements DESHABILITADOS
   ```
3. **Probar endpoints afectados:**
   - GET /api/v1/events/participation/me
   - GET /api/v1/posts/feed/timeline
4. **Monitorear errores:** No deberían aparecer más `DuplicatePreparedStatementError`

### Comandos de Verificación

```bash
# Ver parámetros de asyncpg en runtime
python -c "
import asyncpg
import inspect
sig = inspect.signature(asyncpg.connect)
for param in ['statement_cache_size', 'max_cached_statement_lifetime', 'max_cacheable_statement_size']:
    print(f'{param}: {sig.parameters[param].default}')
"
```

## Prevención Futura

### Health Check de Configuración

Agregar verificación en `/api/v1/health`:
```python
async def check_async_engine_config():
    from app.db.session import async_engine

    # Verificar NullPool
    assert isinstance(async_engine.pool, NullPool), "async_engine debe usar NullPool"

    # Verificar connect_args
    connect_args = async_engine.dialect.on_connect_url_params
    assert connect_args.get("statement_cache_size") == 0
    assert connect_args.get("max_cached_statement_lifetime") == 0
    assert connect_args.get("max_cacheable_statement_size") == 0

    return {"status": "ok", "pgbouncer_compatible": True}
```

### Monitoreo de Errores

Agregar alertas para detectar prepared statement errors:
```python
# En exception handler
if "DuplicatePreparedStatementError" in str(error):
    logger.critical("❌ PGBOUNCER PREPARED STATEMENT ERROR DETECTADO")
    # Enviar alerta a OneSignal/Email
```

## Documentación de Referencia

- **asyncpg connection parameters:** https://magicstack.github.io/asyncpg/current/api/index.html#connection
- **SQLAlchemy asyncpg dialect:** https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
- **pgbouncer transaction pooling:** https://www.pgbouncer.org/features.html
- **Supabase connection pooling:** https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler

## Commits Relacionados

1. `5f6bc09` - Primera tentativa (compiled_cache)
2. `2cad36f` - Segunda tentativa (NullPool + statement_cache_size)
3. `a15f9b9` - **Solución final** (todos los parámetros de caching)
4. `e0b19b9` - Fix de ENUMs de posts (no relacionado)

## Lecciones Aprendidas

1. **Leer documentación completa:** asyncpg tiene múltiples parámetros de caching
2. **Probar en producción:** El comportamiento de pgbouncer difiere entre dev y prod
3. **Monitorear errores:** Los logs de producción revelaron el problema recurrente
4. **No asumir fixes parciales:** Deshabilitar 1 de 3 parámetros no es suficiente

## Estado Actual

✅ **Fix aplicado en:** app/db/session.py
✅ **Pusheado a GitHub:** Commit a15f9b9
🔄 **Esperando deploy en Render:** Auto-deploy en progreso
⏳ **Verificación pendiente:** Monitorear logs de producción después de deploy
