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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.user import user_service
from app.db.session import get_async_db
from app.db.redis_client import get_redis_client, redis

# Import circular seguro - solo para type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User

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
        self.jwks: JwksDict = {"keys": []}
        self._jwks_last_refresh: float = 0.0
        self._load_jwks(initial=True)

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
        
        # 🔍 LOGGING SEGURO (solo DEBUG y enmascarado)
        try:
            settings = get_settings()
            if settings.DEBUG_MODE:
                logger.debug(f"🔐 AUTH0 TOKEN LENGTH: {len(token)}")
                suffix = token[-6:] if len(token) > 6 else ""
                logger.debug(f"🔐 TOKEN PREVIEW: ****{suffix}")
        except Exception:
            pass
        
        payload: Dict = {}
        try:
            # --- VERIFICACIÓN MANUAL RESTAURADA --- 
            unverified_header = jwt.get_unverified_header(token)
            if 'kid' not in unverified_header:
                raise Auth0UnauthenticatedException(detail='Malformed token header: missing kid')

            rsa_key = {}
            if not self.jwks or not self.jwks.get("keys"):
                # Intentar refrescar JWKS si no están cargadas
                self._load_jwks()
            
            # Buscar clave por kid
            rsa_key = self._find_rsa_key(unverified_header['kid'])
            if not rsa_key:
                # Posible rotación de llaves: refrescar JWKS y reintentar una vez
                logger.warning("KID no encontrado en JWKS actual. Intentando refrescar JWKS...")
                self._load_jwks(force=True)
                rsa_key = self._find_rsa_key(unverified_header['kid'])
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
            from app.core.config import get_settings
            debug_mode = get_settings().DEBUG_MODE

            token_scope_str: str = payload.get('scope', '')
            token_scopes = []

            if debug_mode:
                logger.debug(f"Verificando permisos. Requeridos: {security_scopes.scopes}")
                logger.debug(f"Token scope string: '{token_scope_str}'")

            if isinstance(token_scope_str, str):
                token_scopes = token_scope_str.split()
                if debug_mode:
                    logger.debug(f"Token scopes después de split: {token_scopes}")
            else:
                # Este caso es poco probable, pero lo manejamos por seguridad
                # (quizás auth0 cambie el formato del scope)
                logger.error(f"Token scope no es string, tipo: {type(token_scope_str)}")
                raise Auth0UnauthorizedException(detail='Token "scope" field must be a string')

            # Buscar permisos en custom claims del Action
            token_permissions = payload.get('permissions', [])
            if debug_mode:
                logger.debug(f"Token permissions (campo estándar): {token_permissions}")

            # Si no hay permisos en campo estándar, buscar en custom claims del Action
            if not token_permissions:
                token_permissions = payload.get('https://gymapi/permissions', [])
                if debug_mode:
                    logger.debug(f"Token permissions (custom claim namespace): {token_permissions}")

            # Si aún no hay permisos, intentar extraer del campo personalizado sin namespace
            if not token_permissions:
                # Buscar otros posibles custom claims de permisos
                for key in payload.keys():
                    if 'permissions' in key.lower() and isinstance(payload[key], list):
                        token_permissions = payload[key]
                        if debug_mode:
                            logger.debug(f"Token permissions encontrados en {key}: {token_permissions}")
                        break

            if debug_mode:
                logger.debug(f"Token permissions finales: {token_permissions}")

            # Si la JWT contiene alguna información del usuario
            if isinstance(token_permissions, list):
                token_scopes.extend(token_permissions)

            # Crear versiones normalizadas de los permisos del token
            normalized_scopes = normalize_scopes(token_scopes)
            if debug_mode:
                logger.debug(f"Scopes normalizados: {normalized_scopes}")
                logger.debug(f"security_scopes tipo: {type(security_scopes)}")
                logger.debug(f"security_scopes.scopes tipo: {type(security_scopes.scopes)}")

            # Verificar permisos requeridos
            for scope in security_scopes.scopes:
                if debug_mode:
                    logger.debug(f"Verificando permiso: '{scope}' (tipo: {type(scope)})")

                # Crear versión alternativa para permitir tanto formato con : como con _
                alt_scope_format = scope.replace(':', '_') if ':' in scope else scope.replace('_', ':')

                # Verificar si el scope requerido está en los scopes normalizados del token
                if scope in normalized_scopes or alt_scope_format in normalized_scopes:
                    if debug_mode:
                        logger.debug(f"Permiso '{scope}' encontrado en token_scopes")
                else:
                    # Keep warning for production (security relevant)
                    logger.warning(f"Permiso '{scope}' no encontrado en token_scopes")
                    raise Auth0UnauthorizedException(
                        detail=f'Missing "{scope}" scope',
                        headers={'WWW-Authenticate': f'Bearer scope="{security_scopes.scope_str}"'}
                    )

            if debug_mode:
                logger.debug("Verificación de permisos completada con éxito")
        
        try:
            # Extraer el email de diferentes posibles lugares en el payload
            email = None
            email_verified = None
            
            # Buscar el email en claims comunes
            potential_email_claims = [
                'email', 
                f'{auth0_rule_namespace}email', 
                'mail'
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
                f'{auth0_rule_namespace}email_verified'
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
            # Asegurar que los permisos estén en el payload
            if token_permissions:
                payload_with_data['permissions'] = token_permissions
            
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
            # Asegurar que los permisos estén asignados al objeto user
            if not hasattr(user, 'permissions') or user.permissions is None:
                user.permissions = token_permissions

            if self.email_auto_error and not user.email:
                raise Auth0UnauthorizedException(detail=f'Missing email claim (check auth0 rule "Add email to access token")')

            return user

        except ValidationError as e:
            logger.error(f'Handled exception parsing Auth0User: "{e}"', exc_info=True)
            if self.auto_error:
                raise Auth0UnauthorizedException(detail='Error parsing Auth0User')
            else:
                return None

    def _find_rsa_key(self, kid: str) -> Dict[str, str]:
        """Find RSA key by kid in current JWKS."""
        try:
            for key in self.jwks.get('keys', []):
                if key.get('kid') == kid:
                    return {
                        'kty': key['kty'],
                        'kid': key['kid'],
                        'use': key['use'],
                        'n': key['n'],
                        'e': key['e']
                    }
        except Exception:
            pass
        return {}

    def _load_jwks(self, initial: bool = False, force: bool = False) -> None:
        """Load or refresh JWKS with a small TTL and error handling."""
        import time
        now = time.time()
        # Refresh at most every 60 minutes unless forced (Auth0 rotates keys infrequently)
        if not force and not initial and (now - self._jwks_last_refresh) < 3600:
            return
        try:
            url = f'https://{self.domain}/.well-known/jwks.json'
            with urllib.request.urlopen(url, timeout=5) as r:
                self.jwks = json.loads(r.read())
                self._jwks_last_refresh = now
                logger.info('JWKS refreshed successfully')
        except Exception as e:
            # Keep previous JWKS if refresh fails
            logger.error(f"Failed to fetch JWKS from {self.domain}: {e}")
            if initial and not self.jwks.get('keys'):
                # On first load, ensure structure
                self.jwks = {"keys": []}


def normalize_scopes(scopes: List[str]) -> List[str]:
    """
    Normaliza un conjunto de scopes para permitir tanto : como _ en los nombres.
    
    Args:
        scopes: Lista de strings con los scopes
        
    Returns:
        Lista de scopes normalizados, incluyendo versiones alternativas
    """
    normalized = []
    for scope in scopes:
        normalized.append(scope)  # Añadir versión original
        # Añadir versión alternativa
        if ':' in scope:
            normalized.append(scope.replace(':', '_'))
        elif '_' in scope:
            normalized.append(scope.replace('_', ':'))
    return normalized


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
    db: AsyncSession = Depends(get_async_db),
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

        # Llama al servicio para crear o actualizar el usuario localmente (con QR)
        db_user = await user_service.create_or_update_auth0_user_async(db, auth0_user_data)
        
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


async def get_current_db_user(
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(get_current_user)
) -> "User":
    """
    Obtiene el usuario de la base de datos local usando el Auth0 ID.

    Esta dependencia es útil cuando necesitas el ID numérico del usuario
    (por ejemplo, para construir rutas de archivos, claves foráneas, etc.)
    en lugar del Auth0 ID (string con caracteres especiales).

    Returns:
        User: Modelo de usuario de la base de datos con ID numérico

    Raises:
        HTTPException: Si el usuario no existe en la BD local
    """
    db_user = await user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)

    if not db_user:
        raise Auth0UnauthenticatedException(
            detail="Usuario no encontrado en la base de datos local"
        )

    return db_user


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
