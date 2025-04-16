from typing import Any, List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, Security
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.models.gym import Gym
from app.core.tenant import verify_gym_access
from app.schemas.schedule import (
    GymSpecialHours, 
    GymSpecialHoursCreate, 
    GymSpecialHoursUpdate
)
from app.services import schedule
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.db.redis_client import get_redis_client
from redis.asyncio import Redis

router = APIRouter()


@router.get("/", response_model=List[GymSpecialHours])
async def get_special_days(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    upcoming_only: bool = Query(True, description="Si es True, solo devuelve días especiales futuros"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtiene la lista de días especiales.
    """
    # Obtener el ID del gimnasio
    gym_id = current_gym.id
    
    if upcoming_only:
        return await schedule.gym_special_hours_service.get_upcoming_special_days_cached(
            db=db, limit=limit, gym_id=gym_id, redis_client=redis_client
        )
    else:
        # TODO: Implementar endpoint para obtener todos los días especiales con paginación
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Obtener todos los días especiales aún no está implementado"
        )


@router.get("/{special_day_id}", response_model=GymSpecialHours)
async def get_special_day(
    *,
    db: Session = Depends(get_db),
    special_day_id: int = Path(..., description="ID del día especial"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtiene un día especial por ID.
    """
    special_day = await schedule.gym_special_hours_service.get_special_hours_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    )
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Día especial no encontrado"
        )
    
    # Verificar que el usuario tiene acceso al gimnasio
    gym_id = current_gym.id
    if special_day.gym_id != gym_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este día especial"
        )
    
    return special_day


@router.get("/date/{date}", response_model=GymSpecialHours)
async def get_special_day_by_date(
    *,
    db: Session = Depends(get_db),
    date: date = Path(..., description="Fecha (YYYY-MM-DD)"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtiene el horario especial para una fecha específica.
    """
    # Obtener el ID del gimnasio
    gym_id = current_gym.id
    
    special_day = await schedule.gym_special_hours_service.get_special_hours_by_date_cached(
        db=db, date_value=date, gym_id=gym_id, redis_client=redis_client
    )
    
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay horario especial para la fecha {date}"
        )
    
    return special_day


@router.post("/", response_model=GymSpecialHours, status_code=status.HTTP_201_CREATED)
async def create_special_day(
    *,
    db: Session = Depends(get_db),
    special_day_in: GymSpecialHoursCreate,
    overwrite: bool = Query(False, description="Si es True, sobrescribe el horario especial existente para esta fecha"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Crea un nuevo horario especial.
    El tiempo debe ingresarse en formato HH:MM.
    El gym_id se obtiene automáticamente del header.
    
    Se puede usar el parámetro 'overwrite=true' para sobrescribir un horario especial existente para la misma fecha.
    """
    # Verificar si el usuario es admin o super_admin
    local_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        # Verificar si tiene rol de ADMIN en el gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador para esta acción"
            )
    
    # Obtener el ID del gimnasio desde el header a través de current_gym
    gym_id = current_gym.id
    
    # Verificar si ya existe un horario especial para esta fecha
    existing = await schedule.gym_special_hours_service.get_special_hours_by_date_cached(
        db=db, date_value=special_day_in.date, gym_id=gym_id, redis_client=redis_client
    )
    
    # Crear una copia de los datos de entrada y añadir el gym_id del header
    obj_in_data = special_day_in.model_dump()
    
    # Asignar el ID del gimnasio del header
    obj_in_data["gym_id"] = gym_id
    
    # Asignar el ID del usuario que crea
    obj_in_data["created_by"] = getattr(local_user, "id", None)
    
    # Formatear tiempos si están presentes y no es día cerrado
    if not obj_in_data.get("is_closed", False):
        # Asegurarse de que los tiempos sean correctos
        if "open_time" not in obj_in_data or obj_in_data["open_time"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere hora de apertura cuando el gimnasio no está cerrado"
            )
        if "close_time" not in obj_in_data or obj_in_data["close_time"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere hora de cierre cuando el gimnasio no está cerrado"
            )
    
    try:
        # Si ya existe un horario especial para esta fecha y se permite sobrescribir
        if existing and overwrite:
            # Actualizar el horario especial existente
            update_data = GymSpecialHoursUpdate(
                open_time=obj_in_data.get("open_time"),
                close_time=obj_in_data.get("close_time"),
                is_closed=obj_in_data.get("is_closed"),
                description=obj_in_data.get("description")
            )
            return await schedule.gym_special_hours_service.update_special_day_cached(
                db=db, special_day_id=existing.id, special_hours_data=update_data, redis_client=redis_client
            )
        # Si ya existe pero no se permite sobrescribir, devolver error
        elif existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un horario especial para la fecha {special_day_in.date}. Use overwrite=true para sobrescribirlo."
            )
        # Si no existe, crear uno nuevo
        else:
            # Crear objeto especial con todos los datos validados, incluyendo gym_id
            special_hours_data = GymSpecialHoursCreate(
                date=special_day_in.date,
                open_time=obj_in_data.get("open_time"),
                close_time=obj_in_data.get("close_time"),
                is_closed=obj_in_data.get("is_closed", False),
                description=obj_in_data.get("description")
            )
            # Se agrega el gym_id directamente al crear el objeto en el servicio
            return await schedule.gym_special_hours_service.create_special_day_cached(
                db=db, 
                special_hours_data=special_hours_data,
                gym_id=gym_id,
                redis_client=redis_client
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{special_day_id}", response_model=GymSpecialHours)
async def update_special_day(
    *,
    db: Session = Depends(get_db),
    special_day_id: int = Path(..., description="ID del día especial"),
    special_day_in: GymSpecialHoursUpdate,
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Actualiza un horario especial existente.
    
    El tiempo debe ingresarse en formato HH:MM.
    """
    # Verificar si el usuario es admin o super_admin
    local_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        # Verificar si tiene rol de ADMIN en el gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador para esta acción"
            )
    
    # Verificar que el día especial existe y pertenece al gimnasio del usuario
    special_day = await schedule.gym_special_hours_service.get_special_hours_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    )
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Día especial no encontrado"
        )
    
    # Verificar acceso al gimnasio
    gym_id = current_gym.id
    if special_day.gym_id != gym_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este día especial"
        )
    
    return await schedule.gym_special_hours_service.update_special_day_cached(
        db=db, special_day_id=special_day_id, special_hours_data=special_day_in, redis_client=redis_client
    )


@router.put("/date/{date}", response_model=GymSpecialHours)
async def update_special_day_by_date(
    *,
    db: Session = Depends(get_db),
    date: date = Path(..., description="Fecha (YYYY-MM-DD)"),
    special_day_in: GymSpecialHoursUpdate,
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Actualiza un horario especial existente buscándolo por fecha.
    
    El tiempo debe ingresarse en formato HH:MM.
    Si no existe un horario especial para la fecha indicada, se devuelve un error 404.
    """
    # Verificar si el usuario es admin o super_admin
    local_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        # Verificar si tiene rol de ADMIN en el gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador para esta acción"
            )
    
    # Obtener el ID del gimnasio
    gym_id = current_gym.id
    
    # Buscar el día especial por fecha
    special_day = await schedule.gym_special_hours_service.get_special_hours_by_date_cached(
        db=db, date_value=date, gym_id=gym_id, redis_client=redis_client
    )
    
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay horario especial para la fecha {date}"
        )
    
    # Actualizar el día especial
    return await schedule.gym_special_hours_service.update_special_day_cached(
        db=db, special_day_id=special_day.id, special_hours_data=special_day_in, redis_client=redis_client
    )


@router.delete("/{special_day_id}", response_model=GymSpecialHours)
async def delete_special_day(
    *,
    db: Session = Depends(get_db),
    special_day_id: int = Path(..., description="ID del día especial"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Elimina un horario especial.
    """
    # Verificar si el usuario es admin o super_admin
    local_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        # Verificar si tiene rol de ADMIN en el gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador para esta acción"
            )
    
    # Verificar que el día especial existe y pertenece al gimnasio del usuario
    special_day = await schedule.gym_special_hours_service.get_special_hours_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    )
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Día especial no encontrado"
        )
    
    # Verificar acceso al gimnasio
    gym_id = current_gym.id
    if special_day.gym_id != gym_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este día especial"
        )
    
    return await schedule.gym_special_hours_service.delete_special_day_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    ) 