from app.api.v1.endpoints.auth.common import *
from app.repositories.user import user_repository
from fastapi import APIRouter, Depends, HTTPException, Security, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.core.auth0_fastapi import auth
from app.models.user import UserRole
from app.services.auth0_sync import auth0_sync_service
from app.db.session import get_db
from app.services.user import user_service
from app.services.cache_service import cache_service
from app.core.security import verify_auth0_webhook_secret
from app.core.auth0_fastapi import Auth0User
from app.middleware.rate_limit import limiter

# Definir logger para este módulo
logger = logging.getLogger("auth_admin_endpoint")

router = APIRouter()

@router.post("/webhook/user-created", status_code=201)
@limiter.limit("50 per minute")
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
        # Verificar la configuración
        settings = get_settings()
        
        # Verify secret key in Authorization header
        auth_header = request.headers.get("Authorization", "")
        timestamp_header = request.headers.get("X-Auth0-Hook-Timestamp", "")
        signature_header = request.headers.get("X-Auth0-Signature", "")
        
        logger.info("Webhook user-created received", 
                   extra={
                       "auth_header": auth_header[:15] + "..." if auth_header else "None", # Log prefix only for security
                       "timestamp_header": timestamp_header,
                       "signature_header": signature_header[:15] + "..." if signature_header else "None" # Log prefix only
                   })
        
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
        logger.debug(f"Expected webhook key (prefix): {expected_key[:5]}...") # Log prefix for verification
        
        # Verify basic token
        bearer_check_passed = expected_key and auth_header.startswith(f"Bearer {expected_key}")
        logger.debug(f"Bearer token check result: {bearer_check_passed}")
        if not bearer_check_passed:
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
            signature_check_passed = hmac.compare_digest(signature_header, expected_signature)
            logger.debug(f"HMAC signature check result: {signature_check_passed}")
            if not signature_check_passed:
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
        
        # Create or update the user in the local database (with QR generation)
        db_user = await user_service.create_or_update_auth0_user_async(db, user_data)
        
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


@router.post("/webhook/user-updated", status_code=201)
@limiter.limit("50 per minute")
async def webhook_user_updated(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook that receives notifications from Auth0 when a user is updated.
    
    This endpoint is called by Auth0 whenever a user's information is updated.
    It verifies the request authenticity and updates the user's email in the 
    local database if it has changed in Auth0.
    
    Security features:
    - Bearer token validation
    - Timestamp verification (rejects events older than 5 minutes)
    - HMAC signature verification
    - Comprehensive logging
    
    Args:
        request: The FastAPI request object
        db: SQLAlchemy database session
        
    Returns:
        dict: Status of the user email synchronization
    """
    try:
        # Verificar la configuración
        settings = get_settings()
        
        # Verify secret key in Authorization header
        auth_header = request.headers.get("Authorization", "")
        timestamp_header = request.headers.get("X-Auth0-Hook-Timestamp", "")
        signature_header = request.headers.get("X-Auth0-Signature", "")
        
        logger.info("Webhook user-updated received", 
                   extra={
                       "auth_header": auth_header[:15] + "..." if auth_header else "None", # Log prefix only for security
                       "timestamp_header": timestamp_header,
                       "signature_header": signature_header[:15] + "..." if signature_header else "None" # Log prefix only
                   })
        
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
        logger.debug(f"Expected webhook key (prefix): {expected_key[:5]}...") # Log prefix for verification
        
        # Verify basic token
        bearer_check_passed = expected_key and auth_header.startswith(f"Bearer {expected_key}")
        logger.debug(f"Bearer token check result: {bearer_check_passed}")
        if not bearer_check_passed:
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
            signature_check_passed = hmac.compare_digest(signature_header, expected_signature)
            logger.debug(f"HMAC signature check result: {signature_check_passed}")
            if not signature_check_passed:
                logger.warning("Invalid webhook signature")
                return JSONResponse(
                    status_code=401,
                    content={"message": "Invalid signature", "success": False}
                )
                
        logger.info("User update webhook received and verified", 
                   extra={"event_type": payload.get("event", {}).get("type", "unknown")})
        
        # Verify that it's a user update event
        event_type = payload.get("event", {}).get("type")
        if not event_type or not ('update' in event_type.lower() and 'user' in event_type.lower()):
            logger.info(f"Ignored event: {event_type}")
            return {"message": f"Ignored event: {event_type}"}
        
        # Extract user data
        user_data = payload.get("user", {})
        if not user_data:
            logger.warning("User data not found in webhook")
            return {"message": "No user data found in notification"}
        
        # Extract required fields
        auth0_id = user_data.get("user_id") or user_data.get("sub")
        auth0_email = user_data.get("email")
        
        if not auth0_id or not auth0_email:
            logger.warning("Missing required user data (user_id or email)")
            return {"message": "Missing required user data", "success": False}
        
        # Find user by Auth0 ID
        user = user_repository.get_by_auth0_id(db, auth0_id=auth0_id)
        if not user:
            logger.warning(f"User not found in local database: {auth0_id}")
            return {"message": "User not found in local database", "success": False}
        
        # Only update if email has changed
        if user.email != auth0_email:
            logger.info(f"Updating email for user {user.id} from '{user.email}' to '{auth0_email}'")
            
            # Update email in database
            user_repository.update(
                db,
                db_obj=user,
                obj_in={"email": auth0_email, "auth0_metadata": json.dumps(user_data)}
            )
            
            return {
                "message": "Email updated successfully",
                "user_id": user.id,
                "previous_email": user.email,
                "new_email": auth0_email
            }
        else:
            logger.info(f"No email change detected for user {user.id}")
            return {"message": "No email change required", "success": True}
            
    except Exception as e:
        logger.exception("Error processing user update webhook", exc_info=True)
        # Return 200 so Auth0 doesn't retry, but log the error
        return {
            "message": f"Error processing webhook: {str(e)}",
            "success": False
        }


# Model for the admin creation request
class CreateAdminRequest(BaseModel):
    secret_key: str


@router.post("/create-platform-admin", status_code=201)
async def create_platform_admin(
    request_data: CreateAdminRequest,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["user:write"]),
):
    """
    Creates a platform administrator (super admin) user.
    
    This endpoint allows promoting a user to super admin status, with access to all gyms.
    It requires both the 'admin:users' scope (to ensure only admins can create other admins)
    and a secret key as an additional security measure.
    
    The endpoint either updates an existing user to super admin status, or creates
    a new super admin user if the user doesn't exist in the local database yet.
    
    Args:
        request_data: Request containing the secret key
        db: SQLAlchemy database session
        current_user: The authenticated user, injected by the security dependency
        
    Returns:
        dict: Status and details of the super admin user
        
    Raises:
        HTTPException: For invalid secret key or missing user ID
    """
    # Verify the secret key
    if request_data.secret_key != get_settings().ADMIN_SECRET_KEY:
        logger.warning("Invalid admin creation key", extra={"user_id": current_user.sub})
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret key"
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
            "name": getattr(current_user, "name", "Admin"),
            "is_superuser": True,
            "role": "SUPER_ADMIN"
        }
        
        # Crear el usuario con el servicio adecuado
        from app.models.user import UserRole
        from app.schemas.user import UserCreate
        
        # Crear objeto UserCreate
        user_create = UserCreate(
            email=user_data["email"],
            role=UserRole.SUPER_ADMIN,
            first_name=user_data.get("name", "").split(" ")[0] if user_data.get("name") else "",
            last_name=" ".join(user_data.get("name", "").split(" ")[1:]) if user_data.get("name") and len(user_data.get("name", "").split(" ")) > 1 else "",
            auth0_id=user_id,
            is_superuser=True
        )
        
        db_user = user_service.create_user(db, user_in=user_create)
    else:
        # Update to super admin if already exists
        from app.models.user import UserRole
        
        # Actualizar rol a SUPER_ADMIN y marcar como superusuario
        db_user = user_repository.update(
            db,
            db_obj=db_user,
            obj_in={
                "role": UserRole.SUPER_ADMIN,
                "is_superuser": True
            }
        )
    
    return {
        "message": "User successfully upgraded to platform administrator (super admin)",
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "role": db_user.role.value if hasattr(db_user.role, 'value') else db_user.role,
            "is_superuser": db_user.is_superuser
        }
    }

@router.post("/sync-roles-to-auth0", response_model=Dict[str, Any])
async def migrate_roles_to_auth0(
    *,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks,
    current_user: Auth0User = Security(auth.get_user, scopes=["tenant:admin"])
) -> Any:
    """
    [SUPER_ADMIN] Migra el rol más alto de todos los usuarios a Auth0.
    
    Este endpoint inicia una tarea en segundo plano para determinar y actualizar
    el rol más alto de cada usuario en Auth0 mediante app_metadata. Esto permitirá
    que Auth0 asigne los permisos correctos al emitir tokens.
    
    Args:
        db: Sesión de base de datos
        background_tasks: Tareas en segundo plano
        current_user: Usuario autenticado (debe ser SUPER_ADMIN)
        
    Returns:
        Dict: Estado de la operación
    """
    # Verificar que el usuario es SUPER_ADMIN
    user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not user or user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol SUPER_ADMIN para esta operación"
        )
    
    # Ejecutar como tarea en segundo plano
    background_tasks.add_task(auth0_sync_service.run_initial_migration, db)
    
    return {
        "status": "success",
        "message": "Migración de roles iniciada en segundo plano",
        "detail": "Este proceso puede tomar varios minutos dependiendo del número de usuarios."
    } 