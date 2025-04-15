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
    Check if an IP has exceeded the request limit.
    Returns True if the request is allowed, False if it should be blocked.
    
    Args:
        client_ip: The IP address of the client
        
    Returns:
        bool: Whether the request should be allowed
    """
    current_time = time.time()
    
    # Clean expired entries
    expired_keys = [
        key for key, data in rate_limit_storage.items()
        if data["expires_at"] < current_time
    ]
    for key in expired_keys:
        rate_limit_storage.pop(key, None)
    
    rate_limit_key = f"rate_limit:token:{client_ip}"
    
    # Check if IP already has a record
    if rate_limit_key in rate_limit_storage:
        data = rate_limit_storage[rate_limit_key]
        count = data["count"]
        
        # If limit exceeded, block
        if count >= RATE_LIMIT_MAX_REQUESTS:
            return False
        
        # Increment counter
        data["count"] += 1
        return True
    else:
        # First attempt for this IP
        rate_limit_storage[rate_limit_key] = {
            "count": 1,
            "expires_at": current_time + RATE_LIMIT_WINDOW
        }
        return True

def validate_redirect_uri(redirect_uri: str) -> bool:
    """
    Validates that the redirect URL is in the list of allowed URLs
    using a secure domain comparison.
    
    Args:
        redirect_uri: The URI to validate
        
    Returns:
        bool: Whether the URI is valid and allowed
    """
    if not redirect_uri:
        return False
    
    from urllib.parse import urlparse
    
    # Validate URL format
    parsed_uri = urlparse(redirect_uri)
    if not all([parsed_uri.scheme, parsed_uri.netloc]):
        return False
    
    allowed_uris = settings.AUTH0_ALLOWED_REDIRECT_URIS
    
    # Extract domains and ports from allowed URIs
    allowed_domains = []
    for uri in allowed_uris:
        parsed_allowed = urlparse(uri)
        if parsed_allowed.netloc:
            allowed_domains.append(parsed_allowed.netloc)
    
    # Verify exact match with allowed domains
    return parsed_uri.netloc in allowed_domains

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