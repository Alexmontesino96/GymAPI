# Sistema de Zonas Horarias para Gimnasios

## Resumen

El sistema ahora soporta zonas horarias específicas para cada gimnasio, permitiendo que las sesiones se almacenen como hora local del gimnasio y se conviertan automáticamente para los clientes.

## Conceptos Clave

### Hora Local del Gimnasio
- Las sesiones se almacenan como `datetime naive` (sin timezone)
- Representan la hora local del gimnasio donde ocurre la sesión
- Ejemplo: `14:00:00` = 2:00 PM en la zona horaria del gimnasio

### Timezone del Gimnasio
- Cada gimnasio tiene un campo `timezone` que especifica su zona horaria
- Formato: estándar pytz (ej: `America/Mexico_City`, `UTC`, `Europe/Madrid`)
- Se valida que sea una zona horaria válida al crear/actualizar

## Implementación

### Modelo de Datos

```python
# Modelo Gym actualizado
class Gym(Base):
    # ... otros campos
    timezone = Column(String(50), nullable=False, default='UTC')
```

### Esquemas de API

```python
class GymBase(BaseModel):
    # ... otros campos
    timezone: str = Field('UTC', description="Timezone en formato pytz")
    
    @validator('timezone')
    def validate_timezone(cls, v):
        if v not in pytz.all_timezones:
            raise ValueError(f"Zona horaria inválida: {v}")
        return v
```

### Validación de Tiempo

```python
# Antes: datetime.utcnow() - problemático
current_time = datetime.utcnow()
if session.start_time <= current_time:
    # Error: compara naive con posible aware

# Ahora: usando timezone del gimnasio
if not is_session_in_future(session.start_time, gym.timezone):
    raise HTTPException(400, "Sesión ya comenzó")
```

## API Endpoints

### Endpoint con Timezone

```http
GET /api/v1/schedule/sessions-with-timezone
```

Respuesta:
```json
[
  {
    "id": 123,
    "start_time": "2025-07-27T14:00:00",  // Hora local naive
    "end_time": "2025-07-27T15:00:00",
    "gym_timezone": "America/Mexico_City",
    "time_info": {
      "local_time": "2025-07-27T14:00:00",
      "gym_timezone": "America/Mexico_City",
      "iso_with_timezone": "2025-07-27T14:00:00-06:00",
      "utc_time": "2025-07-27T20:00:00+00:00"
    },
    // ... otros campos de sesión
  }
]
```

## Utilidades de Timezone

### Funciones Principales

```python
from app.core.timezone_utils import (
    convert_naive_to_gym_timezone,
    convert_gym_time_to_utc,
    get_current_time_in_gym_timezone,
    is_session_in_future,
    format_session_time_with_timezone
)

# Convertir hora naive a aware del gimnasio
session_aware = convert_naive_to_gym_timezone(
    session.start_time, 
    gym.timezone
)

# Verificar si sesión está en el futuro
is_future = is_session_in_future(session.start_time, gym.timezone)

# Formatear información de tiempo
time_info = format_session_time_with_timezone(
    session.start_time, 
    gym.timezone
)
```

## Flujo para el Cliente

### Creación de Sesión
1. Cliente envía hora local deseada: `"2025-07-27T14:00:00"`
2. Se almacena como datetime naive en BD
3. Validaciones usan timezone del gimnasio para verificar si está en el futuro

### Consulta de Sesiones
1. Cliente solicita sesiones
2. API devuelve hora naive + timezone del gimnasio + info adicional
3. Cliente convierte a su zona horaria local usando la info proporcionada

### Ejemplo de Conversión en Cliente (JavaScript)

```javascript
// Respuesta de API
const session = {
  start_time: "2025-07-27T14:00:00",
  gym_timezone: "America/Mexico_City",
  time_info: {
    iso_with_timezone: "2025-07-27T14:00:00-06:00"
  }
};

// Convertir a hora local del usuario
const userLocalTime = new Date(session.time_info.iso_with_timezone);
console.log(userLocalTime.toLocaleString()); // Se muestra en timezone del usuario
```

## Migración de Datos Existentes

### Script de Migración
```sql
-- Agregar columna timezone con valor por defecto
ALTER TABLE gyms ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC';

-- Actualizar gymnásios existentes con timezone apropiado
UPDATE gyms SET timezone = 'America/Mexico_City' WHERE id IN (1, 2, 3);
UPDATE gyms SET timezone = 'Europe/Madrid' WHERE id IN (4, 5);

-- Hacer columna NOT NULL después de establecer valores
ALTER TABLE gyms ALTER COLUMN timezone SET NOT NULL;
```

## Ventajas del Sistema

1. **Simplicidad**: Horas se almacenan como el gimnasio las ve localmente
2. **Flexibilidad**: Cada gimnasio puede tener su propia zona horaria
3. **Precisión**: No hay ambigüedad sobre qué representa cada hora
4. **Compatibilidad**: Cliente decide cómo mostrar las horas al usuario

## Casos de Uso

### Gimnasio en México (UTC-6)
- Sesión a las 2:00 PM se almacena como `14:00:00`
- Timezone: `America/Mexico_City`
- Cliente en España ve: 8:00 PM (UTC+1)

### Gimnasio en España (UTC+1)  
- Sesión a las 2:00 PM se almacena como `14:00:00`
- Timezone: `Europe/Madrid`
- Cliente en México ve: 7:00 AM (UTC-6)

## Limitaciones Actuales

1. **Consultas BD**: Algunas consultas aún usan `datetime.utcnow()` para comparaciones directas en BD
2. **Horario de Verano**: pytz maneja automáticamente, pero hay que validar edge cases
3. **Performance**: Conversiones de timezone agregan overhead mínimo

## TODO Futuro

- [ ] Migrar todas las consultas de BD para usar timezone
- [ ] Agregar tests para cambios de horario de verano
- [ ] Considerar caching de conversiones frecuentes
- [ ] Documentación para clientes móviles