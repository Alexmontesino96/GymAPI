"""
Endpoint de Registro de Entrenadores Personales

Este módulo maneja el registro y onboarding de entrenadores personales,
creando automáticamente su workspace y configuración inicial.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
import logging

from app.db.session import get_async_db
from app.db.redis_client import get_redis_client
from app.schemas.trainer import (
    TrainerRegistrationRequest,
    TrainerRegistrationResponse,
    TrainerRegistrationError
)
from app.services.trainer_setup import TrainerSetupService
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/register-trainer",
    response_model=TrainerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Entrenador registrado exitosamente",
            "model": TrainerRegistrationResponse
        },
        400: {
            "description": "Datos inválidos o usuario ya existe",
            "model": TrainerRegistrationError
        },
        429: {
            "description": "Demasiadas solicitudes",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded"
                    }
                }
            }
        },
        500: {
            "description": "Error interno del servidor",
            "model": TrainerRegistrationError
        }
    },
    summary="Registrar nuevo entrenador personal",
    description="""
    Registra un nuevo entrenador personal y crea automáticamente:

    - ✅ Usuario con rol TRAINER
    - ✅ Workspace personal tipo 'personal_trainer'
    - ✅ Configuración de Stripe Connect (si está habilitado)
    - ✅ Módulos esenciales activados
    - ✅ Planes de pago predeterminados
    - ✅ Asignación como OWNER del workspace

    **Este endpoint no requiere autenticación** - es el punto de entrada para nuevos entrenadores.

    ### Proceso:
    1. Validar datos del entrenador
    2. Crear usuario y workspace
    3. Configurar servicios externos (Stripe, etc.)
    4. Activar módulos y crear planes
    5. Retornar información del workspace creado

    ### Rate Limiting:
    - Máximo 5 registros por hora por IP
    - Máximo 20 registros por día por IP

    ### Próximos pasos después del registro:
    1. Completar onboarding de Stripe (si aplica)
    2. Verificar email (implementación futura)
    3. Configurar perfil y foto
    4. Agregar primeros clientes
    """,
    tags=["auth-registration"]
)
@limiter.limit("5/hour;20/day")  # Rate limiting estricto para prevenir spam
async def register_trainer(
    request: Request,
    trainer_data: TrainerRegistrationRequest,
    db: AsyncSession = Depends(get_async_db),
    redis_client: Redis = Depends(get_redis_client)
) -> TrainerRegistrationResponse:
    """
    Registrar un nuevo entrenador personal

    Este endpoint crea automáticamente todo el workspace y configuración
    necesaria para que el entrenador pueda comenzar a trabajar.
    """
    try:
        logger.info(f"Nueva solicitud de registro: {trainer_data.email}")

        # Crear servicio de setup
        setup_service = TrainerSetupService(db)

        # Ejecutar setup completo
        result = await setup_service.create_trainer_workspace(
            email=trainer_data.email,
            first_name=trainer_data.first_name,
            last_name=trainer_data.last_name,
            phone=trainer_data.phone,
            specialties=trainer_data.specialties,
            certifications=trainer_data.certifications,
            timezone=trainer_data.timezone,
            max_clients=trainer_data.max_clients,
            bio=trainer_data.bio
        )

        logger.info(
            f"Entrenador registrado exitosamente: {trainer_data.email} "
            f"(workspace_id: {result['workspace']['id']}, user_id: {result['user']['id']})"
        )

        # Cache del resultado para consultas rápidas posteriores
        cache_key = f"trainer_registration:{result['user']['id']}"
        try:
            import json
            await redis_client.setex(
                cache_key,
                3600,  # 1 hora
                json.dumps(result, default=str)
            )
        except Exception as e:
            logger.warning(f"Error cacheando resultado de registro: {e}")

        return TrainerRegistrationResponse(**result)

    except ValueError as e:
        # Errores de validación o usuario ya existe
        logger.warning(f"Validación falló para {trainer_data.email}: {str(e)}")

        # Determinar código de error específico
        error_code = "VALIDATION_ERROR"
        if "ya tiene un workspace" in str(e).lower():
            error_code = "WORKSPACE_EXISTS"
        elif "email" in str(e).lower():
            error_code = "EMAIL_EXISTS"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": str(e),
                "error_code": error_code,
                "details": {
                    "email": trainer_data.email
                }
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        # Error interno del servidor
        logger.error(
            f"Error inesperado registrando entrenador {trainer_data.email}: {str(e)}",
            exc_info=True
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": "Error interno al crear el workspace. Por favor intente nuevamente.",
                "error_code": "INTERNAL_ERROR",
                "details": {
                    "email": trainer_data.email
                }
            }
        )


@router.get(
    "/trainer/check-email/{email}",
    summary="Verificar disponibilidad de email",
    description="""
    Verifica si un email está disponible para registro de entrenador.

    Útil para validación en tiempo real en formularios de registro.

    **Returns:**
    - `available: true` si el email está disponible
    - `available: false` si el email ya está registrado
    - `has_workspace: true` si el usuario tiene workspace de entrenador
    """,
    tags=["auth-registration"]
)
@limiter.limit("30/minute")
async def check_email_availability(
    request: Request,
    email: str,
    db: AsyncSession = Depends(get_async_db)
) -> dict:
    """
    Verificar si un email está disponible para registro
    """
    try:
        from app.models.user import User
        from app.models.user_gym import UserGym
        from app.models.gym import Gym, GymType

        # Buscar usuario por email
        result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

        if not user:
            return {
                "available": True,
                "message": "Email disponible"
            }

        # Usuario existe, verificar si tiene workspace de entrenador
        result = await db.execute(select(UserGym).join(Gym).where(
            UserGym.user_id == user.id,
            UserGym.role == "OWNER",
            Gym.type == GymType.personal_trainer
        ))
    has_workspace = result.scalar_one_or_none() is not None

        return {
            "available": False,
            "message": "Email ya registrado",
            "has_workspace": has_workspace,
            "details": {
                "user_id": user.id,
                "is_trainer": user.role == "TRAINER"
            }
        }

    except Exception as e:
        logger.error(f"Error verificando disponibilidad de email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al verificar disponibilidad del email"
        )


@router.get(
    "/trainer/validate-subdomain/{subdomain}",
    summary="Validar disponibilidad de subdomain",
    description="""
    Valida si un subdomain está disponible para uso.

    Los subdomains se generan automáticamente, pero este endpoint
    permite verificar disponibilidad si el usuario quiere personalizar.
    """,
    tags=["auth-registration"]
)
@limiter.limit("30/minute")
async def validate_subdomain(
    request: Request,
    subdomain: str,
    db: AsyncSession = Depends(get_async_db)
) -> dict:
    """
    Validar disponibilidad de subdomain
    """
    try:
        from app.models.gym import Gym
        import re

        # Validar formato
        if not re.match(r'^[a-z0-9-]{3,50}$', subdomain):
            return {
                "valid": False,
                "available": False,
                "message": "Formato inválido. Use solo letras minúsculas, números y guiones (3-50 caracteres)"
            }

        # Verificar disponibilidad
        result = await db.execute(select(Gym).where(Gym.subdomain == subdomain))
    exists = result.scalar_one_or_none() is not None

        return {
            "valid": True,
            "available": not exists,
            "message": "Subdomain disponible" if not exists else "Subdomain ya en uso",
            "subdomain": subdomain
        }

    except Exception as e:
        logger.error(f"Error validando subdomain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al validar subdomain"
        )