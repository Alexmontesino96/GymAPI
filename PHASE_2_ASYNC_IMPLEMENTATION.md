# FASE 2: MIGRACIÓN ASYNC - GUÍA DE IMPLEMENTACIÓN DETALLADA

## Resumen Ejecutivo

**Objetivo**: Migrar completamente a arquitectura asíncrona para alcanzar latencias <100ms
**Duración**: 8 semanas (56 días)
**Mejora Esperada**: 85-90% adicional sobre Fase 1 (de 293-886ms → <100ms)
**Estrategia**: Migración incremental con dual-mode (sync + async) hasta completar

---

## SEMANA 1: INFRAESTRUCTURA ASYNC (Días 1-7)

### 1.1 Actualizar Dependencias

**Archivo**: `requirements.txt`

```diff
# Database - Async Support
SQLAlchemy==2.0.23
+asyncpg==0.29.0
+greenlet==3.0.3
psycopg2-binary==2.9.9

# Redis - Async Support
redis==5.0.1
+redis[hiredis]==5.0.1
```

**Comando de instalación**:
```bash
pip install asyncpg==0.29.0 greenlet==3.0.3 redis[hiredis]==5.0.1
pip freeze > requirements.txt
```

---

### 1.2 Crear Async Database Engine

**Archivo**: `app/db/session.py`

**Cambios**:

```python
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import re
import logging
import os

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings_instance = get_settings()

# URL original (sync - psycopg2)
db_url_sync = settings_instance.SQLALCHEMY_DATABASE_URI

# URL async (asyncpg)
db_url_async = str(db_url_sync).replace("postgresql://", "postgresql+asyncpg://")

logger.info(f"Database URLs configuradas: sync={db_url_sync[:30]}***, async={db_url_async[:30]}***")

# ==========================================
# SYNC ENGINE (Existente - NO TOCAR aún)
# ==========================================
try:
    engine = create_engine(
        str(db_url_sync),
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=280,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000"
        }
    )

    with engine.connect() as conn:
        conn.execute(text("SET search_path TO public"))
        logger.info(f"Sync engine verificado correctamente")

except Exception as e:
    logger.critical(f"FALLO CRÍTICO AL CREAR SYNC ENGINE: {e}", exc_info=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ==========================================
# ASYNC ENGINE (NUEVO)
# ==========================================
try:
    async_engine = create_async_engine(
        db_url_async,
        echo=False,
        pool_pre_ping=True,
        pool_size=20,  # Más alto para async
        max_overflow=40,
        pool_timeout=30,
        pool_recycle=280,
        connect_args={
            "server_settings": {
                "application_name": "gymapi_async",
                "statement_timeout": "30000"  # asyncpg usa server_settings
            }
        }
    )

    logger.info(f"Async engine creado correctamente")

except Exception as e:
    logger.critical(f"FALLO CRÍTICO AL CREAR ASYNC ENGINE: {e}", exc_info=True)
    async_engine = None

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


# ==========================================
# DEPENDENCIAS
# ==========================================

# Sync DB dependency (EXISTENTE)
def get_db():
    db = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))
        db.commit()
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Error de SQLAlchemy en la sesión: {e}", exc_info=True)
        db.rollback()
        raise
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Error inesperado en get_db: {e}", exc_info=True)
        raise
    finally:
        if db:
            db.close()


# Async DB dependency (NUEVO)
async def get_async_db():
    """
    Dependencia async para obtener sesión de base de datos.

    Uso en endpoints:
        @router.get("/endpoint")
        async def my_endpoint(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(User))
            users = result.scalars().all()
    """
    if async_engine is None:
        raise RuntimeError("Async engine no inicializado")

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SET search_path TO public"))
            await session.commit()
            yield session
        except SQLAlchemyError as e:
            logger.error(f"Error SQLAlchemy en sesión async: {e}", exc_info=True)
            await session.rollback()
            raise
        except Exception as e:
            from fastapi import HTTPException
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error inesperado en get_async_db: {e}", exc_info=True)
            raise
        finally:
            await session.close()
```

**Testing**:
```bash
# Test de conexión async
python -c "
import asyncio
from app.db.session import async_engine
from sqlalchemy import text

async def test():
    async with async_engine.connect() as conn:
        result = await conn.execute(text('SELECT 1'))
        print(f'✅ Async connection OK: {result.scalar()}')

asyncio.run(test())
"
```

---

### 1.3 Actualizar Redis Client (Async)

**Archivo**: `app/db/redis_client.py`

**Cambios clave**:

```python
import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError
import logging
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ==========================================
# ASYNC REDIS CLIENT (NUEVO)
# ==========================================

# Pool de conexiones async
_async_redis_pool: Optional[ConnectionPool] = None
_async_redis_client: Optional[Redis] = None


async def get_async_redis_client() -> Optional[Redis]:
    """
    Obtiene el cliente Redis async (singleton).

    Uso:
        redis = await get_async_redis_client()
        if redis:
            await redis.set("key", "value")
            value = await redis.get("key")
    """
    global _async_redis_pool, _async_redis_client

    if _async_redis_client is not None:
        return _async_redis_client

    try:
        if _async_redis_pool is None:
            _async_redis_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_POOL_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_POOL_SOCKET_TIMEOUT,
                socket_keepalive=settings.REDIS_POOL_SOCKET_KEEPALIVE,
                health_check_interval=settings.REDIS_POOL_HEALTH_CHECK_INTERVAL,
                retry_on_timeout=settings.REDIS_POOL_RETRY_ON_TIMEOUT,
                decode_responses=True,
                encoding="utf-8"
            )

        _async_redis_client = aioredis.Redis(connection_pool=_async_redis_pool)

        # Ping test
        await _async_redis_client.ping()
        logger.info("✅ Async Redis client inicializado correctamente")

        return _async_redis_client

    except Exception as e:
        logger.error(f"❌ Error inicializando async Redis client: {e}")
        return None


async def close_async_redis():
    """Cerrar pool de conexiones async al shutdown."""
    global _async_redis_pool, _async_redis_client

    if _async_redis_client:
        await _async_redis_client.aclose()
        _async_redis_client = None

    if _async_redis_pool:
        await _async_redis_pool.aclose()
        _async_redis_pool = None

    logger.info("Async Redis client cerrado correctamente")


# ==========================================
# SYNC REDIS CLIENT (EXISTENTE - mantener)
# ==========================================
# ... código existente sin cambios ...
```

**Actualizar `app/main.py`**:

```python
from contextlib import asynccontextmanager
from app.db.redis_client import get_async_redis_client, close_async_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Iniciando GymAPI...")

    # Inicializar Redis async
    redis_client = await get_async_redis_client()
    if redis_client:
        logger.info("✅ Async Redis conectado")
    else:
        logger.warning("⚠️ Redis async no disponible")

    # ... resto de inicialización ...

    yield

    # Shutdown
    logger.info("🛑 Cerrando GymAPI...")
    await close_async_redis()
    logger.info("✅ Shutdown completo")
```

---

### 1.4 Crear Utilidades de Migración

**Nuevo archivo**: `app/core/async_utils.py`

```python
"""
Utilidades para migración gradual sync → async.
Permite ejecutar código sync desde contextos async y viceversa.
"""

import asyncio
from typing import TypeVar, Callable, Any, Coroutine
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


def run_sync_in_async(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    Decorator para ejecutar funciones síncronas en contextos async sin bloquear.

    Uso:
        @run_sync_in_async
        def sync_function(x):
            return x * 2

        # Ahora se puede usar con await:
        result = await sync_function(5)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


async def run_sync_query(db_session, query_func: Callable[[Any], T]) -> T:
    """
    Ejecuta una query SQLAlchemy sync en un executor para no bloquear.

    Uso:
        # En endpoint async con Session sync
        def get_users(session):
            return session.query(User).all()

        users = await run_sync_query(db, get_users)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_func, db_session)


class DualModeRepository:
    """
    Base para repositorios que soportan sync y async.

    Ejemplo:
        class UserRepository(DualModeRepository):
            async def get_user_async(self, user_id: int):
                result = await self.async_session.execute(
                    select(User).where(User.id == user_id)
                )
                return result.scalar_one_or_none()

            def get_user_sync(self, user_id: int):
                return self.sync_session.query(User).filter(User.id == user_id).first()
    """

    def __init__(self, sync_session=None, async_session=None):
        self.sync_session = sync_session
        self.async_session = async_session

    @property
    def is_async_mode(self) -> bool:
        return self.async_session is not None


# Decorador para logging de performance async
def async_timed(log_level: str = "debug"):
    """
    Decorator para medir tiempo de ejecución de funciones async.

    Uso:
        @async_timed(log_level="info")
        async def slow_function():
            await asyncio.sleep(1)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                log_func = getattr(logger, log_level)
                log_func(f"{func.__name__} tomó {elapsed:.2f}ms")
        return wrapper
    return decorator
```

---

## SEMANA 2-3: MIGRACIÓN DE SERVICIOS CORE (Días 8-21)

### 2.1 User Service (Más Crítico)

**Archivo**: `app/services/user.py`

**Estrategia**: Crear versiones async junto a las sync, mantener ambas hasta completar migración.

**Ejemplo de migración**:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UserService:
    """
    Servicio de usuarios con soporte dual sync/async.
    """

    # ==========================================
    # MÉTODOS SYNC (EXISTENTES - mantener)
    # ==========================================

    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Versión sync (legacy)"""
        return db.query(User).filter(User.id == user_id).first()

    def get_user_by_auth0_id(self, db: Session, auth0_id: str) -> Optional[User]:
        """Versión sync (legacy)"""
        return db.query(User).filter(User.auth0_id == auth0_id).first()

    # ... resto de métodos sync ...


    # ==========================================
    # MÉTODOS ASYNC (NUEVOS)
    # ==========================================

    async def get_user_by_id_async(
        self,
        db: AsyncSession,
        user_id: int,
        eager_load: bool = False
    ) -> Optional[User]:
        """
        Obtiene usuario por ID (versión async).

        Args:
            db: Sesión async de SQLAlchemy
            user_id: ID del usuario
            eager_load: Si True, carga relaciones (gyms, etc.)

        Returns:
            Usuario o None
        """
        query = select(User).where(User.id == user_id)

        if eager_load:
            query = query.options(
                selectinload(User.gyms),
                selectinload(User.profile)
            )

        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_user_by_auth0_id_async(
        self,
        db: AsyncSession,
        auth0_id: str,
        eager_load: bool = False
    ) -> Optional[User]:
        """
        Obtiene usuario por Auth0 ID (versión async).

        Args:
            db: Sesión async
            auth0_id: ID de Auth0
            eager_load: Cargar relaciones

        Returns:
            Usuario o None
        """
        query = select(User).where(User.auth0_id == auth0_id)

        if eager_load:
            query = query.options(
                selectinload(User.gyms),
                selectinload(User.profile)
            )

        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Usuario encontrado: {user.id} ({auth0_id})")
        else:
            logger.debug(f"Usuario no encontrado para auth0_id: {auth0_id}")

        return user


    async def create_user_async(
        self,
        db: AsyncSession,
        user_data: UserCreate
    ) -> User:
        """
        Crea usuario (versión async).

        Args:
            db: Sesión async
            user_data: Datos del usuario a crear

        Returns:
            Usuario creado
        """
        user = User(**user_data.model_dump())
        db.add(user)

        try:
            await db.commit()
            await db.refresh(user)
            logger.info(f"Usuario creado: {user.id} ({user.email})")
            return user
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creando usuario: {e}")
            raise


    async def update_user_async(
        self,
        db: AsyncSession,
        user_id: int,
        user_data: UserUpdate
    ) -> Optional[User]:
        """
        Actualiza usuario (versión async).

        Args:
            db: Sesión async
            user_id: ID del usuario
            user_data: Datos a actualizar

        Returns:
            Usuario actualizado o None
        """
        user = await self.get_user_by_id_async(db, user_id)
        if not user:
            return None

        # Actualizar campos
        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            await db.commit()
            await db.refresh(user)
            logger.info(f"Usuario actualizado: {user.id}")
            return user
        except Exception as e:
            await db.rollback()
            logger.error(f"Error actualizando usuario: {e}")
            raise


# Instancia global
user_service = UserService()
```

**Migración de endpoint**:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_db
from app.services.user import user_service
from app.core.auth0_fastapi import get_current_user_async

router = APIRouter()


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_async)
):
    """
    Endpoint migrado a async.

    ANTES:
        def get_user(user_id: int, db: Session = Depends(get_db)):
            user = user_service.get_user_by_id(db, user_id)

    DESPUÉS:
        async def get_user(user_id: int, db: AsyncSession = Depends(get_async_db)):
            user = await user_service.get_user_by_id_async(db, user_id)
    """
    user = await user_service.get_user_by_id_async(db, user_id, eager_load=True)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    return user
```

---

### 2.2 Gym Service

**Similar a User Service**: Crear métodos `*_async()` paralelos.

**Priorizar**:
- `get_gym_by_id_async()`
- `get_user_gyms_async()`
- `get_gym_members_async()`

---

### 2.3 Schedule Service

**Archivo**: `app/services/schedule.py`

**Cambios clave**:
- Migrar queries de clases a async
- Mantener cache con Redis async
- Eager loading en queries async

```python
async def get_classes_async(
    db: AsyncSession,
    gym_id: int,
    redis_client: Optional[Redis] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Class]:
    """
    Obtiene clases del gimnasio (async).
    """
    cache_key = f"gym:{gym_id}:classes"

    # Intentar cache
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit: {cache_key}")
                return [Class(**c) for c in json.loads(cached)]
        except Exception as e:
            logger.debug(f"Cache miss: {e}")

    # Query con eager loading
    query = (
        select(Class)
        .where(Class.gym_id == gym_id)
        .options(
            selectinload(Class.custom_category),
            selectinload(Class.instructor)
        )
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    classes = result.scalars().all()

    # Guardar en cache
    if redis_client and classes:
        try:
            await redis_client.setex(
                cache_key,
                300,  # 5 minutos
                json.dumps([c.to_dict() for c in classes])
            )
        except Exception as e:
            logger.error(f"Error cacheando clases: {e}")

    return classes
```

---

## SEMANA 4-5: MIGRACIÓN DE MIDDLEWARE (Días 22-35)

### 4.1 TenantAuthMiddleware Async

**Archivo**: `app/middleware/tenant_auth.py`

**Cambio crítico**: Middleware debe ser completamente async.

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.redis_client import get_async_redis_client
from app.services.user import user_service
from app.core.auth0_fastapi import verify_token_async
import logging

logger = logging.getLogger(__name__)


class TenantAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware async para autenticación multi-tenant.
    """

    async def dispatch(self, request: Request, call_next):
        import time
        start = time.time()

        path = request.url.path

        # Inicializar state
        request.state.gym = None
        request.state.user = None
        request.state.role_in_gym = None

        # Rutas exentas
        if any(path.startswith(exempt) for exempt in GYM_EXEMPT_PATHS):
            response = await call_next(request)
            return response

        # Extraer gym_id del header
        gym_id = None
        gym_id_header = request.headers.get("X-Gym-ID")
        if gym_id_header:
            try:
                gym_id = int(gym_id_header)
            except ValueError:
                return Response(
                    content='{"detail": "X-Gym-ID inválido"}',
                    status_code=400,
                    media_type="application/json"
                )

        # Verificar token y obtener usuario
        if not any(path.startswith(exempt) for exempt in AUTH_EXEMPT_PATHS):
            auth_header = request.headers.get("authorization", "")

            if not auth_header.startswith("Bearer "):
                return Response(
                    content='{"detail": "Token requerido"}',
                    status_code=401,
                    media_type="application/json"
                )

            token = auth_header[7:]

            try:
                # Verificar token (async)
                payload = await verify_token_async(token)
                auth0_id = payload.get("sub")

                if not auth0_id:
                    raise ValueError("Token sin sub")

                # Obtener usuario (async)
                async with AsyncSessionLocal() as db:
                    redis_client = await get_async_redis_client()

                    user = await user_service.get_user_by_auth0_id_async(
                        db, auth0_id, eager_load=True
                    )

                    if not user:
                        return Response(
                            content='{"detail": "Usuario no encontrado"}',
                            status_code=404,
                            media_type="application/json"
                        )

                    request.state.user = user

                    # Si se requiere gym, verificar membresía
                    if gym_id:
                        membership = await self.check_gym_membership_async(
                            db, user.id, gym_id
                        )

                        if not membership:
                            return Response(
                                content='{"detail": "Acceso denegado al gimnasio"}',
                                status_code=403,
                                media_type="application/json"
                            )

                        request.state.gym_id = gym_id
                        request.state.role_in_gym = membership.role.value

            except Exception as e:
                logger.error(f"Error en auth middleware: {e}")
                return Response(
                    content='{"detail": "Error de autenticación"}',
                    status_code=401,
                    media_type="application/json"
                )

        # Continuar con la request
        response = await call_next(request)

        elapsed = (time.time() - start) * 1000
        logger.debug(f"TenantAuthMiddleware: {elapsed:.2f}ms")

        return response


    async def check_gym_membership_async(self, db: AsyncSession, user_id: int, gym_id: int):
        """Verifica membresía del usuario al gym (async)."""
        from sqlalchemy import select
        from app.models.user_gym import UserGym

        query = select(UserGym).where(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()
```

---

## SEMANA 6-7: TESTING Y OPTIMIZACIÓN (Días 36-49)

### 6.1 Tests Async

**Nuevo archivo**: `tests/async/test_user_service_async.py`

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.services.user import user_service
from app.models.user import User
from app.schemas.user import UserCreate

# Fixture para DB async
@pytest.fixture
async def async_db_session():
    """Sesión de DB async para tests."""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost:5432/test_db",
        echo=False
    )

    AsyncSessionTest = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionTest() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_user_by_id_async(async_db_session):
    """Test de get_user_by_id_async."""
    # Crear usuario de prueba
    user_data = UserCreate(
        email="test@example.com",
        auth0_id="auth0|123",
        name="Test User"
    )

    user = await user_service.create_user_async(async_db_session, user_data)
    assert user.id is not None

    # Obtener usuario
    fetched = await user_service.get_user_by_id_async(async_db_session, user.id)
    assert fetched is not None
    assert fetched.email == "test@example.com"


@pytest.mark.asyncio
async def test_user_not_found_async(async_db_session):
    """Test de usuario no encontrado."""
    user = await user_service.get_user_by_id_async(async_db_session, 99999)
    assert user is None
```

**Ejecutar**:
```bash
pytest tests/async/ -v --asyncio-mode=auto
```

---

### 6.2 Load Testing con Locust

**Nuevo archivo**: `tests/load/locustfile_async.py`

```python
from locust import HttpUser, task, between
import os

class GymAPIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login al iniciar."""
        self.token = os.getenv("TEST_AUTH_TOKEN")
        self.gym_id = os.getenv("TEST_GYM_ID", "1")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Gym-ID": self.gym_id
        }

    @task(3)
    def get_classes(self):
        """Test de endpoint /classes (migrado a async)."""
        self.client.get(
            "/api/v1/schedule/classes",
            headers=self.headers,
            name="GET /classes (async)"
        )

    @task(2)
    def get_events(self):
        """Test de endpoint /events."""
        self.client.get(
            "/api/v1/events",
            headers=self.headers,
            name="GET /events (async)"
        )

    @task(1)
    def get_profile(self):
        """Test de perfil de usuario."""
        self.client.get(
            "/api/v1/users/me",
            headers=self.headers,
            name="GET /users/me (async)"
        )
```

**Ejecutar**:
```bash
locust -f tests/load/locustfile_async.py --host=http://localhost:8000 --users=100 --spawn-rate=10
```

**Métricas esperadas**:
- P50 (mediana): <50ms
- P95: <100ms
- P99: <200ms
- Throughput: >1000 req/s

---

## SEMANA 8: DEPLOYMENT Y MONITORING (Días 50-56)

### 8.1 Configuración de Producción

**Archivo**: `.env.production`

```bash
# Database - Async Pool más grande
DATABASE_URL=postgresql+asyncpg://user:pass@host:6543/db

# Pool sizing para producción
SQLALCHEMY_POOL_SIZE=30
SQLALCHEMY_MAX_OVERFLOW=60

# Redis - Async
REDIS_URL=rediss://default:pass@redis-host:6379/0
REDIS_POOL_MAX_CONNECTIONS=100

# Debug desactivado
DEBUG_MODE=false
SQLALCHEMY_ECHO=false

# Async workers
UVICORN_WORKERS=4
```

**Comando de inicio**:
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 30 \
  --keep-alive 5 \
  --max-requests 10000 \
  --max-requests-jitter 1000
```

---

### 8.2 Monitoring con Prometheus

**Nuevo archivo**: `app/core/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge
import time
from functools import wraps

# Métricas async
async_requests_total = Counter(
    'gymapi_async_requests_total',
    'Total async requests',
    ['method', 'endpoint', 'status']
)

async_request_duration = Histogram(
    'gymapi_async_request_duration_seconds',
    'Async request duration',
    ['method', 'endpoint']
)

async_db_query_duration = Histogram(
    'gymapi_async_db_query_duration_seconds',
    'Async DB query duration',
    ['operation']
)

async_redis_operations = Counter(
    'gymapi_async_redis_operations_total',
    'Async Redis operations',
    ['operation', 'status']
)


def track_async_db_query(operation: str):
    """Decorator para trackear queries async."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                async_db_query_duration.labels(operation=operation).observe(duration)
        return wrapper
    return decorator
```

**Dashboard Grafana**: Ver `grafana/dashboards/async_performance.json`

---

## CHECKLIST DE VALIDACIÓN

### Antes de Cada Deploy:

- [ ] Todos los tests pasan (`pytest tests/ -v`)
- [ ] Tests async pasan (`pytest tests/async/ -v`)
- [ ] Load test cumple SLA (<100ms P95)
- [ ] Sin errores en logs de staging por 24h
- [ ] Rollback plan documentado
- [ ] Backup de DB creado

### Post-Deploy Monitoring (Primeras 2 horas):

- [ ] Latencia P95 <100ms
- [ ] Error rate <0.1%
- [ ] CPU <70%
- [ ] Memory <80%
- [ ] DB connections <50% pool
- [ ] Redis hit rate >90%

---

## ROLLBACK PLAN

Si P95 latency >500ms o error rate >1%:

```bash
# 1. Revertir a versión anterior
git revert HEAD
git push origin main

# 2. Rebuild y redeploy
docker build -t gymapi:rollback .
docker tag gymapi:rollback gymapi:latest
# Deploy según plataforma

# 3. Verificar métricas en 5 minutos
# 4. Si persiste, rollback de DB (solo si hubo migraciones)
alembic downgrade -1
```

---

## MÉTRICAS DE ÉXITO

### Fase 2 Completa:

| Métrica | Antes (Fase 1) | Objetivo Fase 2 | Actual |
|---------|----------------|-----------------|---------|
| **P50 Latency** | 293ms | <30ms | TBD |
| **P95 Latency** | 886ms | <100ms | TBD |
| **P99 Latency** | ~1500ms | <200ms | TBD |
| **Throughput** | ~200 req/s | >1000 req/s | TBD |
| **Error Rate** | 0.05% | <0.01% | TBD |
| **DB Connections** | 8/10 avg | <15/30 avg | TBD |

---

## PRÓXIMOS PASOS INMEDIATOS

1. ✅ Actualizar `requirements.txt`
2. ✅ Modificar `app/db/session.py`
3. ✅ Crear `get_async_db()` dependency
4. ✅ Actualizar Redis client
5. ⏳ Migrar `user_service` a async
6. ⏳ Migrar endpoints `/users/*`
7. ⏳ Testing con `pytest-asyncio`

---

**Documento creado**: 2025-12-01
**Última actualización**: 2025-12-01
**Versión**: 1.0
**Estado**: 🚀 LISTO PARA IMPLEMENTAR
