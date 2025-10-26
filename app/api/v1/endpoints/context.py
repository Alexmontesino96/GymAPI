"""
Context API Endpoints para UI Adaptativa

Este módulo proporciona endpoints para obtener contexto del workspace actual,
permitiendo que el frontend adapte la UI según el tipo de gimnasio
(tradicional vs entrenador personal).
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis_client import get_redis_client
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_access, get_current_gym
from app.core.config import Settings
from app.models.gym import GymType
from app.models.user import User
from app.models.user_gym import GymRoleType
from app.schemas.gym import GymSchema, GymType as GymTypeSchema
from app.services.user import user_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

settings = Settings()


def get_terminology(gym_type: GymTypeSchema) -> Dict[str, str]:
    """
    Retorna terminología apropiada según el tipo de gym
    para adaptar la UI del frontend
    """
    if gym_type == GymTypeSchema.personal_trainer:
        return {
            "gym": "espacio de trabajo",
            "gym_plural": "espacios de trabajo",
            "member": "cliente",
            "members": "clientes",
            "trainer": "asistente",
            "trainers": "asistentes",
            "class": "sesión",
            "classes": "sesiones",
            "schedule": "agenda",
            "membership": "plan de entrenamiento",
            "memberships": "planes de entrenamiento",
            "equipment": "material",
            "event": "cita",
            "events": "citas",
            "owner": "entrenador principal",
            "admin": "administrador",
            "dashboard": "panel de control"
        }
    else:
        return {
            "gym": "gimnasio",
            "gym_plural": "gimnasios",
            "member": "miembro",
            "members": "miembros",
            "trainer": "entrenador",
            "trainers": "entrenadores",
            "class": "clase",
            "classes": "clases",
            "schedule": "horario",
            "membership": "membresía",
            "memberships": "membresías",
            "equipment": "equipamiento",
            "event": "evento",
            "events": "eventos",
            "owner": "propietario",
            "admin": "administrador",
            "dashboard": "dashboard"
        }


def get_enabled_features(gym_type: GymTypeSchema, user_role: str) -> Dict[str, bool]:
    """
    Retorna qué funcionalidades están habilitadas según el tipo de gym
    y el rol del usuario
    """
    base_features = {
        "chat": True,
        "notifications": True,
        "profile": True,
        "health_tracking": True,
        "nutrition": True,
        "surveys": True,
        "payments": True
    }

    if gym_type == GymTypeSchema.personal_trainer:
        # Entrenador personal - features específicas
        trainer_features = {
            **base_features,
            "show_multiple_trainers": False,  # Solo un entrenador
            "show_equipment_management": False,  # No gestión de equipos
            "show_class_schedule": False,  # No horario de clases
            "show_gym_hours": False,  # No horarios de apertura/cierre
            "show_appointments": True,  # Agenda de citas
            "show_client_progress": True,  # Progreso de clientes
            "show_session_packages": True,  # Paquetes de sesiones
            "simplified_billing": True,  # Facturación simplificada
            "show_staff_management": False,  # No gestión de staff
            "max_clients_limit": True,  # Límite de clientes
            "personal_branding": True,  # Branding personal
            "quick_client_add": True,  # Agregar clientes rápidamente
            "session_tracking": True,  # Tracking de sesiones
            "client_notes": True  # Notas sobre clientes
        }
        return trainer_features
    else:
        # Gimnasio tradicional - features estándar
        gym_features = {
            **base_features,
            "show_multiple_trainers": True,
            "show_equipment_management": True,
            "show_class_schedule": True,
            "show_gym_hours": True,
            "show_appointments": False,
            "show_client_progress": False,
            "show_session_packages": False,
            "simplified_billing": False,
            "show_staff_management": user_role in ["OWNER", "ADMIN"],
            "max_clients_limit": False,
            "personal_branding": False,
            "quick_client_add": False,
            "session_tracking": False,
            "client_notes": False,
            "event_management": True,
            "capacity_management": True,
            "equipment_booking": True
        }
        return gym_features


def get_navigation_menu(gym_type: GymTypeSchema, user_role: str) -> List[Dict]:
    """
    Retorna el menú de navegación adaptado según el tipo de gym
    y el rol del usuario
    """
    if gym_type == GymTypeSchema.personal_trainer:
        # Menú para entrenador personal
        menu = [
            {"id": "dashboard", "label": "Dashboard", "icon": "home", "path": "/"},
            {"id": "clients", "label": "Mis Clientes", "icon": "users", "path": "/clients"},
            {"id": "appointments", "label": "Agenda", "icon": "calendar", "path": "/appointments"},
            {"id": "nutrition", "label": "Planes Nutricionales", "icon": "apple", "path": "/nutrition"},
            {"id": "progress", "label": "Progreso", "icon": "chart-line", "path": "/progress"},
            {"id": "payments", "label": "Pagos", "icon": "credit-card", "path": "/payments"},
            {"id": "chat", "label": "Mensajes", "icon": "message-circle", "path": "/chat"},
        ]

        # Agregar opciones de administrador si es OWNER
        if user_role == "OWNER":
            menu.extend([
                {"id": "analytics", "label": "Estadísticas", "icon": "bar-chart", "path": "/analytics"},
                {"id": "settings", "label": "Configuración", "icon": "settings", "path": "/settings"}
            ])

    else:
        # Menú tradicional para gimnasios
        menu = [
            {"id": "dashboard", "label": "Dashboard", "icon": "home", "path": "/"},
            {"id": "members", "label": "Miembros", "icon": "users", "path": "/members"},
            {"id": "schedule", "label": "Horarios", "icon": "clock", "path": "/schedule"},
            {"id": "classes", "label": "Clases", "icon": "activity", "path": "/classes"},
            {"id": "events", "label": "Eventos", "icon": "calendar", "path": "/events"},
            {"id": "billing", "label": "Facturación", "icon": "credit-card", "path": "/billing"},
            {"id": "chat", "label": "Chat", "icon": "message-circle", "path": "/chat"},
        ]

        # Agregar opciones según el rol
        if user_role in ["OWNER", "ADMIN"]:
            menu.extend([
                {"id": "trainers", "label": "Entrenadores", "icon": "user-check", "path": "/trainers"},
                {"id": "equipment", "label": "Equipamiento", "icon": "dumbbell", "path": "/equipment"},
                {"id": "analytics", "label": "Analíticas", "icon": "bar-chart-2", "path": "/analytics"},
                {"id": "settings", "label": "Configuración", "icon": "settings", "path": "/settings"}
            ])
        elif user_role == "TRAINER":
            menu.extend([
                {"id": "my-members", "label": "Mis Miembros", "icon": "user-check", "path": "/my-members"},
                {"id": "my-classes", "label": "Mis Clases", "icon": "activity", "path": "/my-classes"}
            ])

    return menu


def get_quick_actions(gym_type: GymTypeSchema, user_role: str) -> List[Dict]:
    """
    Retorna acciones rápidas contextuales para el dashboard
    """
    if gym_type == GymTypeSchema.personal_trainer:
        return [
            {
                "id": "add_client",
                "label": "Nuevo Cliente",
                "icon": "user-plus",
                "color": "primary",
                "action": "modal:add-client"
            },
            {
                "id": "schedule_session",
                "label": "Agendar Sesión",
                "icon": "calendar-plus",
                "color": "success",
                "action": "modal:schedule-session"
            },
            {
                "id": "create_nutrition_plan",
                "label": "Plan Nutricional",
                "icon": "clipboard",
                "color": "info",
                "action": "navigate:/nutrition/new"
            },
            {
                "id": "record_payment",
                "label": "Registrar Pago",
                "icon": "dollar-sign",
                "color": "warning",
                "action": "modal:record-payment"
            }
        ]
    else:
        actions = [
            {
                "id": "add_member",
                "label": "Nuevo Miembro",
                "icon": "user-plus",
                "color": "primary",
                "action": "modal:add-member"
            },
            {
                "id": "create_event",
                "label": "Crear Evento",
                "icon": "calendar-plus",
                "color": "success",
                "action": "navigate:/events/new"
            }
        ]

        if user_role in ["OWNER", "ADMIN"]:
            actions.extend([
                {
                    "id": "add_class",
                    "label": "Nueva Clase",
                    "icon": "plus-circle",
                    "color": "info",
                    "action": "navigate:/classes/new"
                },
                {
                    "id": "send_notification",
                    "label": "Enviar Notificación",
                    "icon": "bell",
                    "color": "warning",
                    "action": "modal:send-notification"
                }
            ])

        return actions


@router.get("/workspace")
async def get_workspace_context(
    request: Request,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(get_current_gym),
    current_user: Auth0User = Security(auth.get_user),
    redis_client: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Obtiene el contexto completo del workspace actual para adaptar la UI.

    Este endpoint es crucial para que el frontend sepa:
    - Tipo de gimnasio (tradicional vs entrenador personal)
    - Terminología a usar
    - Features habilitadas/deshabilitadas
    - Menú de navegación adaptado
    - Acciones rápidas disponibles
    - Configuración de branding

    **Returns:**
    - workspace: Información del gimnasio/workspace actual
    - terminology: Diccionario con términos adaptados
    - features: Features habilitadas según el tipo
    - navigation: Menú de navegación contextual
    - quick_actions: Acciones rápidas para el dashboard
    - branding: Configuración de marca y colores
    - user_context: Información del usuario y su rol
    """
    try:
        if not current_gym:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo obtener el gimnasio actual"
            )

        # Obtener usuario interno y su rol
        internal_user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )

        if not internal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Obtener rol del usuario en este gimnasio
        user_role = getattr(request.state, 'role_in_gym', GymRoleType.MEMBER)

        # Convertir enum a string si es necesario
        role_str = user_role.value if hasattr(user_role, 'value') else str(user_role) if user_role else 'MEMBER'

        # Construir contexto
        terminology = get_terminology(current_gym.type)
        features = get_enabled_features(current_gym.type, user_role)
        navigation = get_navigation_menu(current_gym.type, user_role)
        quick_actions = get_quick_actions(current_gym.type, user_role)

        # Configuración de branding según el tipo
        if current_gym.type == GymTypeSchema.personal_trainer:
            branding = {
                "logo_url": current_gym.logo_url,
                "primary_color": "#28a745",  # Verde para entrenadores
                "secondary_color": "#6c757d",
                "accent_color": "#ffc107",
                "app_title": current_gym.display_name,
                "app_subtitle": "Entrenamiento Personalizado",
                "theme": "trainer",
                "show_logo": True,
                "compact_mode": True
            }
        else:
            branding = {
                "logo_url": current_gym.logo_url,
                "primary_color": "#007bff",  # Azul para gimnasios
                "secondary_color": "#6c757d",
                "accent_color": "#28a745",
                "app_title": current_gym.name,
                "app_subtitle": "Sistema de Gestión",
                "theme": "gym",
                "show_logo": True,
                "compact_mode": False
            }

        # Información del usuario
        user_context = {
            "id": internal_user.id,
            "email": internal_user.email,
            "name": f"{internal_user.first_name} {internal_user.last_name}",
            "photo_url": internal_user.picture,  # El modelo User usa 'picture' no 'photo_url'
            "role": role_str,
            "role_label": terminology.get(role_str.lower(), role_str),
            "permissions": get_user_permissions(user_role)
        }

        # Construir respuesta completa
        context = {
            "workspace": {
                "id": current_gym.id,
                "name": current_gym.name,
                "type": current_gym.type.value,
                "is_personal_trainer": current_gym.is_personal_trainer,
                "display_name": current_gym.display_name,
                "entity_label": current_gym.entity_type_label,
                "timezone": current_gym.timezone,
                "email": current_gym.email,
                "phone": current_gym.phone,
                "address": current_gym.address,
                "max_clients": current_gym.max_clients if current_gym.is_personal_trainer else None,
                "specialties": current_gym.trainer_specialties if current_gym.is_personal_trainer else None
            },
            "terminology": terminology,
            "features": features,
            "navigation": navigation,
            "quick_actions": quick_actions,
            "branding": branding,
            "user_context": user_context,
            "api_version": "1.0.0",
            "environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "production"
        }

        logger.info(f"Context served for {current_gym.type} gym {current_gym.id}, user {internal_user.id}")
        return context

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workspace context: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el contexto del workspace"
        )


def get_user_permissions(role: str) -> List[str]:
    """
    Retorna lista de permisos según el rol
    """
    permissions_map = {
        "OWNER": [
            "gym:read", "gym:write", "gym:delete",
            "members:read", "members:write", "members:delete",
            "billing:read", "billing:write",
            "settings:read", "settings:write",
            "analytics:read",
            "staff:read", "staff:write",
            "all:*"
        ],
        "ADMIN": [
            "gym:read", "gym:write",
            "members:read", "members:write",
            "billing:read",
            "settings:read", "settings:write",
            "analytics:read",
            "staff:read"
        ],
        "TRAINER": [
            "gym:read",
            "members:read", "members:write:assigned",
            "classes:read", "classes:write:assigned",
            "chat:read", "chat:write",
            "nutrition:read", "nutrition:write"
        ],
        "MEMBER": [
            "gym:read:basic",
            "profile:read", "profile:write:own",
            "classes:read", "classes:book",
            "chat:read", "chat:write:limited",
            "nutrition:read:own"
        ]
    }

    return permissions_map.get(role, ["gym:read:basic"])


@router.get("/workspace/stats")
async def get_workspace_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user),
    redis_client: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Obtiene estadísticas rápidas del workspace actual.

    Las estadísticas varían según el tipo de gimnasio:
    - Entrenador personal: clientes activos, sesiones, ingresos
    - Gimnasio tradicional: miembros, clases, ocupación
    """
    try:
        # Cache key específico por tipo
        cache_key = f"workspace_stats:{current_gym.id}:{current_gym.type.value}"

        # Intentar obtener de cache
        cached_stats = await redis_client.get(cache_key)
        if cached_stats:
            import json
            return json.loads(cached_stats)

        if current_gym.is_personal_trainer:
            # Estadísticas para entrenador personal
            from app.models.user_gym import UserGym
            from app.models.event import Event
            from datetime import datetime, timedelta

            # Contar clientes activos
            active_clients = db.query(UserGym).filter(
                UserGym.gym_id == current_gym.id,
                UserGym.role == GymRoleType.MEMBER,
                UserGym.is_active == True
            ).count()

            # Sesiones de esta semana
            week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
            week_sessions = db.query(Event).filter(
                Event.gym_id == current_gym.id,
                Event.start_time >= week_start
            ).count()

            stats = {
                "type": "trainer",
                "metrics": {
                    "active_clients": active_clients,
                    "max_clients": current_gym.max_clients or 30,
                    "capacity_percentage": (active_clients / (current_gym.max_clients or 30)) * 100,
                    "sessions_this_week": week_sessions,
                    "avg_sessions_per_client": week_sessions / max(active_clients, 1),
                    "client_retention_rate": 95.0,  # TODO: Calcular real
                    "revenue_this_month": 45000.00  # TODO: Obtener de Stripe
                }
            }
        else:
            # Estadísticas para gimnasio tradicional
            from app.models.user_gym import UserGym
            from app.models.schedule import Class

            # Contar miembros por rol
            members_count = db.query(UserGym).filter(
                UserGym.gym_id == current_gym.id,
                UserGym.role == GymRoleType.MEMBER,
                UserGym.is_active == True
            ).count()

            trainers_count = db.query(UserGym).filter(
                UserGym.gym_id == current_gym.id,
                UserGym.role == GymRoleType.TRAINER,
                UserGym.is_active == True
            ).count()

            # Contar clases activas
            classes_count = db.query(Class).filter(
                Class.gym_id == current_gym.id,
                Class.is_active == True
            ).count()

            stats = {
                "type": "gym",
                "metrics": {
                    "total_members": members_count,
                    "active_trainers": trainers_count,
                    "active_classes": classes_count,
                    "occupancy_rate": 75.0,  # TODO: Calcular real
                    "member_growth_rate": 5.2,  # TODO: Calcular real
                    "revenue_this_month": 250000.00  # TODO: Obtener de Stripe
                }
            }

        # Cachear por 5 minutos
        import json
        await redis_client.setex(cache_key, 300, json.dumps(stats))

        return stats

    except Exception as e:
        logger.error(f"Error getting workspace stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas del workspace"
        )