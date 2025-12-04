"""
AsyncGymRepository - Repositorio async para operaciones de gimnasios (tenants).

Este repositorio hereda de AsyncBaseRepository y agrega métodos específicos
para operaciones de gimnasios con full async/await.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.gym import Gym
from app.repositories.async_base import AsyncBaseRepository
from app.schemas.gym import GymCreate, GymUpdate


class AsyncGymRepository(AsyncBaseRepository[Gym, GymCreate, GymUpdate]):
    """
    Repositorio async para operaciones CRUD sobre gimnasios (tenants).

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener gimnasio por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples gimnasios
    - create(db, obj_in, gym_id) - Crear gimnasio
    - update(db, db_obj, obj_in, gym_id) - Actualizar gimnasio
    - remove(db, id, gym_id) - Eliminar gimnasio
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos de Gym:
    - get_by_subdomain() - Buscar por subdominio único
    - get_active_gyms() - Obtener gimnasios activos
    - search_gyms() - Búsqueda por nombre/subdominio

    Nota: El parámetro gym_id es ignorado para Gym model ya que Gym ES el tenant.
    """

    async def get_by_subdomain(self, db: AsyncSession, *, subdomain: str) -> Optional[Gym]:
        """
        Obtener un gimnasio por su subdominio único.

        Args:
            db: Sesión de base de datos async
            subdomain: Subdominio único del gimnasio

        Returns:
            El gimnasio o None si no existe

        Example:
            gym = await async_gym_repository.get_by_subdomain(db, subdomain="mi-gym")
        """
        stmt = select(Gym).where(Gym.subdomain == subdomain)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_gyms(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Gym]:
        """
        Obtener gimnasios activos con paginación.

        Args:
            db: Sesión de base de datos async
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de gimnasios activos

        Example:
            active_gyms = await async_gym_repository.get_active_gyms(
                db,
                skip=0,
                limit=20
            )
        """
        stmt = select(Gym).where(Gym.is_active == True).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def search_gyms(
        self,
        db: AsyncSession,
        *,
        term: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Gym]:
        """
        Buscar gimnasios por nombre o subdominio.

        Búsqueda case-insensitive usando ILIKE.

        Args:
            db: Sesión de base de datos async
            term: Término de búsqueda parcial (nombre o subdominio)
            is_active: Filtrar por estado activo/inactivo (opcional)
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de gimnasios que coinciden con la búsqueda

        Example:
            # Buscar por término
            results = await async_gym_repository.search_gyms(
                db,
                term="fitness",
                is_active=True
            )

            # Obtener solo activos
            active = await async_gym_repository.search_gyms(
                db,
                is_active=True,
                limit=50
            )
        """
        stmt = select(Gym)

        # Búsqueda parcial en nombre o subdominio
        if term:
            stmt = stmt.where(
                or_(
                    Gym.name.ilike(f"%{term}%"),
                    Gym.subdomain.ilike(f"%{term}%")
                )
            )

        # Filtrar por estado activo
        if is_active is not None:
            stmt = stmt.where(Gym.is_active == is_active)

        # Aplicar paginación
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())


# Instancia singleton del repositorio async
async_gym_repository = AsyncGymRepository(Gym)
