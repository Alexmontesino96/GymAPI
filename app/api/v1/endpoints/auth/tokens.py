from app.api.v1.endpoints.auth.common import *

router = APIRouter()

@router.options("/token")
async def options_token():
    """
    Handles OPTIONS requests for the /token endpoint (pre-flight CORS).
    
    This endpoint is used by browsers to check if they're allowed to make
    cross-origin requests to the token endpoint. It returns appropriate
    CORS headers to allow the actual request.
    
    Returns:
        JSONResponse: Empty content with CORS headers
    """
    headers = {
        "Access-Control-Allow-Origin": "*",  # Or a more restrictive list of domains
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400",  # 24 hours
    }
    
    return JSONResponse(content={}, headers=headers)

@router.post("/token")
async def exchange_token(
    request: Request,
    code: Optional[str] = Body(None, description="Authorization code from Auth0"),
    code_verifier: Optional[str] = Body(None, description="PKCE Code Verifier"),
    redirect_uri: Optional[str] = Body(None, description="Redirect URL used in the initial request"),
    grant_type: Optional[str] = Body("authorization_code", description="OAuth2 grant type"),
    client_id: Optional[str] = Body(None, description="Auth0 client ID"),
    client_secret: Optional[str] = Body(None, description="Auth0 client secret"),
):
    """
    Exchanges an authorization code for access and refresh tokens.
    
    This endpoint implements the OAuth2 token exchange, allowing clients to
    obtain access tokens after receiving an authorization code. It supports
    both JSON and form-encoded requests, includes rate limiting protection,
    and implements PKCE for enhanced security.
    
    Args:
        request: The FastAPI request object
        code: Authorization code from Auth0
        code_verifier: PKCE code verifier (paired with code_challenge from /login)
        redirect_uri: Redirect URI used in the initial authorization request
        grant_type: OAuth2 grant type (default: "authorization_code")
        client_id: Auth0 client ID (optional, defaults to server config)
        client_secret: Auth0 client secret (optional, defaults to server config)
        
    Returns:
        dict: Token response containing access_token, refresh_token, etc.
        
    Raises:
        HTTPException: For rate limiting, invalid parameters, or Auth0 errors
    """
    settings = get_settings()
    
    # Apply rate limiting
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        logger.warning("Rate limit exceeded", extra={"client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later."
        )

    try:
        # Extract data from body if coming as form
        form_data = {}
        if request.headers.get("content-type") == "application/x-www-form-urlencoded":
            form_data = await request.form()
            form_data_dict = dict(form_data)
            
            logger.debug("Form received in /token", extra={
                "content_type": "application/x-www-form-urlencoded",
                "has_code": "code" in form_data_dict,
                "has_code_verifier": "code_verifier" in form_data_dict,
                "has_redirect_uri": "redirect_uri" in form_data_dict
            })
            
            if not code:
                code = form_data.get("code", "")
            
            if not code_verifier:
                code_verifier = form_data.get("code_verifier", "")
            
            if not redirect_uri:
                redirect_uri = form_data.get("redirect_uri", "")
            
            if not grant_type or grant_type == "authorization_code":
                grant_type = form_data.get("grant_type", "authorization_code")
            
            if not client_id:
                client_id = form_data.get("client_id", "")
            
            if not client_secret:
                client_secret = form_data.get("client_secret", "")
        else:
            logger.debug("JSON received in /token", extra={
                "content_type": request.headers.get("content-type", "unknown"),
                "has_code": bool(code),
                "has_code_verifier": bool(code_verifier),
                "has_redirect_uri": bool(redirect_uri)
            })

        # Verify that the code is present
        if not code:
            logger.warning("Token exchange attempt without authorization code")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code is required"
            )
        
        # Validate the redirect URL if provided
        if redirect_uri:
            # Explicitly allow some common URLs
            if redirect_uri in ["http://localhost:3001", "http://localhost:3000"]:
                logger.debug("Redirect URL explicitly allowed", extra={"redirect_uri": redirect_uri})
            elif not validate_redirect_uri(redirect_uri):
                logger.warning("Redirect URL not allowed", extra={"redirect_uri": redirect_uri})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Redirect URL not allowed: {redirect_uri}"
                )
            
        # Use the provided redirect URL or the default one
        callback_url = redirect_uri if redirect_uri else settings.AUTH0_CALLBACK_URL
        
        # Use provided values or default values
        client_id_to_use = client_id if client_id else settings.AUTH0_CLIENT_ID
        client_secret_to_use = client_secret if client_secret else settings.AUTH0_CLIENT_SECRET
        
        # Verify that the client_id is valid
        if client_id_to_use != settings.AUTH0_CLIENT_ID:
            logger.warning("Invalid Client ID", extra={"provided_client_id": "[REDACTED]"})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Client ID"
            )
        
        token_url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
        payload = {
            "grant_type": grant_type,
            "client_id": client_id_to_use,
            "client_secret": client_secret_to_use,
            "code": code,
            "redirect_uri": callback_url,
        }
        
        # Add code_verifier if provided (for PKCE)
        if code_verifier:
            payload["code_verifier"] = code_verifier
            logger.debug("Using PKCE code_verifier")
        
        logger.info("Exchanging code for tokens", extra={
            "grant_type": grant_type,
            "redirect_uri": callback_url
        })
        
        # Use urllib directly for code-to-token exchange
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        with urllib.request.urlopen(req) as response:
            token_data = json.loads(response.read().decode())
            logger.info("Tokens received successfully")
            return token_data
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error("Error in token exchange", extra={"error": error_msg})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error exchanging code for tokens: {error_msg}",
        ) 