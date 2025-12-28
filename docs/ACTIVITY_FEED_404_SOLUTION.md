# 🚨 Solución al Error 404 de Activity Feed

*Fecha: 28 de Diciembre 2024*
*Problema: Frontend recibe 404 al acceder a /api/v1/activity-feed/realtime*

## 📊 Diagnóstico del Problema

### Logs del Error
```
GET /api/v1/activity-feed/realtime HTTP/1.1" 404 Not Found
gym_id: 4
Authorization: Bearer [token válido]
```

### Causa Raíz
El módulo **`activity_feed`** NO está habilitado para el gimnasio con ID 4.

El endpoint existe y está correctamente configurado:
- ✅ Archivo: `/app/api/v1/endpoints/activity_feed.py`
- ✅ Router registrado en `/app/api/v1/api.py`
- ❌ Módulo NO habilitado para gym_id=4

### Verificación del Problema
El router de activity_feed tiene esta protección:
```python
router = APIRouter(
    tags=["Activity Feed"],
    dependencies=[module_enabled("activity_feed")]  # ⚠️ Requiere módulo habilitado
)
```

## 🛠️ Soluciones

### Solución 1: Habilitar el Módulo (Recomendado)

#### Opción A: Via API (Si tienes permisos de admin)
```bash
curl -X PUT http://gymapi.com/api/v1/modules/activity_feed/toggle \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "X-Gym-Id: 4" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

#### Opción B: Via Base de Datos
```sql
-- Verificar si el módulo existe para el gimnasio
SELECT * FROM gym_module
WHERE gym_id = 4 AND module_id = (
    SELECT id FROM module WHERE code = 'activity_feed'
);

-- Si no existe, crearlo
INSERT INTO gym_module (gym_id, module_id, is_active, created_at, updated_at)
SELECT 4, id, true, NOW(), NOW()
FROM module
WHERE code = 'activity_feed';

-- Si existe pero está desactivado, activarlo
UPDATE gym_module
SET is_active = true, updated_at = NOW()
WHERE gym_id = 4 AND module_id = (
    SELECT id FROM module WHERE code = 'activity_feed'
);
```

#### Opción C: Via Script Python
```python
from app.db.session import SessionLocal
from app.services.module import module_service
from app.models.module import Module
from app.models.gym import GymModule

db = SessionLocal()
try:
    # Obtener el módulo activity_feed
    module = db.query(Module).filter_by(code='activity_feed').first()

    if module:
        # Verificar si existe la relación
        gym_module = db.query(GymModule).filter_by(
            gym_id=4,
            module_id=module.id
        ).first()

        if gym_module:
            # Activar si está desactivado
            gym_module.is_active = True
        else:
            # Crear la relación
            gym_module = GymModule(
                gym_id=4,
                module_id=module.id,
                is_active=True
            )
            db.add(gym_module)

        db.commit()
        print("✅ Módulo activity_feed habilitado para gym_id=4")
    else:
        print("❌ Módulo activity_feed no existe en la base de datos")
finally:
    db.close()
```

### Solución 2: Usar Endpoints Alternativos (Temporal)

Si no puedes habilitar el módulo inmediatamente, usa estos endpoints alternativos:

#### 1. **Eventos del Gimnasio** (Disponible)
```javascript
// En lugar de activity feed, usar eventos
const response = await fetch('/api/v1/events', {
    headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-Id': '4'
    }
});

// Los eventos muestran actividad real del gimnasio
```

#### 2. **Dashboard de Usuario** (Disponible)
```javascript
// Obtener estadísticas del usuario
const response = await fetch('/api/v1/users/dashboard', {
    headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-Id': '4'
    }
});

// Incluye estadísticas personales y del gimnasio
```

#### 3. **Métricas del Gimnasio** (Si está habilitado)
```javascript
const response = await fetch('/api/v1/metrics/gym/summary', {
    headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-Id': '4'
    }
});
```

### Solución 3: Implementar Polling Temporal

Mientras se habilita el módulo, implementar un sistema de polling con los endpoints disponibles:

```javascript
class ActivityFeedAlternative {
    constructor(token, gymId) {
        this.token = token;
        this.gymId = gymId;
        this.pollingInterval = null;
    }

    async getRealtimeData() {
        try {
            // Intentar primero el endpoint real
            const response = await fetch('/api/v1/activity-feed/realtime', {
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'X-Gym-Id': this.gymId
                }
            });

            if (response.ok) {
                return await response.json();
            }

            // Fallback: Construir datos similares con otros endpoints
            return await this.buildAlternativeData();

        } catch (error) {
            console.error('Error fetching realtime data:', error);
            return await this.buildAlternativeData();
        }
    }

    async buildAlternativeData() {
        // Combinar datos de varios endpoints
        const [events, attendance] = await Promise.all([
            this.getRecentEvents(),
            this.getCurrentAttendance()
        ]);

        return {
            status: 'success',
            data: {
                active_users: attendance.current_count || 0,
                recent_activities: events.slice(0, 5).map(event => ({
                    type: 'event',
                    message: `${event.participants_count} personas en ${event.name}`,
                    timestamp: event.start_date
                })),
                peak_hours: attendance.is_peak_hour || false,
                daily_total: attendance.daily_total || 0
            }
        };
    }

    async getRecentEvents() {
        try {
            const response = await fetch('/api/v1/events?limit=5&status=active', {
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'X-Gym-Id': this.gymId
                }
            });
            if (response.ok) {
                const data = await response.json();
                return data.events || [];
            }
        } catch (error) {
            console.error('Error fetching events:', error);
        }
        return [];
    }

    async getCurrentAttendance() {
        try {
            const response = await fetch('/api/v1/attendance/current', {
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'X-Gym-Id': this.gymId
                }
            });
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Error fetching attendance:', error);
        }
        return {};
    }

    startPolling(callback, interval = 30000) {
        // Polling cada 30 segundos
        this.pollingInterval = setInterval(async () => {
            const data = await this.getRealtimeData();
            callback(data);
        }, interval);

        // Llamada inicial
        this.getRealtimeData().then(callback);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}

// Uso
const feedService = new ActivityFeedAlternative(token, '4');

feedService.startPolling((data) => {
    console.log('Datos de actividad:', data);
    updateUI(data);
});

// Limpiar cuando se desmonte el componente
// feedService.stopPolling();
```

## 📋 Checklist de Implementación

### Para el Backend:
- [ ] Verificar si el módulo activity_feed existe en la BD
- [ ] Habilitar el módulo para gym_id=4
- [ ] Verificar que Redis está funcionando (requerido para activity feed)
- [ ] Confirmar que el servicio ActivityFeedService está operativo

### Para el Frontend:
- [ ] Implementar manejo de errores 404 con fallback
- [ ] Agregar la clase ActivityFeedAlternative
- [ ] Cambiar el polling de 'realtime' a intervalos de 30s
- [ ] Mostrar mensaje informativo si el módulo no está disponible

## 🔍 Verificación

### Test del Endpoint (Una vez habilitado)
```bash
# Verificar que funciona
curl -X GET "http://gymapi.com/api/v1/activity-feed/realtime" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Gym-Id: 4"

# Respuesta esperada
{
  "status": "success",
  "data": {
    "active_users": 23,
    "recent_activities": [...],
    "peak_hours": false,
    "daily_total": 145
  }
}
```

### Verificar Módulos Activos
```bash
curl -X GET "http://gymapi.com/api/v1/modules/status" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Gym-Id: 4"
```

## 💡 Recomendaciones

1. **Corto Plazo**: Implementar la clase `ActivityFeedAlternative` en el frontend para tener funcionalidad inmediata.

2. **Mediano Plazo**: Habilitar el módulo `activity_feed` para gym_id=4 en la base de datos.

3. **Largo Plazo**: Considerar hacer que ciertos módulos sean obligatorios o habilitados por defecto para evitar estos problemas.

## 🎯 Endpoints Disponibles de Activity Feed (Una vez habilitado)

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/v1/activity-feed/` | Feed principal de actividades |
| `GET /api/v1/activity-feed/realtime` | Estadísticas en tiempo real |
| `GET /api/v1/activity-feed/insights` | Insights motivacionales |
| `GET /api/v1/activity-feed/rankings/{type}` | Rankings anónimos |
| `GET /api/v1/activity-feed/stats/summary` | Resumen diario |
| `WS /api/v1/activity-feed/ws` | WebSocket para updates en tiempo real |

## 📞 Soporte

Si necesitas ayuda para habilitar el módulo:
1. Contacta al administrador del sistema
2. Proporciona el gym_id (4) y el módulo requerido (activity_feed)
3. Solicita la activación del módulo

---

*Documentación creada por: Claude Code Assistant*
*Problema: Frontend recibiendo 404 en activity-feed/realtime*
*Solución: Habilitar módulo o usar endpoints alternativos*