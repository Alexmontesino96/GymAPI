import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, Dict, List, Type

from fastapi import HTTPException, Depends, Request, Security
from fastapi.security import SecurityScopes, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security import OAuth2, OAuth2PasswordBearer, OAuth2AuthorizationCodeBearer, OpenIdConnect
from fastapi.openapi.models import OAuthFlows, OAuthFlowImplicit
from jose import jwt
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import TypedDict

from app.core.config import settings

logger = logging.getLogger('fastapi_auth0')

auth0_rule_namespace: str = 'https://github.com/dorinclisu/fastapi-auth0/'


class Auth0UnauthenticatedException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        """Returns HTTP 401"""
        super().__init__(401, detail, **kwargs)


class Auth0UnauthorizedException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        """Returns HTTP 403"""
        super().__init__(403, detail, **kwargs)


class HTTPAuth0Error(BaseModel):
    detail: str


unauthenticated_response: Dict = {401: {'model': HTTPAuth0Error}}
unauthorized_response: Dict = {403: {'model': HTTPAuth0Error}}
security_responses: Dict = {**unauthenticated_response, **unauthorized_response}


class Auth0User(BaseModel):
    id: str = Field(..., alias='sub')
    permissions: Optional[List[str]] = None
    # Campos para capturar información del usuario desde el token
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    name: Optional[str] = None
    picture: Optional[str] = None


class Auth0HTTPBearer(HTTPBearer):
    async def __call__(self, request: Request):
        return await super().__call__(request)


class OAuth2ImplicitBearer(OAuth2):
    def __init__(self,
                 authorizationUrl: str,
                 scopes: Dict[str, str] = {},
                 scheme_name: Optional[str] = None,
                 auto_error: bool = True):
        flows = OAuthFlows(implicit=OAuthFlowImplicit(authorizationUrl=authorizationUrl, scopes=scopes))
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        # Overwrite parent call to prevent useless overhead, the actual auth is done in Auth0.get_user
        # This scheme is just for Swagger UI
        return None


class JwksKeyDict(TypedDict):
    kid: str
    kty: str
    use: str
    n: str
    e: str


class JwksDict(TypedDict):
    keys: List[JwksKeyDict]


class Auth0:
    def __init__(self, domain: str, api_audience: str, scopes: Dict[str, str] = {},
                 auto_error: bool = True, scope_auto_error: bool = True, email_auto_error: bool = False,
                 auth0user_model: Type[Auth0User] = Auth0User):
        self.domain = domain
        self.audience = api_audience

        self.auto_error = auto_error
        self.scope_auto_error = scope_auto_error
        self.email_auto_error = email_auto_error

        self.auth0_user_model = auth0user_model

        self.algorithms = ['RS256']
        r = urllib.request.urlopen(f'https://{domain}/.well-known/jwks.json')
        self.jwks: JwksDict = json.loads(r.read())

        authorization_url_qs = urllib.parse.urlencode({'audience': api_audience})
        authorization_url = f'https://{domain}/authorize?{authorization_url_qs}'
        self.implicit_scheme = OAuth2ImplicitBearer(
            authorizationUrl=authorization_url,
            scopes=scopes,
            scheme_name='Auth0ImplicitBearer')
        self.password_scheme = OAuth2PasswordBearer(tokenUrl=f'https://{domain}/oauth/token', scopes=scopes)
        self.authcode_scheme = OAuth2AuthorizationCodeBearer(
            authorizationUrl=authorization_url,
            tokenUrl=f'https://{domain}/oauth/token',
            scopes=scopes)
        self.oidc_scheme = OpenIdConnect(openIdConnectUrl=f'https://{domain}/.well-known/openid-configuration')

    async def get_user(self,
                      security_scopes: SecurityScopes,
                      creds: Optional[HTTPAuthorizationCredentials] = Depends(Auth0HTTPBearer(auto_error=False)),
                      ) -> Optional[Auth0User]:
        """
        Verify the Authorization: Bearer token and return the user.
        If there is any problem and auto_error = True then raise Auth0UnauthenticatedException or Auth0UnauthorizedException,
        otherwise return None.

        Not to be called directly, but to be placed within a Depends() or Security() wrapper.
        Example: def path_op_func(user: Auth0User = Security(auth.get_user)).
        """
        if creds is None:
            if self.auto_error:
                # See HTTPBearer from FastAPI:
                # latest - https://github.com/tiangolo/fastapi/blob/master/fastapi/security/http.py
                # 0.65.1 - https://github.com/tiangolo/fastapi/blob/aece74982d7c9c1acac98e2c872c4cb885677fc7/fastapi/security/http.py
                raise HTTPException(403, detail='Missing bearer token')  # must be 403 until solving https://github.com/tiangolo/fastapi/pull/2120
            else:
                return None

        token = creds.credentials
        payload: Dict = {}
        try:
            unverified_header = jwt.get_unverified_header(token)

            if 'kid' not in unverified_header:
                msg = 'Malformed token header'
                if self.auto_error:
                    raise Auth0UnauthenticatedException(detail=msg)
                else:
                    logger.warning(msg)
                    return None

            rsa_key = {}
            for key in self.jwks['keys']:
                if key['kid'] == unverified_header['kid']:
                    rsa_key = {
                        'kty': key['kty'],
                        'kid': key['kid'],
                        'use': key['use'],
                        'n': key['n'],
                        'e': key['e']
                    }
                    break
            if rsa_key:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=self.algorithms,
                    audience=self.audience,
                    issuer=f'https://{self.domain}/'
                )
            else:
                msg = 'Invalid kid header (wrong tenant or rotated public key)'
                if self.auto_error:
                    raise Auth0UnauthenticatedException(detail=msg)
                else:
                    logger.warning(msg)
                    return None

        except jwt.ExpiredSignatureError:
            msg = 'Expired token'
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail=msg)
            else:
                logger.warning(msg)
                return None

        except jwt.JWTClaimsError:
            msg = 'Invalid token claims (wrong issuer or audience)'
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail=msg)
            else:
                logger.warning(msg)
                return None

        except jwt.JWTError:
            msg = 'Malformed token'
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail=msg)
            else:
                logger.warning(msg)
                return None

        except Auth0UnauthenticatedException:
            raise

        except Exception as e:
            # This is an unlikely case but handle it just to be safe (maybe the token is specially crafted to bug our code)
            logger.error(f'Handled exception decoding token: "{e}"', exc_info=True)
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail='Error decoding token')
            else:
                return None

        if self.scope_auto_error:
            token_scope_str: str = payload.get('scope', '')

            if isinstance(token_scope_str, str):
                token_scopes = token_scope_str.split()

                for scope in security_scopes.scopes:
                    if scope not in token_scopes:
                        raise Auth0UnauthorizedException(detail=f'Missing "{scope}" scope',
                                                       headers={'WWW-Authenticate': f'Bearer scope="{security_scopes.scope_str}"'})
            else:
                # This is an unlikely case but handle it just to be safe (perhaps auth0 will change the scope format)
                raise Auth0UnauthorizedException(detail='Token "scope" field must be a string')

        try:
            # Extraer el email de diferentes posibles lugares en el payload
            email = None
            email_verified = None
            
            # Buscar el email en claims comunes
            potential_email_claims = [
                'email', 
                f'{auth0_rule_namespace}email', 
                'mail', 
                'e-mail',
                'https://example.com/email',
                'https://gymapi.com/email',
                'https://gymapi/email'
            ]
            
            # Buscar en los claims principales
            for claim in potential_email_claims:
                if claim in payload and payload[claim]:
                    email = payload[claim]
                    break
            
            # Si todavía no tenemos email, buscar en cualquier claim que contenga 'email'
            if not email:
                for key, value in payload.items():
                    if 'email' in key.lower() and value and isinstance(value, str):
                        email = value
                        break
            
            # Buscar email_verified en claims comunes
            potential_verified_claims = [
                'email_verified', 
                f'{auth0_rule_namespace}email_verified',
                'https://example.com/email_verified',
                'https://gymapi.com/email_verified',
                'https://gymapi/email_verified'
            ]
            
            for claim in potential_verified_claims:
                if claim in payload and payload[claim] is not None:
                    email_verified = payload[claim]
                    break
            
            # Extraer nombre y foto si están disponibles
            name = payload.get('name', None)
            picture = payload.get('picture', None)
            
            # Crear una copia del payload para añadir los campos extraídos
            payload_with_data = dict(payload)
            if email:
                payload_with_data['email'] = email
            if email_verified is not None:
                payload_with_data['email_verified'] = email_verified
            if name:
                payload_with_data['name'] = name
            if picture:
                payload_with_data['picture'] = picture
            
            # Crear el objeto de usuario
            user = self.auth0_user_model(**payload_with_data)
            
            # Asignar manualmente si no se pudo extraer del payload
            if not hasattr(user, 'email') or user.email is None:
                user.email = email
            if not hasattr(user, 'email_verified') or user.email_verified is None:
                user.email_verified = email_verified
            if not hasattr(user, 'name') or user.name is None:
                user.name = name
            if not hasattr(user, 'picture') or user.picture is None:
                user.picture = picture

            if self.email_auto_error and not user.email:
                raise Auth0UnauthorizedException(detail=f'Missing email claim (check auth0 rule "Add email to access token")')

            return user

        except ValidationError as e:
            logger.error(f'Handled exception parsing Auth0User: "{e}"', exc_info=True)
            if self.auto_error:
                raise Auth0UnauthorizedException(detail='Error parsing Auth0User')
            else:
                return None


# Inicializar Auth0 con la configuración del proyecto
auth = Auth0(
    domain=settings.AUTH0_DOMAIN,
    api_audience=settings.AUTH0_API_AUDIENCE,
    scopes={
        "openid": "OpenID profile",
        "profile": "Profile information",
        "email": "Email information",
        "read:users": "Leer información de usuarios",
        "write:users": "Crear o modificar usuarios",
        "delete:users": "Eliminar usuarios",
        "read:trainer-members": "Leer relaciones entrenador-miembro",
        "write:trainer-members": "Crear o modificar relaciones entrenador-miembro",
        "delete:trainer-members": "Eliminar relaciones entrenador-miembro"
    }
)

# Función de ayuda para obtener usuario sin permisos específicos
async def get_current_user(user: Auth0User = Security(auth.get_user, scopes=[])):
    """
    Obtiene el usuario actual autenticado.
    """
    if user is None:
        raise Auth0UnauthenticatedException(detail="No se pudieron validar las credenciales")
    return user


async def get_current_user_with_permissions(required_permissions: List[str] = [], user: Auth0User = Security(auth.get_user)):
    """
    Verifica que el usuario tenga los permisos específicos.
    """
    if not user:
        raise Auth0UnauthenticatedException(detail="No se pudieron validar las credenciales")
    
    user_permissions = user.permissions or []
    
    for permission in required_permissions:
        if permission not in user_permissions:
            raise Auth0UnauthorizedException(detail=f"No tienes permiso para realizar esta acción: {permission}")
    
    return user 