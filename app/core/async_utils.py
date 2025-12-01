"""
Utilidades para migración gradual sync → async.
Permite ejecutar código sync desde contextos async y viceversa.

Este módulo facilita la transición incremental de la arquitectura,
permitiendo que código sync y async coexistan durante la migración.
"""

import asyncio
from typing import TypeVar, Callable, Any, Coroutine
from functools import wraps
import logging
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')


def run_sync_in_async(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    Decorator para ejecutar funciones síncronas en contextos async sin bloquear.

    Ejecuta la función en un ThreadPoolExecutor para no bloquear el event loop.

    Uso:
        @run_sync_in_async
        def sync_function(x):
            return x * 2

        # Ahora se puede usar con await:
        result = await sync_function(5)

    Args:
        func: Función síncrona a wrappear

    Returns:
        Función async que ejecuta la función sync en un executor
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


async def run_sync_query(db_session, query_func: Callable[[Any], T]) -> T:
    """
    Ejecuta una query SQLAlchemy sync en un executor para no bloquear.

    Útil durante la transición cuando se necesita usar queries sync
    desde endpoints async.

    Uso:
        # En endpoint async con Session sync
        def get_users(session):
            return session.query(User).all()

        users = await run_sync_query(db, get_users)

    Args:
        db_session: Sesión de SQLAlchemy (sync)
        query_func: Función que ejecuta la query

    Returns:
        Resultado de la query
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_func, db_session)


class DualModeRepository:
    """
    Base para repositorios que soportan sync y async.

    Permite crear repositorios que pueden trabajar en ambos modos
    durante la transición, facilitando la migración incremental.

    Ejemplo:
        class UserRepository(DualModeRepository):
            async def get_user_async(self, user_id: int):
                if not self.is_async_mode:
                    raise RuntimeError("Async mode not initialized")

                result = await self.async_session.execute(
                    select(User).where(User.id == user_id)
                )
                return result.scalar_one_or_none()

            def get_user_sync(self, user_id: int):
                if not self.sync_session:
                    raise RuntimeError("Sync mode not initialized")

                return self.sync_session.query(User).filter(User.id == user_id).first()
    """

    def __init__(self, sync_session=None, async_session=None):
        """
        Inicializa el repositorio dual.

        Args:
            sync_session: Sesión SQLAlchemy sync (opcional)
            async_session: Sesión SQLAlchemy async (opcional)
        """
        self.sync_session = sync_session
        self.async_session = async_session

    @property
    def is_async_mode(self) -> bool:
        """Verifica si el repositorio está en modo async."""
        return self.async_session is not None

    @property
    def is_sync_mode(self) -> bool:
        """Verifica si el repositorio está en modo sync."""
        return self.sync_session is not None


def async_timed(log_level: str = "debug"):
    """
    Decorator para medir tiempo de ejecución de funciones async.

    Útil para profiling y debugging durante la migración.

    Uso:
        @async_timed(log_level="info")
        async def slow_function():
            await asyncio.sleep(1)

        # Logs: "slow_function tomó 1000.00ms"

    Args:
        log_level: Nivel de logging (debug, info, warning, error)

    Returns:
        Decorator que mide y loguea el tiempo
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
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


def sync_timed(log_level: str = "debug"):
    """
    Decorator para medir tiempo de ejecución de funciones síncronas.

    Similar a async_timed pero para funciones sync.

    Uso:
        @sync_timed(log_level="info")
        def slow_function():
            time.sleep(1)

        # Logs: "slow_function tomó 1000.00ms"

    Args:
        log_level: Nivel de logging (debug, info, warning, error)

    Returns:
        Decorator que mide y loguea el tiempo
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                log_func = getattr(logger, log_level)
                log_func(f"{func.__name__} tomó {elapsed:.2f}ms")
        return wrapper
    return decorator


async def batch_gather(*coroutines, return_exceptions: bool = False):
    """
    Ejecuta múltiples coroutines en paralelo con logging mejorado.

    Wrapper sobre asyncio.gather con mejor manejo de errores.

    Uso:
        results = await batch_gather(
            fetch_user(1),
            fetch_gym(2),
            fetch_classes(3),
            return_exceptions=True
        )

    Args:
        *coroutines: Coroutines a ejecutar en paralelo
        return_exceptions: Si True, retorna excepciones en vez de lanzarlas

    Returns:
        Lista de resultados en el mismo orden que las coroutines
    """
    start = time.perf_counter()
    try:
        results = await asyncio.gather(*coroutines, return_exceptions=return_exceptions)

        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(f"batch_gather ejecutó {len(coroutines)} operaciones en {elapsed:.2f}ms")

        return results
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error(f"batch_gather falló después de {elapsed:.2f}ms: {e}")
        raise


class AsyncContextTimer:
    """
    Context manager para medir tiempo de bloques de código async.

    Uso:
        async with AsyncContextTimer("operación compleja"):
            await fetch_data()
            await process_data()
            await save_data()

        # Logs: "operación compleja tomó 250.00ms"
    """

    def __init__(self, name: str, log_level: str = "debug"):
        """
        Inicializa el timer.

        Args:
            name: Nombre de la operación (para logging)
            log_level: Nivel de logging
        """
        self.name = name
        self.log_level = log_level
        self.start_time = None

    async def __aenter__(self):
        """Inicia el timer."""
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finaliza el timer y loguea el resultado."""
        elapsed = (time.perf_counter() - self.start_time) * 1000
        log_func = getattr(logger, self.log_level)

        if exc_type is not None:
            log_func(f"{self.name} falló después de {elapsed:.2f}ms")
        else:
            log_func(f"{self.name} tomó {elapsed:.2f}ms")

        # No suprimir excepciones
        return False
