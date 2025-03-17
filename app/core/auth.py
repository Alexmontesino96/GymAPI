from typing import Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes, OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from jose import jwt
from pydantic import ValidationError

from app.core.config import settings

# Crear un esquema OAuth2 personalizado para flujo implícito
class OAuth2ImplicitBearer(OAuth2):
    def __init__(
        self,
        authorizationUrl: str,
        scopes: dict = None,
    ):
        if scopes is None:
            scopes = {}
        flows = OAuthFlowsModel(implicit={"authorizationUrl": authorizationUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name="oauth2")

# Esquema OAuth2 para autenticación por contraseña (para compatibilidad)
oauth2_password_scheme = OAuth2PasswordBearer(
    tokenUrl=f"https://{settings.AUTH0_DOMAIN}/oauth/token"
)

# Esquema OAuth2 para flujo implícito (para Swagger UI)
oauth2_scheme = OAuth2ImplicitBearer(
    authorizationUrl=f"https://{settings.AUTH0_DOMAIN}/authorize?audience={settings.AUTH0_API_AUDIENCE}",
    scopes={
        "openid": "OpenID profile",
        "profile": "Profile information",
        "email": "Email information",
    }
)

class Auth0:
    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_API_AUDIENCE
        self.issuer = settings.AUTH0_ISSUER
        self.algorithms = settings.AUTH0_ALGORITHMS
        self.jwks = None

    async def get_jwks(self):
        if self.jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://{self.domain}/.well-known/jwks.json")
                self.jwks = response.json()
        return self.jwks

    async def verify_token(self, token: str) -> Dict:
        jwks = await self.get_jwks()
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales de autenticación inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales de autenticación inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options={"verify_aud": True}
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token ha expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTClaimsError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Claims incorrectos: verifica audience y issuer",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudieron validar las credenciales",
                headers={"WWW-Authenticate": "Bearer"},
            )

auth0 = Auth0()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Verifica y decodifica el token JWT para obtener el usuario actual.
    """
    try:
        payload = await auth0.verify_token(token)
        return payload
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudieron validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_with_permissions(
    required_permissions: List[str] = [],
    token: str = Depends(oauth2_scheme),
):
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