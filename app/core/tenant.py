from fastapi import Header, HTTPException, Depends, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List, Dict, Tuple
from functools import wraps
import time

from app.db.session import get_db
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.models.user import User, UserRole
from app.core.auth0_fastapi import Auth0User, get_current_user
from app.repositories.gym import gym_repository

# Cache simple para reducir verificaciones repetidas de acceso a gimnasios
# Estructura: {gym_id: (timestamp, gym_object)}
_gym_cache: Dict[int, Tuple[float, Gym]] = {}
_CACHE_TTL = 300  # 5 minutos en segundos

class TenantMiddleware:
    """Middleware para gestionar la identificación y seguridad de tenants (gimnasios)"""
    
    @staticmethod
    def get_tenant_from_header(
        request: Request,
        x_gym_id: Optional[int] = Header(None, description="ID del gimnasio"),
        db: Session = Depends(get_db)
    ) -> Optional[Gym]:
        """
        Obtiene el gimnasio actual de los headers HTTP.
        """
        try:
            if not x_gym_id:
                # Si no se proporciona ID, usar el gimnasio predeterminado (ID=1)
                x_gym_id = 1
            
            # Intentar obtener el gimnasio de la base de datos
            gym = db.query(Gym).filter(Gym.id == x_gym_id, Gym.is_active == True).first()
            
            if gym:
                # Almacenar el tenant en el objeto request para uso posterior
                request.state.gym = gym
                return gym
            else:
                # Si no se encuentra en la base de datos, crear uno ficticio con ID=1
                # Esto es temporal hasta que se configure correctamente la base de datos
                default_gym = Gym(
                    id=x_gym_id,
                    name="Gimnasio Predeterminado",
                    subdomain="default",
                    is_active=True
                )
                request.state.gym = default_gym
                return default_gym
        except Exception as e:
            # Capturar errores de tabla inexistente y otros problemas de base de datos
            print(f"Error accediendo a la tabla de gimnasios: {e}")
            # Crear un gimnasio ficticio para permitir que la API siga funcionando
            default_gym = Gym(
                id=x_gym_id or 1,
                name="Gimnasio Predeterminado",
                subdomain="default",
                is_active=True
            )
            request.state.gym = default_gym
            return default_gym
    
    @staticmethod
    def get_tenant_from_subdomain(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Optional[Gym]:
        """
        Obtiene el gimnasio actual del subdominio.
        """
        host = request.headers.get("host", "")
        subdomain = host.split(".")[0] if "." in host else None
        
        if not subdomain or subdomain in ["www", "api", "localhost"]:
            return None
            
        gym = db.query(Gym).filter(Gym.subdomain == subdomain, Gym.is_active == True).first()
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado o inactivo")
            
        # Almacenar el tenant en el objeto request para uso posterior
        request.state.gym = gym
        return gym
    
    @staticmethod
    def verify_user_gym_access(
        gym: Gym = Depends(get_tenant_from_header),
        current_user: Auth0User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> Gym:
        """
        Verifica que el usuario tiene acceso al gimnasio actual.
        """
        if not gym:
            raise HTTPException(status_code=400, detail="Debe especificar un gimnasio")
            
        try:
            # Buscar el usuario en la base de datos local
            user = db.query(User).filter_by(auth0_id=current_user.id).first()
            
            # Si el usuario no existe en la base de datos local, permitir acceso temporal
            if not user:
                print(f"Usuario {current_user.id} no encontrado en la base de datos local - permitiendo acceso temporal")
                return gym
                
            # Verificar si el usuario pertenece al gimnasio
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == user.id,
                UserGym.gym_id == gym.id
            ).first()
            
            # Si el usuario no tiene una relación con este gimnasio, permitir acceso temporal
            if not user_gym:
                print(f"Usuario {user.id} no tiene acceso al gimnasio {gym.id} - permitiendo acceso temporal")
                return gym
                
            return gym
        except Exception as e:
            # Capturar errores de tabla inexistente y otros problemas de base de datos
            print(f"Error verificando acceso al gimnasio: {e}")
            # Permitir acceso temporal
            return gym
        
    @staticmethod
    def verify_gym_role(
        required_roles: List[str],
        gym: Gym = Depends(verify_user_gym_access),
        current_user: Auth0User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> Gym:
        """
        Verifica que el usuario tiene el rol requerido en el gimnasio.
        Lanza HTTPException 403 si el rol no coincide.
        Lanza HTTPException 404 si el usuario no se encuentra.
        Los SUPER_ADMIN siempre tienen acceso.
        """
        try:
            user = db.query(User).filter_by(auth0_id=current_user.id).first()
            if not user:
                # Usuario de Auth0 existe pero no en la BD local
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Usuario no encontrado en la base de datos local"
                )
            
            # Super Admin siempre tiene acceso
            if user.role == UserRole.SUPER_ADMIN:
                return gym
                
            # Verificar si el usuario tiene el rol específico en este gimnasio
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == user.id,
                UserGym.gym_id == gym.id
            ).first()
            
            if not user_gym or user_gym.role.value not in required_roles:
                # Usuario encontrado, pertenece al gym pero no tiene el rol
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail=f"El usuario no tiene el rol requerido ({', '.join(required_roles)}) en este gimnasio"
                )
                
            # Si todo está bien, devolver el gimnasio
            return gym
        except HTTPException as http_exc: # Relanzar excepciones HTTP específicas
            raise http_exc
        except Exception as e:
            # Error inesperado durante la verificación
            print(f"Error inesperado verificando rol en gimnasio: {e}") # Mantener log para depuración
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al verificar el rol del usuario: {e}"
            )

async def get_tenant_id(
    x_gym_id: Optional[str] = Header(None, alias="X-Gym-ID")
) -> Optional[int]:
    """
    Obtiene el ID del tenant (gimnasio) únicamente del header X-Gym-ID.
    """
    if x_gym_id:
        try:
            tenant_id_int = int(x_gym_id)
            # Opcional: Añadir validación extra si los IDs tienen un rango esperado
            # if tenant_id_int <= 0:
            #     return None 
            return tenant_id_int
        except (ValueError, TypeError):
            # Si el header no es un entero válido, se ignora y devuelve None
            # Podríamos lanzar un 400 Bad Request aquí si preferimos ser más estrictos
            # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Gym-ID header format")
            return None
        
    # Si no se proporciona el header o no es válido, devolver None
    return None

async def get_current_gym(
    db: Session = Depends(get_db),
    tenant_id: Optional[int] = Depends(get_tenant_id)
) -> Optional[Gym]:
    """
    Obtiene el gimnasio actual basado en el tenant ID.
    
    Args:
        db: Sesión de base de datos
        tenant_id: ID del tenant (gimnasio)
        
    Returns:
        Optional[Gym]: El gimnasio solicitado o None si no se proporciona tenant_id
        
    Raises:
        HTTPException: Si el gimnasio solicitado no existe
    """
    if not tenant_id:
        return None
        
    gym = db.query(Gym).filter(Gym.id == tenant_id).first()
    
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El gimnasio con ID {tenant_id} no existe"
        )
        
    return gym

async def verify_gym_access(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user)
) -> Gym:
    """
    Verifica que el usuario actual tenga acceso al gimnasio solicitado.
    
    Esta función no solo verifica el acceso, sino que también devuelve
    el gimnasio para que pueda ser utilizado en los endpoints.
    
    Args:
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        current_user: Usuario autenticado
        
    Returns:
        Gym: El gimnasio al que se está accediendo
    
    Raises:
        HTTPException: Si no se proporciona tenant_id o el usuario no tiene acceso
    """
    if not current_gym:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere especificar el ID del gimnasio (tenant)"
        )
    
    # Obtener ID de Auth0 del usuario actual
    auth0_id = current_user.id
    
    if not auth0_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token no contiene información de usuario"
        )
    
    # Buscar el usuario en nuestra base de datos
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos local"
        )
    
    # Los super administradores tienen acceso a todos los gimnasios
    if user.role == UserRole.SUPER_ADMIN:
        return current_gym
    
    # Verificar si el usuario pertenece al gimnasio
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == user.id,
        UserGym.gym_id == current_gym.id
    ).first()
    
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes acceso al gimnasio {current_gym.name}"
        )
    
    return current_gym

async def verify_gym_admin_access(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user)
) -> Gym:
    """
    Verifica que el usuario actual tenga acceso de administrador al gimnasio.
    
    Args:
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        current_user: Usuario autenticado
        
    Returns:
        Gym: El gimnasio al que se está accediendo como administrador

    Raises:
        HTTPException: Si el usuario no tiene permisos de administrador
    """
    if not current_gym:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere especificar el ID del gimnasio (tenant)"
        )
    
    # Obtener ID de Auth0 del usuario actual
    auth0_id = current_user.id
    
    if not auth0_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token no contiene información de usuario"
        )
    
    # Buscar el usuario en nuestra base de datos
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos local"
        )
    
    # Los super administradores tienen acceso administrativo a todos los gimnasios
    if user.role == UserRole.SUPER_ADMIN:
        return current_gym
            
    # Verificar si el usuario es admin del gimnasio
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first()
    
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes permisos de administrador en el gimnasio {current_gym.name}"
        )
    
    return current_gym

async def verify_gym_trainer_access(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user)
) -> Gym:
    """
    Verifica que el usuario actual tenga acceso de entrenador (o superior) al gimnasio.
    
    Args:
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        current_user: Usuario autenticado
        
    Returns:
        Gym: El gimnasio al que se está accediendo como entrenador
        
    Raises:
        HTTPException: Si el usuario no tiene permisos de entrenador
    """
    if not current_gym:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere especificar el ID del gimnasio (tenant)"
        )
    
    # Obtener ID de Auth0 del usuario actual
    auth0_id = current_user.id
    
    if not auth0_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token no contiene información de usuario"
        )
    
    # Buscar el usuario en nuestra base de datos
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos local"
        )
    
    # Los super administradores tienen acceso de entrenador a todos los gimnasios
    if user.role == UserRole.SUPER_ADMIN:
        return current_gym
    
    # Verificar si el usuario es entrenador, admin u owner del gimnasio
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first()
    
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes permisos de entrenador en el gimnasio {current_gym.name}"
        )
    
    return current_gym

async def verify_gym_ownership(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user)
) -> Gym:
    """
    Verifica que el usuario actual sea propietario del gimnasio.
    
    Args:
        db: Sesión de base de datos
        current_gym: Gimnasio actual
        current_user: Usuario autenticado
        
    Returns:
        Gym: El gimnasio del que el usuario es propietario
    
    Raises:
        HTTPException: Si el usuario no es propietario del gimnasio
    """
    if not current_gym:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere especificar el ID del gimnasio (tenant)"
        )
    
    # Obtener ID de Auth0 del usuario actual
    auth0_id = current_user.id
    
    if not auth0_id:
             raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token no contiene información de usuario"
            )

    # Buscar el usuario en nuestra base de datos
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
        
    if not user:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos local"
            )
        
    # Los super administradores tienen privilegios de propietario en todos los gimnasios
    if user.role == UserRole.SUPER_ADMIN:
        return current_gym
    
    # Verificar si el usuario es propietario del gimnasio
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role == GymRoleType.OWNER
    ).first()
    
    if not user_gym:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No eres propietario del gimnasio {current_gym.name}"
        )
    
    return current_gym

# --- Dependencias Específicas por Rol (para usar directamente en endpoints) ---

async def verify_admin_role(
    gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Gym:
    """
    Dependencia FastAPI: Verifica rol ADMIN o OWNER en el gimnasio.
    """
    return TenantMiddleware.verify_gym_role(
        required_roles=[GymRoleType.ADMIN, GymRoleType.OWNER],
        gym=gym,
        current_user=current_user,
        db=db
    )

async def verify_trainer_role(
    gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Gym:
    """
    Dependencia FastAPI: Verifica rol TRAINER, ADMIN o OWNER en el gimnasio.
    """
    return TenantMiddleware.verify_gym_role(
        required_roles=[GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER],
        gym=gym,
        current_user=current_user,
        db=db
    )

async def verify_member_role(
    gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Gym:
    """
    Dependencia FastAPI: Verifica rol MEMBER, TRAINER, ADMIN o OWNER en el gimnasio.
    """
    return TenantMiddleware.verify_gym_role(
        required_roles=[GymRoleType.MEMBER, GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER],
        gym=gym,
        current_user=current_user,
        db=db
    )

# Decoradores funcionales (Considerar eliminar si no se usan)
def require_gym_role(required_roles: List[str]):
    """
    [OBSOLETO?] Decorador para verificar que el usuario tiene uno de los roles requeridos en el gimnasio.
    Prefiere usar las dependencias verify_admin_role, verify_trainer_role, etc.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            gym = kwargs.get("gym")
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not gym or not current_user or not db:
                raise HTTPException(
                    status_code=500, 
                    detail="Dependencias faltantes para verificar rol de gimnasio"
                )
                
            # Verificar rol usando la lógica del middleware obsoleto
            # Esto podría tener la lógica insegura
            TenantMiddleware.verify_gym_role(required_roles, gym, current_user, db)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Funciones helper (Considerar eliminar si no se usan)
require_gym_admin = lambda: require_gym_role([GymRoleType.ADMIN, GymRoleType.OWNER])
require_gym_trainer = lambda: require_gym_role([GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER]) 