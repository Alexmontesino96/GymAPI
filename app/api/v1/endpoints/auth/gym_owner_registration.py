"""
Endpoint de Registro de Dueños de Gimnasio

Este módulo maneja el registro y onboarding de dueños de gimnasios,
creando automáticamente el gimnasio, usuario en Auth0 y configuración inicial.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from redis.asyncio import Redis
import logging

from app.db.session import get_db
from app.db.redis_client import get_redis_client
from app.schemas.gym_owner import (
    GymOwnerRegistrationRequest,
    GymOwnerRegistrationResponse,
    GymOwnerRegistrationError
)
from app.services.gym_owner_setup import GymOwnerSetupService
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/register-gym-owner",
    response_model=GymOwnerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Gimnasio y dueño registrados exitosamente",
            "model": GymOwnerRegistrationResponse
        },
        400: {
            "description": "Datos inválidos o email ya existe",
            "model": GymOwnerRegistrationError
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
            "model": GymOwnerRegistrationError
        }
    },
    summary="Registrar nuevo dueño de gimnasio",
    description="""
    Registra un nuevo dueño de gimnasio y crea automáticamente:

    - ✅ Usuario en Auth0 con contraseña
    - ✅ Usuario en base de datos local con rol ADMIN
    - ✅ Gimnasio tradicional (tipo 'gym')
    - ✅ Asociación usuario-gimnasio como OWNER
    - ✅ Módulos esenciales activados

    **Este endpoint no requiere autenticación** - es el punto de entrada para nuevos gimnasios.

    ### Validaciones:
    - Email único (no existe en BD ni Auth0)
    - Contraseña segura (8+ caracteres, mayúsculas, minúsculas, números)
    - Teléfono en formato internacional válido

    ### Rate Limiting:
    - Máximo 5 registros por hora por IP
    - Máximo 20 registros por día por IP

    ### Próximos pasos después del registro:
    1. Verificar email (email de Auth0)
    2. Configurar Stripe Connect para pagos
    3. Configurar horarios del gimnasio
    4. Crear clases y horarios
    5. Agregar primeros miembros
    """,
    tags=["auth-registration"]
)
@limiter.limit("5/hour;20/day")  # Rate limiting estricto para prevenir spam
async def register_gym_owner(
    request: Request,
    owner_data: GymOwnerRegistrationRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client)
) -> GymOwnerRegistrationResponse:
    """
    Registrar un nuevo dueño de gimnasio con gimnasio completo

    Este endpoint crea automáticamente todo el workspace y configuración
    necesaria para que el gimnasio pueda comenzar a operar.
    """
    try:
        logger.info(f"Nueva solicitud de registro de gimnasio: {owner_data.email}")

        # Crear servicio de setup
        setup_service = GymOwnerSetupService(db)

        # Ejecutar setup completo
        result = await setup_service.create_gym_owner_workspace(
            email=owner_data.email,
            password=owner_data.password,
            first_name=owner_data.first_name,
            last_name=owner_data.last_name,
            phone=owner_data.phone,
            gym_name=owner_data.gym_name,
            gym_address=owner_data.gym_address,
            gym_phone=owner_data.gym_phone,
            gym_email=owner_data.gym_email,
            timezone=owner_data.timezone
        )

        logger.info(
            f"Gimnasio registrado exitosamente: {owner_data.gym_name} "
            f"(gym_id: {result['gym']['id']}, user_id: {result['user']['id']})"
        )

        # Cache del resultado para consultas rápidas posteriores
        cache_key = f"gym_registration:{result['gym']['id']}"
        try:
            import json
            await redis_client.setex(
                cache_key,
                3600,  # 1 hora
                json.dumps(result, default=str)
            )
        except Exception as e:
            logger.warning(f"Error cacheando resultado de registro: {e}")

        return GymOwnerRegistrationResponse(**result)

    except ValueError as e:
        # Errores de validación o email duplicado
        logger.warning(f"Validación falló para {owner_data.email}: {str(e)}")

        # Determinar código de error específico
        error_code = "VALIDATION_ERROR"
        if "email" in str(e).lower() and ("ya" in str(e).lower() or "en uso" in str(e).lower()):
            error_code = "EMAIL_EXISTS"
        elif "contraseña" in str(e).lower():
            error_code = "WEAK_PASSWORD"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": str(e),
                "error_code": error_code,
                "details": {
                    "email": owner_data.email,
                    "gym_name": owner_data.gym_name
                }
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        # Error interno del servidor
        logger.error(
            f"Error inesperado registrando gimnasio {owner_data.gym_name}: {str(e)}",
            exc_info=True
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": "Error interno al crear el gimnasio. Por favor intente nuevamente.",
                "error_code": "INTERNAL_ERROR",
                "details": {
                    "email": owner_data.email,
                    "gym_name": owner_data.gym_name
                }
            }
        )
