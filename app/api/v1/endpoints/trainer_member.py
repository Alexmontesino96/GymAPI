from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session

from app.core.auth0_fastapi import auth, get_current_user, get_current_user_with_permissions, Auth0User
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.trainer_member import trainer_member_service
from app.services.user import user_service
from app.schemas.trainer_member import (
    TrainerMemberRelationship,
    TrainerMemberRelationshipCreate,
    TrainerMemberRelationshipUpdate,
    UserWithRelationship
)

router = APIRouter()


@router.post("/", response_model=TrainerMemberRelationship)
async def create_trainer_member_relationship(
    relationship_in: TrainerMemberRelationshipCreate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Crear una nueva relación entre un entrenador y un miembro.
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
    
    # Crear la relación
    relationship = trainer_member_service.create_relationship(
        db, relationship_in=relationship_in, created_by_id=db_user.id
    )
    return relationship


@router.get("/", response_model=List[TrainerMemberRelationship])
async def read_relationships(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Recuperar todas las relaciones (solo para administradores).
    """
    # Obtener el usuario actual de la base de datos
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user or db_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para acceder a esta información",
        )
    
    # Esta vista es solo para administradores
    relationships = trainer_member_service.get_all_relationships(db, skip=skip, limit=limit)
    return relationships


@router.get("/trainer/{trainer_id}/members", response_model=List[Dict])
async def read_members_by_trainer(
    trainer_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Recuperar todos los miembros asignados a un entrenador.
    """
    # Verificar permisos (solo el propio entrenador o un admin pueden ver esto)
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    if db_user.id != trainer_id and db_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para acceder a esta información",
        )
    
    # Obtener los miembros del entrenador
    members = trainer_member_service.get_members_by_trainer(
        db, trainer_id=trainer_id, skip=skip, limit=limit
    )
    return members


@router.get("/member/{member_id}/trainers", response_model=List[Dict])
async def read_trainers_by_member(
    member_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Recuperar todos los entrenadores asignados a un miembro.
    """
    # Verificar permisos (solo el propio miembro o un admin pueden ver esto)
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    if db_user.id != member_id and db_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para acceder a esta información",
        )
    
    # Obtener los entrenadores del miembro
    trainers = trainer_member_service.get_trainers_by_member(
        db, member_id=member_id, skip=skip, limit=limit
    )
    return trainers


@router.get("/my-trainers", response_model=List[Dict])
async def read_my_trainers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Recuperar todos los entrenadores del usuario autenticado.
    """
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    # Verificar si el usuario es un miembro
    if db_user.role != UserRole.MEMBER:
        raise HTTPException(
            status_code=400,
            detail="Esta función solo está disponible para miembros",
        )
    
    # Obtener los entrenadores del miembro
    trainers = trainer_member_service.get_trainers_by_member(
        db, member_id=db_user.id, skip=skip, limit=limit
    )
    return trainers


@router.get("/my-members", response_model=List[Dict])
async def read_my_members(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Recuperar todos los miembros del entrenador autenticado.
    """
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    # Verificar si el usuario es un entrenador
    if db_user.role != UserRole.TRAINER:
        raise HTTPException(
            status_code=400,
            detail="Esta función solo está disponible para entrenadores",
        )
    
    # Obtener los miembros del entrenador
    members = trainer_member_service.get_members_by_trainer(
        db, trainer_id=db_user.id, skip=skip, limit=limit
    )
    return members


@router.get("/{relationship_id}", response_model=TrainerMemberRelationship)
async def read_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Recuperar una relación específica por ID.
    """
    relationship = trainer_member_service.get_relationship(db, relationship_id=relationship_id)
    
    # Verificar permisos (solo los involucrados o un admin pueden ver esto)
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    if (db_user.id != relationship.trainer_id and 
        db_user.id != relationship.member_id and 
        db_user.role != UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para acceder a esta información",
        )
    
    return relationship


@router.put("/{relationship_id}", response_model=TrainerMemberRelationship)
async def update_relationship(
    relationship_id: int,
    relationship_update: TrainerMemberRelationshipUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Actualizar una relación específica.
    """
    # Obtener la relación actual
    relationship = trainer_member_service.get_relationship(db, relationship_id=relationship_id)
    
    # Verificar permisos (solo los involucrados o un admin pueden actualizar esto)
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    if (db_user.id != relationship.trainer_id and 
        db_user.id != relationship.member_id and 
        db_user.role != UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para modificar esta relación",
        )
    
    # Actualizar la relación
    updated_relationship = trainer_member_service.update_relationship(
        db, relationship_id=relationship_id, relationship_update=relationship_update
    )
    return updated_relationship


@router.delete("/{relationship_id}", response_model=TrainerMemberRelationship)
async def delete_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Eliminar una relación específica.
    """
    # Obtener la relación actual
    relationship = trainer_member_service.get_relationship(db, relationship_id=relationship_id)
    
    # Verificar permisos (solo los involucrados o un admin pueden eliminar esto)
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local",
        )
    
    if (db_user.id != relationship.trainer_id and 
        db_user.id != relationship.member_id and 
        db_user.role != UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para eliminar esta relación",
        )
    
    # Eliminar la relación
    deleted_relationship = trainer_member_service.delete_relationship(
        db, relationship_id=relationship_id
    )
    return deleted_relationship 