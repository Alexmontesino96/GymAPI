# 🚀 Guía Frontend: Crear Planes LIVE con IA

## 📋 Resumen

El backend ahora soporta la creación de **planes LIVE** (grupales con fecha sincronizada) usando el endpoint de generación con IA. Esta guía explica los cambios necesarios en el frontend.

---

## ✨ Nuevos Campos Disponibles

### 1. `plan_type` (Opcional)

**Tipo:** `string`
**Valores:** `"template"` | `"live"`
**Default:** `"template"`

```typescript
plan_type: "template"  // Plan individual (comportamiento actual)
plan_type: "live"      // Plan grupal con fecha fija (NUEVO)
```

### 2. `live_start_date` (Condicional)

**Tipo:** `string` (ISO 8601 datetime)
**Requerido:** SOLO si `plan_type === "live"`
**Formato:** `"YYYY-MM-DDTHH:mm:ssZ"`

```typescript
live_start_date: "2026-03-01T00:00:00Z"  // Fecha de inicio del plan grupal
```

---

## 🔧 Cambios en el Request

### Request Anterior (Solo Templates)

```json
POST /api/v1/nutrition/plans/generate

{
  "title": "Plan Pérdida de Peso",
  "duration_days": 14,
  "goal": "weight_loss",
  "target_calories": 1800,
  "meals_per_day": 5,
  "difficulty_level": "beginner",
  "budget_level": "medium"
}
```

### Request Nuevo (Plan TEMPLATE - Sin Cambios)

```json
{
  "title": "Plan Pérdida de Peso Individual",
  "plan_type": "template",  // ⭐ Nuevo campo (opcional, default)
  "duration_days": 14,
  "goal": "weight_loss",
  "target_calories": 1800,
  "meals_per_day": 5
}
```

### Request Nuevo (Plan LIVE - Challenge Grupal)

```json
{
  "title": "Challenge 21 Días Marzo 2026",
  "plan_type": "live",                      // ⭐ NUEVO
  "live_start_date": "2026-03-01T00:00:00Z",  // ⭐ NUEVO (REQUERIDO)
  "duration_days": 21,
  "goal": "weight_loss",
  "target_calories": 1500,
  "meals_per_day": 5,
  "dietary_restrictions": ["gluten_free"],
  "prompt": "Plan detox con jugos verdes"
}
```

---

## 🎨 Implementación en UI

### Opción 1: Toggle Simple

```tsx
const [planType, setPlanType] = useState<'template' | 'live'>('template');
const [startDate, setStartDate] = useState<Date | null>(null);

<FormControl>
  <FormLabel>Tipo de Plan</FormLabel>
  <RadioGroup value={planType} onChange={(e) => setPlanType(e.target.value)}>
    <Radio value="template">
      Individual (Template) - Cada usuario empieza cuando quiere
    </Radio>
    <Radio value="live">
      Grupal (Live) - Todos empiezan en la misma fecha
    </Radio>
  </RadioGroup>
</FormControl>

{planType === 'live' && (
  <FormControl isRequired>
    <FormLabel>Fecha de Inicio del Challenge</FormLabel>
    <DatePicker
      selected={startDate}
      onChange={setStartDate}
      minDate={new Date()}
      showTimeSelect
      dateFormat="yyyy-MM-dd HH:mm"
    />
    <FormHelperText>
      Todos los participantes verán el mismo día en esta fecha
    </FormHelperText>
  </FormControl>
)}
```

### Opción 2: Steps Wizard

```tsx
// Step 1: Seleccionar tipo
<Step title="Tipo de Plan">
  <PlanTypeSelector onChange={setPlanType} />
</Step>

// Step 2: Configurar calendario (solo si LIVE)
{planType === 'live' && (
  <Step title="Fecha de Inicio">
    <LiveStartDatePicker onChange={setStartDate} />
  </Step>
)}

// Step 3: Configurar plan con IA
<Step title="Generar con IA">
  <AIGenerationForm
    planType={planType}
    startDate={startDate}
  />
</Step>
```

---

## 📤 Envío del Request

```typescript
interface AIGenerationRequest {
  title: string;
  goal: 'weight_loss' | 'muscle_gain' | 'maintenance' | 'performance';
  target_calories: number;
  duration_days: number;

  // Nuevos campos opcionales
  plan_type?: 'template' | 'live';
  live_start_date?: string;  // ISO 8601

  // Campos existentes
  meals_per_day?: number;
  difficulty_level?: 'beginner' | 'intermediate' | 'advanced';
  budget_level?: 'economic' | 'medium' | 'premium';
  dietary_restrictions?: string[];
  prompt?: string;
}

async function generatePlan(data: AIGenerationRequest) {
  const payload: AIGenerationRequest = {
    title: data.title,
    goal: data.goal,
    target_calories: data.target_calories,
    duration_days: data.duration_days,
    meals_per_day: data.meals_per_day || 5,
  };

  // Agregar campos de plan LIVE si aplica
  if (data.plan_type === 'live') {
    if (!data.live_start_date) {
      throw new Error('Planes LIVE requieren fecha de inicio');
    }
    payload.plan_type = 'live';
    payload.live_start_date = data.live_start_date;
  }

  const response = await fetch('/api/v1/nutrition/plans/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'x-gym-id': gymId,
    },
    body: JSON.stringify(payload),
  });

  return response.json();
}
```

---

## ✅ Validaciones

### En el Frontend

```typescript
function validatePlanData(data: AIGenerationRequest): string | null {
  // Validación 1: Si es LIVE, requiere fecha
  if (data.plan_type === 'live' && !data.live_start_date) {
    return 'Los planes LIVE requieren una fecha de inicio';
  }

  // Validación 2: Fecha debe ser futura
  if (data.plan_type === 'live' && data.live_start_date) {
    const startDate = new Date(data.live_start_date);
    if (startDate < new Date()) {
      return 'La fecha de inicio debe ser futura';
    }
  }

  // Validación 3: Templates no deben tener fecha
  if (data.plan_type === 'template' && data.live_start_date) {
    return 'Los planes individuales no necesitan fecha de inicio';
  }

  return null; // ✅ Válido
}
```

### Errores del Backend

El backend validará automáticamente y retornará:

```json
// Error 400: Falta live_start_date
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Los planes LIVE requieren 'live_start_date'. Especifica la fecha de inicio del plan grupal."
    }
  ]
}

// Error 400: Template con live_start_date
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Los planes TEMPLATE no deben tener 'live_start_date'. Solo los planes LIVE la requieren."
    }
  ]
}
```

---

## 🎯 Casos de Uso Recomendados

### Plan TEMPLATE (Uso actual - Sin cambios)
```json
{
  "title": "Plan Personalizado Pérdida de Grasa",
  "plan_type": "template",  // o simplemente omitir
  "duration_days": 14,
  "goal": "weight_loss",
  "target_calories": 1800
}
```
✅ Usuario empieza cuando quiere
✅ Progreso individual
✅ Fecha flexible

### Plan LIVE (Nuevo - Challenge Grupal)
```json
{
  "title": "Challenge Marzo 2026 - 30 Días Fit",
  "plan_type": "live",
  "live_start_date": "2026-03-01T00:00:00Z",
  "duration_days": 30,
  "goal": "performance",
  "target_calories": 2000
}
```
✅ Todos empiezan el 1 de marzo
✅ Día sincronizado para todos
✅ Estadísticas grupales
✅ Challenge comunitario

---

## 📊 Response del Backend

El response es el mismo para ambos tipos:

```json
{
  "plan_id": 123,
  "name": "Challenge 21 Días Marzo 2026",
  "description": "Plan generado con IA...",
  "total_days": 21,
  "nutritional_goal": "weight_loss",
  "target_calories": 1500,
  "daily_plans_count": 21,
  "total_meals": 105,
  "ai_metadata": {
    "model": "gpt-4o-mini",
    "version": "2024-07-18"
  },
  "generation_time_ms": 12500,
  "cost_estimate_usd": 0.0234
}
```

Para obtener los detalles del plan (incluyendo `plan_type` y `live_start_date`):

```typescript
GET /api/v1/nutrition/plans/{plan_id}

// Response
{
  "id": 123,
  "title": "Challenge 21 Días Marzo 2026",
  "plan_type": "live",              // ⭐ Indica que es LIVE
  "live_start_date": "2026-03-01T00:00:00Z",  // ⭐ Fecha global
  "is_live_active": false,           // Se activará automáticamente
  "live_participants_count": 0,      // Contador en tiempo real
  "duration_days": 21,
  "goal": "weight_loss",
  // ... resto de campos
}
```

---

## 💡 Consejos de UX

### 1. **Mostrar Estado del Plan LIVE**

```tsx
{plan.plan_type === 'live' && (
  <Badge colorScheme={getStatusColor(plan)}>
    {getStatusText(plan)}
  </Badge>
)}

function getStatusText(plan: NutritionPlan): string {
  const startDate = new Date(plan.live_start_date);
  const today = new Date();
  const endDate = new Date(startDate);
  endDate.setDate(endDate.getDate() + plan.duration_days);

  if (today < startDate) {
    const daysUntil = Math.ceil((startDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    return `Inicia en ${daysUntil} día${daysUntil !== 1 ? 's' : ''}`;
  } else if (today >= startDate && today < endDate) {
    return 'En progreso';
  } else {
    return 'Finalizado';
  }
}
```

### 2. **Contador de Participantes en LIVE**

```tsx
{plan.plan_type === 'live' && (
  <HStack>
    <Icon as={FiUsers} />
    <Text>{plan.live_participants_count} participantes</Text>
  </HStack>
)}
```

### 3. **Advertencia antes de crear LIVE**

```tsx
{planType === 'live' && (
  <Alert status="info">
    <AlertIcon />
    <Box>
      <AlertTitle>Plan Challenge Grupal</AlertTitle>
      <AlertDescription>
        Todos los usuarios verán el mismo día en la fecha que selecciones.
        Una vez iniciado, no se puede cambiar la fecha de inicio.
      </AlertDescription>
    </Box>
  </Alert>
)}
```

---

## 🧪 Testing

### Test Case 1: Crear Plan TEMPLATE (sin cambios)
```typescript
test('should create template plan with AI', async () => {
  const response = await generatePlan({
    title: 'Plan Test',
    goal: 'weight_loss',
    target_calories: 1800,
    duration_days: 7,
  });

  expect(response.plan_id).toBeDefined();
  // plan_type será "template" por default
});
```

### Test Case 2: Crear Plan LIVE exitoso
```typescript
test('should create live plan with start date', async () => {
  const futureDate = new Date();
  futureDate.setDate(futureDate.getDate() + 7);

  const response = await generatePlan({
    title: 'Challenge Test',
    plan_type: 'live',
    live_start_date: futureDate.toISOString(),
    goal: 'performance',
    target_calories: 2000,
    duration_days: 21,
  });

  expect(response.plan_id).toBeDefined();
});
```

### Test Case 3: Validar error si falta fecha
```typescript
test('should fail if live plan without start date', async () => {
  await expect(
    generatePlan({
      title: 'Challenge Test',
      plan_type: 'live',  // Sin live_start_date
      goal: 'weight_loss',
      target_calories: 1500,
      duration_days: 14,
    })
  ).rejects.toThrow('Los planes LIVE requieren \'live_start_date\'');
});
```

---

## 📞 Soporte

Si tienes dudas sobre la implementación:

1. **Documentación del endpoint:** `GET /api/v1/docs` → Buscar `/nutrition/plans/generate`
2. **Ejemplos en Swagger:** http://localhost:8000/api/v1/docs
3. **Endpoint de prueba:** Usa Postman/Insomnia con los ejemplos de este documento

---

## 🎉 Resumen de Cambios

| Campo | Antes | Ahora |
|-------|-------|-------|
| `plan_type` | ❌ No existía | ✅ Opcional (`"template"` o `"live"`) |
| `live_start_date` | ❌ No existía | ✅ Requerido solo si `plan_type === "live"` |
| Validación | ❌ No había | ✅ Backend valida automáticamente |

**Backward Compatible:** ✅ Sí
Los requests anteriores sin `plan_type` siguen funcionando igual (crean templates).

**Breaking Changes:** ❌ No
No necesitas actualizar nada si solo usas templates.
