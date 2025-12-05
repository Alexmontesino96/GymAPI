"""
Trainer-Member Relationship Module - API Endpoints

This module manages the relationships between trainers and members in the gym system.
It provides functionality for:

- Creating and managing trainer-member assignments
- Listing members assigned to specific trainers
- Listing trainers assigned to specific members
- Accessing relationship details for both roles

The relationship system is designed to support various training scenarios, including:
- One trainer with multiple members (standard personal training)
- One member with multiple trainers (specialized training in different areas)
- Administrative oversight of all relationships

Each endpoint is protected with appropriate permission scopes to ensure data security
and proper access control based on user roles.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Security, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth0_fastapi import auth, get_current_user, get_current_user_with_permissions, Auth0User
from app.db.session import get_async_db
from app.models.user import User, UserRole
from app.services.async_trainer_member import async_trainer_member_service
from app.services.user import user_service
from app.schemas.trainer_member import (
    TrainerMemberRelationship,
    TrainerMemberRelationshipCreate,
    TrainerMemberRelationshipUpdate,
    UserWithRelationship
)
from app.core.tenant import verify_gym_access
from app.schemas.gym import GymSchema

router = APIRouter()


@router.post("/", response_model=TrainerMemberRelationship)
async def create_trainer_member_relationship(
    request: Request,
    relationship_in: TrainerMemberRelationshipCreate,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> Any:
    """
    Create a new relationship between a trainer and a member.
    
    This endpoint establishes an official training relationship between a trainer
    and a member, enabling specialized communication and tracking. The relationship
    can include training goals, notes, and custom attributes.
    
    Permissions:
        - Requires 'create:relationships' scope (trainers and administrators)
        
    Args:
        relationship_in: Relationship data including trainer_id and member_id
        db: Database session
        user: Authenticated user with appropriate permissions
        current_gym: Gym schema with gym context
        
    Returns:
        TrainerMemberRelationship: The newly created relationship
        
    Raises:
        HTTPException: 400 if token doesn't contain user info, 404 if user not found
    """
    # Get current user from database
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(
            status_code=400,
            detail="Token does not contain user information (sub)",
        )
    
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    # Create the relationship
    relationship = await async_trainer_member_service.create_relationship(
        db, relationship_in=relationship_in, created_by_id=db_user.id
    )
    return relationship


@router.get("/", response_model=List[TrainerMemberRelationship])
async def read_relationships(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
) -> Any:
    """
    Retrieve all trainer-member relationships.
    
    This administrative endpoint provides a complete view of all training
    relationships in the system, supporting oversight and management functions.
    
    Permissions:
        - Requires 'admin:relationships' scope (administrators only)
        
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        db: Database session
        user: Authenticated administrator
        
    Returns:
        List[TrainerMemberRelationship]: List of all relationships
    """
    relationships = await async_trainer_member_service.get_all_relationships(db, skip=skip, limit=limit)
    return relationships


@router.get("/trainer/{trainer_id}/members", response_model=List[Dict])
async def read_members_by_trainer(
    request: Request,
    trainer_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> Any:
    """
    Retrieve all members assigned to a specific trainer in the current gym.
    
    This endpoint returns the list of members being trained by a specific trainer,
    including relationship details. Access is restricted to the trainer themselves
    or administrators.
    
    Permissions:
        - Requires 'read:relationships' scope
        - Must be the specified trainer or an administrator
        
    Args:
        trainer_id: ID of the trainer
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        db: Database session
        user: Authenticated user with appropriate permissions
        current_gym: Gym schema with gym context
        
    Returns:
        List[Dict]: List of members with relationship details
        
    Raises:
        HTTPException: 404 if user not found, 403 if unauthorized
    """
    # Still verify if the user is the trainer or an admin
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    if db_user.id != trainer_id and db_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this information",
        )
    
    # Get trainer's members
    members = await async_trainer_member_service.get_members_by_trainer(
        db, trainer_id=trainer_id, skip=skip, limit=limit
    )
    return members


@router.get("/member/{member_id}/trainers", response_model=List[Dict])
async def read_trainers_by_member(
    member_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
) -> Any:
    """
    Retrieve all trainers assigned to a specific member.
    
    This endpoint returns the list of trainers working with a specific member,
    including relationship details. Access is restricted to the member themselves
    or administrators.
    
    Permissions:
        - Requires 'read:relationships' scope
        - Must be the specified member or an administrator
        
    Args:
        member_id: ID of the member
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        db: Database session
        user: Authenticated user with appropriate permissions
        
    Returns:
        List[Dict]: List of trainers with relationship details
        
    Raises:
        HTTPException: 404 if user not found, 403 if unauthorized
    """
    # Still verify if the user is the member or an admin
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    if db_user.id != member_id and db_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this information",
        )
    
    # Get member's trainers
    trainers = await async_trainer_member_service.get_trainers_by_member(
        db, member_id=member_id, skip=skip, limit=limit
    )
    return trainers


@router.get("/my-trainers", response_model=List[Dict])
async def read_my_trainers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
) -> Any:
    """
    Retrieve all trainers of the authenticated member.
    
    This convenience endpoint allows members to view all of their assigned trainers
    and training relationships without needing to know their own user ID.
    
    Permissions:
        - Requires 'read:own_relationships' scope (all authenticated users)
        - Must have MEMBER role
        
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        db: Database session
        user: Authenticated member
        
    Returns:
        List[Dict]: List of the member's trainers with relationship details
        
    Raises:
        HTTPException: 404 if user not found, 400 if not a member
    """
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    # Verify if the user is a member
    if db_user.role != UserRole.MEMBER:
        raise HTTPException(
            status_code=400,
            detail="This function is only available for members",
        )
    
    # Get member's trainers
    trainers = await async_trainer_member_service.get_trainers_by_member(
        db, member_id=db_user.id, skip=skip, limit=limit
    )
    return trainers


@router.get("/my-members", response_model=List[Dict])
async def read_my_members(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
) -> Any:
    """
    Retrieve all members of the authenticated trainer.
    
    This convenience endpoint allows trainers to view all of their assigned members
    and training relationships without needing to know their own user ID.
    
    Permissions:
        - Requires 'read:own_relationships' scope (all authenticated users)
        - Must have TRAINER role
        
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        db: Database session
        user: Authenticated trainer
        
    Returns:
        List[Dict]: List of the trainer's members with relationship details
        
    Raises:
        HTTPException: 404 if user not found, 400 if not a trainer
    """
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)

    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )

    # Verify if the user is a trainer
    if db_user.role != UserRole.TRAINER:
        raise HTTPException(
            status_code=400,
            detail="This function is only available for trainers",
        )
    
    # Get trainer's members
    members = await async_trainer_member_service.get_members_by_trainer(
        db, trainer_id=db_user.id, skip=skip, limit=limit
    )
    return members


@router.get("/{relationship_id}", response_model=TrainerMemberRelationship)
async def read_relationship(
    request: Request,
    relationship_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> Any:
    """
    Retrieve a specific trainer-member relationship by ID within the current gym.
    
    This endpoint provides detailed information about a specific training relationship,
    including notes, goals, and metadata. Access is restricted to users who are
    part of the relationship or administrators.
    
    Permissions:
        - Requires 'read:relationships' scope
        - Must be part of the relationship or an administrator
        
    Args:
        relationship_id: ID of the relationship to retrieve
        db: Database session
        user: Authenticated user with appropriate permissions
        current_gym: Gym schema with gym context
        
    Returns:
        TrainerMemberRelationship: The requested relationship details
        
    Raises:
        HTTPException: 404 if user not found, 403 if unauthorized
    """
    relationship = await async_trainer_member_service.get_relationship(db, relationship_id=relationship_id)
    
    if not relationship or relationship.gym_id != current_gym.id:
        raise HTTPException(status_code=404, detail="Relationship not found in this gym")
    
    # Still verify if the user is part of the relationship or an admin
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    if (db_user.id != relationship.trainer_id and 
        db_user.id != relationship.member_id and 
        db_user.role != UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this information",
        )
    
    return relationship


@router.put("/{relationship_id}", response_model=TrainerMemberRelationship)
async def update_relationship(
    relationship_id: int,
    relationship_update: TrainerMemberRelationshipUpdate,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
) -> Any:
    """
    Update an existing trainer-member relationship.
    
    This endpoint allows updating relationship details such as notes, status,
    goals, and other attributes. Access is restricted to the trainer in the
    relationship or administrators.
    
    Permissions:
        - Requires 'update:relationships' scope
        - Must be the trainer in the relationship or an administrator
        
    Args:
        relationship_id: ID of the relationship to update
        relationship_update: Updated relationship data
        db: Database session
        user: Authenticated user with appropriate permissions
        
    Returns:
        TrainerMemberRelationship: The updated relationship
        
    Raises:
        HTTPException: 404 if relationship or user not found, 403 if unauthorized
    """
    # Get the relationship
    relationship = await async_trainer_member_service.get_relationship(db, relationship_id=relationship_id)
    if not relationship:
        raise HTTPException(
            status_code=404,
            detail="Relationship not found",
        )
    
    # Still verify if the user is the trainer or an admin
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    # Only the trainer or an admin can update the relationship
    if db_user.id != relationship.trainer_id and db_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to update this relationship",
        )
    
    # Update the relationship
    updated_relationship = await async_trainer_member_service.update_relationship(
        db, relationship_id=relationship_id, relationship_in=relationship_update
    )
    return updated_relationship


@router.delete("/{relationship_id}", response_model=TrainerMemberRelationship)
async def delete_relationship(
    relationship_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
) -> Any:
    """
    Delete a trainer-member relationship.
    
    This endpoint ends a training relationship between a trainer and a member.
    Access is restricted to users who are part of the relationship or administrators.
    
    Permissions:
        - Requires 'delete:relationships' scope
        - Must be part of the relationship or an administrator
        
    Args:
        relationship_id: ID of the relationship to delete
        db: Database session
        user: Authenticated user with appropriate permissions
        
    Returns:
        TrainerMemberRelationship: The deleted relationship
        
    Raises:
        HTTPException: 404 if relationship or user not found, 403 if unauthorized
    """
    # Get the relationship
    relationship = await async_trainer_member_service.get_relationship(db, relationship_id=relationship_id)
    if not relationship:
        raise HTTPException(
            status_code=404,
            detail="Relationship not found",
        )
    
    # Still verify if the user is part of the relationship or an admin
    auth0_id = user.id
    db_user = await user_service.get_user_by_auth0_id_async_direct(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    # Only users who are part of the relationship or admins can delete it
    if (db_user.id != relationship.trainer_id and 
        db_user.id != relationship.member_id and 
        db_user.role != UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this relationship",
        )
    
    # Delete the relationship
    deleted_relationship = await async_trainer_member_service.delete_relationship(
        db, relationship_id=relationship_id
    )
    return deleted_relationship 