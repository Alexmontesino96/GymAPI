from app.api.v1.endpoints.auth.common import *

router = APIRouter()

@router.get("/me")
async def read_users_me(user: Auth0User = Security(auth.get_user, scopes=["read:profile"])):
    """
    Returns the information of the currently authenticated user.
    
    This endpoint retrieves all the user information available in the Auth0 token,
    including profile data, permissions, and any custom claims. It requires the
    'read:profile' scope to access.
    
    Args:
        user: The authenticated user, injected by the security dependency
        
    Returns:
        Auth0User: Complete user information extracted from the token
    """
    return user


@router.get("/test-email")
async def test_email_in_token(request: Request, user: Auth0User = Security(auth.get_user, scopes=["read:profile"])):
    """
    Test endpoint to verify the presence of email in the token.
    
    This diagnostic endpoint helps identify if the email claim is present in the
    user's JWT token. It's useful for debugging authentication issues related to
    missing email data. It returns information about both the token content and
    the request headers.
    
    Args:
        request: The FastAPI request object
        user: The authenticated user, injected by the security dependency
        
    Returns:
        dict: Debug information including user data and headers
    """
    # Basic user information
    user_info = {
        "id": user.id,
        "email": getattr(user, "email", None)
    }
    
    # Check headers
    auth_header = request.headers.get("Authorization", "")
    has_auth = bool(auth_header)
    
    # For debugging
    result = {
        "user": user_info,
        "has_authorization_header": has_auth,
        "header_type": auth_header.split(" ")[0] if has_auth and " " in auth_header else None,
        "email_present": user.email is not None
    }
    
    return result


@router.get("/get-user-email")
async def get_user_email(user: Auth0User = Security(auth.get_user, scopes=["read:profile"])):
    """
    Returns the email of the authenticated user.
    
    This endpoint is a simplified version of /me that returns only the email
    address. It verifies the email is present in the token and returns a
    400 error if it's missing.
    
    Args:
        user: The authenticated user, injected by the security dependency
        
    Returns:
        dict: Contains the user's email
        
    Raises:
        HTTPException: If email is not available in the token
    """
    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not available in token. Make sure to request the 'email' permission when authenticating."
        )
    
    return {"email": user.email}


@router.get("/check-permissions")
async def check_permissions(current_user: Auth0User = Security(auth.get_user, scopes=["read:profile"])):
    """
    Verifies the permissions of the current user.
    
    This endpoint returns all permissions (scopes) associated with the user's
    JWT token, along with other profile information. It's useful for debugging
    permission issues and for client applications to determine available functionality.
    
    Args:
        current_user: The authenticated user, injected by the security dependency
        
    Returns:
        dict: Contains permissions and complete user information
    """
    # Get permissions from JWT token
    permissions = getattr(current_user, "permissions", [])
    
    # Get other fields
    user_info = {
        "id": current_user.id,
        "email": getattr(current_user, "email", None),
        "name": getattr(current_user, "name", None),
        "picture": getattr(current_user, "picture", None),
        "permissions": permissions,
        "raw_user_data": current_user.dict()
    }
    
    return {
        "message": "Permissions verified",
        "user": user_info,
    } 