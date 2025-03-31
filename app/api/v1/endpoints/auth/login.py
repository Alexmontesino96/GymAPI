from app.api.v1.endpoints.auth.common import *

router = APIRouter()

@router.get("/login")
def login_redirect(
    redirect_uri: Optional[str] = Query(None, description="URL to redirect after login"),
    code_challenge: Optional[str] = Query(None, description="PKCE Code Challenge"),
    code_challenge_method: Optional[str] = Query(None, description="PKCE Code Challenge Method")
):
    """
    Returns the URL to start Auth0 login with support for dynamic redirection.
    
    This endpoint generates an Auth0 authorization URL that the client can use to initiate
    the OAuth2 authorization flow. It supports PKCE for enhanced security and 
    allows dynamic redirect URIs if they're in the allowed list.
    
    Args:
        redirect_uri: Optional URL to redirect after login completion
        code_challenge: PKCE code challenge for preventing authorization code interception
        code_challenge_method: Method used to generate the code challenge (e.g., "S256")
        
    Returns:
        dict: Contains auth_url for redirecting the user, state token, and redirect_uri
        
    Raises:
        HTTPException: If the redirect_uri is not in the allowed list
    """
    # Validate the redirect URL if provided
    if redirect_uri and not validate_redirect_uri(redirect_uri):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Redirect URL not allowed: {redirect_uri}"
        )
    
    # If a redirect URL is provided, use it as callback
    # Otherwise, use the one configured in the application
    callback_url = redirect_uri if redirect_uri else settings.AUTH0_CALLBACK_URL
    
    # Generate state to keep redirection information
    state = generate_state_param(redirect_uri=redirect_uri, is_api=True)
    
    # Prepare parameters for the authorization URL
    auth_params = {
        'audience': settings.AUTH0_API_AUDIENCE,
        'scope': 'openid profile email',
        'response_type': 'code',
        'client_id': settings.AUTH0_CLIENT_ID,
        'redirect_uri': callback_url,
        'state': state
    }
    
    # Add PKCE parameters if provided
    if code_challenge and code_challenge_method:
        auth_params['code_challenge'] = code_challenge
        auth_params['code_challenge_method'] = code_challenge_method
    
    authorization_url_qs = urllib.parse.urlencode(auth_params)
    auth_url = f"https://{settings.AUTH0_DOMAIN}/authorize?{authorization_url_qs}"
    
    return {"auth_url": auth_url, "state": state, "redirect_uri": callback_url}


@router.get("/login-redirect")
def login_redirect_automatic(
    redirect_uri: Optional[str] = Query(None, description="URL to redirect after login")
):
    """
    Automatically redirects the user to Auth0 login page with support for dynamic redirection.
    
    Unlike the /login endpoint which returns the URL, this endpoint performs an immediate
    redirect to Auth0's authorization page. It's useful for server-side applications
    or when direct redirection is preferred.
    
    Args:
        redirect_uri: Optional URL to redirect after login completion
        
    Returns:
        RedirectResponse: Immediate redirect to Auth0 login
        
    Raises:
        HTTPException: If the redirect_uri is not in the allowed list
    """
    # Validate the redirect URL if provided
    if redirect_uri and not validate_redirect_uri(redirect_uri):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Redirect URL not allowed: {redirect_uri}"
        )
    
    # If a redirect URL is provided, use it as callback
    # Otherwise, use the one configured in the application
    callback_url = redirect_uri if redirect_uri else settings.AUTH0_CALLBACK_URL
    
    # Generate state to keep redirection information
    state = generate_state_param(redirect_uri=redirect_uri, is_api=False)
    
    authorization_url_qs = urllib.parse.urlencode({
        'audience': settings.AUTH0_API_AUDIENCE,
        'scope': 'openid profile email',
        'response_type': 'code',
        'client_id': settings.AUTH0_CLIENT_ID,
        'redirect_uri': callback_url,
        'state': state
    })
    auth_url = f"https://{settings.AUTH0_DOMAIN}/authorize?{authorization_url_qs}"
    
    return RedirectResponse(auth_url)


@router.get("/callback")
async def auth0_callback(
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: Optional[str] = Query(None, description="State parameter")
):
    """
    Callback that receives the Auth0 code after login and redirects to the frontend
    with the code so it can exchange it for tokens.
    
    This endpoint handles the callback from Auth0 after user authentication.
    It validates the state parameter, retrieves any stored state information,
    and either returns the authorization code (for API clients) or redirects
    to the original redirect URI with the code as a parameter.
    
    Args:
        request: The FastAPI request object
        code: Authorization code from Auth0
        state: State parameter used to prevent CSRF attacks
        
    Returns:
        Union[dict, RedirectResponse]: Either a JSON response with the code or a redirect
        
    Raises:
        HTTPException: If there's an error in the parameters or Auth0 configuration
    """
    # Check if there's an error in the URL parameters
    params = dict(request.query_params)
    if "error" in params:
        error_msg = params.get("error_description", params.get("error", "Unknown error"))
        if "Service not found" in error_msg and settings.AUTH0_API_AUDIENCE in error_msg:
            detail = f"Auth0 configuration error: API Audience '{settings.AUTH0_API_AUDIENCE}' is not configured correctly."
        else:
            detail = f"Error in Auth0 authentication: {error_msg}"
        
        logger.error("Error in Auth0 callback", extra={"error": error_msg})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    
    # Retrieve state information if available
    state_data = {}
    if state and state in state_storage:
        state_data = state_storage.pop(state)  # Remove after use
    
    redirect_uri = state_data.get("redirect_uri")
    is_api = state_data.get("is_api", False)
    
    # Debug log
    logger.debug(
        "Auth0 callback received", 
        extra={
            "has_code": bool(code),
            "has_state": bool(state),
            "has_redirect": bool(redirect_uri),
            "is_api": is_api
        }
    )
    
    # If API request, return the code for frontend exchange
    if is_api:
        return {"code": code, "state": state, "redirect_uri": redirect_uri}
    
    # If there's a redirect URL, redirect to the frontend with the code as a query parameter
    if redirect_uri and validate_redirect_uri(redirect_uri):
        # Build the redirect URL with the code as a parameter
        redirect_params = {
            "code": code,
            "state": state if state else ""
        }
        query_string = urllib.parse.urlencode(redirect_params)
        redirect_url = f"{redirect_uri}?{query_string}"
        logger.info("Redirecting to frontend", extra={"redirect_uri": redirect_uri})
        return RedirectResponse(redirect_url)
    
    # By default, return the code as JSON
    return {"code": code, "state": state}


@router.get("/config")
async def get_auth_config(redirect_uri: Optional[str] = Query(None)):
    """
    Returns the authentication configuration for the frontend.
    
    This endpoint provides all the necessary Auth0 configuration parameters
    that a frontend client needs to implement authentication flows.
    It respects the provided redirect_uri if it's in the allowed list.
    
    Args:
        redirect_uri: Optional default redirect URI for the frontend
        
    Returns:
        dict: Auth0 configuration parameters including domain, clientId, etc.
    """
    # If a redirect URL is provided, use it as default
    frontend_uri = redirect_uri or "http://localhost:3001"
    
    # Check if the provided URL is allowed
    if redirect_uri and not validate_redirect_uri(redirect_uri):
        # If not allowed, use the default value
        frontend_uri = "http://localhost:3001"
        logger.debug(f"Provided redirect URL not allowed: {redirect_uri}, using default value")
    
    return {
        "domain": settings.AUTH0_DOMAIN,
        "clientId": settings.AUTH0_CLIENT_ID,
        "audience": settings.AUTH0_API_AUDIENCE,
        "scope": "openid profile email",
        "redirectUri": frontend_uri,
        "allowedRedirectUris": settings.AUTH0_ALLOWED_REDIRECT_URIS,
        "callbackUrl": settings.AUTH0_CALLBACK_URL,
        "useDirectCallback": True,  # Indicates if the frontend should use its own URL as callback
        "apiBaseUrl": f"http://localhost:8080{settings.API_V1_STR}"
    }


@router.get("/logout")
async def logout(redirect_uri: Optional[str] = Query(None, description="URL to redirect after logout")):
    """
    Logs out the user and redirects to the specified page.
    
    This endpoint generates the URL for Auth0 logout which will clear the user's
    Auth0 session. After logout, Auth0 will redirect to the specified redirect_uri.
    
    Args:
        redirect_uri: Optional URL to redirect after logout
        
    Returns:
        dict: Contains the logout_url for redirecting the user
        
    Raises:
        HTTPException: If the redirect_uri is not in the allowed list
    """
    # Validate the redirect URL if provided
    if redirect_uri and not validate_redirect_uri(redirect_uri):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Redirect URL not allowed: {redirect_uri}"
        )
    
    # Use the provided redirect URL or the default
    return_to = urllib.parse.quote(redirect_uri or "http://localhost:8000")
    logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?client_id={settings.AUTH0_CLIENT_ID}&returnTo={return_to}"
    
    return {"logout_url": logout_url} 