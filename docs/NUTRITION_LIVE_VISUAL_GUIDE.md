# 🎨 Guía Visual: Planes Nutricionales LIVE

## 📊 Diagrama de Flujo: Ciclo de Vida de un Plan LIVE

```
┌─────────────────────────────────────────────────────────────────┐
│                    CREACIÓN DEL PLAN LIVE                        │
│                  (Trainer/Admin crea el plan)                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CONFIGURACIÓN INICIAL                         │
│        • Establecer live_start_date                             │
│        • Definir duration_days (ej: 21 días)                    │
│        • Crear meals para cada día                              │
│        • Marcar is_live_active = true                           │
└─────────────────────────────────────────────────────────────────┘
                                ↓
        ┌───────────────────────┴───────────────────────┐
        ↓                                               ↓
┌──────────────────┐                        ┌──────────────────┐
│  PERIODO DE      │                        │   PLAN ACTIVO    │
│  INSCRIPCIÓN     │                        │   (Día 4+)       │
│  (Días 1-3)      │                        │                  │
├──────────────────┤                        ├──────────────────┤
│ ✅ Usuarios pueden│                        │ ❌ No más        │
│    unirse        │                        │    inscripciones │
│ ✅ Notificaciones│                        │ ✅ Sincronización│
│    de invitación │                        │    diaria        │
└──────────────────┘                        └──────────────────┘
        ↓                                               ↓
        └───────────────────────┬───────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                        DÍA A DÍA                                 │
│   • Medianoche: Avance automático al siguiente día              │
│   • 8 AM, 1 PM, 7 PM: Notificaciones de comidas                │
│   • Usuarios completan meals                                    │
│   • Actualización de estadísticas grupales                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    (Después de duration_days)
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                      FINALIZACIÓN                                │
│        • Plan pasa a ARCHIVED                                   │
│        • Certificados de completación                           │
│        • Estadísticas finales                                   │
│        • is_live_active = false                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 🗓️ Timeline Visual de un Plan LIVE de 7 Días

```
Dic 20    Dic 21    Dic 22    Dic 23    Dic 24    Dic 25    Dic 26
Día 1     Día 2     Día 3     Día 4     Día 5     Día 6     Día 7
START     →         →         CIERRE    →         →         END
  ↓         ↓         ↓       INSCR.      ↓         ↓         ↓
[====== INSCRIPCIONES OK ======][===== SOLO PARTICIPANTES =====]
  ↓         ↓         ↓         ↓         ↓         ↓         ↓
👥 10     👥 25     👥 40     👥 40     👥 40     👥 40     👥 40
users     users     users    (fijo)    (fijo)    (fijo)   (final)
```

## 🔄 Sincronización Automática de Días

### Backend (Python)
```python
# app/services/nutrition_live_service.py
from datetime import datetime, timezone
from typing import Optional

class NutritionLiveService:
    @staticmethod
    def get_current_day_number(plan: NutritionPlan) -> int:
        """
        Calcula el día actual basado en live_start_date.
        Todos los usuarios ven el mismo día.
        """
        if not plan.live_start_date:
            return 1

        now = datetime.now(timezone.utc)
        start = plan.live_start_date.replace(tzinfo=timezone.utc)

        # Calcular días transcurridos
        days_elapsed = (now - start).days

        # El día actual es días transcurridos + 1
        current_day = min(days_elapsed + 1, plan.duration_days)

        return max(1, current_day)  # Nunca menos de día 1

    @staticmethod
    def can_user_join(plan: NutritionPlan) -> bool:
        """
        Los usuarios solo pueden unirse en los primeros 3 días.
        """
        current_day = NutritionLiveService.get_current_day_number(plan)
        return current_day <= 3 and plan.is_live_active

    @staticmethod
    def get_meals_for_today(plan: NutritionPlan) -> list:
        """
        Retorna las comidas del día actual para todos los participantes.
        """
        current_day = NutritionLiveService.get_current_day_number(plan)

        # Buscar el daily_plan correspondiente
        for daily_plan in plan.daily_plans:
            if daily_plan.day_number == current_day:
                return daily_plan.meals

        return []
```

### Frontend (React + TypeScript)
```tsx
// services/LivePlanSyncService.ts
export class LivePlanSyncService {
  /**
   * Calcula el día actual del plan LIVE
   */
  static getCurrentDay(liveStartDate: string, durationDays: number): number {
    const start = new Date(liveStartDate);
    const now = new Date();

    // Calcular diferencia en días
    const diffTime = Math.abs(now.getTime() - start.getTime());
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    // Día actual (1-indexed)
    const currentDay = Math.min(diffDays + 1, durationDays);
    return Math.max(1, currentDay);
  }

  /**
   * Determina si el plan acepta nuevos participantes
   */
  static canJoinPlan(liveStartDate: string): boolean {
    const currentDay = this.getCurrentDay(liveStartDate, 999);
    return currentDay <= 3;
  }

  /**
   * Calcula tiempo hasta el próximo día
   */
  static getTimeUntilNextDay(): { hours: number; minutes: number } {
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(0, 0, 0, 0);

    const diff = tomorrow.getTime() - now.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    return { hours, minutes };
  }
}
```

## 📱 Componentes UI Específicos para LIVE

### 1. Indicador de Sincronización
```tsx
// components/LiveSyncIndicator.tsx
export function LiveSyncIndicator({ participantCount, currentDay, totalDays }) {
  const [pulse, setPulse] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => setPulse(p => !p), 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="live-sync-indicator">
      <div className={`live-dot ${pulse ? 'pulse' : ''}`}>
        <span className="dot"></span>
      </div>
      <div className="sync-info">
        <h4>🔴 PLAN EN VIVO</h4>
        <p>Día {currentDay} de {totalDays}</p>
        <p>{participantCount} participantes sincronizados</p>
      </div>
    </div>
  );
}
```

```css
/* styles/LiveSync.css */
.live-sync-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
  border-radius: 12px;
  color: white;
}

.live-dot {
  position: relative;
  width: 24px;
  height: 24px;
}

.live-dot .dot {
  position: absolute;
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.live-dot.pulse::before {
  content: '';
  position: absolute;
  width: 24px;
  height: 24px;
  background: rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}
```

### 2. Countdown hasta el Próximo Día
```tsx
// components/NextDayCountdown.tsx
export function NextDayCountdown() {
  const [timeLeft, setTimeLeft] = useState({ hours: 0, minutes: 0, seconds: 0 });

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      const tomorrow = new Date(now);
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(0, 0, 0, 0);

      const diff = tomorrow.getTime() - now.getTime();

      setTimeLeft({
        hours: Math.floor(diff / (1000 * 60 * 60)),
        minutes: Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)),
        seconds: Math.floor((diff % (1000 * 60)) / 1000)
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="countdown-container">
      <h4>⏰ Próximo día en:</h4>
      <div className="countdown-display">
        <div className="time-unit">
          <span className="time-value">{timeLeft.hours.toString().padStart(2, '0')}</span>
          <span className="time-label">HRS</span>
        </div>
        <span className="separator">:</span>
        <div className="time-unit">
          <span className="time-value">{timeLeft.minutes.toString().padStart(2, '0')}</span>
          <span className="time-label">MIN</span>
        </div>
        <span className="separator">:</span>
        <div className="time-unit">
          <span className="time-value">{timeLeft.seconds.toString().padStart(2, '0')}</span>
          <span className="time-label">SEG</span>
        </div>
      </div>
    </div>
  );
}
```

### 3. Progreso Grupal en Tiempo Real
```tsx
// components/GroupProgress.tsx
export function GroupProgress({ planId }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Actualizar cada minuto
    const fetchStats = async () => {
      const response = await fetch(`/api/v1/nutrition/plans/${planId}/group-stats`);
      const data = await response.json();
      setStats(data);
    };

    fetchStats();
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, [planId]);

  if (!stats) return null;

  return (
    <div className="group-progress">
      <h3>📊 Progreso del Grupo Hoy</h3>

      <div className="progress-grid">
        <div className="stat-card">
          <div className="stat-icon">🍳</div>
          <div className="stat-value">{stats.breakfast_completed}%</div>
          <div className="stat-label">Desayunaron</div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🥗</div>
          <div className="stat-value">{stats.lunch_completed}%</div>
          <div className="stat-label">Almorzaron</div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🍽️</div>
          <div className="stat-value">{stats.dinner_completed}%</div>
          <div className="stat-label">Cenaron</div>
        </div>
      </div>

      <div className="leaderboard">
        <h4>🏆 Top Participantes</h4>
        {stats.top_performers.map((user, idx) => (
          <div key={user.id} className="leaderboard-item">
            <span className="rank">{idx + 1}</span>
            <span className="name">{user.name}</span>
            <span className="completion">{user.completion_rate}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## 🔔 Sistema de Notificaciones LIVE

### Configuración de OneSignal
```tsx
// services/LiveNotifications.ts
export class LiveNotificationService {
  static setupLiveNotifications(userId: number, planId: number) {
    // Suscribir a tags específicos del plan LIVE
    OneSignal.sendTags({
      live_plan_id: planId.toString(),
      user_type: 'live_participant',
      notification_time: 'default' // 8am, 1pm, 7pm
    });

    // Handlers para diferentes tipos de notificaciones
    OneSignal.addEventListener('received', (notification) => {
      const { type, data } = notification.payload.additionalData;

      switch(type) {
        case 'live_new_day':
          this.handleNewDay(data);
          break;
        case 'live_meal_reminder':
          this.handleMealReminder(data);
          break;
        case 'live_group_achievement':
          this.handleGroupAchievement(data);
          break;
      }
    });
  }

  static handleNewDay(data: any) {
    // Mostrar toast/modal
    toast.info(`🌅 ¡Día ${data.day_number} disponible!`, {
      action: {
        label: 'Ver Plan',
        onClick: () => window.location.href = `/nutrition/live/${data.plan_id}`
      }
    });
  }

  static handleMealReminder(data: any) {
    // Notificación con acción directa
    toast.warning(`🍽️ Hora de ${data.meal_type_display}`, {
      duration: 10000,
      action: {
        label: 'Marcar Completado',
        onClick: () => this.completeMeal(data.meal_id)
      }
    });
  }

  static handleGroupAchievement(data: any) {
    // Celebración grupal
    confetti();
    toast.success(`🎉 ${data.message}`);
  }
}
```

## 📊 Métricas y Analytics para LIVE

### Dashboard de Administrador
```tsx
// components/admin/LivePlanDashboard.tsx
export function LivePlanDashboard({ planId }) {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    fetchMetrics();
  }, [planId]);

  const fetchMetrics = async () => {
    const response = await fetch(`/api/v1/admin/nutrition/plans/${planId}/metrics`);
    const data = await response.json();
    setMetrics(data);
  };

  if (!metrics) return <Loading />;

  return (
    <div className="admin-dashboard">
      <h2>Dashboard del Plan LIVE</h2>

      {/* KPIs principales */}
      <div className="kpi-grid">
        <KPICard
          title="Participantes Activos"
          value={metrics.active_participants}
          total={metrics.total_participants}
          icon="👥"
        />
        <KPICard
          title="Tasa de Completación"
          value={`${metrics.completion_rate}%`}
          trend={metrics.completion_trend}
          icon="✅"
        />
        <KPICard
          title="Engagement Diario"
          value={`${metrics.daily_engagement}%`}
          subtitle="Usuarios que completaron al menos 1 comida"
          icon="📊"
        />
      </div>

      {/* Gráfica de progreso diario */}
      <div className="chart-container">
        <h3>Progreso por Día</h3>
        <LineChart
          data={metrics.daily_progress}
          xAxis="day"
          yAxis="completion_percentage"
          color="#4CAF50"
        />
      </div>

      {/* Tabla de participantes */}
      <div className="participants-table">
        <h3>Detalle de Participantes</h3>
        <table>
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Días Completados</th>
              <th>% Comidas</th>
              <th>Última Actividad</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {metrics.participants.map(p => (
              <tr key={p.user_id}>
                <td>{p.name}</td>
                <td>{p.days_completed}/{metrics.total_days}</td>
                <td>{p.meals_completion}%</td>
                <td>{formatDate(p.last_activity)}</td>
                <td>
                  <StatusBadge status={p.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

## 🎯 Casos de Uso Específicos

### Caso 1: Usuario se une a plan LIVE
```tsx
async function handleJoinLivePlan(planId: number) {
  try {
    // 1. Verificar elegibilidad
    const planInfo = await api.get(`/plans/${planId}`);
    if (!LivePlanSyncService.canJoinPlan(planInfo.live_start_date)) {
      throw new Error('Este plan ya no acepta nuevos participantes');
    }

    // 2. Unirse al plan
    await api.post(`/plans/${planId}/follow`);

    // 3. Configurar notificaciones
    LiveNotificationService.setupLiveNotifications(userId, planId);

    // 4. Redirigir al plan
    navigate(`/nutrition/live/${planId}`);

  } catch (error) {
    toast.error(error.message);
  }
}
```

### Caso 2: Cambio de día automático
```tsx
// Hook para detectar cambio de día
function useAutoRefreshOnNewDay(planId: number) {
  useEffect(() => {
    const checkForNewDay = () => {
      const now = new Date();

      // Si son las 00:00-00:05
      if (now.getHours() === 0 && now.getMinutes() < 5) {
        // Refrescar datos del plan
        window.location.reload();
      }
    };

    // Revisar cada minuto
    const interval = setInterval(checkForNewDay, 60000);
    return () => clearInterval(interval);
  }, [planId]);
}
```

### Caso 3: Mostrar días bloqueados
```tsx
function DaySelector({ plan, currentDay }) {
  return (
    <div className="day-selector">
      {Array.from({ length: plan.duration_days }, (_, i) => i + 1).map(day => (
        <button
          key={day}
          className={`day-button ${
            day === currentDay ? 'current' :
            day < currentDay ? 'past' :
            'future'
          }`}
          disabled={plan.plan_type === 'LIVE' && day !== currentDay}
          onClick={() => {
            if (plan.plan_type === 'TEMPLATE') {
              navigateToDay(day);
            }
          }}
        >
          <span className="day-number">Día {day}</span>
          {day === currentDay && plan.plan_type === 'LIVE' && (
            <span className="live-badge">HOY</span>
          )}
          {day > currentDay && plan.plan_type === 'LIVE' && (
            <span className="lock-icon">🔒</span>
          )}
        </button>
      ))}
    </div>
  );
}
```

---

*Guía visual creada por Claude Code Assistant*
*26 de Diciembre 2024*