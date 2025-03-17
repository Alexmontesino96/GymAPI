from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session

from app.core.auth0_fastapi import auth, get_current_user, get_current_user_with_permissions, Auth0User
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.user import user_service
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate, UserRoleUpdate, UserProfileUpdate

router = APIRouter()


@router.get("/", response_model=List[UserSchema])
async def read_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user, scopes=[]),
) -> Any:
    """
    Recupera todos los usuarios.
    """
    users = user_service.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/by-role/{role}", response_model=List[UserSchema])
async def read_users_by_role(
    role: UserRole,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user),
) -> Any:
    """
    Recupera usuarios filtrados por rol.
    """
    users = user_service.get_users_by_role(db, role=role, skip=skip, limit=limit)
    return users


@router.get("/trainers", response_model=List[UserSchema])
async def read_trainers(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user),
) -> Any:
    """
    Recupera todos los entrenadores.
    """
    trainers = user_service.get_users_by_role(db, role=UserRole.TRAINER, skip=skip, limit=limit)
    return trainers


@router.get("/members", response_model=List[UserSchema])
async def read_members(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user),
) -> Any:
    """
    Recupera todos los miembros.
    """
    members = user_service.get_users_by_role(db, role=UserRole.MEMBER, skip=skip, limit=limit)
    return members


@router.post("/", response_model=UserSchema)
async def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user_with_permissions),
) -> Any:
    """
    Crear un nuevo usuario.
    Solo para administradores.
    """
    user = user_service.create_user(db, user_in=user_in)
    return user


@router.get("/profile", response_model=UserSchema)
async def get_user_profile(
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Obtiene el perfil del usuario autenticado.
    Si el usuario no existe en la base de datos local, crea un perfil básico.
    """
    # Obtener el ID de Auth0
    auth0_id = user.id
    
    if not auth0_id:
        raise HTTPException(
            status_code=400,
            detail="El token no contiene información de usuario (sub)",
        )
    
    # Sincronizar el usuario con la base de datos local
    user_data = {
        "sub": auth0_id,
        "email": getattr(user, "email", None)
    }
    db_user = user_service.create_or_update_auth0_user(db, user_data)
    return db_user


@router.put("/profile", response_model=UserSchema)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Actualiza el perfil del usuario autenticado.
    """
    # Obtener el usuario actual de la base de datos
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(
            status_code=400,
            detail="El token no contiene información de usuario (sub)",
        )
    
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    # Actualizar el perfil
    updated_user = user_service.update_user_profile(db, user_id=db_user.id, profile_in=profile_update)
    return updated_user


@router.put("/{user_id}/role", response_model=UserSchema)
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user_with_permissions),
) -> Any:
    """
    Actualiza el rol de un usuario.
    Solo para administradores.
    """
    updated_user = user_service.update_user_role(db, user_id=user_id, role_update=role_update)
    return updated_user


@router.get("/{user_id}", response_model=UserSchema)
async def read_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Obtener un usuario específico por ID.
    """
    db_user = user_service.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )
    return db_user


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user_with_permissions),
) -> Any:
    """
    Actualizar un usuario.
    Solo para administradores.
    """
    updated_user = user_service.update_user(db, user_id=user_id, user_in=user_in)
    return updated_user


@router.delete("/{user_id}", response_model=UserSchema)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user_with_permissions),
) -> Any:
    """
    Eliminar un usuario.
    Solo para administradores.
    """
    deleted_user = user_service.delete_user(db, user_id=user_id)
    return deleted_user


@router.post("/register", response_model=UserSchema)
async def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> Any:
    """
    Registrar un nuevo usuario en el sistema.
    
    Este es un endpoint público que no requiere autenticación.
    Los usuarios registrados a través de este endpoint siempre tendrán el rol MEMBER.
    """
    # Forzar el rol a MEMBER independientemente de lo que se envíe en la petición
    user_data = user_in.model_dump()
    user_data["role"] = UserRole.MEMBER
    user_data["is_superuser"] = False  # Asegurar que no se creen superusuarios
    
    # Verificar que se provee un email y contraseña
    if not user_data.get("email"):
        raise HTTPException(
            status_code=400,
            detail="El email es obligatorio para el registro"
        )
    
    if not user_data.get("password"):
        raise HTTPException(
            status_code=400,
            detail="La contraseña es obligatoria para el registro"
        )
    
    # Crear el usuario con los datos sanitizados
    user_create = UserCreate(**user_data)
    try:
        user = user_service.create_user(db, user_in=user_create)
        return user
    except HTTPException as e:
        # Re-lanzar excepciones del servicio
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear el usuario: {str(e)}"
        ) 