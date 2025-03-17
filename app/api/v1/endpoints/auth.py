import urllib.parse
import json
import urllib.request
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, HTTPException, status, Security, Body
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.services.user import user_service
from app.db.session import get_db

router = APIRouter()


@router.get("/login")
def login_redirect():
    """
    Devuelve la URL para iniciar sesión en Auth0
    """
    # Verificar el valor correcto de AUTH0_API_AUDIENCE
    print(f"Using API audience: {settings.AUTH0_API_AUDIENCE}")
    
    authorization_url_qs = urllib.parse.urlencode({
        'audience': settings.AUTH0_API_AUDIENCE,
        'scope': 'openid profile email',
        'response_type': 'code',
        'client_id': settings.AUTH0_CLIENT_ID,
        'redirect_uri': settings.AUTH0_CALLBACK_URL,
    })
    auth_url = f"https://{settings.AUTH0_DOMAIN}/authorize?{authorization_url_qs}"
    
    return {"auth_url": auth_url}


@router.get("/login-redirect")
def login_redirect_automatic():
    """
    Redirige automáticamente al usuario a la página de login de Auth0
    """
    # Verificar el valor correcto de AUTH0_API_AUDIENCE
    print(f"Using API audience: {settings.AUTH0_API_AUDIENCE}")
    
    authorization_url_qs = urllib.parse.urlencode({
        'audience': settings.AUTH0_API_AUDIENCE,
        'scope': 'openid profile email',
        'response_type': 'code',
        'client_id': settings.AUTH0_CLIENT_ID,
        'redirect_uri': settings.AUTH0_CALLBACK_URL,
    })
    auth_url = f"https://{settings.AUTH0_DOMAIN}/authorize?{authorization_url_qs}"
    
    return RedirectResponse(auth_url)


@router.get("/callback")
async def auth0_callback(request: Request):
    """
    Callback que recibe el código de Auth0 después del login
    y lo intercambia por un token de acceso
    """
    # Verificar si hay un error en los parámetros de la URL
    params = dict(request.query_params)
    if "error" in params:
        error_msg = params.get("error_description", params.get("error", "Error desconocido"))
        if "Service not found" in error_msg and settings.AUTH0_API_AUDIENCE in error_msg:
            # Error específico de audience no configurado correctamente
            detail = f"Error de configuración en Auth0: El API Audience '{settings.AUTH0_API_AUDIENCE}' no está configurado correctamente. Por favor, verifica la configuración de Auth0."
        else:
            detail = f"Error en la autenticación con Auth0: {error_msg}"
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    
    # Verificar que el código está presente
    code = params.get("code")
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parámetro 'code' requerido"
        )
    
    try:
        token_url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.AUTH0_CLIENT_ID,
            "client_secret": settings.AUTH0_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.AUTH0_CALLBACK_URL,
        }
        
        # Utilizar urllib directamente para el intercambio de código por token
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        with urllib.request.urlopen(req) as response:
            token_data = json.loads(response.read().decode())
            return token_data
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar el callback: {str(e)}",
        )


@router.get("/me")
async def read_users_me(user: Auth0User = Security(auth.get_user, scopes=[])):
    """
    Obtener información del usuario actual autenticado con Auth0
    """
    return user


@router.get("/test-email")
async def test_email_in_token(request: Request, user: Auth0User = Security(auth.get_user, scopes=[])):
    """
    Ruta de prueba para verificar que el email del usuario se incluye en el token JWT
    """
    # Obtener el token completo desde la cabecera Authorization
    auth_header = request.headers.get("Authorization", "")
    token = None
    payload_raw = {}
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Quitar "Bearer " del inicio
        try:
            # Decodificar el token sin verificar la firma para ver todos los claims
            # Esto es solo para diagnóstico y no debe usarse en producción
            from jose import jwt
            # Especificar una clave vacía y deshabilitar la verificación
            payload_raw = jwt.decode(token, '', options={"verify_signature": False})
        except Exception as e:
            payload_raw = {"error": str(e)}
    
    return {
        "user_id": user.id,
        "email": user.email,
        "email_verified": getattr(user, "email_verified", None),
        "email_included": user.email is not None,
        "all_claims": user.dict(),
        "raw_token_payload": payload_raw,
        "token_preview": token[:20] + "..." if token else None
    }


@router.get("/logout")
async def logout():
    """
    Cierra la sesión del usuario y redirige a la página de inicio
    """
    return_to = urllib.parse.quote("http://localhost:8000")
    logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?client_id={settings.AUTH0_CLIENT_ID}&returnTo={return_to}"
    
    return {"logout_url": logout_url}


@router.post("/webhook/user-created", status_code=201)
async def webhook_user_created(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook que recibe notificaciones de Auth0 cuando se registra un nuevo usuario.
    Este endpoint debe estar protegido con un secreto compartido para evitar llamadas no autorizadas.
    """
    try:
        # Verificar la clave secreta en el encabezado Authorization
        # Esta misma clave debe configurarse en Auth0 como un secreto
        auth_header = request.headers.get("Authorization", "")
        expected_key = settings.AUTH0_WEBHOOK_SECRET  # Este valor debe añadirse a la configuración
        
        # Si la clave está configurada, verificamos
        if expected_key and not auth_header.startswith(f"Bearer {expected_key}"):
            print("ERROR: Clave secreta de webhook inválida o ausente")
            return {
                "message": "Clave de autenticación inválida",
                "success": False
            }
        
        # Obtener los datos del usuario
        payload = await request.json()
        print(f"Webhook recibido: {payload}")
        
        # Verificar que se trata de un evento de creación de usuario
        event_type = payload.get("event", {}).get("type")
        if event_type != "user.created" and event_type != "user_created":
            return {"message": f"Evento ignorado: {event_type}"}
        
        # Extraer datos de usuario
        user_data = payload.get("user", {})
        if not user_data:
            return {"message": "No se encontraron datos de usuario en la notificación"}
        
        # Crear o actualizar el usuario en la base de datos local
        db_user = user_service.create_or_update_auth0_user(db, user_data)
        
        return {
            "message": "Usuario sincronizado correctamente",
            "user_id": db_user.id,
            "email": db_user.email
        }
    except Exception as e:
        print(f"Error en webhook: {str(e)}")
        # Devolvemos 200 para que Auth0 no reintente, pero registramos el error
        return {
            "message": f"Error procesando el webhook: {str(e)}",
            "success": False
        }


# Modelo para la solicitud de creación de administrador
class CreateAdminRequest(BaseModel):
    secret_key: str


@router.post("/create-admin", status_code=201)
async def create_admin_user(
    request_data: CreateAdminRequest,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=[]),
):
    """
    Convierte al usuario actual en administrador con todos los permisos.
    Requiere una clave secreta para autorizar esta operación.
    Esta función debe usarse con precaución, ya que otorga privilegios de administrador.
    """
    # Verificar la clave secreta
    if request_data.secret_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clave secreta inválida para crear administradores"
        )
        
    try:
        # Convertir el usuario Auth0 actual en un administrador
        user_data = {
            "sub": current_user.id,
            "email": getattr(current_user, "email", None),
            # Añadir otros datos disponibles en el token
            "name": getattr(current_user, "name", None),
            "picture": getattr(current_user, "picture", None),
        }
        
        # Crear o actualizar el usuario como administrador
        admin_user = user_service.create_admin_from_auth0(db, user_data)
        
        return {
            "message": "Usuario convertido en administrador correctamente",
            "user_id": admin_user.id,
            "email": admin_user.email,
            "is_admin": True,
            "is_superuser": admin_user.is_superuser,
            "note": "Este usuario ahora tiene permisos de administrador en la base de datos local. Para pruebas, puedes simular que tienes todos los permisos en Auth0 usando postman o una herramienta similar."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando usuario administrador: {str(e)}"
        )


@router.get("/get-user-email")
async def get_user_email(user: Auth0User = Security(auth.get_user, scopes=[])):
    """
    Endpoint para obtener el email del usuario directamente desde Auth0 usando el Management API
    """
    try:
        from app.core.auth0_helper import get_management_client
        
        # Obtener el ID de Auth0 del usuario actual
        auth0_id = user.id
        
        # Obtener el cliente de gestión de Auth0
        mgmt_api = await get_management_client()
        
        # Extraer el ID de usuario sin el prefijo "auth0|"
        auth0_user_id = auth0_id
        if auth0_user_id.startswith("auth0|"):
            auth0_user_id = auth0_user_id.replace("auth0|", "")
        
        # Obtener la información completa del usuario desde Auth0
        user_info = mgmt_api.users.get(auth0_user_id)
        
        # Extraer el email
        email = user_info.get("email", "No disponible")
        email_verified = user_info.get("email_verified", False)
        
        return {
            "auth0_id": auth0_id,
            "email": email,
            "email_verified": email_verified,
            "user_info": user_info
        }
    except Exception as e:
        return {
            "error": f"Error al obtener información del usuario: {str(e)}",
            "auth0_id": user.id
        }


@router.get("/check-permissions")
async def check_permissions(current_user: Auth0User = Security(auth.get_user, scopes=[])):
    """
    Endpoint para verificar los permisos del usuario actual en el token JWT
    """
    # Extraer permisos del token
    permissions = getattr(current_user, "permissions", []) or []
    
    # Verificar permisos específicos para eventos
    has_create_events = "create:events" in permissions
    has_create_event = "create:event" in permissions  # Comprobar también formato singular
    has_admin_all = "admin:all" in permissions
    can_create_events = has_create_events or has_create_event or has_admin_all
    
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "permissions": permissions,
        "permisos_específicos": {
            "create:events (plural)": has_create_events,
            "create:event (singular)": has_create_event,
            "admin:all": has_admin_all,
            "puede_crear_eventos": can_create_events
        },
        "todos_los_claims_del_token": current_user.dict()
    } 