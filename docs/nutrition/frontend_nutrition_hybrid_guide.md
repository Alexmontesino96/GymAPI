# 🍎 Frontend Guide: Sistema Híbrido de Planes Nutricionales

## 📋 Resumen de Cambios

El sistema de planes nutricionales ha sido completamente extendido para soportar **3 tipos diferentes de planes** con comportamientos únicos:

- **🟢 TEMPLATE**: Planes flexibles (comportamiento actual mantenido)
- **🔴 LIVE**: Planes sincronizados en tiempo real 
- **📦 ARCHIVED**: Planes live terminados, convertidos a templates reutilizables

## 🎯 Impacto en Frontend

### ✅ **Compatibilidad Backward**
- ✅ **Todos los endpoints existentes siguen funcionando**
- ✅ **Los planes existentes se comportan igual (tipo TEMPLATE por defecto)**
- ✅ **No se requieren cambios inmediatos en UI existente**

### 🆕 **Nuevas Funcionalidades Disponibles**
- 🎨 **Dashboard categorizado** por tipos de planes
- 📅 **Calendario de planes live** con fechas de inicio
- 🔄 **Estados dinámicos** de planes (próximo, activo, terminado)
- 👥 **Contadores de participantes** en tiempo real
- 📦 **Biblioteca de planes archivados** probados por la comunidad

---

## 🌐 API Changes & New Endpoints

### 📊 **Endpoints Modificados (Backward Compatible)**

#### `GET /api/v1/nutrition/plans`
**Nuevos query parameters opcionales:**
```typescript
interface NutritionPlanFilters {
  // Filtros existentes (sin cambios)
  goal?: string;
  difficulty_level?: string;
  search_query?: string;
  
  // ✨ NUEVOS filtros híbridos
  plan_type?: 'template' | 'live' | 'archived';
  status?: 'not_started' | 'running' | 'finished';
  is_live_active?: boolean;
}
```

**Respuesta extendida:**
```typescript
interface NutritionPlan {
  // Campos existentes (sin cambios)
  id: number;
  title: string;
  description?: string;
  goal: string;
  // ... otros campos existentes
  
  // ✨ NUEVOS campos híbridos
  plan_type: 'template' | 'live' | 'archived';
  live_start_date?: string; // ISO datetime
  live_end_date?: string;
  is_live_active: boolean;
  live_participants_count: number;
  original_live_plan_id?: number;
  archived_at?: string;
  original_participants_count?: number;
  
  // Campos calculados dinámicamente
  current_day?: number;
  status?: 'not_started' | 'running' | 'finished';
  days_until_start?: number;
}
```

#### `GET /api/v1/nutrition/today`
**Respuesta extendida:**
```typescript
interface TodayMealPlan {
  // Campos existentes
  date: string;
  meals: Meal[];
  completion_percentage: number;
  
  // ✨ NUEVOS campos híbridos
  plan?: NutritionPlan;
  current_day: number;
  status: 'not_started' | 'running' | 'finished';
  days_until_start?: number;
}
```

#### `GET /api/v1/nutrition/dashboard`
**Respuesta completamente nueva:**
```typescript
interface NutritionDashboardHybrid {
  // Planes categorizados por tipo
  template_plans: NutritionPlan[];
  live_plans: NutritionPlan[];
  available_plans: NutritionPlan[];
  
  // Plan actual del usuario
  today_plan?: TodayMealPlan;
  
  // Estadísticas
  completion_streak: number;
  weekly_progress: UserDailyProgress[];
}
```

### 🆕 **Nuevos Endpoints**

#### `GET /api/v1/nutrition/plans/hybrid`
**Listado categorizado por tipos:**
```typescript
interface NutritionPlanListResponseHybrid {
  live_plans: NutritionPlan[];
  template_plans: NutritionPlan[];
  archived_plans: NutritionPlan[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}
```

#### `GET /api/v1/nutrition/plans/{planId}/status`
**Estado en tiempo real de un plan:**
```typescript
interface PlanStatus {
  plan_id: number;
  plan_type: 'template' | 'live' | 'archived';
  current_day: number;
  status: 'not_started' | 'running' | 'finished';
  days_until_start?: number;
  is_live_active: boolean;
  live_participants_count: number;
  is_following: boolean;
}
```

#### `PUT /api/v1/nutrition/plans/{planId}/live-status`
**Actualizar estado de plan live (solo creadores):**
```typescript
interface LivePlanStatusUpdate {
  is_live_active: boolean;
  live_participants_count?: number;
}
```

#### `POST /api/v1/nutrition/plans/{planId}/archive`
**Archivar plan live terminado:**
```typescript
interface ArchivePlanRequest {
  create_template_version: boolean;
  template_title?: string;
}
```

#### `GET /api/v1/nutrition/enums/plan-types`
**Tipos de planes disponibles:**
```typescript
interface EnumOption {
  value: string;
  label: string;
}
// Response: [{ value: 'template', label: 'Template' }, ...]
```

#### `GET /api/v1/nutrition/enums/plan-statuses`
**Estados de planes disponibles:**
```typescript
// Response: [{ value: 'not_started', label: 'Not Started' }, ...]
```

---

## 🎨 UX/UI Implementation Guide

### 🔄 **Plan Type Indicators**

#### Visual Differentiation
```tsx
const PlanTypeIndicator = ({ plan }) => {
  const indicators = {
    template: { 
      icon: '📋', 
      color: 'blue', 
      label: 'Flexible' 
    },
    live: { 
      icon: '🔴', 
      color: 'red', 
      label: 'Live' 
    },
    archived: { 
      icon: '📦', 
      color: 'purple', 
      label: 'Archived' 
    }
  };
  
  const indicator = indicators[plan.plan_type];
  
  return (
    <Badge color={indicator.color}>
      {indicator.icon} {indicator.label}
    </Badge>
  );
};
```

### 📅 **Plan Status & Timing**

#### Template Plans
```tsx
const TemplatePlanCard = ({ plan }) => (
  <Card>
    <PlanTypeIndicator plan={plan} />
    <h3>{plan.title}</h3>
    <p>🚀 Empieza cuando quieras</p>
    <p>📊 {plan.duration_days} días</p>
    <Button>Empezar Plan</Button>
  </Card>
);
```

#### Live Plans
```tsx
const LivePlanCard = ({ plan }) => {
  const renderStatus = () => {
    if (plan.status === 'not_started') {
      return (
        <div>
          <p>⏰ Empieza en {plan.days_until_start} días</p>
          <p>📅 {formatDate(plan.live_start_date)}</p>
        </div>
      );
    }
    
    if (plan.status === 'running') {
      return (
        <div>
          <p>🔴 LIVE - Día {plan.current_day}</p>
          <p>👥 {plan.live_participants_count} participantes</p>
        </div>
      );
    }
    
    return <p>✅ Plan terminado</p>;
  };
  
  return (
    <Card>
      <PlanTypeIndicator plan={plan} />
      <h3>{plan.title}</h3>
      {renderStatus()}
      <Button disabled={plan.status === 'finished'}>
        {plan.status === 'not_started' ? 'Reservar Lugar' : 'Unirse'}
      </Button>
    </Card>
  );
};
```

#### Archived Plans
```tsx
const ArchivedPlanCard = ({ plan }) => (
  <Card>
    <PlanTypeIndicator plan={plan} />
    <h3>{plan.title}</h3>
    <p>📊 Probado por {plan.original_participants_count} usuarios</p>
    <p>⭐ Plan exitoso archivado</p>
    <Button>Empezar Ahora</Button>
  </Card>
);
```

### 📱 **Dashboard Híbrido**

```tsx
const NutritionDashboard = () => {
  const [dashboard, setDashboard] = useState<NutritionDashboardHybrid>();
  
  useEffect(() => {
    fetch('/api/v1/nutrition/dashboard')
      .then(res => res.json())
      .then(setDashboard);
  }, []);
  
  return (
    <div>
      {/* Plan de Hoy */}
      <TodaySection plan={dashboard?.today_plan} />
      
      {/* Planes Live Activos */}
      <Section title="🔴 Planes Live">
        {dashboard?.live_plans.map(plan => 
          <LivePlanCard key={plan.id} plan={plan} />
        )}
      </Section>
      
      {/* Mis Planes Template */}
      <Section title="📋 Mis Planes">
        {dashboard?.template_plans.map(plan => 
          <TemplatePlanCard key={plan.id} plan={plan} />
        )}
      </Section>
      
      {/* Planes Disponibles */}
      <Section title="📚 Descubrir">
        {dashboard?.available_plans.map(plan => 
          <PlanCard key={plan.id} plan={plan} />
        )}
      </Section>
    </div>
  );
};
```

### 📅 **Today Plan Component**

```tsx
const TodaySection = ({ plan }: { plan?: TodayMealPlan }) => {
  if (!plan?.plan) {
    return (
      <Card>
        <h2>📅 Hoy</h2>
        <p>No tienes planes activos para hoy</p>
        <Button>Explorar Planes</Button>
      </Card>
    );
  }
  
  const renderMessage = () => {
    if (plan.status === 'not_started') {
      return (
        <p>
          ⏰ Tu plan "{plan.plan.title}" empieza en {plan.days_until_start} días
        </p>
      );
    }
    
    if (plan.status === 'running') {
      return (
        <div>
          <h3>🍽️ Día {plan.current_day} - {plan.plan.title}</h3>
          <p>{plan.meals.length} comidas programadas</p>
          <ProgressBar 
            value={plan.completion_percentage} 
            label={`${plan.completion_percentage.toFixed(0)}% completado`}
          />
        </div>
      );
    }
    
    return <p>✅ Plan completado</p>;
  };
  
  return (
    <Card>
      <h2>📅 Hoy</h2>
      <PlanTypeIndicator plan={plan.plan} />
      {renderMessage()}
      
      {plan.meals.length > 0 && (
        <div>
          {plan.meals.map(meal => 
            <MealCard key={meal.id} meal={meal} />
          )}
        </div>
      )}
    </Card>
  );
};
```

---

## 🛠️ Implementation Priority

### 🎯 **Phase 1: Core Compatibility (Immediate)**
1. ✅ **Update TypeScript interfaces** para nuevos campos
2. ✅ **Add plan type indicators** en cards existentes
3. ✅ **Handle new dashboard response** structure

### 🎯 **Phase 2: Enhanced UX (Short Term)**
1. 🎨 **Implement categorized listing** (`/plans/hybrid`)
2. 📅 **Add live plan countdown timers**
3. 👥 **Show participant counters** en planes live
4. 📊 **Enhanced plan status** indicators

### 🎯 **Phase 3: Advanced Features (Medium Term)**
1. 🔔 **Live plan notifications** (próximos a empezar)
2. 📈 **Real-time participant updates**
3. 🎯 **Plan recommendation engine** (template vs live)
4. 📦 **Archived plans showcase**

### 🎯 **Phase 4: Creator Tools (Long Term)**
1. 🛠️ **Live plan creation wizard**
2. 📊 **Analytics dashboard** for creators
3. 🔄 **Plan archiving interface**
4. 📅 **Scheduling tools** for live plans

---

## 📋 State Management Recommendations

### Redux/Context Structure
```typescript
interface NutritionState {
  // Existing state (mantenido)
  plans: NutritionPlan[];
  todayPlan?: TodayMealPlan;
  
  // New hybrid state
  dashboardHybrid?: NutritionDashboardHybrid;
  planStatuses: Record<number, PlanStatus>;
  livePlansUpdates: Record<number, LivePlanUpdate>;
}

// Actions
const nutritionSlice = {
  // Existing actions (mantenidos)
  setPlans,
  setTodayPlan,
  
  // New actions
  setDashboardHybrid,
  updatePlanStatus,
  updateLivePlanParticipants,
  markPlanAsArchived
};
```

### Real-time Updates
```typescript
// WebSocket for live plan updates
const useLivePlanUpdates = (planId: number) => {
  useEffect(() => {
    const ws = new WebSocket(`/ws/nutrition/plans/${planId}`);
    
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      
      if (update.type === 'participant_count') {
        dispatch(updateLivePlanParticipants({
          planId,
          count: update.count
        }));
      }
    };
    
    return () => ws.close();
  }, [planId]);
};
```

---

## 🧪 Testing Strategy

### Unit Tests
```typescript
describe('PlanTypeIndicator', () => {
  it('shows correct indicator for template plan', () => {
    const plan = { plan_type: 'template' };
    render(<PlanTypeIndicator plan={plan} />);
    expect(screen.getByText('📋 Flexible')).toBeInTheDocument();
  });
  
  it('shows live status for active live plan', () => {
    const plan = { 
      plan_type: 'live', 
      status: 'running',
      current_day: 5 
    };
    render(<LivePlanCard plan={plan} />);
    expect(screen.getByText('🔴 LIVE - Día 5')).toBeInTheDocument();
  });
});
```

### Integration Tests
```typescript
describe('Dashboard Integration', () => {
  it('loads hybrid dashboard correctly', async () => {
    mockApi('/api/v1/nutrition/dashboard', mockDashboardResponse);
    
    render(<NutritionDashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('🔴 Planes Live')).toBeInTheDocument();
      expect(screen.getByText('📋 Mis Planes')).toBeInTheDocument();
    });
  });
});
```

---

## 🚀 Migration Guide

### Existing Components
```typescript
// ✅ BEFORE (sigue funcionando)
const PlanCard = ({ plan }) => (
  <div>
    <h3>{plan.title}</h3>
    <p>{plan.description}</p>
  </div>
);

// ✨ ENHANCED (recomendado)
const PlanCard = ({ plan }) => (
  <div>
    <PlanTypeIndicator plan={plan} />
    <h3>{plan.title}</h3>
    <p>{plan.description}</p>
    {plan.plan_type === 'live' && (
      <LivePlanStatus plan={plan} />
    )}
  </div>
);
```

### API Calls
```typescript
// ✅ BEFORE (sigue funcionando)
const plans = await fetch('/api/v1/nutrition/plans').then(r => r.json());

// ✨ ENHANCED (más información)
const plans = await fetch('/api/v1/nutrition/plans?plan_type=live&status=running')
  .then(r => r.json());

// 🆕 NEW (categorizado)
const categorized = await fetch('/api/v1/nutrition/plans/hybrid')
  .then(r => r.json());
```

---

## 🎯 Key Takeaways para Frontend

1. **🔄 Backward Compatibility**: Todo lo existente sigue funcionando
2. **📊 Enhanced Data**: Más información disponible en respuestas API
3. **🎨 Visual Differentiation**: Necesario distinguir tipos de planes visualmente
4. **📅 Time-based Logic**: Planes live requieren manejo de fechas y estados
5. **👥 Real-time Updates**: Considerar WebSockets para participantes live
6. **📱 Progressive Enhancement**: Implementar features gradualmente

**🚀 El sistema está diseñado para máxima flexibilidad y experiencia de usuario mejorada mientras mantiene compatibilidad total con código existente.** 