from typing import Optional, List, Dict, Any, Generic, TypeVar, Type, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from fastapi.encoders import jsonable_encoder

from app.models.gym import Gym
from app.repositories.base import BaseRepository
from app.schemas.gym import GymCreate, GymUpdate

class GymRepository(BaseRepository[Gym, GymCreate, GymUpdate]):
    """Repositorio para operaciones CRUD sobre gimnasios (tenants)"""
    
    def get_by_subdomain(self, db: Session, *, subdomain: str) -> Optional[Gym]:
        """
        Obtener un gimnasio por su subdominio.
        
        Args:
            db: Sesión de base de datos
            subdomain: Subdominio único del gimnasio
            
        Returns:
            El gimnasio o None si no existe
        """
        return db.query(self.model).filter(Gym.subdomain == subdomain).first()
    
    def get_active_gyms(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Gym]:
        """
        Obtener gimnasios activos.
        
        Args:
            db: Sesión de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            
        Returns:
            Lista de gimnasios activos
        """
        return db.query(self.model).filter(Gym.is_active == True).offset(skip).limit(limit).all()
    
    def search_gyms(
        self, 
        db: Session, 
        *, 
        term: str = None, 
        is_active: bool = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Gym]:
        """
        Buscar gimnasios por nombre o subdominio.
        
        Args:
            db: Sesión de base de datos
            term: Término de búsqueda (parcial de nombre o subdominio)
            is_active: Filtrar por estado activo/inactivo
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            
        Returns:
            Lista de gimnasios que coinciden con la búsqueda
        """
        query = db.query(self.model)
        
        if term:
            query = query.filter(
                (Gym.name.ilike(f"%{term}%")) | (Gym.subdomain.ilike(f"%{term}%"))
            )
        
        if is_active is not None:
            query = query.filter(Gym.is_active == is_active)

        return query.offset(skip).limit(limit).all()

    # ==========================================
    # Métodos async específicos de Gym
    # ==========================================

    async def get_by_subdomain_async(self, db: AsyncSession, *, subdomain: str) -> Optional[Gym]:
        """
        Obtener un gimnasio por su subdominio (async).

        Args:
            db: Sesión de base de datos async
            subdomain: Subdominio único del gimnasio

        Returns:
            El gimnasio o None si no existe
        """
        stmt = select(Gym).where(Gym.subdomain == subdomain)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_gyms_async(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[Gym]:
        """
        Obtener gimnasios activos (async).

        Args:
            db: Sesión de base de datos async
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de gimnasios activos
        """
        stmt = select(Gym).where(Gym.is_active == True).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def search_gyms_async(
        self,
        db: AsyncSession,
        *,
        term: str = None,
        is_active: bool = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Gym]:
        """
        Buscar gimnasios por nombre o subdominio (async).

        Args:
            db: Sesión de base de datos async
            term: Término de búsqueda (parcial de nombre o subdominio)
            is_active: Filtrar por estado activo/inactivo
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de gimnasios que coinciden con la búsqueda
        """
        stmt = select(Gym)

        if term:
            stmt = stmt.where(
                or_(
                    Gym.name.ilike(f"%{term}%"),
                    Gym.subdomain.ilike(f"%{term}%")
                )
            )

        if is_active is not None:
            stmt = stmt.where(Gym.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    # ==========================================
    # Métodos async heredados de BaseRepository
    # ==========================================

    async def get_async(self, db: AsyncSession, id: Any, gym_id: Optional[int] = None) -> Optional[Gym]:
        """
        Obtener un gimnasio por ID (async).

        Note: gym_id parameter is ignored for Gym model (no multi-tenant filtering needed
        since Gym IS the tenant).

        Args:
            db: Sesión de base de datos async
            id: ID del gimnasio a obtener
            gym_id: Ignorado para modelo Gym

        Returns:
            El gimnasio o None si no existe
        """
        stmt = select(Gym).where(Gym.id == id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_async(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Gym]:
        """
        Obtener múltiples gimnasios con filtros opcionales (async).

        Note: gym_id parameter is ignored for Gym model.

        Args:
            db: Sesión de base de datos async
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            gym_id: Ignorado para modelo Gym
            filters: Diccionario de filtros adicionales {campo: valor}

        Returns:
            Lista de gimnasios que coinciden con los criterios
        """
        stmt = select(Gym)

        # Aplicar filtros adicionales si se proporcionan
        if filters:
            for field, value in filters.items():
                if hasattr(Gym, field):
                    stmt = stmt.where(getattr(Gym, field) == value)

        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def create_async(self, db: AsyncSession, *, obj_in: GymCreate, gym_id: Optional[int] = None) -> Gym:
        """
        Crear un nuevo gimnasio (async).

        Note: gym_id parameter is ignored for Gym model.

        Args:
            db: Sesión de base de datos async
            obj_in: Datos del gimnasio a crear
            gym_id: Ignorado para modelo Gym

        Returns:
            El gimnasio creado
        """
        if hasattr(obj_in, 'model_dump'):
            obj_in_data = obj_in.model_dump()
        elif hasattr(obj_in, '__dict__'):
            obj_in_data = obj_in.__dict__.copy()
        else:
            obj_in_data = jsonable_encoder(obj_in)

        db_obj = Gym(**obj_in_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update_async(
        self,
        db: AsyncSession,
        *,
        db_obj: Gym,
        obj_in: Union[GymUpdate, Dict[str, Any]],
        gym_id: Optional[int] = None
    ) -> Gym:
        """
        Actualizar un gimnasio (async).

        Note: gym_id parameter is ignored for Gym model.

        Args:
            db: Sesión de base de datos async
            db_obj: Gimnasio existente a actualizar
            obj_in: Datos de actualización
            gym_id: Ignorado para modelo Gym

        Returns:
            El gimnasio actualizado
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        elif hasattr(obj_in, 'model_dump'):
            update_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, '__dict__'):
            update_data = {k: v for k, v in obj_in.__dict__.items() if v is not None}
        else:
            update_data = obj_in

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def remove_async(self, db: AsyncSession, *, id: int, gym_id: Optional[int] = None) -> Gym:
        """
        Eliminar un gimnasio (async).

        Note: gym_id parameter is ignored for Gym model.

        Args:
            db: Sesión de base de datos async
            id: ID del gimnasio a eliminar
            gym_id: Ignorado para modelo Gym

        Returns:
            El gimnasio eliminado

        Raises:
            ValueError: Si el gimnasio no existe
        """
        gym = await self.get_async(db, id=id)
        if not gym:
            raise ValueError(f"Gimnasio con ID {id} no encontrado")

        await db.delete(gym)
        await db.flush()
        return gym

    async def exists_async(self, db: AsyncSession, id: int, gym_id: Optional[int] = None) -> bool:
        """
        Verificar si un gimnasio existe (async).

        Note: gym_id parameter is ignored for Gym model.

        Args:
            db: Sesión de base de datos async
            id: ID del gimnasio a verificar
            gym_id: Ignorado para modelo Gym

        Returns:
            True si el gimnasio existe, False en caso contrario
        """
        stmt = select(Gym.id).where(Gym.id == id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


gym_repository = GymRepository(Gym) 