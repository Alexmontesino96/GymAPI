"""
Tests para AsyncBaseRepository - FASE 1
Verifica que las operaciones CRUD async funcionan correctamente.

NOTA: Los tests usan flush() + rollback() en lugar de commit()
para ser compatibles con pgbouncer (Supabase Transaction Pooler).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.async_base import AsyncBaseRepository
from app.models.user import User
from app.models.gym import Gym
from app.schemas.user import UserCreate, UserUpdate
from app.db.session import AsyncSessionLocal


class TestAsyncBaseRepositoryGet:
    """Tests para el método get() async."""

    @pytest.mark.asyncio
    async def test_get_existing_user(self):
        """Verifica que get() puede obtener un usuario existente."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)
                user_data = UserCreate(
                    email="test_get@example.com",
                    first_name="Test",
                    last_name="Get",
                    auth0_id="test_get_123"
                )

                created_user = await repo.create(db, obj_in=user_data)
                await db.flush()

                # Obtener usuario
                fetched_user = await repo.get(db, id=created_user.id)

                assert fetched_user is not None
                assert fetched_user.id == created_user.id
                assert fetched_user.email == "test_get@example.com"
                print("✅ test_get_existing_user passed")
            finally:
                await db.rollback()

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self):
        """Verifica que get() retorna None para un ID que no existe."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)
                fetched_user = await repo.get(db, id=999999)
                assert fetched_user is None
                print("✅ test_get_nonexistent_user passed")
            finally:
                await db.rollback()


class TestAsyncBaseRepositoryGetMulti:
    """Tests para el método get_multi() async."""

    @pytest.mark.asyncio
    async def test_get_multi_basic(self):
        """Verifica que get_multi() retorna múltiples usuarios."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # Crear varios usuarios
                users_to_create = [
                    UserCreate(
                        email=f"user{i}@test.com",
                        first_name=f"User",
                        last_name=f"{i}",
                        auth0_id=f"test_multi_{i}"
                    )
                    for i in range(5)
                ]

                created_users = []
                for user_data in users_to_create:
                    user = await repo.create(db, obj_in=user_data)
                    created_users.append(user)
                await db.flush()

                # Obtener múltiples usuarios
                users = await repo.get_multi(db, skip=0, limit=10)

                assert len(users) >= 5  # Al menos los 5 que creamos
                assert all(isinstance(u, User) for u in users)
                print("✅ test_get_multi_basic passed")
            finally:
                await db.rollback()

    @pytest.mark.asyncio
    async def test_get_multi_pagination(self):
        """Verifica que get_multi() pagina correctamente."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # Crear 10 usuarios
                created_users = []
                for i in range(10):
                    user = await repo.create(
                        db,
                        obj_in=UserCreate(
                            email=f"pagination{i}@test.com",
                            first_name="Page",
                            last_name=str(i),
                            auth0_id=f"test_page_{i}"
                        )
                    )
                    created_users.append(user)
                await db.flush()

                # Primera página
                page1 = await repo.get_multi(db, skip=0, limit=5)
                assert len(page1) <= 5

                # Segunda página
                page2 = await repo.get_multi(db, skip=5, limit=5)
                assert len(page2) <= 5

                print("✅ test_get_multi_pagination passed")
            finally:
                await db.rollback()


class TestAsyncBaseRepositoryCreate:
    """Tests para el método create() async."""

    @pytest.mark.asyncio
    async def test_create_user_with_schema(self):
        """Verifica que create() puede crear un usuario con schema Pydantic."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                user_data = UserCreate(
                    email="create_test@example.com",
                    first_name="Create",
                    last_name="Test",
                    auth0_id="test_create_schema"
                )

                created_user = await repo.create(db, obj_in=user_data)
                await db.flush()

                assert created_user.id is not None
                assert created_user.email == "create_test@example.com"
                assert created_user.first_name == "Create"

                print("✅ test_create_user_with_schema passed")
            finally:
                await db.rollback()

    @pytest.mark.asyncio
    async def test_create_user_with_dict(self):
        """Verifica que create() puede crear un usuario con dict."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                user_data = {
                    "email": "create_dict@example.com",
                    "first_name": "Dict",
                    "last_name": "Create",
                    "auth0_id": "test_create_dict"
                }

                created_user = await repo.create(db, obj_in=user_data)
                await db.flush()

                assert created_user.id is not None
                assert created_user.email == "create_dict@example.com"

                print("✅ test_create_user_with_dict passed")
            finally:
                await db.rollback()


class TestAsyncBaseRepositoryUpdate:
    """Tests para el método update() async."""

    @pytest.mark.asyncio
    async def test_update_user_with_schema(self):
        """Verifica que update() puede actualizar un usuario."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # Crear usuario
                user = await repo.create(
                    db,
                    obj_in=UserCreate(
                        email="before_update@example.com",
                        first_name="Before",
                        last_name="Update",
                        auth0_id="test_update_before"
                    )
                )
                await db.flush()

                # Actualizar usuario
                update_data = UserUpdate(
                    first_name="After",
                    last_name="Updated"
                )

                updated_user = await repo.update(db, db_obj=user, obj_in=update_data)
                await db.flush()

                assert updated_user.first_name == "After"
                assert updated_user.last_name == "Updated"
                assert updated_user.email == "before_update@example.com"  # No cambió

                print("✅ test_update_user_with_schema passed")
            finally:
                await db.rollback()

    @pytest.mark.asyncio
    async def test_update_user_with_dict(self):
        """Verifica que update() funciona con dict."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # Crear usuario
                user = await repo.create(
                    db,
                    obj_in=UserCreate(
                        email="dict_update@example.com",
                        first_name="Original",
                        last_name="Name",
                        auth0_id="test_update_dict"
                    )
                )
                await db.flush()

                # Actualizar con dict
                updated = await repo.update(
                    db,
                    db_obj=user,
                    obj_in={"first_name": "Modified"}
                )
                await db.flush()

                assert updated.first_name == "Modified"
                assert updated.last_name == "Name"  # Sin cambios

                print("✅ test_update_user_with_dict passed")
            finally:
                await db.rollback()


class TestAsyncBaseRepositoryRemove:
    """Tests para el método remove() async."""

    @pytest.mark.asyncio
    async def test_remove_existing_user(self):
        """Verifica que remove() puede eliminar un usuario existente."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # Crear usuario
                user = await repo.create(
                    db,
                    obj_in=UserCreate(
                        email="to_delete@example.com",
                        first_name="Delete",
                        last_name="Me",
                        auth0_id="test_delete_me"
                    )
                )
                await db.flush()
                user_id = user.id

                # Eliminar usuario
                removed = await repo.remove(db, id=user_id)
                await db.flush()

                assert removed.id == user_id

                # Verificar que ya no existe (después del flush)
                fetched = await repo.get(db, id=user_id)
                assert fetched is None

                print("✅ test_remove_existing_user passed")
            finally:
                await db.rollback()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_user_raises_error(self):
        """Verifica que remove() lanza error para ID inexistente."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                with pytest.raises(ValueError, match="no encontrado"):
                    await repo.remove(db, id=999999)

                print("✅ test_remove_nonexistent_user_raises_error passed")
            finally:
                await db.rollback()


class TestAsyncBaseRepositoryExists:
    """Tests para el método exists() async."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_user(self):
        """Verifica que exists() retorna True para usuario existente."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # Crear usuario
                user = await repo.create(
                    db,
                    obj_in=UserCreate(
                        email="exists_test@example.com",
                        first_name="Exists",
                        last_name="Test",
                        auth0_id="test_exists_true"
                    )
                )
                await db.flush()

                # Verificar existencia
                does_exist = await repo.exists(db, id=user.id)

                assert does_exist is True

                print("✅ test_exists_returns_true_for_existing_user passed")
            finally:
                await db.rollback()

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_nonexistent_user(self):
        """Verifica que exists() retorna False para usuario inexistente."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                does_exist = await repo.exists(db, id=999999)

                assert does_exist is False

                print("✅ test_exists_returns_false_for_nonexistent_user passed")
            finally:
                await db.rollback()


# Test de integración completo
class TestAsyncBaseRepositoryIntegration:
    """Test de integración del ciclo completo CRUD."""

    @pytest.mark.asyncio
    async def test_full_crud_cycle(self):
        """Verifica el ciclo completo: Create → Read → Update → Delete."""
        async with AsyncSessionLocal() as db:
            try:
                repo = AsyncBaseRepository(User)

                # 1. CREATE
                user = await repo.create(
                    db,
                    obj_in=UserCreate(
                        email="fullcycle@example.com",
                        first_name="Full",
                        last_name="Cycle",
                        auth0_id="test_full_cycle"
                    )
                )
                await db.flush()
                assert user.id is not None
                print(f"  ✅ Created user with ID {user.id}")

                # 2. READ
                fetched = await repo.get(db, id=user.id)
                assert fetched is not None
                assert fetched.email == "fullcycle@example.com"
                print(f"  ✅ Read user {fetched.id}")

                # 3. UPDATE
                updated = await repo.update(
                    db,
                    db_obj=fetched,
                    obj_in={"first_name": "Updated"}
                )
                await db.flush()
                assert updated.first_name == "Updated"
                print(f"  ✅ Updated user {updated.id}")

                # 4. DELETE
                removed = await repo.remove(db, id=updated.id)
                await db.flush()
                print(f"  ✅ Removed user {removed.id}")

                # 5. VERIFY DELETION
                deleted_check = await repo.get(db, id=user.id)
                assert deleted_check is None
                print("  ✅ Verified deletion")

                print("✅ test_full_crud_cycle passed")
            finally:
                await db.rollback()
