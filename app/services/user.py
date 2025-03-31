from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.user import user_repository
from app.schemas.user import UserCreate, UserUpdate, User, UserRoleUpdate, UserProfileUpdate, UserSearchParams
from app.models.user import UserRole


class UserService:
    def get_user(self, db: Session, user_id: int) -> Optional[User]:
        """
        Obtener un usuario por ID.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return user

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Obtener un usuario por email.
        """
        return user_repository.get_by_email(db, email=email)

    def get_user_by_auth0_id(self, db: Session, auth0_id: str) -> Optional[User]:
        """
        Obtener un usuario por ID de Auth0.
        """
        return user_repository.get_by_auth0_id(db, auth0_id=auth0_id)

    def get_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Obtener múltiples usuarios.
        """
        return user_repository.get_multi(db, skip=skip, limit=limit)

    def get_users_by_role(self, db: Session, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Obtener usuarios filtrados por rol.
        """
        return user_repository.get_by_role(db, role=role, skip=skip, limit=limit)

    def search_users(self, db: Session, search_params: UserSearchParams) -> List[User]:
        """
        Búsqueda avanzada de usuarios con múltiples criterios.
        
        Args:
            db: Sesión de base de datos
            search_params: Parámetros de búsqueda (nombre, email, rol, etc.)
            
        Returns:
            List[User]: Lista de usuarios que coinciden con los criterios
        """
        return user_repository.search(
            db,
            name=search_params.name,
            email=search_params.email,
            role=search_params.role,
            is_active=search_params.is_active,
            created_before=search_params.created_before,
            created_after=search_params.created_after,
            skip=search_params.skip,
            limit=search_params.limit
        )

    def create_user(self, db: Session, user_in: UserCreate) -> User:
        """
        Crear un nuevo usuario.
        """
        user = user_repository.get_by_email(db, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail="Ya existe un usuario con este email en el sistema",
            )
        return user_repository.create(db, obj_in=user_in)

    def create_or_update_auth0_user(self, db: Session, auth0_user: Dict) -> User:
        """
        Crear o actualizar un usuario a partir de datos de Auth0.
        """
        auth0_id = auth0_user.get("sub")
        if not auth0_id:
            raise HTTPException(
                status_code=400,
                detail="Los datos de Auth0 no contienen un ID (sub)",
            )
        
        # Primero intentar buscar por Auth0 ID
        user = user_repository.get_by_auth0_id(db, auth0_id=auth0_id)
        if user:
            return user
        
        # Luego intentar buscar por email
        email = auth0_user.get("email")
        if email:
            user = user_repository.get_by_email(db, email=email)
            if user:
                # Actualizar el Auth0 ID si el usuario ya existe
                return user_repository.update(
                    db,
                    db_obj=user,
                    obj_in={"auth0_id": auth0_id, "auth0_metadata": auth0_user},
                )
        
        # Crear un nuevo usuario
        return user_repository.create_from_auth0(db, auth0_user=auth0_user)

    def update_user(self, db: Session, user_id: int, user_in: UserUpdate) -> User:
        """
        Actualizar un usuario.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return user_repository.update(db, db_obj=user, obj_in=user_in)

    def update_user_profile(self, db: Session, user_id: int, profile_in: UserProfileUpdate) -> User:
        """
        Actualizar solo el perfil de un usuario.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return user_repository.update(db, db_obj=user, obj_in=profile_in)

    def update_user_role(self, db: Session, user_id: int, role_update: UserRoleUpdate) -> User:
        """
        Actualizar el rol de un usuario.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
        # Verificar si es un rol válido
        if role_update.role not in [UserRole.ADMIN, UserRole.TRAINER, UserRole.MEMBER]:
            raise HTTPException(status_code=400, detail="Rol no válido")
            
        return user_repository.update(db, db_obj=user, obj_in={"role": role_update.role})

    def delete_user(self, db: Session, user_id: int) -> User:
        """
        Eliminar un usuario.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return user_repository.remove(db, id=user_id)

    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """
        Autenticar un usuario.
        """
        user = user_repository.authenticate(db, email=email, password=password)
        return user

    def is_active(self, user: User) -> bool:
        """
        Verificar si un usuario está activo.
        """
        return user_repository.is_active(user)

    def is_superuser(self, user: User) -> bool:
        """
        Verificar si un usuario es superusuario.
        """
        return user_repository.is_superuser(user)

    def has_role(self, user: User, role: UserRole) -> bool:
        """
        Verificar si un usuario tiene un rol específico.
        """
        return user.role == role
        
    def create_admin_from_auth0(self, db: Session, auth0_user: Dict) -> User:
        """
        Crear o actualizar un usuario de Auth0 como administrador con todos los permisos.
        Este método debe usarse con precaución, ya que otorga privilegios de administrador.
        """
        # Asegurarse de que el usuario tenga un email, aunque sea generado
        auth0_id = auth0_user.get("sub")
        if not auth0_user.get("email") and auth0_id:
            auth0_user["email"] = f"admin_{auth0_id.replace('|', '_')}@example.com"
            
        # Primero crear o actualizar el usuario usando el método existente
        user = self.create_or_update_auth0_user(db, auth0_user)
        
        # Luego actualizar su rol a ADMIN y marcarlo como superusuario
        user = user_repository.update(
            db, 
            db_obj=user, 
            obj_in={
                "role": UserRole.ADMIN,
                "is_superuser": True
            }
        )
        
        return user


user_service = UserService() 