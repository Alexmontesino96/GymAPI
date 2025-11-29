# Activity Feed API Documentation

Sistema de feed de actividades en tiempo real que muestra estadísticas agregadas del gimnasio para aumentar el engagement y motivación de los usuarios.

## Base URL

```
/api/v1/activity-feed
```

## Autenticación

Todos los endpoints requieren autenticación JWT. El `gym_id` se extrae automáticamente del token.

```
Authorization: Bearer <token>
```

---

## Endpoints

### 1. Obtener Feed de Actividades

Obtiene el feed principal con actividades recientes del gimnasio.

```http
GET /api/v1/activity-feed/
```

#### Query Parameters

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Número de actividades (1-100) |
| `offset` | int | 0 | Offset para paginación |

#### Request Example

```bash
curl -X GET "https://api.example.com/api/v1/activity-feed/?limit=10&offset=0" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK

```json
{
  "activities": [
    {
      "id": "1_training_count_1701234567.123",
      "type": "realtime",
      "subtype": "training_count",
      "count": 25,
      "message": "25 personas entrenando ahora",
      "timestamp": "2024-11-29T15:30:00.000Z",
      "icon": "💪",
      "ttl_minutes": 5,
      "time_ago": "hace 5 minutos"
    },
    {
      "type": "class_completed",
      "message": "✅ Clase completada con 18 guerreros",
      "timestamp": "2024-11-29T15:00:00.000Z",
      "icon": "✅"
    }
  ],
  "count": 10,
  "has_more": true,
  "offset": 0,
  "limit": 10
}
```

---

### 2. Estadísticas en Tiempo Real

Obtiene estadísticas actuales del gimnasio.

```http
GET /api/v1/activity-feed/realtime
```

#### Request Example

```bash
curl -X GET "https://api.example.com/api/v1/activity-feed/realtime" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK

```json
{
  "status": "success",
  "data": {
    "total_training": 45,
    "by_area": {
      "CrossFit": 15,
      "Spinning": 12,
      "Yoga": 8
    },
    "popular_classes": [
      {"name": "CrossFit", "count": 15},
      {"name": "Spinning", "count": 12},
      {"name": "Yoga", "count": 8}
    ],
    "peak_time": true,
    "last_update": "2024-11-29T15:30:00.000Z"
  }
}
```

---

### 3. Insights Motivacionales

Genera mensajes motivacionales basados en la actividad actual.

```http
GET /api/v1/activity-feed/insights
```

#### Request Example

```bash
curl -X GET "https://api.example.com/api/v1/activity-feed/insights" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK

```json
{
  "insights": [
    {
      "message": "🔥 ¡45 guerreros activos ahora mismo!",
      "type": "realtime",
      "priority": 1
    },
    {
      "message": "⭐ 12 logros desbloqueados hoy",
      "type": "achievement",
      "priority": 2
    },
    {
      "message": "💪 8 récords personales superados",
      "type": "record",
      "priority": 1
    }
  ],
  "count": 3
}
```

---

### 4. Rankings

Obtiene rankings de usuarios con nombre y user_id para mostrar fotos de perfil.

```http
GET /api/v1/activity-feed/rankings/{ranking_type}
```

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `ranking_type` | string | Tipo de ranking |

**Tipos válidos:**
- `consistency` - Días consecutivos de entrenamiento
- `attendance` - Clases asistidas
- `improvement` - Porcentaje de mejora
- `activity` - Horas de actividad
- `dedication` - Puntos de dedicación

#### Query Parameters

| Parámetro | Tipo | Default | Valores | Descripción |
|-----------|------|---------|---------|-------------|
| `period` | string | weekly | daily, weekly, monthly | Período del ranking |
| `limit` | int | 10 | 1-50 | Posiciones a mostrar |

#### Request Example

```bash
curl -X GET "https://api.example.com/api/v1/activity-feed/rankings/attendance?period=daily&limit=10" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK

```json
{
  "type": "attendance",
  "period": "daily",
  "rankings": [
    {
      "position": 1,
      "value": 5,
      "user_id": 123,
      "name": "Juan P.",
      "label": "Juan P."
    },
    {
      "position": 2,
      "value": 4,
      "user_id": 456,
      "name": "María G.",
      "label": "María G."
    },
    {
      "position": 3,
      "value": 3,
      "user_id": 789,
      "name": "Carlos R.",
      "label": "Carlos R."
    }
  ],
  "unit": "clases",
  "count": 3
}
```

#### Response 400 Bad Request

```json
{
  "detail": "Tipo de ranking inválido. Tipos válidos: ['consistency', 'attendance', 'improvement', 'activity', 'dedication']"
}
```

---

### 5. Resumen de Estadísticas del Día

Obtiene un resumen completo de las estadísticas diarias.

```http
GET /api/v1/activity-feed/stats/summary
```

#### Request Example

```bash
curl -X GET "https://api.example.com/api/v1/activity-feed/stats/summary" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK

```json
{
  "date": "today",
  "stats": {
    "attendance": 156,
    "achievements": 23,
    "personal_records": 12,
    "goals_completed": 8,
    "classes_completed": 15,
    "total_hours": 234.5,
    "active_streaks": 67,
    "average_class_size": 10.4,
    "engagement_score": 85
  },
  "highlights": [
    "🔥 Día increíble con 156 asistencias",
    "💪 12 récords rotos hoy",
    "⭐ 23 logros desbloqueados"
  ]
}
```

---

### 6. WebSocket - Feed en Tiempo Real

Conexión WebSocket para recibir actualizaciones instantáneas.

```
WS /api/v1/activity-feed/ws?gym_id={gym_id}
```

#### Query Parameters

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `gym_id` | int | Sí | ID del gimnasio |

#### Connection Example (JavaScript)

```javascript
const ws = new WebSocket('wss://api.example.com/api/v1/activity-feed/ws?gym_id=1');

ws.onopen = () => {
  console.log('Conectado al Activity Feed');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'connection') {
    console.log('Bienvenida:', data.message);
  } else if (data.type === 'activity') {
    console.log('Nueva actividad:', data.data);
    // Actualizar UI con la nueva actividad
  }
};

ws.onclose = () => {
  console.log('Desconectado del Activity Feed');
};
```

#### Mensajes Recibidos

**Mensaje de conexión:**
```json
{
  "type": "connection",
  "message": "Conectado al feed en tiempo real",
  "gym_id": 1
}
```

**Nueva actividad:**
```json
{
  "type": "activity",
  "data": {
    "id": "1_training_count_1701234567.123",
    "type": "realtime",
    "subtype": "training_count",
    "count": 30,
    "message": "30 personas entrenando ahora",
    "timestamp": "2024-11-29T15:35:00.000Z",
    "icon": "💪"
  }
}
```

---

### 7. Health Check

Verifica el estado del sistema de Activity Feed.

```http
GET /api/v1/activity-feed/health
```

#### Request Example

```bash
curl -X GET "https://api.example.com/api/v1/activity-feed/health" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK (Healthy)

```json
{
  "status": "healthy",
  "redis": "connected",
  "memory_usage_mb": 12.45,
  "anonymous_mode": true,
  "privacy_compliant": true,
  "keys_count": {
    "feed": 5,
    "realtime": 12,
    "daily": 8,
    "total": 25
  },
  "configuration": {
    "min_aggregation_threshold": 3,
    "show_user_names": false,
    "ttl_enabled": true
  }
}
```

#### Response (Unhealthy)

```json
{
  "status": "unhealthy",
  "error": "Connection refused",
  "redis": "disconnected"
}
```

---

### 8. Generar Actividad de Prueba (Solo Testing)

Endpoint para generar actividades de prueba. **Solo usar en desarrollo.**

```http
POST /api/v1/activity-feed/test/generate-activity
```

#### Query Parameters

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `activity_type` | string | Sí | Tipo de actividad |
| `count` | int | Sí | Cantidad (mínimo 1) |

**Tipos de actividad:**
- `training_count` - Personas entrenando
- `class_checkin` - Check-ins de clase
- `achievement_unlocked` - Logros
- `streak_milestone` - Hitos de racha
- `pr_broken` - Récords personales
- `goal_completed` - Metas cumplidas

#### Request Example

```bash
curl -X POST "https://api.example.com/api/v1/activity-feed/test/generate-activity?activity_type=training_count&count=25" \
  -H "Authorization: Bearer <token>"
```

#### Response 200 OK (Publicado)

```json
{
  "status": "success",
  "activity": {
    "id": "1_training_count_1701234567.123",
    "type": "realtime",
    "subtype": "training_count",
    "count": 25,
    "message": "25 personas entrenando ahora",
    "timestamp": "2024-11-29T15:30:00.000Z",
    "icon": "💪",
    "ttl_minutes": 5
  }
}
```

#### Response 200 OK (No publicado - umbral mínimo)

```json
{
  "status": "not_published",
  "reason": "Count 2 below threshold"
}
```

> **Nota:** Las actividades con `count < 3` no se publican para proteger la privacidad (umbral mínimo de agregación).

---

## Tipos de Actividades

| Tipo | Icono | Descripción |
|------|-------|-------------|
| `training_count` | 💪 | Personas entrenando actualmente |
| `class_checkin` | 📍 | Check-ins en una clase |
| `achievement_unlocked` | ⭐ | Logros desbloqueados |
| `streak_milestone` | 🔥 | Hitos de racha (7, 14, 30 días...) |
| `pr_broken` | 🏆 | Récords personales rotos |
| `goal_completed` | 🎯 | Metas cumplidas |
| `social_activity` | 👥 | Actividad social |
| `class_popular` | 📈 | Clase popular |
| `hourly_summary` | 📊 | Resumen horario |
| `motivational` | 💫 | Mensaje motivacional |
| `class_completed` | ✅ | Clase completada |

---

## Configuración de TTL

| Tipo de Dato | TTL | Descripción |
|--------------|-----|-------------|
| Realtime | 5 min | Datos en tiempo real |
| Hourly | 1 hora | Resúmenes horarios |
| Daily | 24 horas | Estadísticas diarias |
| Weekly | 7 días | Rankings semanales |
| Feed | 24 horas | Items del feed |

---

## Jobs Programados

El sistema ejecuta los siguientes jobs automáticamente:

| Job | Frecuencia | Descripción |
|-----|------------|-------------|
| `update_realtime_counters` | Cada 5 min | Actualiza contadores de actividad |
| `generate_hourly_summary` | Cada hora | Genera resumen horario |
| `update_daily_rankings` | 23:50 | Actualiza rankings del día |
| `reset_daily_counters` | 00:05 | Resetea contadores diarios |
| `generate_motivational_burst` | Cada 30 min | Genera insights motivacionales |
| `cleanup_expired_data` | Cada 2 horas | Limpieza y monitoreo |

---

## Privacidad

- **Umbral mínimo de agregación:** 3 personas
- **Rankings:** Muestran nombre parcial (ej: "Juan P.") + `user_id` para foto
- **Sin exposición de IDs** en actividades del feed
- **TTL automático** para eliminación de datos
- **Multi-tenant:** Datos aislados por `gym_id`

---

## Errores Comunes

| Código | Descripción |
|--------|-------------|
| 400 | Tipo de ranking inválido |
| 401 | Token JWT inválido o expirado |
| 500 | Error interno del servidor |

---

## Ejemplos de Integración

### React Native

```javascript
// Hook para el Activity Feed
import { useState, useEffect } from 'react';

const useActivityFeed = (token) => {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFeed = async () => {
      const response = await fetch('/api/v1/activity-feed/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setActivities(data.activities);
      setLoading(false);
    };

    fetchFeed();
  }, [token]);

  return { activities, loading };
};
```

### WebSocket con Reconexión

```javascript
class ActivityFeedSocket {
  constructor(gymId, onActivity) {
    this.gymId = gymId;
    this.onActivity = onActivity;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(`wss://api.example.com/api/v1/activity-feed/ws?gym_id=${this.gymId}`);

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'activity') {
        this.onActivity(data.data);
      }
    };

    this.ws.onclose = () => {
      // Reconectar después de 5 segundos
      setTimeout(() => this.connect(), 5000);
    };
  }

  disconnect() {
    this.ws.close();
  }
}
```
