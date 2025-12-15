"""
Tests de infraestructura async - Fase 2 Semana 1

Este módulo verifica que la infraestructura async básica funciona correctamente:
- Async database engine (asyncpg)
- Async session management
- Async utilities
"""

import pytest
import asyncio
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

# Importar infraestructura async
from app.db.session import async_engine, AsyncSessionLocal, get_async_db


class TestAsyncInfrastructure:
    """Tests de infraestructura async básica."""

    @pytest.mark.asyncio
    async def test_async_engine_initialized(self):
        """Verifica que el async engine está inicializado."""
        assert async_engine is not None, "Async engine debe estar inicializado"
        print("✅ Async engine inicializado correctamente")

    @pytest.mark.asyncio
    async def test_async_session_maker_initialized(self):
        """Verifica que AsyncSessionLocal está inicializado."""
        assert AsyncSessionLocal is not None, "AsyncSessionLocal debe estar inicializado"
        print("✅ AsyncSessionLocal inicializado correctamente")

    @pytest.mark.asyncio
    async def test_async_connection(self):
        """Verifica que se puede conectar a la DB con async engine."""
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            value = result.scalar()
            assert value == 1, "Query de prueba debe retornar 1"
            print(f"✅ Async connection OK: test query returned {value}")

    @pytest.mark.asyncio
    async def test_async_session_basic(self):
        """Verifica que se puede crear una sesión async básica."""
        async with AsyncSessionLocal() as session:
            assert isinstance(session, AsyncSession), "Debe ser instancia de AsyncSession"
            result = await session.execute(text("SELECT 1 as test"))
            value = result.scalar()
            assert value == 1, "Query en sesión async debe funcionar"
            print(f"✅ Async session OK: test query returned {value}")

    @pytest.mark.asyncio
    async def test_async_session_with_search_path(self):
        """Verifica que search_path está configurado automáticamente desde server_settings."""
        async with AsyncSessionLocal() as session:
            # search_path ya está configurado en server_settings del engine
            # NO ejecutar SET aquí para evitar conflictos con pgbouncer

            # Verificar search_path
            result = await session.execute(text("SHOW search_path"))
            search_path = result.scalar()
            assert "public" in search_path, "search_path debe incluir 'public'"
            print(f"✅ Search path configurado automáticamente: {search_path}")

    @pytest.mark.asyncio
    async def test_get_async_db_dependency(self):
        """Verifica que la dependencia get_async_db funciona."""
        async for session in get_async_db():
            assert isinstance(session, AsyncSession), "Debe retornar AsyncSession"

            # Test query
            result = await session.execute(text("SELECT 1 as test"))
            value = result.scalar()
            assert value == 1, "Query debe funcionar en dependencia"
            print(f"✅ get_async_db dependency OK: {value}")

    @pytest.mark.asyncio
    async def test_async_transaction_commit(self):
        """Verifica que se pueden hacer commits en transacciones async."""
        async with AsyncSessionLocal() as session:
            # Ejecutar query simple que no modifica datos
            result = await session.execute(text("SELECT 1 as test"))
            value = result.scalar()

            await session.commit()
            assert value == 1
            print("✅ Async transaction commit OK")

    @pytest.mark.asyncio
    async def test_async_transaction_rollback(self):
        """Verifica que se pueden hacer rollbacks en transacciones async."""
        async with AsyncSessionLocal() as session:
            # Ejecutar query simple
            result = await session.execute(text("SELECT 1 as test"))
            value = result.scalar()

            await session.rollback()
            assert value == 1
            print("✅ Async transaction rollback OK")

    @pytest.mark.asyncio
    async def test_async_pool_size(self):
        """Verifica que el pool de conexiones async está configurado correctamente."""
        assert async_engine.pool.size() >= 0, "Pool debe estar inicializado"
        print(f"✅ Async pool initialized with size: {async_engine.pool.size()}")

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self):
        """Verifica que se pueden manejar múltiples sesiones concurrentes."""
        async def query_task(session_num):
            async with AsyncSessionLocal() as session:
                result = await session.execute(text(f"SELECT {session_num} as test"))
                return result.scalar()

        # Crear 5 tareas concurrentes
        tasks = [query_task(i) for i in range(1, 6)]
        results = await asyncio.gather(*tasks)

        assert results == [1, 2, 3, 4, 5], "Todas las queries deben retornar sus valores"
        print(f"✅ Multiple concurrent sessions OK: {results}")

    @pytest.mark.asyncio
    async def test_async_utilities_import(self):
        """Verifica que las utilidades async se pueden importar."""
        from app.core.async_utils import (
            run_sync_in_async,
            run_sync_query,
            DualModeRepository,
            async_timed,
            batch_gather,
            AsyncContextTimer
        )

        assert run_sync_in_async is not None
        assert run_sync_query is not None
        assert DualModeRepository is not None
        assert async_timed is not None
        assert batch_gather is not None
        assert AsyncContextTimer is not None
        print("✅ Async utilities importadas correctamente")

    @pytest.mark.asyncio
    async def test_async_timed_decorator(self):
        """Verifica que el decorator async_timed funciona."""
        from app.core.async_utils import async_timed

        @async_timed(log_level="debug")
        async def test_function():
            await asyncio.sleep(0.01)  # 10ms
            return "success"

        result = await test_function()
        assert result == "success"
        print("✅ async_timed decorator OK")

    @pytest.mark.asyncio
    async def test_batch_gather_utility(self):
        """Verifica que batch_gather funciona correctamente."""
        from app.core.async_utils import batch_gather

        async def task1():
            await asyncio.sleep(0.01)
            return 1

        async def task2():
            await asyncio.sleep(0.01)
            return 2

        async def task3():
            await asyncio.sleep(0.01)
            return 3

        results = await batch_gather(task1(), task2(), task3())
        assert results == [1, 2, 3]
        print("✅ batch_gather utility OK")

    @pytest.mark.asyncio
    async def test_async_context_timer(self):
        """Verifica que AsyncContextTimer funciona."""
        from app.core.async_utils import AsyncContextTimer

        async with AsyncContextTimer("test operation"):
            await asyncio.sleep(0.01)
            # Timer debe loguear automáticamente

        print("✅ AsyncContextTimer OK")


if __name__ == "__main__":
    # Permitir ejecutar tests directamente
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
