# API de Activity Feed - Actividades en Tiempo Real

## Índice

- [Descripción General](#descripción-general)
- [Arquitectura](#arquitectura)
- [Endpoints](#endpoints)
  - [Feed de Actividades](#1-get-activity_feed)
  - [Estadísticas en Tiempo Real](#2-get-activity_feedrealtime)
  - [Insights Motivacionales](#3-get-activity_feedinsights)
  - [Rankings Anónimos](#4-get-activity_feedrankingsranking_type)
  - [Resumen Diario](#5-get-activity_feedstatssummary)
  - [WebSocket en Tiempo Real](#6-websocket-activity_feedws)
  - [Health Check](#7-get-activity_feedhealth)
  - [Testing](#8-post-activity_feedtestgenerate-activity)
- [Modelos de Datos](#modelos-de-datos)
- [Privacidad y Seguridad](#privacidad-y-seguridad)
- [Ejemplos de Uso](#ejemplos-de-uso)

---

## Descripción General

El **Activity Feed** es un sistema de actividades en tiempo real completamente **anónimo** que muestra estadísticas agregadas del gimnasio sin exponer identidades de usuarios.

### Principio Fundamental
> **"Números que motivan, sin nombres que comprometan"**

### Características Principales

✅ **100% Anónimo**: Solo muestra cantidades y estadísticas agregadas
✅ **Tiempo Real**: Actualizaciones instantáneas vía WebSocket
✅ **Motivacional**: Insights dinámicos que inspiran a la comunidad
✅ **Privacy-First**: Umbral mínimo de agregación (3+ usuarios)
✅ **Efímero**: Datos con TTL automático en Redis
✅ **Sin Configuración**: No requiere activación de módulo

---

## Arquitectura

### Stack Tecnológico

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend / Mobile App                     │
├─────────────────────────────────────────────────────────────┤
│                   REST API + WebSocket                       │
│            (app/api/v1/endpoints/activity_feed.py)           │
├─────────────────────────────────────────────────────────────┤
│              Activity Feed Service Layer                     │
│          (app/services/activity_feed_service.py)             │
│                                                              │
│  - Publicar actividades anónimas                            │
│  - Generar insights motivacionales                          │
│  - Gestionar rankings anónimos                              │
├─────────────────────────────────────────────────────────────┤
│            Activity Aggregator Service                       │
│          (app/services/activity_aggregator.py)               │
│                                                              │
│  - Agregar eventos del sistema                              │
│  - Convertir eventos en estadísticas                        │
│  - Publicar en Redis PubSub                                 │
├─────────────────────────────────────────────────────────────┤
│                     Redis (Data Store)                       │
│                                                              │
│  - Almacenamiento efímero con TTL                           │
│  - PubSub para actualizaciones en tiempo real               │
│  - Contadores atómicos                                      │
└─────────────────────────────────────────────────────────────┘
```

### TTL (Time To Live) Configurados

| Tipo de Dato | TTL | Uso |
|--------------|-----|-----|
| **Realtime** | 5 minutos | Datos en tiempo real (personas activas) |
| **Hourly** | 1 hora | Resúmenes horarios |
| **Daily** | 24 horas | Estadísticas diarias |
| **Weekly** | 7 días | Rankings semanales |
| **Feed** | 24 horas | Items del feed de actividades |

### Umbrales de Privacidad

- **Mínimo de Agregación**: 3 usuarios
- **Actividades afectadas**: `training_count`, `class_checkin`
- **Principio**: No se publican actividades con menos de 3 participantes

---

## Endpoints

### Base URL
```
/api/v1/activity_feed
```

### Headers Requeridos
```http
X-Gym-ID: 7
Authorization: Bearer {token}
```

---

## 1. GET /activity_feed/

Obtiene el feed de actividades anónimo con paginación.

### Request

**Query Parameters:**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `limit` | int | No | 20 | Número de actividades (1-100) |
| `offset` | int | No | 0 | Offset para paginación |

**Ejemplo:**
```bash
curl -X GET "https://api.gymapi.com/api/v1/activity_feed/?limit=10&offset=0" \
  -H "X-Gym-ID: 7" \
  -H "Authorization: Bearer {token}"
```

### Response

**Status:** `200 OK`

```json
{
  "activities": [
    {
      "id": "7_training_count_1734660000.123",
      "type": "realtime",
      "subtype": "training_count",
      "count": 45,
      "message": "💪 45 personas entrenando ahora mismo",
      "timestamp": "2025-12-19T15:30:00.000Z",
      "icon": "💪",
      "ttl_minutes": 5
    },
    {
      "id": "7_achievement_unlocked_1734659900.456",
      "type": "realtime",
      "subtype": "achievement_unlocked",
      "count": 12,
      "message": "⭐ 12 logros desbloqueados en la última hora",
      "timestamp": "2025-12-19T15:25:00.000Z",
      "icon": "⭐",
      "ttl_minutes": 5
    }
  ],
  "count": 2,
  "has_more": true,
  "offset": 0,
  "limit": 10
}
```

### Tipos de Actividades

| Tipo | Icono | Descripción |
|------|-------|-------------|
| `training_count` | 💪 | Personas entrenando actualmente |
| `class_checkin` | 📍 | Check-ins a clases |
| `achievement_unlocked` | ⭐ | Logros desbloqueados |
| `streak_milestone` | 🔥 | Hitos de racha alcanzados |
| `pr_broken` | 🏆 | Récords personales superados |
| `goal_completed` | 🎯 | Metas completadas |
| `social_activity` | 👥 | Actividad social |
| `class_popular` | 📈 | Clases populares |
| `hourly_summary` | 📊 | Resumen horario |
| `motivational` | 💫 | Mensaje motivacional |

---

## 2. GET /activity_feed/realtime

Obtiene estadísticas en tiempo real del gimnasio.

### Request

**Ejemplo:**
```bash
curl -X GET "https://api.gymapi.com/api/v1/activity_feed/realtime" \
  -H "X-Gym-ID: 7" \
  -H "Authorization: Bearer {token}"
```

### Response

**Status:** `200 OK`

```json
{
  "status": "success",
  "data": {
    "active_now": 45,
    "by_area": {
      "cardio": 15,
      "weights": 22,
      "functional": 8
    },
    "popular_classes": [
      {
        "name": "Spinning",
        "participants": 18,
        "capacity": 20,
        "percentage": 90
      },
      {
        "name": "CrossFit",
        "participants": 12,
        "capacity": 15,
        "percentage": 80
      }
    ],
    "is_peak_hour": true,
    "peak_hours": ["07:00-09:00", "18:00-21:00"],
    "hourly_trend": "increasing"
  }
}
```

### Campos del Response

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `active_now` | int | Total de personas entrenando ahora |
| `by_area` | object | Distribución por áreas del gimnasio |
| `popular_classes` | array | Clases más populares actuales |
| `is_peak_hour` | boolean | Si es hora pico |
| `peak_hours` | array | Horarios pico del día |
| `hourly_trend` | string | Tendencia horaria (increasing, decreasing, stable) |

---

## 3. GET /activity_feed/insights

Obtiene insights motivacionales basados en actividad actual.

### Request

**Ejemplo:**
```bash
curl -X GET "https://api.gymapi.com/api/v1/activity_feed/insights" \
  -H "X-Gym-ID: 7" \
  -H "Authorization: Bearer {token}"
```

### Response

**Status:** `200 OK`

```json
{
  "insights": [
    "🔥 45 guerreros activos ahora mismo",
    "⭐ 12 logros desbloqueados hoy",
    "💪 8 récords personales superados",
    "🎯 Tendencia al alza en la última hora"
  ],
  "count": 4
}
```

### Tipos de Insights Generados

- **Actividad Actual**: Personas entrenando en tiempo real
- **Logros del Día**: Achievements desbloqueados
- **Récords Rotos**: PRs superados
- **Tendencias**: Análisis de actividad horaria/diaria
- **Hitos de Racha**: Usuarios con streaks importantes
- **Popularidad de Clases**: Clases más concurridas

---

## 4. GET /activity_feed/rankings/{ranking_type}

Obtiene rankings anónimos (solo valores, sin nombres).

### Request

**Path Parameters:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `ranking_type` | string | Sí | Tipo de ranking |

**Query Parameters:**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `period` | string | No | `weekly` | Período (daily, weekly, monthly) |
| `limit` | int | No | 10 | Posiciones a mostrar (1-50) |

**Ejemplo:**
```bash
curl -X GET "https://api.gymapi.com/api/v1/activity_feed/rankings/consistency?period=weekly&limit=5" \
  -H "X-Gym-ID: 7" \
  -H "Authorization: Bearer {token}"
```

### Tipos de Rankings Disponibles

| Tipo | Descripción | Unidad |
|------|-------------|--------|
| `consistency` | Días consecutivos de entrenamiento | días consecutivos |
| `attendance` | Clases asistidas en el período | clases |
| `improvement` | Porcentaje de mejora | % mejora |
| `activity` | Horas totales de entrenamiento | horas |
| `dedication` | Puntuación de dedicación | puntos |

### Response

**Status:** `200 OK`

```json
{
  "type": "consistency",
  "period": "weekly",
  "rankings": [
    {
      "position": 1,
      "value": 30,
      "badge": "🥇"
    },
    {
      "position": 2,
      "value": 28,
      "badge": "🥈"
    },
    {
      "position": 3,
      "value": 25,
      "badge": "🥉"
    },
    {
      "position": 4,
      "value": 21,
      "badge": null
    },
    {
      "position": 5,
      "value": 18,
      "badge": null
    }
  ],
  "unit": "días consecutivos",
  "count": 5
}
```

### Notas de Privacidad

- ✅ **Solo valores numéricos**, sin nombres ni identificadores
- ✅ Rankings con **mínimo 5 participantes**
- ✅ No se muestra posición del usuario actual (evita identificación)

---

## 5. GET /activity_feed/stats/summary

Obtiene resumen de estadísticas del día actual.

### Request

**Ejemplo:**
```bash
curl -X GET "https://api.gymapi.com/api/v1/activity_feed/stats/summary" \
  -H "X-Gym-ID: 7" \
  -H "Authorization: Bearer {token}"
```

### Response

**Status:** `200 OK`

```json
{
  "date": "today",
  "stats": {
    "attendance": 234,
    "achievements": 45,
    "personal_records": 18,
    "goals_completed": 32,
    "classes_completed": 28,
    "total_hours": 487.5,
    "active_streaks": 67,
    "average_class_size": 8.4,
    "engagement_score": 89
  },
  "highlights": [
    "🔥 Día increíble con 234 asistencias",
    "💪 18 récords rotos hoy",
    "⭐ 45 logros desbloqueados"
  ]
}
```

### Métricas Calculadas

| Métrica | Descripción | Fórmula |
|---------|-------------|---------|
| `attendance` | Total de asistencias | Contador incremental |
| `achievements` | Logros desbloqueados | Contador incremental |
| `personal_records` | Récords rotos | Contador incremental |
| `goals_completed` | Metas completadas | Contador incremental |
| `classes_completed` | Clases finalizadas | Contador incremental |
| `total_hours` | Horas totales | Suma acumulativa |
| `active_streaks` | Rachas activas | Usuarios con streak > 0 |
| `average_class_size` | Promedio de asistentes | attendance / classes_completed |
| `engagement_score` | Puntuación de engagement | (attendance×2) + (achievements×5) + (PR×10) + (goals×3) |

### Highlights Generados

Los highlights se generan automáticamente basados en umbrales:

- **Attendance > 100**: "🔥 Día increíble con {N} asistencias"
- **Personal Records > 10**: "💪 {N} récords rotos hoy"
- **Achievements > 20**: "⭐ {N} logros desbloqueados"
- **Active Streaks > 50**: "🔥 {N} rachas activas"
- **Engagement Score > 80**: "🏆 Engagement excepcional del gimnasio"

---

## 6. WebSocket /activity_feed/ws

Conexión WebSocket para recibir actualizaciones del feed en tiempo real.

### Conexión

**URL:**
```
wss://api.gymapi.com/api/v1/activity_feed/ws?gym_id=7
```

**Query Parameters:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `gym_id` | int | Sí | ID del gimnasio |

### Ejemplo JavaScript

```javascript
const ws = new WebSocket('wss://api.gymapi.com/api/v1/activity_feed/ws?gym_id=7');

ws.onopen = () => {
  console.log('Conectado al feed en tiempo real');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'connection') {
    console.log('Mensaje de bienvenida:', data.message);
  }

  if (data.type === 'activity') {
    console.log('Nueva actividad:', data.data);
    // Actualizar UI con nueva actividad
    displayActivity(data.data);
  }
};

ws.onerror = (error) => {
  console.error('Error en WebSocket:', error);
};

ws.onclose = () => {
  console.log('Desconectado del feed');
};
```

### Mensajes Recibidos

#### 1. Mensaje de Conexión

```json
{
  "type": "connection",
  "message": "Conectado al feed en tiempo real",
  "gym_id": 7
}
```

#### 2. Nueva Actividad

```json
{
  "type": "activity",
  "data": {
    "id": "7_class_checkin_1734660123.456",
    "type": "realtime",
    "subtype": "class_checkin",
    "count": 8,
    "message": "📍 8 personas se unieron a Spinning",
    "timestamp": "2025-12-19T15:35:23.456Z",
    "icon": "📍",
    "ttl_minutes": 5,
    "metadata": {
      "class_name": "Spinning"
    }
  }
}
```

### Canal Redis PubSub

Internamente, el WebSocket se suscribe a:
```
gym:{gym_id}:feed:updates
```

### Manejo de Errores

| Código | Descripción |
|--------|-------------|
| `1000` | Cierre normal |
| `1001` | Cliente se fue |
| `1006` | Conexión anormal (sin handshake) |
| `1011` | Error del servidor |

---

## 7. GET /activity_feed/health

Health check del sistema de Activity Feed.

### Request

**Ejemplo:**
```bash
curl -X GET "https://api.gymapi.com/api/v1/activity_feed/health" \
  -H "Authorization: Bearer {token}"
```

### Response - Sistema Saludable

**Status:** `200 OK`

```json
{
  "status": "healthy",
  "redis": "connected",
  "memory_usage_mb": 45.32,
  "anonymous_mode": true,
  "privacy_compliant": true,
  "keys_count": {
    "feed": 127,
    "realtime": 34,
    "daily": 89,
    "total": 250
  },
  "configuration": {
    "min_aggregation_threshold": 3,
    "show_user_names": false,
    "ttl_enabled": true
  }
}
```

### Response - Sistema No Saludable

**Status:** `200 OK` (pero con status "unhealthy")

```json
{
  "status": "unhealthy",
  "error": "Connection refused",
  "redis": "disconnected"
}
```

### Métricas Monitoreadas

| Métrica | Descripción |
|---------|-------------|
| `redis` | Estado de conexión a Redis |
| `memory_usage_mb` | Uso de memoria de Redis |
| `keys_count` | Número de keys por tipo |
| `anonymous_mode` | Confirmación de modo anónimo (siempre true) |
| `privacy_compliant` | Cumplimiento de privacidad (siempre true) |

---

## 8. POST /activity_feed/test/generate-activity

**⚠️ Solo para desarrollo/testing**

Genera actividades de prueba para simular el feed.

### Request

**Query Parameters:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `activity_type` | string | Sí | Tipo de actividad a generar |
| `count` | int | Sí | Cantidad para la actividad (≥1) |

**Ejemplo:**
```bash
curl -X POST "https://api.gymapi.com/api/v1/activity_feed/test/generate-activity?activity_type=training_count&count=25" \
  -H "X-Gym-ID: 7" \
  -H "Authorization: Bearer {token}"
```

### Response - Actividad Publicada

**Status:** `200 OK`

```json
{
  "status": "success",
  "activity": {
    "id": "7_training_count_1734660500.789",
    "type": "realtime",
    "subtype": "training_count",
    "count": 25,
    "message": "💪 25 personas entrenando ahora mismo",
    "timestamp": "2025-12-19T15:41:40.789Z",
    "icon": "💪",
    "ttl_minutes": 5,
    "metadata": {
      "source": "test"
    }
  }
}
```

### Response - No Publicada (Por Debajo del Umbral)

**Status:** `200 OK`

```json
{
  "status": "not_published",
  "reason": "Count 2 below threshold"
}
```

---

## Modelos de Datos

### Activity

```typescript
interface Activity {
  id: string;                    // Formato: {gym_id}_{type}_{timestamp}
  type: "realtime" | "summary";  // Tipo de actividad
  subtype: string;               // Subtipo específico
  count: number;                 // Cantidad/número principal
  message: string;               // Mensaje legible
  timestamp: string;             // ISO 8601
  icon: string;                  // Emoji representativo
  ttl_minutes: number;           // Tiempo de vida en minutos
  metadata?: Record<string, any>; // Metadatos opcionales
}
```

### RealtimeStats

```typescript
interface RealtimeStats {
  active_now: number;
  by_area: Record<string, number>;
  popular_classes: PopularClass[];
  is_peak_hour: boolean;
  peak_hours: string[];
  hourly_trend: "increasing" | "decreasing" | "stable";
}

interface PopularClass {
  name: string;
  participants: number;
  capacity: number;
  percentage: number;
}
```

### Ranking

```typescript
interface Ranking {
  position: number;
  value: number;
  badge: string | null;  // 🥇 🥈 🥉 para top 3
}
```

### DailySummary

```typescript
interface DailySummary {
  date: string;
  stats: {
    attendance: number;
    achievements: number;
    personal_records: number;
    goals_completed: number;
    classes_completed: number;
    total_hours: number;
    active_streaks: number;
    average_class_size: number;
    engagement_score: number;
  };
  highlights: string[];
}
```

---

## Privacidad y Seguridad

### Principios de Privacidad

#### 1. **Agregación Obligatoria**
```typescript
// ❌ NUNCA se expone
{
  "user_id": 123,
  "user_name": "Juan Pérez",
  "activity": "check-in"
}

// ✅ SIEMPRE agregado
{
  "count": 15,
  "message": "15 personas se unieron a la clase"
}
```

#### 2. **Umbral Mínimo**
```python
MIN_AGGREGATION_THRESHOLD = 3

# Solo se publica si count >= 3
if count < MIN_AGGREGATION_THRESHOLD:
    return None  # No publicar
```

#### 3. **TTL Automático**
Todos los datos se autodestruyen:
- **Realtime**: 5 minutos
- **Daily**: 24 horas
- **Weekly**: 7 días

#### 4. **Sin Identificadores**
- ❌ No user_id
- ❌ No nombres
- ❌ No emails
- ❌ No fotos
- ✅ Solo números y estadísticas

### Cumplimiento de Regulaciones

| Regulación | Cumplimiento |
|------------|--------------|
| **GDPR** | ✅ Datos anónimos no son datos personales |
| **CCPA** | ✅ No se venden ni comparten datos personales |
| **HIPAA** | ✅ No se expone información de salud identificable |
| **Privacy by Design** | ✅ Anonimización desde el diseño |

### Configuración de Privacidad

```python
# app/services/activity_feed_service.py

class ActivityFeedService:
    # Umbrales mínimos
    MIN_AGGREGATION_THRESHOLD = 3

    # Configuración inmutable
    ANONYMOUS_MODE = True  # No se puede deshabilitar
    SHOW_USER_NAMES = False  # Hardcoded a False
    TTL_ENABLED = True  # Siempre habilitado
```

---

## Ejemplos de Uso

### 1. Mostrar Feed en Pantalla Principal

```javascript
async function loadActivityFeed() {
  try {
    const response = await fetch('/api/v1/activity_feed/?limit=20', {
      headers: {
        'X-Gym-ID': '7',
        'Authorization': `Bearer ${token}`
      }
    });

    const data = await response.json();

    data.activities.forEach(activity => {
      displayActivity(activity);
    });

  } catch (error) {
    console.error('Error cargando feed:', error);
  }
}

function displayActivity(activity) {
  const feedItem = document.createElement('div');
  feedItem.className = 'activity-item';
  feedItem.innerHTML = `
    <span class="icon">${activity.icon}</span>
    <span class="message">${activity.message}</span>
    <span class="time">${formatTime(activity.timestamp)}</span>
  `;
  document.getElementById('activity-feed').prepend(feedItem);
}
```

### 2. Implementar WebSocket para Updates en Tiempo Real

```javascript
class RealtimeFeed {
  constructor(gymId) {
    this.gymId = gymId;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    this.ws = new WebSocket(
      `wss://api.gymapi.com/api/v1/activity_feed/ws?gym_id=${this.gymId}`
    );

    this.ws.onopen = () => {
      console.log('✅ Conectado al feed en tiempo real');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'activity') {
        this.handleNewActivity(data.data);
      }
    };

    this.ws.onerror = (error) => {
      console.error('❌ Error en WebSocket:', error);
    };

    this.ws.onclose = () => {
      console.log('🔌 WebSocket cerrado');
      this.reconnect();
    };
  }

  handleNewActivity(activity) {
    // Mostrar notificación toast
    showToast(activity.message, activity.icon);

    // Actualizar feed
    prependToFeed(activity);

    // Animar entrada
    animateNewActivity(activity.id);
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

      console.log(`🔄 Reintentando conexión en ${delay}ms...`);
      setTimeout(() => this.connect(), delay);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Uso
const feed = new RealtimeFeed(7);
feed.connect();
```

### 3. Dashboard de Estadísticas en Tiempo Real

```javascript
async function updateRealtimeDashboard() {
  try {
    const [stats, insights] = await Promise.all([
      fetch('/api/v1/activity_feed/realtime', {
        headers: {
          'X-Gym-ID': '7',
          'Authorization': `Bearer ${token}`
        }
      }).then(r => r.json()),

      fetch('/api/v1/activity_feed/insights', {
        headers: {
          'X-Gym-ID': '7',
          'Authorization': `Bearer ${token}`
        }
      }).then(r => r.json())
    ]);

    // Actualizar contador principal
    document.getElementById('active-now').textContent = stats.data.active_now;

    // Actualizar distribución por área
    updateAreaChart(stats.data.by_area);

    // Mostrar clases populares
    displayPopularClasses(stats.data.popular_classes);

    // Mostrar insights
    displayInsights(insights.insights);

    // Indicador de hora pico
    togglePeakHourBadge(stats.data.is_peak_hour);

  } catch (error) {
    console.error('Error actualizando dashboard:', error);
  }
}

// Actualizar cada 30 segundos
setInterval(updateRealtimeDashboard, 30000);
```

### 4. Mostrar Rankings Anónimos

```javascript
async function displayWeeklyRankings() {
  const rankingTypes = ['consistency', 'attendance', 'improvement'];

  for (const type of rankingTypes) {
    try {
      const response = await fetch(
        `/api/v1/activity_feed/rankings/${type}?period=weekly&limit=10`,
        {
          headers: {
            'X-Gym-ID': '7',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      const data = await response.json();

      const container = document.getElementById(`ranking-${type}`);
      container.innerHTML = `
        <h3>${formatRankingTitle(type)}</h3>
        <p class="unit">${data.unit}</p>
        <ol class="ranking-list">
          ${data.rankings.map(rank => `
            <li class="rank-item">
              <span class="position">${rank.badge || `#${rank.position}`}</span>
              <span class="value">${rank.value}</span>
            </li>
          `).join('')}
        </ol>
      `;

    } catch (error) {
      console.error(`Error cargando ranking ${type}:`, error);
    }
  }
}
```

### 5. Resumen Diario con Highlights

```javascript
async function showDailySummary() {
  try {
    const response = await fetch('/api/v1/activity_feed/stats/summary', {
      headers: {
        'X-Gym-ID': '7',
        'Authorization': `Bearer ${token}`
      }
    });

    const data = await response.json();

    // Crear tarjetas de estadísticas
    const statsHTML = `
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">${data.stats.attendance}</div>
          <div class="stat-label">Asistencias</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${data.stats.achievements}</div>
          <div class="stat-label">Logros</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${data.stats.personal_records}</div>
          <div class="stat-label">Récords</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${data.stats.total_hours.toFixed(1)}h</div>
          <div class="stat-label">Horas Totales</div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-value">${data.stats.engagement_score}</div>
          <div class="stat-label">Engagement Score</div>
        </div>
      </div>

      <div class="highlights">
        <h3>🌟 Highlights del Día</h3>
        ${data.highlights.map(h => `<p class="highlight-item">${h}</p>`).join('')}
      </div>
    `;

    document.getElementById('daily-summary').innerHTML = statsHTML;

  } catch (error) {
    console.error('Error cargando resumen diario:', error);
  }
}
```

---

## Códigos de Error

| Código | Descripción | Solución |
|--------|-------------|----------|
| `400` | Parámetros inválidos | Verificar query params y tipos |
| `401` | No autenticado | Incluir token válido |
| `403` | Sin permisos | Verificar rol de usuario |
| `404` | Recurso no encontrado | Verificar URL y parámetros |
| `500` | Error del servidor | Revisar logs, verificar Redis |
| `503` | Servicio no disponible | Verificar conexión a Redis |

---

## Mejores Prácticas

### 1. **Polling vs WebSocket**

```javascript
// ❌ Evitar polling excesivo
setInterval(loadActivityFeed, 1000); // Demasiado frecuente

// ✅ Usar WebSocket para tiempo real
const feed = new RealtimeFeed(gymId);
feed.connect();

// ✅ O polling moderado si WebSocket no es posible
setInterval(loadActivityFeed, 30000); // Cada 30 segundos
```

### 2. **Manejo de Reconexión**

```javascript
// ✅ Implementar backoff exponencial
reconnect() {
  const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
  setTimeout(() => this.connect(), delay);
}
```

### 3. **Optimización de Renderizado**

```javascript
// ✅ Limitar items en DOM
const MAX_FEED_ITEMS = 50;

function addActivity(activity) {
  feedContainer.prepend(createActivityElement(activity));

  // Remover items antiguos
  while (feedContainer.children.length > MAX_FEED_ITEMS) {
    feedContainer.lastChild.remove();
  }
}
```

### 4. **Caché del Cliente**

```javascript
// ✅ Cachear datos estáticos
const cache = {
  stats: null,
  lastUpdate: null,
  TTL: 30000 // 30 segundos
};

async function getStats() {
  const now = Date.now();

  if (cache.stats && (now - cache.lastUpdate) < cache.TTL) {
    return cache.stats;
  }

  const stats = await fetchStats();
  cache.stats = stats;
  cache.lastUpdate = now;

  return stats;
}
```

---

## Preguntas Frecuentes

### ¿Por qué el feed es 100% anónimo?

Para **proteger la privacidad** de los usuarios mientras se mantiene la motivación comunitaria. Nadie quiere que todos sepan exactamente cuándo entrenan o qué logran.

### ¿Puedo desactivar el modo anónimo?

No. El modo anónimo está **hardcoded** y no se puede deshabilitar por razones de privacidad y cumplimiento legal (GDPR, CCPA).

### ¿Por qué hay un umbral mínimo de 3?

Para evitar la **reidentificación**. Si solo 1 o 2 personas entrenan, publicar "2 personas activas" podría revelar identidades.

### ¿Cuánto tiempo se guardan los datos?

Los datos tienen **TTL automático**:
- Tiempo real: 5 minutos
- Diarios: 24 horas
- Semanales: 7 días

Después se eliminan automáticamente de Redis.

### ¿Qué pasa si Redis falla?

El sistema tiene **fallback graceful**. Si Redis no está disponible, los endpoints devuelven datos vacíos sin romper la aplicación.

### ¿Cómo se calculan los rankings?

Los rankings se calculan en base a **métricas agregadas** sin vincular a usuarios específicos. Solo se muestran valores numéricos ordenados.

### ¿Puedo obtener mi posición en el ranking?

No. Esto rompería el anonimato al permitir **reidentificación indirecta**. El sistema solo muestra el top N sin identificadores.

---

## Changelog

### v1.0.0 (2025-12-19)
- ✅ Implementación inicial del Activity Feed
- ✅ 8 endpoints REST completos
- ✅ WebSocket para actualizaciones en tiempo real
- ✅ Sistema 100% anónimo con umbral de privacidad
- ✅ TTL automático para todos los datos
- ✅ Rankings anónimos con 5 tipos
- ✅ Insights motivacionales dinámicos
- ✅ Health check endpoint

---

## Soporte

Para reportar issues o sugerencias:
- **GitHub Issues**: https://github.com/Alexmontesino96/GymAPI/issues
- **Email**: soporte@gymapi.com
- **Documentación**: https://docs.gymapi.com

---

**Desarrollado con ❤️ por el equipo de GymAPI**
