# Solución del problema con gym_id en la creación de sesiones

## Descripción del problema

Cuando se intentaba crear una sesión en la aplicación, se producía un error 500 en el servidor con este mensaje:

```
sqlalchemy.exc.IntegrityError: (psycopg2.errors.NotNullViolation) null value in column "gym_id" of relation "class_session" violates not-null constraint
```

El problema se debía a que el campo `gym_id` en la tabla `class_session` es obligatorio (`nullable=False`), pero este valor no estaba siendo asignado durante el proceso de creación de la sesión. Aunque el cliente enviaba el `gym_id` en la solicitud, este valor no estaba definido en el esquema `ClassSessionBase/ClassSessionCreate`, por lo que se descartaba durante la validación.

## Solución implementada

Se realizaron las siguientes modificaciones para resolver el problema:

### 1. Actualización del esquema ClassSessionBase

Se añadió el campo `gym_id` como opcional en el esquema base para permitir que se incluya en la solicitud:

```python
# En app/schemas/schedule.py
class ClassSessionBase(BaseModel):
    class_id: int
    trainer_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    room: Optional[str] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    status: ClassSessionStatus = ClassSessionStatus.SCHEDULED
    notes: Optional[str] = None
    gym_id: Optional[int] = None  # Añadido como opcional
```

### 2. Modificación del endpoint create_session

Se modificó el endpoint para obtener automáticamente el `gym_id` del tenant actual y asignarlo a la sesión antes de crearla:

```python
# En app/api/v1/endpoints/schedule/sessions.py
@router.post("/sessions", response_model=ClassSession)
async def create_session(
    session_data: ClassSessionCreate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"]),
    current_gym: Gym = Depends(get_current_gym)  # Obtener el gimnasio actual
) -> Any:
    # Obtener ID del usuario actual para registrarlo como creador
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    created_by_id = db_user.id if db_user else None
    
    # Asignar el gym_id desde el tenant actual
    session_obj = session_data.model_dump()
    session_obj["gym_id"] = current_gym.id
    
    # Crear un nuevo objeto ClassSessionCreate con el gym_id establecido
    updated_session_data = ClassSessionCreate(**session_obj)
    
    return class_session_service.create_session(
        db, session_data=updated_session_data, created_by_id=created_by_id
    )
```

### 3. Modificación del endpoint create_recurring_sessions

También se aplicó la misma solución al endpoint para crear sesiones recurrentes:

```python
@router.post("/sessions/recurring", response_model=List[ClassSession])
async def create_recurring_sessions(
    base_session: ClassSessionCreate = Body(...),
    start_date: date = Body(..., description="Fecha de inicio"),
    end_date: date = Body(..., description="Fecha de fin"),
    days_of_week: List[int] = Body(
        ..., description="Días de la semana (0=Lunes, 6=Domingo)"
    ),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"]),
    current_gym: Gym = Depends(get_current_gym)  # Obtener el gimnasio actual
) -> Any:
    # ...código existente...
    
    # Asignar el gym_id desde el tenant actual
    session_obj = base_session.model_dump()
    session_obj["gym_id"] = current_gym.id
    
    # Crear un nuevo objeto ClassSessionCreate con el gym_id establecido
    updated_base_session = ClassSessionCreate(**session_obj)
    
    return class_session_service.create_recurring_sessions(
        db, 
        base_session_data=updated_base_session,
        # ...resto de parámetros...
    )
```

### 4. Actualización de importaciones

Se añadieron las importaciones necesarias para `get_current_gym` y `Gym` en los archivos relevantes:

```python
# En app/api/v1/endpoints/schedule/common.py
from app.core.tenant import get_current_gym, verify_gym_access, verify_trainer_role, verify_admin_role
from app.models.gym import Gym
```

## Ventajas de esta solución

1. **Mantiene la separación entre tenants**: Asegura que cada sesión se asocia correctamente con el gimnasio correspondiente.
2. **Seguridad mejorada**: El `gym_id` se obtiene del token de autenticación y los headers verificados, no de datos proporcionados por el cliente.
3. **Experiencia de usuario mejorada**: El cliente ya no necesita proporcionar explícitamente el `gym_id` en las solicitudes.
4. **Simplificación del API**: Los clientes solo necesitan enviar los datos específicos de la sesión.

## Recomendaciones adicionales

1. **Considerar implementar verificaciones similares**: En otros endpoints que requieren `gym_id` u otros campos relacionados con el tenant.
2. **Mejorar la documentación de la API**: Aclarar qué campos se obtienen automáticamente de los headers y cuáles deben proporcionarse en el cuerpo de la solicitud.
3. **Añadir tests automatizados**: Para verificar que la creación de sesiones funciona correctamente con diferentes configuraciones de tenant.

## Prueba de la solución

El archivo `test_fixed_session.py` permite verificar que la solución funciona correctamente y que ahora es posible crear sesiones sin proporcionar explícitamente el `gym_id`. 