from typing import Dict, List, Optional, Any
import json

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2, OAuth2PasswordBearer
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from auth0.authentication import GetToken
from auth0.authentication.token_verifier import TokenVerifier, AsymmetricSignatureVerifier
from auth0.management import Auth0

from app.core.config import get_settings

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Esquema OAuth2 personalizado para flujo de código de autorización con PKCE
class OAuth2AuthorizationCodePKCE(OAuth2):
    def __init__(
        self,
        authorizationUrl: str,
        tokenUrl: str,
        scopes: dict = None,
        auto_error: bool = True,
    ):
        if scopes is None:
            scopes = {}
        flows = OAuthFlowsModel(
            authorizationCode={
                "authorizationUrl": authorizationUrl,
                "tokenUrl": tokenUrl,
                "scopes": scopes
            }
        )
        super().__init__(flows=flows, scheme_name="oauth2", auto_error=auto_error)

# Esquema OAuth2 para flujo de código con PKCE (para Swagger UI)
oauth2_scheme = OAuth2AuthorizationCodePKCE(
    authorizationUrl=f"https://{get_settings().AUTH0_DOMAIN}/authorize?audience={get_settings().AUTH0_API_AUDIENCE}",
    tokenUrl=f"https://{get_settings().AUTH0_DOMAIN}/oauth/token",
    scopes={
        "openid": "OpenID profile",
        "profile": "Profile information",
        "email": "Email information",
    }
)

# Inicializar el token verifier de Auth0
signature_verifier = AsymmetricSignatureVerifier(
    f"https://{get_settings().AUTH0_DOMAIN}/.well-known/jwks.json"
)

token_verifier = TokenVerifier(
    signature_verifier=signature_verifier,
    issuer=get_settings().AUTH0_ISSUER,
    audience=get_settings().AUTH0_API_AUDIENCE
)

# Cliente de autenticación de Auth0
auth0_client = GetToken(get_settings().AUTH0_DOMAIN, get_settings().AUTH0_CLIENT_ID, client_secret=get_settings().AUTH0_CLIENT_SECRET)

# Variable para almacenar el cliente de gestión (inicialización diferida)
_mgmt_api_client = None

async def get_management_client():
    """
    Obtiene un cliente de gestión de Auth0, creándolo si no existe.
    """
    global _mgmt_api_client
    if _mgmt_api_client is None:
        token_response = auth0_client.client_credentials(f'https://{get_settings().AUTH0_DOMAIN}/api/v2/')
        mgmt_api_token = token_response['access_token']
        _mgmt_api_client = Auth0(get_settings().AUTH0_DOMAIN, mgmt_api_token)
    return _mgmt_api_client

async def verify_token(token: str) -> Dict:
    """
    Verifica el token JWT usando el verificador de Auth0.
    """
    try:
        # Quitar el prefijo "Bearer " si existe
        if token.startswith("Bearer "):
            token = token[7:]
            
        # Verificar el token
        token_verifier.verify(token)
        
        # Decodificar el token para obtener los claims
        payload = jwt.decode(
            token,
            options={"verify_signature": False},  # Ya verificamos con Auth0
        )
        
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Credenciales de autenticación inválidas: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Obtiene el usuario actual a partir del token de autenticación.
    """
    try:
        payload = await verify_token(token)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No se pudieron validar las credenciales: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_with_permissions(
    required_permissions: List[str] = [],
    token: str = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """
    Verifica que el usuario actual tenga los permisos requeridos.
    """
    payload = await get_current_user(token=token)
    
    if not required_permissions:
        return payload
    
    token_permissions = payload.get("permissions", [])
    
    for permission in required_permissions:
        if permission not in token_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes permiso para realizar esta acción: {permission}",
            )
    
    return payload

def exchange_code_for_token(code: str, redirect_uri: str) -> Dict[str, Any]:
    """
    Intercambia un código de autorización por un token de acceso.
    """
    try:
        token_response = auth0_client.authorization_code(
            code=code,
            redirect_uri=redirect_uri
        )
        return token_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al intercambiar el código por token: {str(e)}"
        )

def get_swagger_ui_oauth2_redirect_html():
    settings = get_settings()
    return {
        "authorizationUrl": f"https://{settings.AUTH0_DOMAIN}/authorize?audience={settings.AUTH0_API_AUDIENCE}",
        "tokenUrl": f"https://{settings.AUTH0_DOMAIN}/oauth/token",
        "refreshUrl": None,
        "scopes": {
            "openid": "OpenID Connect",
            "profile": "User profile",
            "email": "User email"
        },
    }

def get_jwks():
    settings = get_settings()
    jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    return requests.get(jwks_url).json()

def setup_auth0_jwt(app):
    settings = get_settings()
    app.jwt_decode_options = {
        "verify_signature": True,
        "verify_aud": True,
        "verify_iat": True,
        "verify_exp": True,
        "verify_nbf": False,
        "verify_jti": False,
        "verify_at_hash": False,
        "leeway": 0,
    }
    app.jwt_decode_issuer = settings.AUTH0_ISSUER,
    app.jwt_decode_audience = settings.AUTH0_API_AUDIENCE

def get_auth0_management_client():
    global _mgmt_api_client
    settings = get_settings()
    
    if not _mgmt_api_client:
        auth0_client = GetToken(settings.AUTH0_DOMAIN, settings.AUTH0_CLIENT_ID, client_secret=settings.AUTH0_CLIENT_SECRET)
        try:
            # Obtener token de acceso para la API de gestión
            token_response = auth0_client.client_credentials(f'https://{settings.AUTH0_DOMAIN}/api/v2/')
            mgmt_api_token = token_response['access_token']
            _mgmt_api_client = Auth0(settings.AUTH0_DOMAIN, mgmt_api_token)
        except Exception as e:
            logger.error(f"Error al inicializar Auth0 Management API: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error de configuración de Auth0: {str(e)}")
    
    return _mgmt_api_client 