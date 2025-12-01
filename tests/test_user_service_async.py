"""
Tests async para user_service - Fase 2 Semana 2

Verifica que los métodos async del user_service funcionan correctamente.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user import user_service
from app.models.user import User as UserModel
from app.schemas.user import UserCreate


class TestUserServiceAsync:
    """Tests de métodos async de user_service."""

    @pytest.mark.asyncio
    async def test_get_user_async_not_found(self, async_db_session: AsyncSession):
        """Test get_user_async con usuario inexistente."""
        user = await user_service.get_user_async(async_db_session, user_id=99999)
        assert user is None
        print("✅ get_user_async - usuario no encontrado OK")

    @pytest.mark.asyncio
    async def test_get_users_async_empty(self, async_db_session: AsyncSession):
        """Test get_users_async con BD vacía."""
        users = await user_service.get_users_async(async_db_session, skip=0, limit=10)
        assert isinstance(users, list)
        # La BD de test puede tener o no usuarios
        print(f"✅ get_users_async OK - {len(users)} usuarios encontrados")

    @pytest.mark.asyncio
    async def test_get_user_by_email_async_not_found(self, async_db_session: AsyncSession):
        """Test get_user_by_email_async con email inexistente."""
        user = await user_service.get_user_by_email_async(
            async_db_session,
            email="noexiste@test.com"
        )
        assert user is None
        print("✅ get_user_by_email_async - usuario no encontrado OK")

    @pytest.mark.asyncio
    async def test_get_user_by_auth0_id_async_not_found(self, async_db_session: AsyncSession):
        """Test get_user_by_auth0_id_async_direct con auth0_id inexistente."""
        user = await user_service.get_user_by_auth0_id_async_direct(
            async_db_session,
            auth0_id="auth0|noexiste123"
        )
        assert user is None
        print("✅ get_user_by_auth0_id_async_direct - usuario no encontrado OK")

    @pytest.mark.asyncio
    async def test_create_user_async_basic(self, async_db_session: AsyncSession):
        """Test create_user_async_full con datos básicos."""
        user_data = UserCreate(
            email=f"test_async_{pytest.test_id}@example.com",
            auth0_id=f"auth0|test_async_{pytest.test_id}",
            first_name="Test",
            last_name="Async"
        )

        # Crear usuario
        created_user = await user_service.create_user_async_full(
            async_db_session,
            user_data=user_data,
            redis_client=None  # Sin Redis en tests
        )

        assert created_user is not None
        assert created_user.id is not None
        assert created_user.email == user_data.email
        assert created_user.auth0_id == user_data.auth0_id
        print(f"✅ create_user_async_full OK - usuario {created_user.id} creado")

        # Verificar que se puede obtener
        fetched_user = await user_service.get_user_async(async_db_session, created_user.id)
        assert fetched_user is not None
        assert fetched_user.email == user_data.email
        print(f"✅ Usuario async {created_user.id} verificado en BD")

    @pytest.mark.asyncio
    async def test_get_user_with_eager_load(self, async_db_session: AsyncSession):
        """Test get_user_async con eager loading."""
        # Crear un usuario primero
        user_data = UserCreate(
            email=f"test_eager_{pytest.test_id}@example.com",
            auth0_id=f"auth0|test_eager_{pytest.test_id}",
            first_name="Eager",
            last_name="Loading"
        )

        created_user = await user_service.create_user_async_full(
            async_db_session,
            user_data=user_data
        )

        # Obtener con eager loading
        user_eager = await user_service.get_user_async(
            async_db_session,
            user_id=created_user.id,
            eager_load=True
        )

        assert user_eager is not None
        assert user_eager.id == created_user.id
        # gyms debería estar cargado (aunque esté vacío)
        # No generará queries adicionales al acceder
        print(f"✅ get_user_async con eager_load=True OK - usuario {user_eager.id}")


# Fixture para sesión async (si no existe en conftest.py)
@pytest.fixture
async def async_db_session():
    """Sesión de DB async para tests."""
    from app.db.session import AsyncSessionLocal

    if AsyncSessionLocal is None:
        pytest.skip("AsyncSessionLocal no disponible")

    async with AsyncSessionLocal() as session:
        yield session
        # Cleanup se hace automáticamente al salir del context


# Generar ID único por ejecución de test
@pytest.fixture(scope="session", autouse=True)
def test_id():
    """ID único para esta ejecución de tests."""
    import time
    pytest.test_id = int(time.time() * 1000)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
