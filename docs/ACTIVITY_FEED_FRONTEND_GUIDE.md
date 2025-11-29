# Activity Feed - Guía de Integración Frontend

## Resumen de Cambios Recientes

### Nuevas Features
- Rankings ahora incluyen `user_id` para mostrar fotos de perfil
- Nombres parciales por privacidad (ej: "Juan P." en lugar de "Juan Pérez")
- Feed con TTL de 24 horas (antes era 1 hora)
- WebSocket para actualizaciones en tiempo real
- Jobs automáticos que actualizan el feed cada 5 minutos

---

## Endpoints Principales

### Base URL
```
/api/v1/activity-feed
```

### Headers Requeridos
```javascript
{
  "Authorization": "Bearer <jwt_token>",
  "Content-Type": "application/json"
}
```

---

## 1. Feed Principal

### GET `/api/v1/activity-feed/`

Obtiene la lista de actividades recientes del gimnasio.

```typescript
// Request
const response = await fetch('/api/v1/activity-feed/?limit=20&offset=0', {
  headers: { Authorization: `Bearer ${token}` }
});

// Response
interface ActivityFeedResponse {
  activities: Activity[];
  count: number;
  has_more: boolean;
  offset: number;
  limit: number;
}

interface Activity {
  id?: string;
  type: string;           // "realtime", "class_completed", "motivational", etc.
  subtype?: string;       // "training_count", "class_checkin", etc.
  count?: number;
  message: string;        // Mensaje para mostrar al usuario
  timestamp: string;      // ISO 8601
  icon: string;           // Emoji: 💪, ⭐, 🔥, etc.
  time_ago?: string;      // "hace 5 minutos"
  ttl_minutes?: number;
}
```

### Ejemplo de UI

```tsx
// React Native
const ActivityCard = ({ activity }: { activity: Activity }) => (
  <View style={styles.card}>
    <Text style={styles.icon}>{activity.icon}</Text>
    <View style={styles.content}>
      <Text style={styles.message}>{activity.message}</Text>
      <Text style={styles.time}>{activity.time_ago}</Text>
    </View>
  </View>
);

// Ejemplo de datos que recibirás:
// {
//   "icon": "💪",
//   "message": "25 personas entrenando ahora",
//   "time_ago": "hace 5 minutos"
// }
```

---

## 2. Rankings con Fotos de Perfil

### GET `/api/v1/activity-feed/rankings/{type}?period={period}&limit={limit}`

**Tipos disponibles:** `attendance`, `consistency`, `improvement`, `activity`, `dedication`

**Períodos:** `daily`, `weekly`, `monthly`

```typescript
// Request
const response = await fetch(
  '/api/v1/activity-feed/rankings/attendance?period=daily&limit=10',
  { headers: { Authorization: `Bearer ${token}` } }
);

// Response
interface RankingsResponse {
  type: string;
  period: string;
  rankings: RankingEntry[];
  unit: string;           // "clases", "días consecutivos", etc.
  count: number;
}

interface RankingEntry {
  position: number;       // 1, 2, 3...
  value: number;          // Valor del ranking (clases, días, etc.)
  user_id: number | null; // ID del usuario para obtener foto
  name: string | null;    // "Juan P.", "María G."
  label: string;          // Mismo que name o "Posición X" si es anónimo
}
```

### Obtener Foto de Perfil

Con el `user_id` puedes obtener la foto del usuario:

```typescript
// Construir URL de foto de perfil
const getProfilePhotoUrl = (userId: number) => {
  return `/api/v1/users/${userId}/profile-photo`;
};

// O si usas un CDN/Storage
const getProfilePhotoUrl = (userId: number) => {
  return `https://storage.example.com/profiles/${userId}.jpg`;
};
```

### Ejemplo de UI - Ranking con Fotos

```tsx
// React Native
import { Image } from 'react-native';

const RankingItem = ({ entry, index }: { entry: RankingEntry; index: number }) => {
  const getMedalColor = (position: number) => {
    switch (position) {
      case 1: return '#FFD700'; // Oro
      case 2: return '#C0C0C0'; // Plata
      case 3: return '#CD7F32'; // Bronce
      default: return '#666';
    }
  };

  return (
    <View style={styles.rankingItem}>
      {/* Posición */}
      <View style={[styles.position, { backgroundColor: getMedalColor(entry.position) }]}>
        <Text style={styles.positionText}>{entry.position}</Text>
      </View>

      {/* Foto de perfil */}
      {entry.user_id ? (
        <Image
          source={{ uri: getProfilePhotoUrl(entry.user_id) }}
          style={styles.avatar}
          defaultSource={require('./default-avatar.png')}
        />
      ) : (
        <View style={styles.avatarPlaceholder}>
          <Text>👤</Text>
        </View>
      )}

      {/* Nombre y valor */}
      <View style={styles.info}>
        <Text style={styles.name}>{entry.name || entry.label}</Text>
        <Text style={styles.value}>{entry.value} clases</Text>
      </View>
    </View>
  );
};

const RankingsList = ({ rankings, unit }: { rankings: RankingEntry[]; unit: string }) => (
  <FlatList
    data={rankings}
    keyExtractor={(item) => `rank-${item.position}`}
    renderItem={({ item, index }) => <RankingItem entry={item} index={index} />}
    ListHeaderComponent={
      <Text style={styles.header}>🏆 Top del Día</Text>
    }
  />
);
```

### Estilos sugeridos

```typescript
const styles = StyleSheet.create({
  rankingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#fff',
    borderRadius: 12,
    marginVertical: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  position: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  positionText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 14,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    marginLeft: 12,
  },
  avatarPlaceholder: {
    width: 48,
    height: 48,
    borderRadius: 24,
    marginLeft: 12,
    backgroundColor: '#E0E0E0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  info: {
    flex: 1,
    marginLeft: 12,
  },
  name: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  value: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
});
```

---

## 3. Estadísticas en Tiempo Real

### GET `/api/v1/activity-feed/realtime`

```typescript
// Response
interface RealtimeResponse {
  status: string;
  data: {
    total_training: number;      // Personas entrenando ahora
    by_area: Record<string, number>; // Por clase/área
    popular_classes: PopularClass[];
    peak_time: boolean;          // true si es hora pico (>20 personas)
    last_update: string;
  };
}

interface PopularClass {
  name: string;
  count: number;
}
```

### Ejemplo de UI - Dashboard

```tsx
const RealtimeDashboard = () => {
  const [data, setData] = useState<RealtimeData | null>(null);

  useEffect(() => {
    fetchRealtimeStats();
    // Actualizar cada 30 segundos
    const interval = setInterval(fetchRealtimeStats, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <View style={styles.dashboard}>
      {/* Contador principal */}
      <View style={styles.mainCounter}>
        <Text style={styles.counterNumber}>{data?.total_training || 0}</Text>
        <Text style={styles.counterLabel}>entrenando ahora</Text>
        {data?.peak_time && (
          <View style={styles.peakBadge}>
            <Text style={styles.peakText}>🔥 Hora Pico</Text>
          </View>
        )}
      </View>

      {/* Clases populares */}
      <View style={styles.popularClasses}>
        <Text style={styles.sectionTitle}>Clases Populares</Text>
        {data?.popular_classes.map((cls) => (
          <View key={cls.name} style={styles.classItem}>
            <Text>{cls.name}</Text>
            <Text style={styles.classCount}>{cls.count} personas</Text>
          </View>
        ))}
      </View>
    </View>
  );
};
```

---

## 4. Insights Motivacionales

### GET `/api/v1/activity-feed/insights`

```typescript
// Response
interface InsightsResponse {
  insights: Insight[];
  count: number;
}

interface Insight {
  message: string;    // "🔥 ¡45 guerreros activos ahora mismo!"
  type: string;       // "realtime", "achievement", "record", "consistency"
  priority: number;   // 1 = más importante, 3 = menos
}
```

### Ejemplo de UI - Carrusel de Insights

```tsx
const InsightsCarousel = ({ insights }: { insights: Insight[] }) => {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    // Rotar cada 5 segundos
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % insights.length);
    }, 5000);
    return () => clearInterval(interval);
  }, [insights.length]);

  if (insights.length === 0) return null;

  return (
    <View style={styles.insightContainer}>
      <Text style={styles.insightText}>
        {insights[currentIndex].message}
      </Text>
      <View style={styles.dots}>
        {insights.map((_, i) => (
          <View
            key={i}
            style={[
              styles.dot,
              i === currentIndex && styles.dotActive
            ]}
          />
        ))}
      </View>
    </View>
  );
};
```

---

## 5. WebSocket - Tiempo Real

### Conexión

```typescript
// URL del WebSocket
const wsUrl = `wss://api.example.com/api/v1/activity-feed/ws?gym_id=${gymId}`;
```

### Implementación con Reconexión

```typescript
class ActivityFeedWebSocket {
  private ws: WebSocket | null = null;
  private gymId: number;
  private onActivity: (activity: Activity) => void;
  private onConnectionChange: (connected: boolean) => void;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(
    gymId: number,
    onActivity: (activity: Activity) => void,
    onConnectionChange: (connected: boolean) => void
  ) {
    this.gymId = gymId;
    this.onActivity = onActivity;
    this.onConnectionChange = onConnectionChange;
    this.connect();
  }

  private connect() {
    const wsUrl = `wss://api.example.com/api/v1/activity-feed/ws?gym_id=${this.gymId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('Activity Feed WebSocket connected');
      this.reconnectAttempts = 0;
      this.onConnectionChange(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'connection') {
          console.log('Welcome message:', data.message);
        } else if (data.type === 'activity') {
          this.onActivity(data.data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onclose = () => {
      console.log('Activity Feed WebSocket disconnected');
      this.onConnectionChange(false);
      this.attemptReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connect(), delay);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

### Hook de React

```tsx
import { useEffect, useState, useCallback, useRef } from 'react';

const useActivityFeedWebSocket = (gymId: number) => {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<ActivityFeedWebSocket | null>(null);

  const handleNewActivity = useCallback((activity: Activity) => {
    setActivities((prev) => [activity, ...prev].slice(0, 50)); // Mantener últimas 50
  }, []);

  useEffect(() => {
    wsRef.current = new ActivityFeedWebSocket(
      gymId,
      handleNewActivity,
      setIsConnected
    );

    return () => {
      wsRef.current?.disconnect();
    };
  }, [gymId, handleNewActivity]);

  return { activities, isConnected };
};

// Uso
const ActivityFeedScreen = () => {
  const { activities, isConnected } = useActivityFeedWebSocket(1);

  return (
    <View>
      <View style={styles.connectionStatus}>
        <View style={[
          styles.statusDot,
          { backgroundColor: isConnected ? '#4CAF50' : '#F44336' }
        ]} />
        <Text>{isConnected ? 'En vivo' : 'Reconectando...'}</Text>
      </View>

      <FlatList
        data={activities}
        keyExtractor={(item) => item.id || item.timestamp}
        renderItem={({ item }) => <ActivityCard activity={item} />}
      />
    </View>
  );
};
```

---

## 6. Resumen del Día

### GET `/api/v1/activity-feed/stats/summary`

```typescript
// Response
interface DailySummaryResponse {
  date: string;
  stats: {
    attendance: number;         // Total de asistencias
    achievements: number;       // Logros desbloqueados
    personal_records: number;   // Récords personales
    goals_completed: number;    // Metas cumplidas
    classes_completed: number;  // Clases completadas
    total_hours: number;        // Horas totales entrenadas
    active_streaks: number;     // Rachas activas
    average_class_size: number; // Promedio personas por clase
    engagement_score: number;   // Score de engagement (0-100)
  };
  highlights: string[];         // ["🔥 Día increíble con 156 asistencias", ...]
}
```

### Ejemplo de UI - Resumen

```tsx
const DailySummary = ({ stats, highlights }: DailySummaryResponse) => (
  <View style={styles.summary}>
    {/* Grid de estadísticas */}
    <View style={styles.statsGrid}>
      <StatCard
        icon="👥"
        value={stats.attendance}
        label="Asistencias"
      />
      <StatCard
        icon="⭐"
        value={stats.achievements}
        label="Logros"
      />
      <StatCard
        icon="🏆"
        value={stats.personal_records}
        label="Récords"
      />
      <StatCard
        icon="🔥"
        value={stats.active_streaks}
        label="Rachas"
      />
    </View>

    {/* Highlights */}
    {highlights.length > 0 && (
      <View style={styles.highlights}>
        {highlights.map((text, i) => (
          <Text key={i} style={styles.highlightText}>{text}</Text>
        ))}
      </View>
    )}

    {/* Engagement Score */}
    <View style={styles.engagementContainer}>
      <Text style={styles.engagementLabel}>Engagement del Gimnasio</Text>
      <View style={styles.progressBar}>
        <View
          style={[
            styles.progressFill,
            { width: `${stats.engagement_score}%` }
          ]}
        />
      </View>
      <Text style={styles.engagementValue}>{stats.engagement_score}%</Text>
    </View>
  </View>
);

const StatCard = ({ icon, value, label }: { icon: string; value: number; label: string }) => (
  <View style={styles.statCard}>
    <Text style={styles.statIcon}>{icon}</Text>
    <Text style={styles.statValue}>{value}</Text>
    <Text style={styles.statLabel}>{label}</Text>
  </View>
);
```

---

## 7. Iconos por Tipo de Actividad

```typescript
const ACTIVITY_ICONS: Record<string, string> = {
  training_count: '💪',
  class_checkin: '📍',
  achievement_unlocked: '⭐',
  streak_milestone: '🔥',
  pr_broken: '🏆',
  goal_completed: '🎯',
  social_activity: '👥',
  class_popular: '📈',
  hourly_summary: '📊',
  motivational: '💫',
  class_completed: '✅',
};

// Helper para obtener icono
const getActivityIcon = (type: string, subtype?: string): string => {
  return ACTIVITY_ICONS[subtype || type] || '📊';
};
```

---

## 8. Manejo de Errores

```typescript
const handleApiError = (error: any) => {
  if (error.status === 401) {
    // Token expirado - redirigir a login
    navigation.navigate('Login');
  } else if (error.status === 500) {
    // Error del servidor
    showToast('Error al cargar datos. Intenta de nuevo.');
  }
};

// Wrapper para fetch con manejo de errores
const fetchActivityFeed = async (token: string) => {
  try {
    const response = await fetch('/api/v1/activity-feed/', {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      throw { status: response.status };
    }

    return await response.json();
  } catch (error) {
    handleApiError(error);
    return null;
  }
};
```

---

## 9. Flujo de Pantalla Completo

```tsx
import React, { useEffect, useState } from 'react';
import { View, FlatList, RefreshControl, ActivityIndicator } from 'react-native';

const ActivityFeedScreen = () => {
  const [feed, setFeed] = useState<Activity[]>([]);
  const [rankings, setRankings] = useState<RankingEntry[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const { activities: liveActivities, isConnected } = useActivityFeedWebSocket(gymId);

  // Cargar datos iniciales
  useEffect(() => {
    loadAllData();
  }, []);

  // Combinar actividades históricas con las en vivo
  const allActivities = [...liveActivities, ...feed];

  const loadAllData = async () => {
    setLoading(true);
    await Promise.all([
      loadFeed(),
      loadRankings(),
      loadInsights()
    ]);
    setLoading(false);
  };

  const loadFeed = async () => {
    const data = await fetchActivityFeed(token);
    if (data) setFeed(data.activities);
  };

  const loadRankings = async () => {
    const data = await fetchRankings(token, 'attendance', 'daily');
    if (data) setRankings(data.rankings);
  };

  const loadInsights = async () => {
    const data = await fetchInsights(token);
    if (data) setInsights(data.insights);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadAllData();
    setRefreshing(false);
  };

  if (loading) {
    return <ActivityIndicator size="large" />;
  }

  return (
    <FlatList
      data={allActivities}
      keyExtractor={(item) => item.id || item.timestamp}
      renderItem={({ item }) => <ActivityCard activity={item} />}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      ListHeaderComponent={
        <>
          {/* Estado de conexión */}
          <ConnectionStatus connected={isConnected} />

          {/* Carrusel de insights */}
          <InsightsCarousel insights={insights} />

          {/* Top 3 del día */}
          <View style={styles.rankingsPreview}>
            <Text style={styles.sectionTitle}>🏆 Top del Día</Text>
            {rankings.slice(0, 3).map((entry) => (
              <RankingItem key={entry.position} entry={entry} />
            ))}
          </View>

          <Text style={styles.sectionTitle}>Actividad Reciente</Text>
        </>
      }
    />
  );
};
```

---

## Notas Importantes

1. **Umbral de privacidad:** Las actividades con menos de 3 personas no se muestran
2. **TTL del feed:** 24 horas - las actividades antiguas desaparecen automáticamente
3. **Rankings se actualizan:** Automáticamente a las 23:50 cada día
4. **WebSocket:** Reconectar si se pierde la conexión (exponential backoff)
5. **user_id en rankings:** Puede ser `null` si el ranking es anónimo
6. **Nombres parciales:** Por privacidad se muestra "Juan P." no "Juan Pérez"
