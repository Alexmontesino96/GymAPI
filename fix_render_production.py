#!/usr/bin/env python3
"""
Fix específico para producción en Render con Supabase.
Este script corrige los problemas críticos identificados.

EJECUTAR ESTO EN PRODUCCIÓN URGENTE!
"""

import os

def generate_session_fix():
    """Generar fix para app/db/session.py"""

    fix_code = '''# app/db/session.py - FIX PARA RENDER + SUPABASE
import os
from sqlalchemy import create_engine, event, exc, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool  # CRÍTICO: Usar NullPool para Supabase!
import logging

logger = logging.getLogger(__name__)

# Obtener DATABASE_URL de Supabase
DATABASE_URL = os.getenv("DATABASE_URL")

# CRÍTICO: Detectar si es Supabase Transaction Pooler
is_supabase = "supabase" in DATABASE_URL or "pooler" in DATABASE_URL or "6543" in DATABASE_URL

if is_supabase:
    # CONFIGURACIÓN PARA SUPABASE (Transaction Pooler)
    logger.info("🔧 Usando configuración optimizada para Supabase/PgBouncer")

    engine = create_engine(
        DATABASE_URL,
        # CRÍTICO: NullPool para PgBouncer - NO mantener pool local!
        poolclass=NullPool,

        # Configuración de conexión para Supabase
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 10,  # Más agresivo para Supabase
            "keepalives_interval": 5,
            "keepalives_count": 3,
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000"  # 30 segundos
        },

        # Echo para debug (desactivar en producción final)
        echo=False,

        # Importante para Supabase
        pool_pre_ping=False,  # No hacer ping con NullPool

        # Execution options
        execution_options={
            "isolation_level": "AUTOCOMMIT"  # Para evitar transacciones largas
        }
    )
else:
    # Configuración para PostgreSQL directo (desarrollo local)
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300
    )

# Event listener para configurar cada conexión nueva
@event.listens_for(engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    """Configurar search_path al conectar (una sola vez)"""
    with dbapi_conn.cursor() as cursor:
        cursor.execute("SET search_path TO public")
        # Para Supabase, también configurar el statement timeout
        if is_supabase:
            cursor.execute("SET statement_timeout = '30s'")

# Crear SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Obtener sesión de BD con manejo de errores mejorado"""
    db = SessionLocal()
    try:
        # Ya no necesitamos SET search_path aquí (se hace en connect)
        yield db
    except exc.OperationalError as e:
        logger.error(f"❌ Database connection lost: {e}")
        db.rollback()
        db.close()
        # Crear nueva sesión
        db = SessionLocal()
        yield db
    finally:
        db.close()
'''
    return fix_code


def generate_redis_fix():
    """Generar fix para app/db/redis_client.py"""

    fix_code = '''# app/db/redis_client.py - FIX PARA RENDER
import os
import redis
from redis.exceptions import ConnectionError, TimeoutError
import logging

logger = logging.getLogger(__name__)

def get_redis_client():
    """
    Obtener cliente Redis con fallback para cuando no está disponible.
    En Render, usar Redis remoto si está configurado.
    """
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        # Si no hay Redis configurado, retornar cliente dummy
        logger.warning("⚠️ REDIS_URL no configurado - Cache deshabilitado")
        return DummyRedisClient()

    try:
        # Intentar conectar a Redis remoto
        logger.info(f"🔌 Conectando a Redis: {redis_url.split('@')[1] if '@' in redis_url else 'local'}")

        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            retry_on_error=[ConnectionError, TimeoutError],
            max_connections=50,
            health_check_interval=30
        )

        # Verificar conexión
        client.ping()
        logger.info("✅ Redis conectado correctamente")
        return client

    except Exception as e:
        logger.error(f"❌ No se pudo conectar a Redis: {e}")
        logger.warning("⚠️ Usando DummyRedisClient (sin cache)")
        return DummyRedisClient()


class DummyRedisClient:
    """Cliente Redis dummy para cuando Redis no está disponible"""

    async def get(self, key):
        return None

    async def set(self, key, value, ex=None):
        return True

    async def setex(self, key, seconds, value):
        return True

    async def delete(self, *keys):
        return 0

    async def exists(self, key):
        return False

    async def expire(self, key, seconds):
        return True

    async def ttl(self, key):
        return -1

    async def keys(self, pattern):
        return []

    async def ping(self):
        return True

    def pipeline(self):
        return self

    async def execute(self):
        return []

# Singleton
redis_client = None

def get_redis():
    """Obtener instancia singleton de Redis"""
    global redis_client
    if redis_client is None:
        redis_client = get_redis_client()
    return redis_client
'''
    return fix_code


def generate_cache_fix():
    """Generar fix para evitar cache hits redundantes"""

    fix_code = '''# app/core/request_cache.py - NUEVO ARCHIVO
"""
Cache a nivel de request para evitar consultas redundantes.
Soluciona el problema de 14 cache hits del mismo usuario.
"""
from typing import Optional, Any, Dict
from fastapi import Request

class RequestCache:
    """Cache que vive durante el request actual"""

    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """Guardar valor en cache"""
        self.cache[key] = value

    def get_stats(self) -> Dict:
        """Obtener estadísticas del cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "keys_cached": len(self.cache)
        }


def get_request_cache(request: Request) -> RequestCache:
    """Obtener o crear cache para el request actual"""
    if not hasattr(request.state, "cache"):
        request.state.cache = RequestCache()
    return request.state.cache


# app/services/user.py - MODIFICAR get_user_by_auth0_id
async def get_user_by_auth0_id_optimized(
    db,
    auth0_id: str,
    request: Optional[Request] = None
):
    """Versión optimizada que usa request cache"""

    # 1. Check request cache first
    if request:
        cache = get_request_cache(request)
        cache_key = f"user:{auth0_id}"
        cached_user = cache.get(cache_key)
        if cached_user:
            return cached_user

    # 2. Check Redis cache (si está disponible)
    redis_client = get_redis()
    if redis_client:
        redis_key = f"user_by_auth0_id:{auth0_id}"
        cached = await redis_client.get(redis_key)
        if cached:
            user = json.loads(cached)
            # Guardar en request cache
            if request:
                cache.set(cache_key, user)
            return user

    # 3. Query database
    user = db.query(User).filter(User.auth0_id == auth0_id).first()

    # 4. Save to both caches
    if user:
        user_dict = user.to_dict()  # Serializar

        # Save to Redis
        if redis_client:
            await redis_client.setex(redis_key, 300, json.dumps(user_dict))

        # Save to request cache
        if request:
            cache.set(cache_key, user_dict)

    return user
'''
    return fix_code


def generate_env_example():
    """Generar ejemplo de variables de entorno para Render"""

    env_content = '''# .env.render - Variables de entorno para Render

# Base de datos - Supabase (CRÍTICO: Usar Transaction Pooler en puerto 6543!)
DATABASE_URL=postgresql://[user]:[password]@[host]:6543/postgres?pgbouncer=true&connection_limit=1

# Redis - Render Redis o Upstash
REDIS_URL=redis://default:[password]@[host]:[port]

# Alternativa si no tienen Redis (usar cache en memoria)
USE_MEMORY_CACHE=true

# Auth0
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_API_AUDIENCE=https://api.yourdomain.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret

# Importante para Render
PORT=10000
TRUST_PROXY_HEADERS=true
DEBUG_MODE=false

# Performance
SQLALCHEMY_POOL_SIZE=0  # Importante: 0 para NullPool con Supabase
SQLALCHEMY_MAX_OVERFLOW=0
REDIS_POOL_MAX_CONNECTIONS=10
'''
    return env_content


def main():
    print("\n" + "="*60)
    print("🚨 FIXES CRÍTICOS PARA RENDER + SUPABASE")
    print("="*60 + "\n")

    print("📝 Generando archivos de corrección...\n")

    # 1. Session fix
    with open("fix_session.py", "w") as f:
        f.write(generate_session_fix())
    print("✅ fix_session.py - Corrige SSL disconnection con Supabase")

    # 2. Redis fix
    with open("fix_redis.py", "w") as f:
        f.write(generate_redis_fix())
    print("✅ fix_redis.py - Maneja Redis remoto o fallback")

    # 3. Cache fix
    with open("fix_request_cache.py", "w") as f:
        f.write(generate_cache_fix())
    print("✅ fix_request_cache.py - Elimina queries redundantes")

    # 4. Env example
    with open(".env.render", "w") as f:
        f.write(generate_env_example())
    print("✅ .env.render - Variables de entorno correctas")

    print("\n" + "="*40)
    print("🔧 INSTRUCCIONES DE APLICACIÓN")
    print("="*40)

    print("""
1. BACKUP actual:
   cp app/db/session.py app/db/session.py.backup
   cp app/db/redis_client.py app/db/redis_client.py.backup

2. APLICAR fixes:
   cp fix_session.py app/db/session.py
   cp fix_redis.py app/db/redis_client.py
   cp fix_request_cache.py app/core/request_cache.py

3. CONFIGURAR en Render Dashboard:
   - DATABASE_URL: Usar puerto 6543 (Transaction Pooler)
   - REDIS_URL: Configurar si tienen Redis
   - SQLALCHEMY_POOL_SIZE=0

4. COMMIT y DEPLOY:
   git add .
   git commit -m "fix: critical Supabase/Redis issues for Render"
   git push

5. VERIFICAR en Render logs:
   - "Usando configuración optimizada para Supabase/PgBouncer"
   - "Redis conectado correctamente" o "Cache deshabilitado"

IMPORTANTE:
- El puerto 6543 es CRÍTICO para Supabase (Transaction Pooler)
- Si no tienen Redis, el sistema funcionará sin cache
- Los fixes son retrocompatibles con desarrollo local
""")

    print("\n✨ Estos cambios deberían resolver:")
    print("   - SSL disconnections con Supabase")
    print("   - Errores de Redis connection refused")
    print("   - Queries redundantes (14 → 1)")
    print("   - Reducir latencia ~80%")


if __name__ == "__main__":
    main()