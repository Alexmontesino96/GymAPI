"""
Chat Module - API Endpoints

This module provides real-time chat functionality for the gym application using Stream Chat as 
the underlying service. It enables:

- Direct messaging between users (member-to-trainer communication)
- Group chats for events (event participants communication)
- Room management (creating rooms, adding/removing members)

The chat system is integrated with the user authentication system and uses Stream Chat tokens
for secure access. Each endpoint is protected with appropriate permission scopes.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query, status, Security
from sqlalchemy.orm import Session
import logging # Import logging

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User, auth
from app.core.config import get_settings
from app.services.chat import chat_service
from app.schemas.chat import (
    ChatRoom, 
    ChatRoomCreate, 
    StreamTokenResponse,
    StreamMessageSend
)
from app.models.user import User

router = APIRouter()
logger = logging.getLogger("chat_api") # Initialize logger at the module level

@router.get("/token", response_model=StreamTokenResponse)
async def get_stream_token(
    *,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Get Stream Chat Token

    Generates a secure authentication token for the currently authenticated user
    to connect to the Stream Chat service.

    The token includes user details (name, email, picture) for display purposes
    within the chat interface. It uses the user's internal database ID for Stream identification.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).

    Permissions:
        - Requires 'use:chat' scope (granted to all authenticated users).

    Returns:
        StreamTokenResponse: An object containing:
                               - `token`: The Stream Chat user token.
                               - `api_key`: The Stream Chat application API key.
                               - `internal_user_id`: The user's internal database ID.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'use:chat' scope.
        HTTPException 404: User profile not found in the local database.
    """
    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # User data for Stream Chat profile
    user_data = {
        "name": getattr(internal_user, "display_name", f"{internal_user.first_name} {internal_user.last_name}"), # Use display_name if available
        "email": internal_user.email,
        "image": internal_user.picture # Use 'image' for Stream compatibility
    }

    # Use internal ID to generate the token
    token = chat_service.get_user_token(internal_user.id, user_data) # Ensure user ID is string for Stream

    # Call get_settings() to get the settings object
    settings_obj = get_settings()
    return {
        "token": token,
        "api_key": settings_obj.STREAM_API_KEY, # Use the object
        "internal_user_id": internal_user.id
    }

@router.post("/rooms", response_model=ChatRoom, status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    *,
    db: Session = Depends(get_db),
    room_data: ChatRoomCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"])
):
    """
    Create Chat Room

    Creates a new group chat room. Intended for use by trainers or administrators.
    The creator is automatically added as a member and channel admin.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        room_data (ChatRoomCreate): Data for the new room, including name and initial member IDs.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).

    Permissions:
        - Requires 'create:chat_rooms' scope (typically for trainers/admins).

    Request Body (ChatRoomCreate):
        {
          "name": "string (optional)",
          "member_ids": [integer] /* List of internal user IDs */,
          "is_direct": false (optional, default: false)
        }

    Returns:
        ChatRoomSchema: The newly created chat room object, including its Stream channel ID.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'create:chat_rooms' scope.
        HTTPException 404: Creator's user profile or specified members not found.
        HTTPException 500: Internal error during room creation (e.g., Stream API error).
    """
    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Use internal ID (integer) directly for the service
    creator_id = internal_user.id

    # Service handles room creation in DB and Stream using internal IDs
    # No need to convert IDs to strings here anymore
    return chat_service.create_room(db, creator_id, room_data)

@router.get("/rooms/direct/{other_user_id}", response_model=ChatRoom)
async def get_direct_chat(
    *,
    db: Session = Depends(get_db),
    other_user_id: int = Path(..., title="Internal user ID for direct chat"),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Get or Create Direct Chat Room

    Establishes or retrieves a 1-on-1 direct message channel between the currently
    authenticated user and the specified `other_user_id`.
    If a room already exists, it returns the existing room details. Otherwise,
    a new direct message room is created.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        other_user_id (int): The internal database ID of the other user to chat with.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).

    Permissions:
        - Requires 'use:chat' scope.

    Returns:
        ChatRoomSchema: The direct chat room object.

    Raises:
        HTTPException 400: If the user attempts to create a chat with themselves (`other_user_id` matches current user's ID).
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'use:chat' scope.
        HTTPException 404: Current user's or other user's profile not found.
        HTTPException 500: Internal error during room creation/retrieval.
    """
    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user profile not found"
        )

    if other_user_id == internal_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a direct chat with yourself"
        )

    # Use internal IDs (integers) directly
    user1_id = internal_user.id
    user2_id = other_user_id

    return chat_service.get_or_create_direct_chat(db, user1_id, user2_id)

@router.get("/rooms/event/{event_id}", response_model=ChatRoom)
async def get_event_chat(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Get or Create Event Chat Room

    Retrieves or creates the group chat room associated with a specific event.
    Users must be registered participants of the event to access or create its chat.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        event_id (int): The ID of the event.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).

    Permissions:
        - Requires 'use:chat' scope.
        - User must be a registered participant of the event.

    Returns:
        ChatRoomSchema: The event's chat room object.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: User is not registered for the event or lacks 'use:chat' scope.
        HTTPException 404: Event or User profile not found.
        HTTPException 500: Internal error during room creation/retrieval.
        HTTPException 503: Chat service timeout/latency issue.
    """
    import time
    # import logging # Already imported at module level
    # logger = logging.getLogger("chat_api") # Already initialized
    start_time = time.time()

    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    logger.info(f"Request for event chat {event_id} by internal user {internal_user.id}")

    try:
        # Quick check if event exists (consider moving to service layer)
        from app.models.event import Event
        event_exists = db.query(Event.id).filter(Event.id == event_id).scalar() is not None # More efficient check

        if not event_exists:
            logger.warning(f"Event {event_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

        # Service layer handles permission check (user registered for event) and room logic
        try:
            # Use internal user ID (integer) directly
            user_id = internal_user.id
            result = chat_service.get_or_create_event_chat(db, event_id, user_id)

            total_time = time.time() - start_time
            logger.info(f"Event chat {event_id} processed in {total_time:.2f}s")

            return result
        except ValueError as e:
            # Catch permission errors from the service layer
            logger.warning(f"Access error for event {event_id} chat by user {internal_user.id}: {str(e)}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting event chat {event_id}: {str(e)}", exc_info=True)
            total_time = time.time() - start_time
            if total_time > 5.0: # Timeout threshold
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Chat service is currently experiencing high latency, please try again later"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing event chat: {str(e)}"
                )

    except HTTPException:
        # Re-raise specific HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_event_chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")

@router.post("/rooms/{room_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def add_member_to_room(
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="Local Chat room ID from DB"),
    user_id: int = Path(..., title="Internal user ID to add"),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Add Member to Chat Room

    Adds a specified user (by internal ID) to an existing chat room (identified by local DB ID).

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        room_id (int): The local database ID of the chat room.
        user_id (int): The internal database ID of the user to add.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).

    Permissions:
        - Requires 'manage:chat_rooms' scope (typically for trainers/admins).

    Returns:
        dict: Success message, e.g., `{"status": "User added successfully"}`.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'manage:chat_rooms' scope.
        HTTPException 404: Chat room or User to add not found.
        HTTPException 500: Internal error adding user (e.g., Stream API error).
    """
    try:
        # Use internal ID (integer) directly
        chat_service.add_user_to_channel(db, room_id, user_id)
        return {"status": "User added successfully"}
    except ValueError as e:
        # Catch errors like room/user not found from service
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add user {user_id} to room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add user to room")

@router.delete("/rooms/{room_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_member_from_room(
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="Local Chat room ID from DB"),
    user_id: int = Path(..., title="Internal user ID to remove"),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Remove Member from Chat Room

    Removes a specified user (by internal ID) from an existing chat room (identified by local DB ID).

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        room_id (int): The local database ID of the chat room.
        user_id (int): The internal database ID of the user to remove.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).

    Permissions:
        - Requires 'manage:chat_rooms' scope (typically for trainers/admins).

    Returns:
        dict: Success message, e.g., `{"status": "User removed successfully"}`.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'manage:chat_rooms' scope.
        HTTPException 404: Chat room or User to remove not found.
        HTTPException 500: Internal error removing user (e.g., Stream API error).
    """
    try:
        # Use internal ID (integer) directly
        chat_service.remove_user_from_channel(db, room_id, user_id)
        return {"status": "User removed successfully"}
    except ValueError as e:
        # Catch errors like room/user not found from service
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove user {user_id} from room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove user from room") 