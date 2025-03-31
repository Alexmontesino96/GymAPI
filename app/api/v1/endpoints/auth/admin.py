from app.api.v1.endpoints.auth.common import *

router = APIRouter()

@router.post("/webhook/user-created", status_code=201)
async def webhook_user_created(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook that receives notifications from Auth0 when a new user registers.
    
    This endpoint is called by Auth0 whenever a new user is created. It verifies
    the request authenticity using a shared secret, HMAC signature, and timestamp
    validation to prevent replay attacks. Once verified, it creates or updates
    the user in the local database.
    
    Security features:
    - Bearer token validation
    - Timestamp verification (rejects events older than 5 minutes)
    - HMAC signature verification
    - Comprehensive logging
    
    Args:
        request: The FastAPI request object
        db: SQLAlchemy database session
        
    Returns:
        dict: Status of the user synchronization
    """
    try:
        # Verify secret key in Authorization header
        auth_header = request.headers.get("Authorization", "")
        timestamp_header = request.headers.get("X-Auth0-Hook-Timestamp", "")
        signature_header = request.headers.get("X-Auth0-Signature", "")
        
        # Verify that the necessary headers are present
        if not all([auth_header, timestamp_header, signature_header]):
            logger.warning("Incomplete webhook headers", 
                          extra={"has_auth": bool(auth_header), 
                                "has_timestamp": bool(timestamp_header),
                                "has_signature": bool(signature_header)})
            return JSONResponse(
                status_code=401,
                content={"message": "Incomplete authentication headers", "success": False}
            )
        
        expected_key = settings.AUTH0_WEBHOOK_SECRET
        
        # Verify basic token
        if expected_key and not auth_header.startswith(f"Bearer {expected_key}"):
            logger.warning("Invalid webhook token")
            return JSONResponse(
                status_code=401,
                content={"message": "Invalid authentication key", "success": False}
            )
            
        # Verify timestamp to prevent replay attacks
        try:
            event_timestamp = int(timestamp_header)
            current_time = int(time.time())
            
            # Reject events older than 5 minutes
            if abs(current_time - event_timestamp) > 300:
                logger.warning("Expired webhook timestamp", 
                              extra={"timestamp_diff": abs(current_time - event_timestamp)})
                return JSONResponse(
                    status_code=400,
                    content={"message": "Expired or invalid timestamp", "success": False}
                )
        except (ValueError, TypeError):
            logger.warning("Invalid webhook timestamp", extra={"timestamp": timestamp_header})
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid timestamp format", "success": False}
            )
        
        # Get user data
        body_bytes = await request.body()
        payload = json.loads(body_bytes)
        
        # Verify signature if configured
        if expected_key and signature_header:
            import hmac
            import hashlib
            
            # Calculate expected HMAC (auth0 signs timestamp.payload)
            message = f"{timestamp_header}.{body_bytes.decode('utf-8')}"
            expected_signature = hmac.new(
                expected_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures securely against timing attacks
            if not hmac.compare_digest(signature_header, expected_signature):
                logger.warning("Invalid webhook signature")
                return JSONResponse(
                    status_code=401,
                    content={"message": "Invalid signature", "success": False}
                )
                
        logger.info("Webhook received and verified", 
                   extra={"event_type": payload.get("event", {}).get("type", "unknown")})
        
        # Verify that it's a user creation event
        event_type = payload.get("event", {}).get("type")
        if event_type != "user.created" and event_type != "user_created":
            logger.info(f"Ignored event: {event_type}")
            return {"message": f"Ignored event: {event_type}"}
        
        # Extract user data
        user_data = payload.get("user", {})
        if not user_data:
            logger.warning("User data not found in webhook")
            return {"message": "No user data found in notification"}
        
        # Create or update the user in the local database
        db_user = user_service.create_or_update_auth0_user(db, user_data)
        
        logger.info("User synchronized by webhook", 
                   extra={"user_id": db_user.id, "email": db_user.email})
        
        return {
            "message": "User synchronized successfully",
            "user_id": db_user.id,
            "email": db_user.email
        }
    except Exception as e:
        logger.exception("Error processing webhook", exc_info=True)
        # Return 200 so Auth0 doesn't retry, but log the error
        return {
            "message": f"Error processing webhook: {str(e)}",
            "success": False
        }


# Model for the admin creation request
class CreateAdminRequest(BaseModel):
    secret_key: str


@router.post("/create-admin", status_code=201)
async def create_admin_user(
    request_data: CreateAdminRequest,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:users"]),
):
    """
    Creates an administrator user.
    
    This endpoint allows promoting a user to admin status. It requires both
    the 'admin:users' scope (to ensure only admins can create other admins)
    and a secret key as an additional security measure.
    
    The endpoint either updates an existing user to admin status, or creates
    a new admin user if the user doesn't exist in the local database yet.
    
    Args:
        request_data: Request containing the secret key
        db: SQLAlchemy database session
        current_user: The authenticated user, injected by the security dependency
        
    Returns:
        dict: Status and details of the admin user
        
    Raises:
        HTTPException: For invalid secret key or missing user ID
    """
    # Verify the secret key
    if request_data.secret_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect secret key"
        )
    
    # Verify that the current user exists in the database
    user_id = current_user.id
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=user_id)
    
    # If the user doesn't exist, create them
    if not db_user:
        # Create a basic user with token data
        user_data = {
            "auth0_id": user_id,
            "email": getattr(current_user, "email", "admin@example.com"),
            "full_name": getattr(current_user, "name", "Admin"),
            "is_superuser": True,
            "role": "ADMIN"
        }
        
        db_user = user_service.create_user_from_auth0(db, user_data)
    else:
        # Update to admin if already exists
        db_user = user_service.update_to_admin(db, db_user.id)
    
    return {
        "message": "User successfully updated to administrator",
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": db_user.role.value if hasattr(db_user.role, 'value') else db_user.role,
            "is_superuser": db_user.is_superuser
        }
    } 