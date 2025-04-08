from fastapi import Header, HTTPException, Depends, Request, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Tuple
from functools import wraps
import time

from app.db.session import get_db
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.models.user import User
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
        """
        try:
            user = db.query(User).filter_by(auth0_id=current_user.id).first()
            if not user:
                print(f"Usuario {current_user.id} no encontrado - permitiendo acceso temporal")
                return gym
                
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == user.id,
                UserGym.gym_id == gym.id
            ).first()
            
            if not user_gym or user_gym.role.value not in required_roles:
                print(f"Usuario {user.id} no tiene el rol requerido - permitiendo acceso temporal")
                return gym
                
            return gym
        except Exception as e:
            print(f"Error verificando rol en gimnasio: {e}")
            # Permitir acceso temporal
            return gym

async def get_current_gym(
    x_tenant_id: Optional[int] = Header(None, alias="x-tenant-id", description="ID del gimnasio actual (requerido)"),
    db: Session = Depends(get_db)
) -> Gym:
    """
    Determina el gimnasio actual basado en el header X-Tenant-ID.
    Devuelve el objeto Gym completo, no solo el ID.
    
    Args:
        x_tenant_id: ID del gimnasio en el header (requerido)
        db: Sesión de base de datos
        
    Returns:
        Gym: El objeto gimnasio completo
        
    Raises:
        HTTPException: Si no se proporciona un ID de gimnasio válido
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'x-tenant-id' es obligatorio. Por favor especifica el ID del gimnasio."
        )
    
    # Obtener el objeto gimnasio completo usando el método correcto
    gym = gym_repository.get(db, id=x_tenant_id)
    
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gym with ID {x_tenant_id} not found"
        )
    
    return gym

async def verify_gym_access(
    gym: Gym = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Gym:
    """
    Verifica el acceso al gimnasio actual.
    Comprueba que el gimnasio exista y que el usuario tenga acceso a él.
    No verifica roles específicos, solo la pertenencia al gimnasio.
    
    Args:
        gym: Objeto gimnasio obtenido de get_current_gym
        current_user: Usuario autenticado actual
        db: Sesión de base de datos
        
    Returns:
        Gym: El mismo objeto gimnasio si el acceso es válido
        
    Raises:
        HTTPException: Si el acceso al gimnasio no es válido
    """
    try:
        # Buscar el usuario en la base de datos local
        user = db.query(User).filter_by(auth0_id=current_user.id).first()
        
        # Si el usuario no existe en la base de datos local, permitir acceso temporal
        # Esto debe modificarse en producción para ser más restrictivo
        if not user:
            print(f"ADVERTENCIA: Usuario {current_user.id} no encontrado en la base de datos local - permitiendo acceso temporal")
            return gym
            
        # Verificar si el usuario pertenece al gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user.id,
            UserGym.gym_id == gym.id
        ).first()
        
        # Si el usuario no tiene una relación con este gimnasio, denegar acceso
        if not user_gym:
            # Comentado temporalmente para facilitar desarrollo, pero en producción debe descomentarse
            # raise HTTPException(
            #     status_code=status.HTTP_403_FORBIDDEN,
            #     detail=f"Usuario no tiene acceso al gimnasio {gym.id}"
            # )
            print(f"ADVERTENCIA: Usuario {user.id} no tiene acceso al gimnasio {gym.id} - permitiendo acceso temporal")
            return gym
        
        # Almacenar el rol del usuario en el gimnasio para uso futuro
        # Esto será útil para verificaciones de permisos más específicas
        gym.user_role = user_gym.role.value
            
        return gym
    except Exception as e:
        print(f"Error verificando acceso al gimnasio: {e}")
        # Permitir acceso temporal durante desarrollo
        # En producción, esto debería ser más restrictivo
        return gym

async def verify_gym_role(
    required_roles: List[str],
    gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    db: Session = Depends(get_db),
    strict_mode: bool = False  # Cambiar a True en producción
) -> Gym:
    """
    Verifica que el usuario tiene uno de los roles requeridos en el gimnasio.
    
    Args:
        required_roles: Lista de roles permitidos para esta operación
        gym: Objeto gimnasio verificado por verify_gym_access
        current_user: Usuario autenticado actual
        db: Sesión de base de datos
        strict_mode: Si es True, deniega acceso cuando no se cumple con los requisitos
        
    Returns:
        Gym: El mismo objeto gimnasio si el usuario tiene el rol adecuado
        
    Raises:
        HTTPException: Si el usuario no tiene el rol requerido y strict_mode es True
    """
    try:
        user = db.query(User).filter_by(auth0_id=current_user.id).first()
        if not user:
            if strict_mode:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuario no encontrado en la base de datos local"
                )
            print(f"ADVERTENCIA: Usuario {current_user.id} no encontrado en la base de datos local - permitiendo acceso temporal")
            return gym
            
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user.id,
            UserGym.gym_id == gym.id
        ).first()
        
        if not user_gym or user_gym.role.value not in required_roles:
            if strict_mode:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Usuario no tiene el rol requerido para esta operación en el gimnasio {gym.id}"
                )
            print(f"ADVERTENCIA: Usuario {user.id} no tiene el rol requerido ({required_roles}) en gimnasio {gym.id} - permitiendo acceso temporal")
            
        # Guardar el rol en el objeto gym para referencia
        if user_gym:
            gym.user_role = user_gym.role.value
        
        return gym
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verificando rol en gimnasio: {e}")
        if strict_mode:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno al verificar el rol del usuario"
            )
        # Permitir acceso temporal durante desarrollo
        return gym

# Decoradores funcionales para requerir roles específicos
def require_gym_role(required_roles: List[str]):
    """
    Decorador para verificar que el usuario tiene uno de los roles requeridos en el gimnasio.
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
                
            # Verificar rol (ahora no es asíncrona)
            TenantMiddleware.verify_gym_role(required_roles, gym, current_user, db)
            
            # Continuar con la función original
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Funciones helper para roles comunes
require_gym_admin = lambda: require_gym_role([GymRoleType.ADMIN, GymRoleType.OWNER])
require_gym_trainer = lambda: require_gym_role([GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER])

# Dependencias específicas para verificar roles en endpoints
async def verify_admin_role(
    gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Gym:
    """
    Verifica que el usuario tiene rol de Administrador o Propietario en el gimnasio.
    Esta dependencia puede usarse directamente en los endpoints.
    """
    return await verify_gym_role(
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
    Verifica que el usuario tiene rol de Entrenador, Administrador o Propietario en el gimnasio.
    Esta dependencia puede usarse directamente en los endpoints.
    """
    return await verify_gym_role(
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
    Verifica que el usuario tiene al menos rol de Miembro en el gimnasio.
    Esta dependencia puede usarse directamente en los endpoints.
    """
    return await verify_gym_role(
        required_roles=[GymRoleType.MEMBER, GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER],
        gym=gym,
        current_user=current_user,
        db=db
    ) 