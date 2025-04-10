from typing import List, Optional, Dict, Any, Union, cast
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.models.user import User
from app.models.event import Event
from app.models.schedule import ClassSession

from app.schemas.gym import GymCreate, GymUpdate, GymWithStats
from app.repositories.gym import gym_repository
from fastapi import HTTPException

class GymService:
    def create_gym(self, db: Session, *, gym_in: GymCreate) -> Gym:
        """
        Crear un nuevo gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_in: Datos del gimnasio a crear
            
        Returns:
            El gimnasio creado
        """
        return gym_repository.create(db, obj_in=gym_in)
    
    def get_gym(self, db: Session, gym_id: int) -> Optional[Gym]:
        """
        Obtener un gimnasio por su ID.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            El gimnasio o None si no existe
        """
        return gym_repository.get(db, id=gym_id)
    
    def get_gym_by_subdomain(self, db: Session, subdomain: str) -> Optional[Gym]:
        """
        Obtener un gimnasio por su subdominio.
        
        Args:
            db: Sesión de base de datos
            subdomain: Subdominio del gimnasio
            
        Returns:
            El gimnasio o None si no existe
        """
        return db.query(Gym).filter(Gym.subdomain == subdomain).first()
    
    def get_gyms(
        self, db: Session, *, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None
    ) -> List[Gym]:
        """
        Obtener lista de gimnasios con filtros opcionales.
        
        Args:
            db: Sesión de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            is_active: Filtrar por estado activo/inactivo
            
        Returns:
            Lista de gimnasios
        """
        query = db.query(Gym)
        
        if is_active is not None:
            query = query.filter(Gym.is_active == is_active)
            
        return query.offset(skip).limit(limit).all()
    
    def update_gym(
        self, db: Session, *, gym: Gym, gym_in: Union[GymUpdate, Dict[str, Any]]
    ) -> Gym:
        """
        Actualizar un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym: Objeto gimnasio a actualizar
            gym_in: Datos actualizados
            
        Returns:
            El gimnasio actualizado
        """
        return gym_repository.update(db, db_obj=gym, obj_in=gym_in)
    
    def update_gym_status(self, db: Session, *, gym_id: int, is_active: bool) -> Gym:
        """
        Actualizar el estado de un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            is_active: Nuevo estado
            
        Returns:
            El gimnasio actualizado
            
        Raises:
            HTTPException: Si el gimnasio no existe
        """
        gym = self.get_gym(db, gym_id=gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado")
            
        return gym_repository.update(db, db_obj=gym, obj_in={"is_active": is_active})
    
    def delete_gym(self, db: Session, *, gym_id: int) -> Gym:
        """
        Eliminar un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            El gimnasio eliminado
            
        Raises:
            HTTPException: Si el gimnasio no existe
        """
        gym = self.get_gym(db, gym_id=gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado")
            
        return gym_repository.remove(db, id=gym_id)
    
    def add_user_to_gym(
        self, db: Session, *, gym_id: int, user_id: int, role: GymRoleType = GymRoleType.MEMBER
    ) -> UserGym:
        """
        Añadir un usuario a un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario
            role: Rol del usuario en el gimnasio
            
        Returns:
            La asociación usuario-gimnasio creada
            
        Raises:
            ValueError: Si el usuario ya pertenece al gimnasio
        """
        # Verificar si el usuario ya pertenece al gimnasio
        existing = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        if existing:
            # Si ya existe pero con un rol diferente, actualizar el rol
            if existing.role != role:
                existing.role = role
                db.commit()
                db.refresh(existing)
            return existing
        
        # Crear nueva asociación
        user_gym = UserGym(
            user_id=user_id,
            gym_id=gym_id,
            role=role
        )
        
        db.add(user_gym)
        db.commit()
        db.refresh(user_gym)
        return user_gym
    
    def remove_user_from_gym(self, db: Session, *, gym_id: int, user_id: int) -> None:
        """
        Eliminar un usuario de un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario
            
        Raises:
            ValueError: Si el usuario no pertenece al gimnasio
        """
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        if not user_gym:
            raise ValueError(f"El usuario {user_id} no pertenece al gimnasio {gym_id}")
            
        db.delete(user_gym)
        db.commit()
    
    def update_user_role(
        self, db: Session, *, gym_id: int, user_id: int, role: GymRoleType
    ) -> UserGym:
        """
        Actualizar el rol de un usuario en un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario
            role: Nuevo rol
            
        Returns:
            La asociación actualizada
            
        Raises:
            ValueError: Si el usuario no pertenece al gimnasio
        """
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        if not user_gym:
            raise ValueError(f"El usuario {user_id} no pertenece al gimnasio {gym_id}")
            
        user_gym.role = role
        db.commit()
        db.refresh(user_gym)
        return user_gym
    
    def get_user_gyms(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los gimnasios a los que pertenece un usuario.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            
        Returns:
            Lista de gimnasios con el rol del usuario en cada uno
        """
        user_gyms = db.query(UserGym, Gym).join(
            Gym, UserGym.gym_id == Gym.id
        ).filter(
            UserGym.user_id == user_id,
            Gym.is_active == True
        ).offset(skip).limit(limit).all()
        
        result = []
        for user_gym, gym in user_gyms:
            gym_dict = {
                "id": gym.id,
                "name": gym.name,
                "subdomain": gym.subdomain,
                "logo_url": gym.logo_url,
                "is_active": gym.is_active,
                "role": user_gym.role.value
            }
            result.append(gym_dict)
            
        return result
    
    def get_gym_users(
        self, 
        db: Session, 
        *, 
        gym_id: int, 
        role: Optional[GymRoleType] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los usuarios de un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            role: Filtrar por rol específico
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            
        Returns:
            Lista de usuarios con su rol en el gimnasio
        """
        query = db.query(UserGym, User).join(
            User, UserGym.user_id == User.id
        ).filter(
            UserGym.gym_id == gym_id
        )
        
        if role:
            query = query.filter(UserGym.role == role)
            
        users = query.offset(skip).limit(limit).all()
        
        result = []
        for user_gym, user in users:
            user_dict = {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user_gym.role.value,
                "joined_at": user_gym.created_at
            }
            result.append(user_dict)
            
        return result
    
    def get_gym_with_stats(self, db: Session, *, gym_id: int) -> Optional[GymWithStats]:
        """
        Obtener un gimnasio con estadísticas básicas.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Gimnasio con estadísticas o None si no existe
        """
        gym = self.get_gym(db, gym_id=gym_id)
        if not gym:
            return None
        
        # Contar usuarios por rol
        role_counts = db.query(
            UserGym.role,
            func.count(UserGym.id).label("count")
        ).filter(
            UserGym.gym_id == gym_id
        ).group_by(UserGym.role).all()
        
        # Inicializar contadores
        members_count = 0
        trainers_count = 0
        admins_count = 0
        
        # Asignar contadores según roles
        for role, count in role_counts:
            if role == GymRoleType.MEMBER:
                members_count = count
            elif role == GymRoleType.TRAINER:
                trainers_count = count
            elif role in (GymRoleType.ADMIN, GymRoleType.OWNER):
                admins_count += count
        
        # Contar eventos
        events_count = db.query(func.count(Event.id)).filter(
            Event.gym_id == gym_id
        ).scalar() or 0
        
        # Contar clases
        classes_count = db.query(func.count(ClassSession.id)).filter(
            ClassSession.gym_id == gym_id
        ).scalar() or 0
        
        # Crear objeto con estadísticas
        gym_dict = {
            "id": gym.id,
            "name": gym.name,
            "subdomain": gym.subdomain,
            "logo_url": gym.logo_url,
            "address": gym.address,
            "phone": gym.phone,
            "email": gym.email,
            "description": gym.description,
            "is_active": gym.is_active,
            "created_at": gym.created_at,
            "updated_at": gym.updated_at,
            "members_count": members_count,
            "trainers_count": trainers_count,
            "admins_count": admins_count,
            "events_count": events_count,
            "classes_count": classes_count
        }
        
        return GymWithStats(**gym_dict)
    
    def check_user_in_gym(
        self, db: Session, *, user_id: int, gym_id: int
    ) -> Optional[UserGym]:
        """
        Verificar si un usuario pertenece a un gimnasio.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            
        Returns:
            La asociación usuario-gimnasio o None si no existe
        """
        return db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
    
    def check_user_role_in_gym(
        self, db: Session, *, user_id: int, gym_id: int, required_roles: List[GymRoleType]
    ) -> bool:
        """
        Verificar si un usuario tiene uno de los roles requeridos en un gimnasio.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            required_roles: Lista de roles aceptables
            
        Returns:
            True si el usuario tiene uno de los roles requeridos, False en caso contrario
        """
        user_gym = self.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
        if not user_gym:
            return False
            
        return user_gym.role in required_roles


gym_service = GymService() 