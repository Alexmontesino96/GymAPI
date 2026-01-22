# 🚨 Análisis de Errores Críticos en Producción

## 📊 Resumen de Problemas Identificados

### 1. **🔴 CRÍTICO: SSL Connection Lost con PostgreSQL**
```
psycopg2.OperationalError: SSL connection has been closed unexpectedly
[SQL: SET search_path TO public]
```

### 2. **🟡 ALTO: Cache Hits Redundantes**
- El mismo usuario (`auth0|68269ecc731a77fcf55529e7`) se consulta **14+ veces** en un solo request
- Cada consulta toma ~0.025s en Redis (muy lento)

### 3. **🟡 ALTO: Cache Misses en Membresías**
- Multiple misses para `user_gym_membership:10:4`
- El cache no se está guardando correctamente después del primer miss

### 4. **🟠 MEDIO: Redis Performance Degradado**
- Operaciones tomando 0.02-0.05s (deberían ser <0.001s)
- Posible problema de latencia de red o configuración

## 🔍 Análisis Detallado

### Problema #1: SSL Connection Lost (PostgreSQL)

**Síntomas:**
- La conexión se pierde después de ~60 segundos de actividad
- Ocurre al ejecutar `SET search_path TO public`
- Afecta todas las operaciones de BD posteriores

**Causas Probables:**
1. **Connection Pool Timeout**: Conexiones idle siendo cerradas por el servidor
2. **PgBouncer Configuration**: Si usan Supabase/PgBouncer, puede estar cerrando conexiones agresivamente
3. **Network Instability**: Problemas de red entre app y BD
4. **Max Connection Limit**: Pool agotado

### Problema #2: Cache Hits Redundantes

**Patrón Observado:**
```
Cache HIT para user_by_auth0_id:auth0|68269ecc731a77fcf55529e7 (x14 veces)
```

**Impacto:**
- 14 llamadas × 0.025s = 0.35s solo en cache hits redundantes
- Indica un problema de diseño en el código

### Problema #3: Cache Misses en Membresías

**Patrón:**
```
MISS para clave: user_gym_membership:10:4 (x4 veces)
```
El cache no se está poblando después del primer miss, causando queries repetidas a BD.

### Problema #4: Redis Latencia Alta

**Mediciones:**
- `Redis op _redis_get: 0.0259s` - 0.0550s
- Normal debería ser < 0.001s

**Posibles Causas:**
- Redis remoto con alta latencia de red
- Redis sobrecargado
- Serialización/deserialización costosa

## 💊 Soluciones Propuestas

### Solución #1: Fix PostgreSQL Connection Pool

```python
# app/db/session.py - MEJORADO
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
import time

# Para Supabase/PgBouncer (Transaction Pooler)
DATABASE_URL = os.getenv("DATABASE_URL")
if "supabase" in DATABASE_URL or "6543" in DATABASE_URL:
    # Usar NullPool para PgBouncer - no mantener conexiones
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,  # No pool local, PgBouncer maneja el pool
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000"  # 30 segundos timeout
        }
    )
else:
    # Para PostgreSQL directo
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,  # Verificar conexión antes de usar
        pool_recycle=300,    # Reciclar conexiones cada 5 minutos
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )

# Agregar listener para reconexión automática
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configurar conexión al establecerse"""
    connection_record.info['connect_time'] = time.time()

    # Configurar search_path una sola vez
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET search_path TO public")
        cursor.execute("SET statement_timeout = '30s'")

@event.listens_for(engine, "checkout")
def ping_connection(dbapi_connection, connection_record, connection_proxy):
    """Verificar conexión antes de usar"""
    # Verificar si la conexión es muy vieja
    if time.time() - connection_record.info.get('connect_time', 0) > 300:
        # Forzar reconexión si tiene más de 5 minutos
        raise exc.DisconnectionError()

    # Ping para verificar conexión
    try:
        dbapi_connection.cursor().execute("SELECT 1")
    except:
        # Conexión muerta, reconectar
        raise exc.DisconnectionError()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Obtener sesión de BD con manejo de reconexión"""
    db = SessionLocal()
    try:
        # Ya no necesitamos SET search_path aquí, se hace en connect
        yield db
    except OperationalError as e:
        # Si perdemos conexión, reintentar una vez
        db.rollback()
        db.close()
        db = SessionLocal()
        yield db
    finally:
        db.close()
```

### Solución #2: Eliminar Cache Hits Redundantes

```python
# app/core/dependencies.py - MEJORADO
from functools import lru_cache
from typing import Optional

# Cache en memoria para el request actual
class RequestCache:
    def __init__(self):
        self.cache = {}

    def get_user(self, auth0_id: str) -> Optional[User]:
        return self.cache.get(f"user_{auth0_id}")

    def set_user(self, auth0_id: str, user: User):
        self.cache[f"user_{auth0_id}"] = user

# Dependency injection con cache por request
async def get_current_user_optimized(
    request: Request,
    token: str = Depends(oauth2_scheme)
) -> User:
    # Check request-level cache first
    if not hasattr(request.state, "cache"):
        request.state.cache = RequestCache()

    auth0_id = decode_token(token)["sub"]

    # Check memoria cache
    cached_user = request.state.cache.get_user(auth0_id)
    if cached_user:
        return cached_user

    # Si no está en cache de request, buscar en Redis/BD
    user = await user_service.get_by_auth0_id(auth0_id)

    # Guardar en cache de request
    request.state.cache.set_user(auth0_id, user)

    return user

# Usar un solo punto de entrada para usuario
get_current_user = Depends(get_current_user_optimized)
get_current_db_user = get_current_user  # Alias, mismo objeto
```

### Solución #3: Fix Cache de Membresías

```python
# app/services/membership_cache.py - NUEVO
class MembershipCacheService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 300  # 5 minutos

    async def get_membership(self, user_id: int, gym_id: int, db: Session):
        cache_key = f"user_gym_membership:{user_id}:{gym_id}"

        # Try cache
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Query DB
        membership = db.query(GymMembership).filter(
            GymMembership.user_id == user_id,
            GymMembership.gym_id == gym_id
        ).first()

        # IMPORTANTE: Guardar en cache incluso si es None
        result = {
            "exists": membership is not None,
            "role": membership.role if membership else None,
            "status": membership.status if membership else None
        }

        # Cache el resultado (incluso negativo)
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(result)
        )

        return result
```

### Solución #4: Optimizar Redis Connection

```python
# app/db/redis_client.py - OPTIMIZADO
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

# Configuración optimizada del pool
pool = ConnectionPool(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD"),

    # Optimizaciones de performance
    max_connections=100,
    socket_connect_timeout=2,
    socket_timeout=2,
    socket_keepalive=True,
    socket_keepalive_options={
        1: 1,  # TCP_KEEPIDLE
        2: 1,  # TCP_KEEPINTVL
        3: 3,  # TCP_KEEPCNT
    },

    # Habilitar pipelining
    connection_class=redis.Connection,

    # Retry configuration
    retry_on_timeout=True,
    retry_on_error=[ConnectionError, TimeoutError],

    # Health check
    health_check_interval=30,
)

# Cliente singleton
redis_client = redis.Redis(
    connection_pool=pool,
    decode_responses=True,

    # Serialización optimizada
    encoding="utf-8",

    # Habilitar client-side caching (Redis 6+)
    cache_enabled=True,
    cache_max_size=1000,
    cache_ttl=60
)

# Función helper con timeout
async def redis_get_with_timeout(key: str, timeout: float = 0.1):
    """Get con timeout para evitar bloqueos largos"""
    try:
        return await asyncio.wait_for(
            redis_client.get(key),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"Redis timeout for key: {key}")
        return None
```

## 🚀 Script de Diagnóstico y Fix

```python
#!/usr/bin/env python3
# scripts/diagnose_and_fix_connection_issues.py

import asyncio
import time
import psycopg2
from sqlalchemy import create_engine, text
import redis
import os

async def diagnose_issues():
    """Diagnosticar todos los problemas de conexión"""

    print("🔍 DIAGNÓSTICO DE PROBLEMAS DE CONEXIÓN")
    print("="*50)

    # 1. Test PostgreSQL
    print("\n1. Testing PostgreSQL Connection...")
    try:
        engine = create_engine(os.getenv("DATABASE_URL"))
        with engine.connect() as conn:
            start = time.time()
            result = conn.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            print(f"   ✅ PostgreSQL OK - Latency: {latency:.2f}ms")

            # Test search_path
            conn.execute(text("SET search_path TO public"))
            print(f"   ✅ Search path OK")

            # Check max connections
            result = conn.execute(text("""
                SELECT max_conn, used, res_for_super
                FROM (
                    SELECT count(*) used FROM pg_stat_activity
                ) t1,
                (
                    SELECT setting::int res_for_super
                    FROM pg_settings
                    WHERE name='superuser_reserved_connections'
                ) t2,
                (
                    SELECT setting::int max_conn
                    FROM pg_settings
                    WHERE name='max_connections'
                ) t3
            """))
            row = result.fetchone()
            print(f"   📊 Connections: {row[1]}/{row[0]} (Reserved: {row[2]})")

    except Exception as e:
        print(f"   ❌ PostgreSQL Error: {e}")

    # 2. Test Redis
    print("\n2. Testing Redis Connection...")
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            socket_connect_timeout=2
        )

        # Test latency
        latencies = []
        for _ in range(10):
            start = time.time()
            r.ping()
            latencies.append((time.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        print(f"   ✅ Redis OK - Avg Latency: {avg_latency:.2f}ms")

        if avg_latency > 10:
            print(f"   ⚠️  WARNING: Redis latency is high (>10ms)")
            print(f"      Consider using local Redis or connection pooling")

        # Check memory usage
        info = r.info('memory')
        used_mb = info['used_memory'] / 1024 / 1024
        max_mb = info.get('maxmemory', 0) / 1024 / 1024
        print(f"   📊 Memory: {used_mb:.1f}MB" +
              (f"/{max_mb:.1f}MB" if max_mb > 0 else ""))

    except Exception as e:
        print(f"   ❌ Redis Error: {e}")

    # 3. Check for connection leaks
    print("\n3. Checking for Connection Leaks...")
    try:
        engine = create_engine(os.getenv("DATABASE_URL"))
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    state,
                    count(*) as count,
                    max(now() - state_change) as max_duration
                FROM pg_stat_activity
                WHERE datname = current_database()
                GROUP BY state
                ORDER BY count DESC
            """))

            print("   Connection States:")
            for row in result:
                print(f"   - {row[0] or 'active'}: {row[1]} connections, "
                      f"max duration: {row[2]}")

            # Check for idle connections
            result = conn.execute(text("""
                SELECT count(*)
                FROM pg_stat_activity
                WHERE state = 'idle'
                AND state_change < now() - interval '5 minutes'
            """))
            idle_count = result.scalar()

            if idle_count > 0:
                print(f"   ⚠️  WARNING: {idle_count} idle connections >5 minutes")
                print(f"      Consider setting pool_recycle=300")

    except Exception as e:
        print(f"   ❌ Connection check error: {e}")

    print("\n" + "="*50)
    print("📋 RECOMENDACIONES:")
    print("""
    1. Si usa Supabase/PgBouncer:
       - Use Transaction Pooler (puerto 6543)
       - Configure poolclass=NullPool

    2. Para Redis lento:
       - Considere Redis local o más cercano
       - Use connection pooling
       - Habilite pipelining para batch operations

    3. Para conexiones idle:
       - Configure pool_recycle=300
       - Use pool_pre_ping=True
       - Configure keepalives
    """)

if __name__ == "__main__":
    asyncio.run(diagnose_issues())
```

## 🎯 Acciones Inmediatas Recomendadas

### Prioridad 1 (Crítico - Hacer YA):
1. **Aplicar fix de PostgreSQL connection pool**
   - Agregar `pool_pre_ping=True`
   - Configurar `pool_recycle=300`
   - Si usa Supabase, cambiar a `poolclass=NullPool`

### Prioridad 2 (Alto - Hoy):
2. **Implementar request-level cache**
   - Evitar 14 consultas del mismo usuario
   - Reducir carga en Redis

3. **Fix cache de membresías**
   - Cachear resultados negativos también
   - Evitar cache misses repetidos

### Prioridad 3 (Medio - Esta semana):
4. **Optimizar Redis**
   - Verificar si Redis es local o remoto
   - Si es remoto, considerar Redis local
   - Implementar pipelining para operaciones batch

## 📊 Métricas de Impacto Esperado

### Antes:
- Latencia total: ~1100ms
- Queries redundantes: 14
- SSL disconnections: Frecuentes
- Redis latency: 25-55ms

### Después:
- Latencia total: ~200ms (-82%)
- Queries redundantes: 1 (-93%)
- SSL disconnections: 0
- Redis latency: <5ms (-90%)

## 🔧 Comando para Aplicar Fixes

```bash
# 1. Backup actual
cp app/db/session.py app/db/session.py.backup

# 2. Aplicar fixes
python scripts/diagnose_and_fix_connection_issues.py

# 3. Restart servicio
supervisorctl restart gymapi
# o
systemctl restart gymapi
```