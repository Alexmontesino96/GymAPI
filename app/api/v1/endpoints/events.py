"""
Events Module - API Endpoints

This module handles the creation, management, and participation in gym events.
Events can be workshops, special classes, competitions, or any other activities
organized by the gym. The module provides endpoints for:

- Creating and managing events (trainers and admins)
- Viewing event details (all users)
- Registering for events (members)
- Managing event participation (trainers and event creators)
- Administrative operations (admins only)

All endpoints are protected with appropriate permission scopes.
"""

from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Security
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, get_current_user_with_permissions, Auth0User, auth
from app.schemas.event import (
    Event, 
    EventCreate, 
    EventUpdate, 
    EventDetail,
    EventParticipation, 
    EventParticipationCreate, 
    EventParticipationUpdate,
    EventWithParticipantCount,
    EventsSearchParams
)
from app.models.event import EventStatus, EventParticipationStatus
from app.models.user import UserRole
from app.repositories.event import event_repository, event_participation_repository


router = APIRouter()


# Event Endpoints
@router.post("/", response_model=Event, status_code=status.HTTP_201_CREATED)
async def create_event(
    *,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["create:events"])
) -> Any:
    """
    Create a new event.
    
    This endpoint allows trainers and administrators to create new events
    for the gym. Events can be workshops, special classes, competitions,
    or any other activities that members can participate in.
    
    Permissions:
        - Requires 'create:events' scope (trainers and administrators)
        
    Args:
        db: Database session
        event_in: Event data to create
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        Event: The newly created event
    """
    # Get Auth0 user ID
    user_id = current_user.id
    
    # Create the event
    event = event_repository.create_event(db=db, event_in=event_in, creator_id=user_id)
    return event


@router.get("/", response_model=List[EventWithParticipantCount])
async def read_events(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[EventStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    title_contains: Optional[str] = None,
    location_contains: Optional[str] = None,
    created_by: Optional[int] = None,
    only_available: bool = False,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:events"])
) -> Any:
    """
    Retrieve a list of events with optional filters.
    
    This endpoint returns a paginated list of events that can be filtered
    by various criteria such as status, date range, title, location, and 
    availability. Each event includes a count of current participants.
    
    Permissions:
        - Requires 'read:events' scope (all authenticated users)
        
    Args:
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        status: Filter by event status (SCHEDULED, CANCELLED, COMPLETED)
        start_date: Filter events starting on or after this date
        end_date: Filter events ending on or before this date
        title_contains: Filter events with titles containing this string
        location_contains: Filter events with locations containing this string
        created_by: Filter events created by a specific user ID
        only_available: If true, only return events with available spots
        current_user: Authenticated user
        
    Returns:
        List[EventWithParticipantCount]: List of events with participant counts
    """
    events = event_repository.get_events(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        start_date=start_date,
        end_date=end_date,
        title_contains=title_contains,
        location_contains=location_contains,
        created_by=created_by,
        only_available=only_available
    )
    
    # Add participant count to each event
    result = []
    for event in events:
        # Count registered participants
        participants_count = len([
            p for p in event.participants 
            if p.status == EventParticipationStatus.REGISTERED
        ])
        
        # Create object with count
        event_dict = Event.from_orm(event).dict()
        event_dict["participants_count"] = participants_count
        result.append(EventWithParticipantCount(**event_dict))
        
    return result


@router.get("/me", response_model=List[Event])
async def read_my_events(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:own_events"])
) -> Any:
    """
    Retrieve events created by the authenticated user.
    
    This endpoint allows trainers and administrators to view the events
    they have created. It provides a convenient way to manage one's own events.
    
    Permissions:
        - Requires 'read:own_events' scope (all authenticated users)
        
    Args:
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        current_user: Authenticated user
        
    Returns:
        List[Event]: List of events created by the user
    """
    # Get Auth0 user ID
    user_id = current_user.id
    events = event_repository.get_events_by_creator(
        db=db, creator_id=user_id, skip=skip, limit=limit
    )
    return events


@router.get("/{event_id}", response_model=EventDetail)
async def read_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:events"])
) -> Any:
    """
    Retrieve details of a specific event by ID.
    
    This endpoint returns detailed information about an event, including
    its title, description, date/time, location, and capacity. The participants
    list is only included if the requesting user is the event creator or an admin.
    
    Permissions:
        - Requires 'read:events' scope (all authenticated users)
        - Viewing participant list requires event ownership or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event to retrieve
        current_user: Authenticated user
        
    Returns:
        EventDetail: Detailed event information
        
    Raises:
        HTTPException: 404 if event not found
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check permissions to view participants
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    is_creator = event.creator_id == user_id
    
    # Create detailed object
    event_dict = Event.from_orm(event).dict()
    
    # Include participants only if admin or creator
    if is_admin or is_creator:
        event_dict["participants"] = [
            EventParticipation.from_orm(p) for p in event.participants
        ]
    else:
        # For normal users, include only count
        event_dict["participants"] = []
        event_dict["participants_count"] = len([
            p for p in event.participants 
            if p.status == EventParticipationStatus.REGISTERED
        ])
        
    return EventDetail(**event_dict)


@router.put("/{event_id}", response_model=Event)
async def update_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    event_in: EventUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["update:events"])
) -> Any:
    """
    Update an existing event.
    
    This endpoint allows the event creator or administrators to update
    event details such as title, description, time, location, capacity,
    and status. Only the creator of the event or administrators can perform
    this operation.
    
    Permissions:
        - Requires 'update:events' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event to update
        event_in: Updated event data
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        Event: The updated event
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Verify permissions
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    # Only the creator or an admin can update
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this event"
        )
    
    # Update event
    updated_event = event_repository.update_event(
        db=db, event_id=event_id, event_in=event_in
    )
    return updated_event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["delete:events"])
) -> None:
    """
    Delete an event.
    
    This endpoint allows the event creator or administrators to delete
    an event. This will also remove all associated participations.
    Only the creator of the event or administrators can perform this operation.
    
    Permissions:
        - Requires 'delete:events' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event to delete
        current_user: Authenticated user with appropriate permissions
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Verify permissions
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    # Only the creator or an admin can delete
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this event"
        )
    
    # Delete event
    event_repository.delete_event(db=db, event_id=event_id)
    return None


@router.delete("/admin/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:events"])
) -> None:
    """
    Administrative endpoint to delete any event regardless of ownership.
    
    This is a specialized admin-only endpoint that allows administrators to
    delete any event without ownership verification. It's useful for content
    moderation and managing events when the original creator is unavailable.
    
    Permissions:
        - Requires 'admin:events' scope (administrators only)
        - This is a protected administrative operation
        
    Args:
        db: Database session
        event_id: ID of the event to delete
        current_user: Authenticated administrator
        
    Raises:
        HTTPException: 404 if event not found, 500 for other errors
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Delete event without ownership verification
    try:
        event_repository.delete_event(db=db, event_id=event_id)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting event: {str(e)}"
        )


# Event Participation Endpoints
@router.post("/participation", response_model=EventParticipation, status_code=status.HTTP_201_CREATED)
async def register_for_event(
    *,
    db: Session = Depends(get_db),
    participation_in: EventParticipationCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["create:participations"])
) -> Any:
    """
    Register for an event.
    
    This endpoint allows members to register for events. It performs various
    checks to ensure the event is available, has capacity, and the user isn't
    already registered. If successful, the user is added to the event's participants.
    
    Permissions:
        - Requires 'create:participations' scope (all authenticated users)
        
    Args:
        db: Database session
        participation_in: Participation data including event ID
        current_user: Authenticated user
        
    Returns:
        EventParticipation: The created participation record
        
    Raises:
        HTTPException: 404 if event not found, 400 for validation errors
    """
    # Get Auth0 user ID
    user_id = current_user.id
    
    # Check if event exists and is available
    event = event_repository.get_event(db=db, event_id=participation_in.event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check if event is open for registration
    if event.status != EventStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event is not open for registration"
        )
    
    # Check if there are spaces available
    current_participants = len([
        p for p in event.participants 
        if p.status == EventParticipationStatus.REGISTERED
    ])
    
    if event.capacity and current_participants >= event.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event is at full capacity"
        )
    
    # Check if user is already registered
    existing = event_participation_repository.get_participant(
        db=db, event_id=participation_in.event_id, user_id=user_id
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already registered for this event"
        )
    
    # Create participation
    participation = event_participation_repository.create_participation(
        db=db, participation_in=participation_in, user_id=user_id
    )
    
    return participation


@router.get("/participation/me", response_model=List[EventParticipation])
async def read_my_participations(
    *,
    db: Session = Depends(get_db),
    status: Optional[EventParticipationStatus] = None,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:own_participations"])
) -> Any:
    """
    Retrieve participations of the authenticated user.
    
    This endpoint allows users to view the events they have registered for,
    optionally filtered by status (registered, cancelled, waiting list).
    
    Permissions:
        - Requires 'read:own_participations' scope (all authenticated users)
        
    Args:
        db: Database session
        status: Optional filter by participation status
        current_user: Authenticated user
        
    Returns:
        List[EventParticipation]: User's event participations
    """
    # Get Auth0 user ID
    user_id = current_user.id
    participations = event_participation_repository.get_user_participations(
        db=db, user_id=user_id, status=status
    )
    return participations


@router.get("/participation/event/{event_id}", response_model=List[EventParticipation])
async def read_event_participations(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    status: Optional[EventParticipationStatus] = None,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:participations"])
) -> Any:
    """
    Retrieve participations for a specific event.
    
    This endpoint allows event creators and administrators to view all
    participants for a specific event, optionally filtered by status.
    Only the event creator or administrators can access this information.
    
    Permissions:
        - Requires 'read:participations' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event
        status: Optional filter by participation status
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        List[EventParticipation]: List of event participations
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Verify permissions
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    # Only the creator or an admin can see all participants
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view participants for this event"
        )
    
    # Get participants
    participations = event_participation_repository.get_event_participations(
        db=db, event_id=event_id, status=status
    )
    return participations


@router.delete("/participation/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_participation(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["delete:own_participations"])
) -> None:
    """
    Cancel participation in an event.
    
    This endpoint allows users to cancel their registration for an event.
    Users can only cancel their own participations.
    
    Permissions:
        - Requires 'delete:own_participations' scope (all authenticated users)
        
    Args:
        db: Database session
        event_id: ID of the event to cancel participation for
        current_user: Authenticated user
        
    Raises:
        HTTPException: 404 if participation not found
    """
    # Get Auth0 user ID
    user_id = current_user.id
    
    # Check if participation exists
    participation = event_participation_repository.get_participant(
        db=db, event_id=event_id, user_id=user_id
    )
    
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participation not found"
        )
    
    # Delete participation
    event_participation_repository.delete_participation(db=db, participation_id=participation.id)
    return None


@router.put("/participation/{participation_id}", response_model=EventParticipation)
async def update_participation(
    *,
    db: Session = Depends(get_db),
    participation_id: int = Path(..., title="Participation ID"),
    participation_in: EventParticipationUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["update:participations"])
) -> Any:
    """
    Update participation status.
    
    This endpoint allows event creators and administrators to update
    the status of a participant, such as marking attendance or changing
    their status. Only the event creator or administrators can perform
    this operation.
    
    Permissions:
        - Requires 'update:participations' scope (trainers and administrators)
        - Also requires event ownership or admin privileges
        
    Args:
        db: Database session
        participation_id: ID of the participation to update
        participation_in: Updated participation data
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        EventParticipation: The updated participation record
        
    Raises:
        HTTPException: 404 if participation not found, 403 if insufficient permissions
    """
    # Get participation
    participation = event_participation_repository.get_participation(
        db=db, participation_id=participation_id
    )
    
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participation not found"
        )
    
    # Get event
    event = event_repository.get_event(db=db, event_id=participation.event_id)
    
    # Verify permissions
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    # Only the event creator or an admin can update participation
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this participation"
        )
    
    # Update participation
    updated = event_participation_repository.update_participation(
        db=db, participation_id=participation_id, participation_in=participation_in
    )
    return updated 