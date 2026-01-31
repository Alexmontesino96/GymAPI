# 📊 Cómo Obtener el Historial de Clases del Usuario - Guía Frontend

## Endpoint Principal

### `GET /api/v1/schedule/participation/my-history`

Este endpoint permite obtener el historial completo de asistencia a clases del usuario autenticado.

## 🎯 Obtener Clases de la Última Semana

### Ejemplo de Request

```javascript
// Calcular fechas de la última semana
const endDate = new Date(); // Hoy
const startDate = new Date();
startDate.setDate(startDate.getDate() - 7); // Hace 7 días

// Formatear fechas en formato YYYY-MM-DD
const formatDate = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Hacer request al API
const response = await fetch(
  `${API_BASE_URL}/api/v1/schedule/participation/my-history?` +
  `start_date=${formatDate(startDate)}&` +
  `end_date=${formatDate(endDate)}`,
  {
    headers: {
      'Authorization': `Bearer ${authToken}`,
      'X-Gym-ID': gymId
    }
  }
);

const classHistory = await response.json();
```

### Ejemplo con Axios

```javascript
import axios from 'axios';
import { format, subDays } from 'date-fns';

// Configurar fechas
const endDate = new Date();
const startDate = subDays(endDate, 7);

// Hacer request
const getLastWeekClasses = async () => {
  try {
    const response = await axios.get(
      '/api/v1/schedule/participation/my-history',
      {
        params: {
          start_date: format(startDate, 'yyyy-MM-dd'),
          end_date: format(endDate, 'yyyy-MM-dd'),
          limit: 50 // Máximo de clases a retornar
        },
        headers: {
          'X-Gym-ID': gymId
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error fetching class history:', error);
    throw error;
  }
};
```

## 📋 Estructura de la Respuesta

```json
[
  {
    "participation": {
      "id": 123,
      "session_id": 456,
      "member_id": 789,
      "gym_id": 1,
      "status": "attended",  // Estados: "registered", "attended", "cancelled", "no_show"
      "registration_time": "2026-01-23T10:30:00Z",
      "attendance_time": "2026-01-23T18:00:00Z",
      "cancellation_time": null,
      "cancellation_reason": null
    },
    "session": {
      "id": 456,
      "class_id": 101,
      "trainer_id": 202,
      "gym_id": 1,
      "start_time": "2026-01-23T18:00:00Z",  // UTC
      "end_time": "2026-01-23T19:00:00Z",    // UTC
      "start_time_local": "2026-01-23T13:00:00",  // Hora local del gimnasio
      "end_time_local": "2026-01-23T14:00:00",    // Hora local del gimnasio
      "status": "completed",
      "room": "Studio A",
      "current_participants": 15,
      "override_capacity": null,
      "notes": null,
      "timezone": "America/Mexico_City",  // Timezone del gimnasio
      "time_info": {
        "local_time": "2026-01-23T13:00:00",
        "gym_timezone": "America/Mexico_City",
        "iso_with_timezone": "2026-01-23T13:00:00-05:00",
        "utc_time": "2026-01-23T18:00:00+00:00"
      }
    },
    "class": {
      "id": 101,
      "name": "Yoga Flow",
      "description": "Clase de yoga estilo Vinyasa",
      "duration": 60,
      "max_capacity": 20,
      "difficulty_level": "intermediate",
      "category_enum": "yoga",
      "category_id": null,
      "is_active": true,
      "gym_id": 1
    }
  }
  // ... más clases
]
```

## 🔧 Parámetros de Query

| Parámetro | Tipo | Requerido | Descripción | Ejemplo |
|-----------|------|-----------|-------------|---------|
| `start_date` | date | No | Fecha de inicio (inclusiva) | `2026-01-23` |
| `end_date` | date | No | Fecha de fin (inclusiva) | `2026-01-30` |
| `skip` | int | No | Registros a omitir (paginación) | `0` |
| `limit` | int | No | Máximo de registros (1-100) | `20` |

## 🔐 Headers Requeridos

```javascript
{
  'Authorization': 'Bearer {token}',  // Token JWT de Auth0
  'X-Gym-ID': '{gym_id}'              // ID del gimnasio
}
```

## 📊 Filtrar por Estado de Asistencia

```javascript
// Obtener solo clases a las que asistió
const attendedClasses = classHistory.filter(
  item => item.participation.status === 'attended'
);

// Obtener clases canceladas
const cancelledClasses = classHistory.filter(
  item => item.participation.status === 'cancelled'
);

// Obtener no shows
const noShowClasses = classHistory.filter(
  item => item.participation.status === 'no_show'
);
```

## 🎯 Casos de Uso Comunes

### 1. Mostrar Estadísticas de la Última Semana

```javascript
const getWeeklyStats = async () => {
  const history = await getLastWeekClasses();

  const stats = {
    totalRegistered: history.length,
    attended: history.filter(h => h.participation.status === 'attended').length,
    cancelled: history.filter(h => h.participation.status === 'cancelled').length,
    noShow: history.filter(h => h.participation.status === 'no_show').length
  };

  return stats;
};
```

### 2. Agrupar por Tipo de Clase

```javascript
const groupByClassType = (history) => {
  const grouped = {};

  history.forEach(item => {
    const category = item.class.category_enum || 'other';
    if (!grouped[category]) {
      grouped[category] = [];
    }
    grouped[category].push(item);
  });

  return grouped;
};
```

### 3. Calcular Tiempo Total de Entrenamiento

```javascript
const calculateTotalTrainingTime = (history) => {
  const attendedClasses = history.filter(
    h => h.participation.status === 'attended'
  );

  const totalMinutes = attendedClasses.reduce((total, item) => {
    return total + (item.class.duration || 0);
  }, 0);

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  return { hours, minutes, totalMinutes };
};
```

## 🚀 Componente React de Ejemplo

```jsx
import React, { useState, useEffect } from 'react';
import { format, subDays } from 'date-fns';
import { es } from 'date-fns/locale';

const UserClassHistory = ({ gymId }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchLastWeekHistory();
  }, [gymId]);

  const fetchLastWeekHistory = async () => {
    try {
      setLoading(true);
      const endDate = new Date();
      const startDate = subDays(endDate, 7);

      const response = await fetch(
        `/api/v1/schedule/participation/my-history?` +
        `start_date=${format(startDate, 'yyyy-MM-dd')}&` +
        `end_date=${format(endDate, 'yyyy-MM-dd')}`,
        {
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
            'X-Gym-ID': gymId
          }
        }
      );

      if (!response.ok) throw new Error('Failed to fetch history');

      const data = await response.json();
      setHistory(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      'attended': '✅ Asistió',
      'registered': '📝 Registrado',
      'cancelled': '❌ Cancelado',
      'no_show': '⚠️ No asistió'
    };
    return badges[status] || status;
  };

  if (loading) return <div>Cargando historial...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="class-history">
      <h2>Mis Clases - Última Semana</h2>

      {history.length === 0 ? (
        <p>No has asistido a clases esta semana</p>
      ) : (
        <div className="class-list">
          {history.map(item => (
            <div key={item.participation.id} className="class-card">
              <h3>{item.class.name}</h3>
              <p>
                {format(
                  new Date(item.session.start_time_local),
                  "EEEE d 'de' MMMM, HH:mm",
                  { locale: es }
                )}
              </p>
              <p>Duración: {item.class.duration} min</p>
              <p>Sala: {item.session.room}</p>
              <span className="status-badge">
                {getStatusBadge(item.participation.status)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="stats">
        <h3>Resumen</h3>
        <p>Total clases: {history.length}</p>
        <p>
          Asistidas: {history.filter(h => h.participation.status === 'attended').length}
        </p>
        <p>
          Tiempo total: {
            history
              .filter(h => h.participation.status === 'attended')
              .reduce((sum, h) => sum + h.class.duration, 0)
          } minutos
        </p>
      </div>
    </div>
  );
};

export default UserClassHistory;
```

## 📱 Endpoint Alternativo para Móvil

### `GET /api/v1/schedule/participation/my-classes-simple`

Este endpoint devuelve solo las clases **futuras** registradas (no el historial pasado).
Para historial, usar siempre `/my-history`.

## ⚠️ Notas Importantes

1. **Timezone**: Los parámetros `start_date` y `end_date` se interpretan en la zona horaria del gimnasio
2. **Límites**: Máximo 100 registros por request
3. **Caché**: Los datos están cacheados para optimizar performance
4. **Permisos**: Requiere scope `resource:read`
5. **Filtrado**: Solo devuelve clases del gimnasio actual (`X-Gym-ID` header)

## 🔍 Otros Endpoints Relacionados

- `GET /api/v1/schedule/participation/my-classes` - Clases futuras registradas
- `GET /api/v1/schedule/participation/my-participation-status` - Estado de participación en un rango
- `GET /api/v1/schedule/sessions` - Todas las sesiones disponibles
- `POST /api/v1/schedule/participation/register/{session_id}` - Registrarse a una clase

## 📞 Manejo de Errores

```javascript
try {
  const history = await getLastWeekClasses();
  // Procesar datos...
} catch (error) {
  if (error.response) {
    switch (error.response.status) {
      case 401:
        // Token inválido o expirado
        redirectToLogin();
        break;
      case 403:
        // Sin permisos
        showError('No tienes permisos para ver este contenido');
        break;
      case 404:
        // Usuario no encontrado
        showError('Usuario no encontrado');
        break;
      case 422:
        // Error de validación
        showError('Formato de fecha inválido');
        break;
      default:
        showError('Error al cargar el historial');
    }
  }
}
```