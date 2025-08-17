import urllib.parse
import json
import urllib.request
import secrets
import base64
import time
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, Request, HTTPException, status, Security, Body, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.services.user import user_service
from app.db.session import get_db

# Configure appropriate logging
import logging
logger = logging.getLogger("auth")

# Dictionary to store temporary state information with TTL
# In production, this should be stored in Redis or another persistent solution
state_storage = {}
STATE_EXPIRATION_SECONDS = 600  # 10 minutes

# Rate limiting control
rate_limit_storage = {}  # In production, use Redis
RATE_LIMIT_MAX_REQUESTS = 10  # Maximum number of requests
RATE_LIMIT_WINDOW = 60 * 60  # Time window in seconds (1 hour)

def cleanup_expired_states():
    """
    Remove expired states from storage to prevent memory leaks
    and maintain security by invalidating old authorization attempts.
    """
    current_time = time.time()
    expired_states = [
        state_key for state_key, state_data in state_storage.items()
        if state_data.get("expires_at", 0) < current_time
    ]
    for state_key in expired_states:
        state_storage.pop(state_key, None)

def check_rate_limit(client_ip: str) -> bool:
    """
    Temporalmente deshabilitado: siempre permite la solicitud.
    """
    return True

def validate_redirect_uri(redirect_uri: str) -> bool:
    """
    Temporalmente deshabilitado: acepta cualquier redirect_uri bien formada.
    """
    if not redirect_uri:
        return False
    from urllib.parse import urlparse
    parsed = urlparse(redirect_uri)
    return bool(parsed.scheme and parsed.netloc)

def generate_state_param(redirect_uri: Optional[str] = None, is_api: bool = False) -> str:
    """
    Generates a state parameter for OAuth2 with additional information
    and expiration time.
    
    Args:
        redirect_uri: Optional redirect URI to include in state data
        is_api: Whether this is an API request or direct browser flow
        
    Returns:
        str: A secure random state token
    """
    # Clean expired states periodically
    cleanup_expired_states()
    
    # Generate a random token for the state
    random_state = secrets.token_urlsafe(32)
    
    # Store information associated with the state with expiration time
    state_data = {
        "redirect_uri": redirect_uri,
        "is_api": is_api,
        "created_at": time.time(),
        "expires_at": time.time() + STATE_EXPIRATION_SECONDS
    }
    
    # Save information in temporary storage
    state_storage[random_state] = state_data
    
    return random_state 
