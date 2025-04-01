from typing import Optional, List, Dict, Any, Generic, TypeVar, Type, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session

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


gym_repository = GymRepository(Gym) 