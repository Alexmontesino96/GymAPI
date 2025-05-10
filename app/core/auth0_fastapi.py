import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, Dict, List, Type

from fastapi import HTTPException, Depends, Request, Security
from fastapi.security import SecurityScopes, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security import OAuth2, OAuth2PasswordBearer, OAuth2AuthorizationCodeBearer, OpenIdConnect
from fastapi.openapi.models import OAuthFlows, OAuthFlowImplicit
from jose import jwt, JWTError
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import TypedDict
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.user import user_service
from app.db.session import get_db
from app.db.redis_client import get_redis_client, redis

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


# Volver a definir TypedDicts para JWKS
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

        # Volver a cargar JWKS al inicializar
        self.algorithms = ['RS256']
        try:
            r = urllib.request.urlopen(f'https://{domain}/.well-known/jwks.json')
            self.jwks: JwksDict = json.loads(r.read())
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from {domain}: {e}")
            # Podríamos querer manejar esto más robustamente, p.ej. reintentar o fallar
            self.jwks = {"keys": []}

        authorization_url_qs = urllib.parse.urlencode({'audience': api_audience})
        authorization_url = f'https://{domain}/authorize?{authorization_url_qs}'
        self.implicit_scheme = OAuth2ImplicitBearer(
            authorizationUrl=authorization_url,
            scopes=scopes,
            scheme_name='Auth0ImplicitBearer')
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
        Uses jose.jwt for verification, checking signature, audience, issuer, and expiry.
        """
        if creds is None:
            if self.auto_error:
                raise HTTPException(403, detail='Missing bearer token')
            else:
                return None

        token = creds.credentials
        payload: Dict = {}
        try:
            # --- VERIFICACIÓN MANUAL RESTAURADA --- 
            unverified_header = jwt.get_unverified_header(token)
            if 'kid' not in unverified_header:
                raise Auth0UnauthenticatedException(detail='Malformed token header: missing kid')

            rsa_key = {}
            if not self.jwks or not self.jwks.get("keys"):
                 raise Auth0UnauthenticatedException(detail='JWKS not loaded or invalid')
                 
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
            
            if not rsa_key:
                 raise Auth0UnauthenticatedException(detail='Invalid kid header (wrong tenant or rotated public key)')

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=f'https://{self.domain}/'
            )
            # --- FIN VERIFICACIÓN MANUAL RESTAURADA --- 

        # Capturar excepciones específicas de jose.jwt
        except jwt.ExpiredSignatureError:
            msg = 'Expired token'
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail=msg)
            else:
                logger.warning(msg)
                return None
        except jwt.JWTClaimsError as e:
            # Esto captura errores de audience, issuer, etc.
            msg = f'Invalid token claims: {str(e)}'
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail=msg)
            else:
                logger.warning(msg)
                return None
        except JWTError as e: # Captura genérica de jose
            msg = f'Malformed token: {str(e)}'
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail=msg)
            else:
                logger.warning(msg)
                return None
        # Captura de nuestra excepción si la lanzamos antes
        except Auth0UnauthenticatedException as e:
             if self.auto_error: raise e
             else: logger.warning(e.detail); return None
        # Captura genérica final por si acaso
        except Exception as e:
            logger.error(f'Unhandled exception verifying token: "{e}" M', exc_info=True)
            if self.auto_error:
                raise Auth0UnauthenticatedException(detail='Error verifying token')
            else:
                return None

        if self.scope_auto_error:
            token_scope_str: str = payload.get('scope', '')
            token_scopes = []
            
            logger.info(f"Verificando permisos. Requeridos: {security_scopes.scopes}")
            logger.info(f"Token scope string: '{token_scope_str}'")
            
            if isinstance(token_scope_str, str):
                token_scopes = token_scope_str.split()
                logger.info(f"Token scopes después de split: {token_scopes}")
            else:
                # Este caso es poco probable, pero lo manejamos por seguridad
                # (quizás auth0 cambie el formato del scope)
                logger.error(f"Token scope no es string, tipo: {type(token_scope_str)}")
                raise Auth0UnauthorizedException(detail='Token "scope" field must be a string')
            
            # Comprobar también en permissions (como array)
            token_permissions = payload.get('permissions', [])
            logger.info(f"Token permissions: {token_permissions}")
            
            if isinstance(token_permissions, list):
                token_scopes.extend(token_permissions)
                logger.info(f"Token scopes después de añadir permissions: {token_scopes}")
            
            # Crear versiones normalizadas de los permisos del token
            normalized_token_scopes = []
            for ts in token_scopes:
                normalized_token_scopes.append(ts)  # Agregar original
                # Agregar versión alternativa (con _ en lugar de : o viceversa)
                if ':' in ts:
                    normalized_token_scopes.append(ts.replace(':', '_'))
                elif '_' in ts:
                    normalized_token_scopes.append(ts.replace('_', ':'))
            
            logger.info(f"Token scopes normalizados (incluyendo ambos formatos): {normalized_token_scopes}")
            
            # Registrar tipo de segurity_scopes
            logger.info(f"security_scopes tipo: {type(security_scopes)}")
            logger.info(f"security_scopes.scopes tipo: {type(security_scopes.scopes)}")
            
            # Verificar permisos requeridos
            for scope in security_scopes.scopes:
                logger.info(f"Verificando permiso: '{scope}' (tipo: {type(scope)})")
                
                # Verificar tanto el formato original como con : y _ intercambiados
                alt_scope_format = scope.replace(':', '_') if ':' in scope else scope.replace('_', ':')
                logger.info(f"Permiso en formato alternativo: '{alt_scope_format}'")
                
                # Comprobación flexible: aceptar cualquier formato
                if scope in normalized_token_scopes or alt_scope_format in normalized_token_scopes:
                    logger.info(f"Permiso '{scope}' (o su alternativa '{alt_scope_format}') encontrado en token_scopes")
                else:
                    logger.warning(f"Permiso '{scope}' no encontrado en token_scopes normalizados")
                    logger.warning(f"Token scopes normalizados: {normalized_token_scopes}")
                    
                    # Verificar cada elemento del token_scopes para buscar similitudes
                    for ts in token_scopes:
                        similarity = 0
                        if ts.lower() == scope.lower():
                            similarity = 1
                        elif ts.replace(':', '_') == scope.replace(':', '_'):
                            similarity = 2
                        elif ts.replace('_', ':') == scope.replace('_', ':'):
                            similarity = 3
                        
                        if similarity > 0:
                            logger.warning(f"Permiso similar encontrado: '{ts}' (similitud tipo {similarity})")
                    
                    raise Auth0UnauthorizedException(detail=f'Missing "{scope}" scope',
                                                   headers={'WWW-Authenticate': f'Bearer scope="{security_scopes.scope_str}"'})
            
            logger.info("Verificación de permisos completada con éxito")
        
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


# Función para inicializar Auth0 usando get_settings
def initialize_auth0() -> Auth0:
    settings = get_settings() # Obtener la instancia de configuración
    return Auth0(
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

# Crear la instancia auth llamando a la función
auth = initialize_auth0()

# Función de ayuda para obtener usuario sin permisos específicos
async def get_current_user(
    db: Session = Depends(get_db), 
    user: Auth0User = Security(auth.get_user, scopes=[]),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Obtiene el usuario actual autenticado y asegura la sincronización con la BD local.
    
    Esta función actúa como la dependencia principal para obtener el usuario.
    Después de validar el token con Auth0, llama a user_service para crear
    o actualizar el usuario en la base de datos local (sincronización Just-in-Time).
    """
    if user is None:
        raise Auth0UnauthenticatedException(detail="No se pudieron validar las credenciales")

    # --- Sincronización Just-in-Time ---    
    try:
        # Primero verificar si el usuario ya existe en caché
        if redis_client:
            cached_user = await user_service.get_user_by_auth0_id_cached(
                db=db, 
                auth0_id=user.id, 
                redis_client=redis_client
            )
            if cached_user:
                # Si ya existe en caché, devolver sin consultar la base de datos
                return user

        # Si no está en caché o no hay Redis, proceder con la sincronización normal
        # Prepara los datos mínimos necesarios para la sincronización
        auth0_user_data = {
            "sub": user.id,  # 'sub' es el id de Auth0
            "email": getattr(user, "email", None),
            "name": getattr(user, "name", None),
            "picture": getattr(user, "picture", None),
            "email_verified": getattr(user, "email_verified", None)
        }
        
        # Llama al servicio para crear o actualizar el usuario localmente
        db_user = user_service.create_or_update_auth0_user(db, auth0_user_data)
        
        # Opcional: Podríamos enriquecer el objeto 'user' (Auth0User)
        # con el ID interno de la BD si fuera necesario en los endpoints.
        # user.db_id = db_user.id 
        
    except ImportError:
        logger.error("Error al importar user_service para sincronización JIT.")
        # Decide si lanzar excepción o continuar sin sincronizar
    except Exception as e:
        logger.error(f"Error durante la sincronización Just-in-Time del usuario {user.id}: {str(e)}", exc_info=True)
        # Decide si lanzar excepción o continuar sin sincronizar.
        # Podría ser problemático si el usuario NO existe localmente y falla la creación.
        # Considerar lanzar HTTPException si la sincronización es crítica.

    return user # Devolver el usuario original de Auth0 (posiblemente enriquecido)


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