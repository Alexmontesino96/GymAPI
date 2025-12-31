# 🔧 Guía de Integración - Sistema de Nutrición

## 📋 Tabla de Contenidos
- [Quick Start](#quick-start)
- [Autenticación](#autenticación)
- [Frontend Integration](#frontend-integration)
- [Mobile Apps](#mobile-apps)
- [Webhooks y Eventos](#webhooks-y-eventos)
- [Testing](#testing)
- [Mejores Prácticas](#mejores-prácticas)
- [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Configuración Inicial
```bash
# Variables de entorno necesarias
CHAT_GPT_MODEL=sk-...  # API key de OpenAI
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
AUTH0_DOMAIN=...
AUTH0_API_AUDIENCE=...
```

### 2. Verificar Módulo Activo
```python
# Verificar que el gimnasio tiene el módulo de nutrición activo
GET /api/v1/gyms/{gym_id}/modules

Response:
{
    "modules": [
        {
            "name": "nutrition",
            "enabled": true,
            "config": {
                "ai_enabled": true,
                "safety_screening": true
            }
        }
    ]
}
```

### 3. Primer Request
```python
# Obtener planes disponibles
GET /api/v1/nutrition/plans/available
Authorization: Bearer {token}

Response: 200 OK
[
    {
        "id": 1,
        "name": "Plan Básico 1800cal",
        "is_public": true,
        "nutritional_goal": "weight_loss"
    }
]
```

## Autenticación

### JWT Token Structure
```json
{
    "sub": "auth0|user123",
    "gym_id": 5,
    "role": "trainer",
    "permissions": [
        "nutrition:read",
        "nutrition:write",
        "nutrition:ai_generate"
    ],
    "exp": 1735500000
}
```

### Headers Requeridos
```http
Authorization: Bearer eyJ0eXAiOiJKV1Q...
Content-Type: application/json
X-Gym-ID: 5  # Opcional, se extrae del token
```

### Validación de Permisos
```python
# Decorator en endpoints
@require_permission("nutrition:ai_generate")
async def generate_with_ai(request):
    # Solo trainers y admins pueden ejecutar
    pass
```

## Frontend Integration

### React/Next.js Example

#### 1. Context Provider
```typescript
// contexts/NutritionContext.tsx
import { createContext, useContext, useState } from 'react';

interface NutritionContextType {
    currentPlan: NutritionPlan | null;
    userProgress: UserProgress | null;
    safetyScreening: SafetyScreening | null;
    loadPlan: (planId: number) => Promise<void>;
    followPlan: (planId: number) => Promise<void>;
    completeScreening: (data: ScreeningData) => Promise<void>;
}

const NutritionContext = createContext<NutritionContextType>();

export const NutritionProvider: React.FC = ({ children }) => {
    const [currentPlan, setCurrentPlan] = useState(null);
    const [safetyScreening, setSafetyScreening] = useState(null);

    const followPlan = async (planId: number) => {
        try {
            // Verificar si necesita screening
            const planDetails = await api.get(`/nutrition/plans/${planId}`);

            if (planDetails.requires_screening && !safetyScreening?.is_valid) {
                // Redirigir a screening
                router.push('/nutrition/safety-screening');
                return;
            }

            // Seguir plan
            const response = await api.post(`/nutrition/plans/${planId}/follow`);
            setCurrentPlan(response.data);
        } catch (error) {
            if (error.response?.status === 403) {
                // Requiere screening médico
                toast.error('Este plan requiere evaluación médica');
                router.push('/nutrition/safety-screening');
            }
        }
    };

    return (
        <NutritionContext.Provider value={{ ... }}>
            {children}
        </NutritionContext.Provider>
    );
};
```

#### 2. Plan Display Component
```typescript
// components/NutritionPlan.tsx
import { useState, useEffect } from 'react';
import { useNutrition } from '@/contexts/NutritionContext';

export const NutritionPlanView: React.FC = () => {
    const { currentPlan, userProgress } = useNutrition();
    const [selectedDay, setSelectedDay] = useState(1);

    if (!currentPlan) {
        return <PlanSelector />;
    }

    return (
        <div className="nutrition-plan">
            {/* Header con información general */}
            <PlanHeader plan={currentPlan} />

            {/* Navegación por días */}
            <DaySelector
                totalDays={currentPlan.total_days}
                currentDay={selectedDay}
                onDayChange={setSelectedDay}
            />

            {/* Comidas del día */}
            <DailyMeals
                meals={currentPlan.daily_plans[selectedDay - 1].meals}
                onMealComplete={handleMealComplete}
            />

            {/* Progreso */}
            <ProgressTracker progress={userProgress} />
        </div>
    );
};
```

#### 3. Safety Screening Form
```typescript
// components/SafetyScreeningForm.tsx
export const SafetyScreeningForm: React.FC = () => {
    const [formData, setFormData] = useState<ScreeningData>({
        age: null,
        weight: null,
        height: null,
        sex: '',
        medical_conditions: [],
        is_pregnant: false,
        is_breastfeeding: false,
        takes_medications: false,
        has_eating_disorder_history: false
    });

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();

        try {
            const response = await api.post('/nutrition/safety-screening', formData);

            if (response.data.can_proceed) {
                toast.success('Evaluación completada con éxito');
                router.push('/nutrition/plans');
            } else {
                // Mostrar advertencias
                showWarnings(response.data.warnings);

                if (response.data.requires_professional) {
                    showProfessionalReferral(response.data.recommended_specialists);
                }
            }
        } catch (error) {
            toast.error('Error al procesar evaluación');
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            {/* Campos del formulario */}
            <MedicalQuestions onChange={updateFormData} />

            {/* Disclaimer */}
            <Disclaimer version="1.0" />

            <button type="submit">
                Completar Evaluación
            </button>
        </form>
    );
};
```

#### 4. AI Generation (Admin/Trainer)
```typescript
// components/AIGeneratorForm.tsx
export const AIGeneratorForm: React.FC = () => {
    const [isGenerating, setIsGenerating] = useState(false);
    const [prompt, setPrompt] = useState('');

    const generatePlan = async () => {
        setIsGenerating(true);

        try {
            const response = await api.post('/nutrition/plans/generate', {
                prompt,
                duration_days: 7,
                user_context: {
                    // Contexto del usuario objetivo
                }
            });

            toast.success('Plan generado con éxito');
            router.push(`/nutrition/plans/${response.data.plan_id}`);
        } catch (error) {
            toast.error('Error al generar plan');
        } finally {
            setIsGenerating(false);
        }
    };

    return (
        <div>
            <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe el plan que deseas generar..."
            />

            <button
                onClick={generatePlan}
                disabled={isGenerating}
            >
                {isGenerating ? 'Generando...' : 'Generar con IA'}
            </button>

            {isGenerating && (
                <div className="cost-estimate">
                    Costo estimado: $0.002 USD
                </div>
            )}
        </div>
    );
};
```

## Mobile Apps

### React Native Integration

#### 1. API Client Setup
```typescript
// services/nutritionApi.ts
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL } from '@env';

class NutritionAPI {
    private token: string | null = null;

    async init() {
        this.token = await AsyncStorage.getItem('auth_token');
    }

    async getPlans(): Promise<NutritionPlan[]> {
        const response = await fetch(`${API_BASE_URL}/nutrition/plans`, {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch plans');
        }

        return response.json();
    }

    async trackMeal(mealId: number, completed: boolean) {
        return fetch(`${API_BASE_URL}/nutrition/meals/${mealId}/complete`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ completed })
        });
    }

    async analyzeImage(imageUri: string) {
        const formData = new FormData();
        formData.append('image', {
            uri: imageUri,
            type: 'image/jpeg',
            name: 'meal.jpg'
        } as any);

        return fetch(`${API_BASE_URL}/nutrition/meals/analyze`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        });
    }
}

export default new NutritionAPI();
```

#### 2. Offline Support
```typescript
// utils/offlineSync.ts
import NetInfo from '@react-native-community/netinfo';
import { Queue } from 'react-native-job-queue';

export class OfflineNutritionSync {
    private queue = new Queue();

    async trackMealOffline(mealData: MealCompletion) {
        // Guardar localmente
        await AsyncStorage.setItem(
            `pending_meal_${Date.now()}`,
            JSON.stringify(mealData)
        );

        // Agregar a cola de sincronización
        this.queue.addJob({
            name: 'sync-meal',
            payload: mealData,
            attempts: 3,
            timeout: 30000
        });
    }

    async syncPendingData() {
        const isConnected = await NetInfo.fetch();

        if (isConnected.isConnected) {
            const pendingKeys = await AsyncStorage.getAllKeys();
            const mealKeys = pendingKeys.filter(k => k.startsWith('pending_meal_'));

            for (const key of mealKeys) {
                const data = await AsyncStorage.getItem(key);
                if (data) {
                    try {
                        await api.trackMeal(JSON.parse(data));
                        await AsyncStorage.removeItem(key);
                    } catch (error) {
                        console.error('Failed to sync meal:', error);
                    }
                }
            }
        }
    }
}
```

#### 3. Push Notifications
```typescript
// services/nutritionNotifications.ts
import messaging from '@react-native-firebase/messaging';
import PushNotification from 'react-native-push-notification';

export class NutritionNotifications {
    setupMealReminders() {
        // Desayuno
        PushNotification.localNotificationSchedule({
            title: '🍳 Hora del Desayuno',
            message: 'No olvides registrar tu desayuno',
            date: this.getNextMealTime('08:00'),
            repeatType: 'day',
            id: 'breakfast_reminder'
        });

        // Almuerzo
        PushNotification.localNotificationSchedule({
            title: '🥗 Hora del Almuerzo',
            message: 'Es momento de tu almuerzo saludable',
            date: this.getNextMealTime('13:00'),
            repeatType: 'day',
            id: 'lunch_reminder'
        });

        // Cena
        PushNotification.localNotificationSchedule({
            title: '🍽️ Hora de la Cena',
            message: 'Completa tu día con una cena balanceada',
            date: this.getNextMealTime('19:00'),
            repeatType: 'day',
            id: 'dinner_reminder'
        });
    }

    private getNextMealTime(time: string): Date {
        const [hours, minutes] = time.split(':').map(Number);
        const date = new Date();
        date.setHours(hours, minutes, 0, 0);

        if (date < new Date()) {
            date.setDate(date.getDate() + 1);
        }

        return date;
    }
}
```

## Webhooks y Eventos

### 1. Configuración de Webhooks
```python
# Registrar webhook endpoint
POST /api/v1/webhooks/register
{
    "url": "https://yourapp.com/webhooks/nutrition",
    "events": [
        "plan.created",
        "plan.followed",
        "meal.completed",
        "screening.completed"
    ],
    "secret": "webhook_secret_key"
}
```

### 2. Eventos Disponibles
```python
NUTRITION_EVENTS = {
    "plan.created": {
        "description": "Nuevo plan creado",
        "payload": {
            "plan_id": int,
            "created_by": int,
            "gym_id": int
        }
    },
    "plan.followed": {
        "description": "Usuario siguió un plan",
        "payload": {
            "plan_id": int,
            "user_id": int,
            "requires_screening": bool
        }
    },
    "meal.completed": {
        "description": "Comida marcada como completada",
        "payload": {
            "meal_id": int,
            "user_id": int,
            "completion_percentage": float
        }
    },
    "screening.completed": {
        "description": "Evaluación médica completada",
        "payload": {
            "user_id": int,
            "risk_level": str,
            "can_proceed": bool
        }
    },
    "ai.generation.completed": {
        "description": "Plan generado con IA",
        "payload": {
            "plan_id": int,
            "cost_usd": float,
            "model": str
        }
    }
}
```

### 3. Webhook Handler Example
```python
# Tu servidor recibiendo webhooks
from flask import Flask, request
import hmac
import hashlib

app = Flask(__name__)

@app.route('/webhooks/nutrition', methods=['POST'])
def handle_nutrition_webhook():
    # Verificar firma
    signature = request.headers.get('X-Webhook-Signature')
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        request.data,
        hashlib.sha256
    ).hexdigest()

    if signature != expected:
        return 'Unauthorized', 401

    # Procesar evento
    event = request.json
    event_type = event['type']

    if event_type == 'plan.followed':
        handle_plan_followed(event['payload'])
    elif event_type == 'screening.completed':
        handle_screening_completed(event['payload'])

    return 'OK', 200

def handle_plan_followed(payload):
    # Enviar email de bienvenida
    # Crear tareas de seguimiento
    # Analytics
    pass
```

## Testing

### 1. Unit Tests
```python
# tests/test_nutrition_safety.py
import pytest
from app.services.nutrition_ai_safety import NutritionAISafetyService

@pytest.mark.asyncio
async def test_high_risk_user_blocked():
    """Usuario de alto riesgo no puede seguir plan restrictivo"""
    service = NutritionAISafetyService()

    screening_data = {
        "age": 16,  # Menor de edad
        "weight": 45,
        "height": 165,
        "has_eating_disorder_history": True
    }

    result = await service.evaluate_user_safety(
        user_id=1,
        screening_data=screening_data,
        gym_id=1
    )

    assert result["risk_level"] == "CRITICAL"
    assert result["can_proceed"] == False
    assert "eating disorder" in str(result["warnings"])
```

### 2. Integration Tests
```python
# tests/integration/test_nutrition_flow.py
@pytest.mark.integration
async def test_complete_nutrition_flow():
    """Test flujo completo: screening -> follow -> track"""

    # 1. Completar screening
    screening_response = await client.post(
        "/api/v1/nutrition/safety-screening",
        json=valid_screening_data,
        headers=auth_headers
    )
    assert screening_response.status_code == 200

    # 2. Seguir plan
    follow_response = await client.post(
        f"/api/v1/nutrition/plans/{plan_id}/follow",
        headers=auth_headers
    )
    assert follow_response.status_code == 200

    # 3. Completar comida
    complete_response = await client.post(
        f"/api/v1/nutrition/meals/{meal_id}/complete",
        json={"completed": True},
        headers=auth_headers
    )
    assert complete_response.status_code == 200

    # 4. Verificar progreso
    progress = await client.get(
        "/api/v1/nutrition/progress/today",
        headers=auth_headers
    )
    assert progress.json()["meals_completed"] == 1
```

### 3. Load Testing
```python
# tests/load/test_nutrition_load.py
from locust import HttpUser, task, between

class NutritionUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login and get token
        self.token = self.login()

    @task(3)
    def view_plans(self):
        self.client.get(
            "/api/v1/nutrition/plans",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def complete_meal(self):
        self.client.post(
            "/api/v1/nutrition/meals/1/complete",
            json={"completed": True},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def view_progress(self):
        self.client.get(
            "/api/v1/nutrition/progress/weekly",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

## Mejores Prácticas

### 1. Rate Limiting
```typescript
// Implementar rate limiting en cliente
class RateLimitedAPI {
    private requestQueue: Array<() => Promise<any>> = [];
    private processing = false;
    private requestCount = 0;
    private resetTime = Date.now() + 60000;

    async makeRequest(fn: () => Promise<any>) {
        // Reset counter cada minuto
        if (Date.now() > this.resetTime) {
            this.requestCount = 0;
            this.resetTime = Date.now() + 60000;
        }

        // Check limit
        if (this.requestCount >= 60) {
            throw new Error('Rate limit exceeded');
        }

        this.requestCount++;
        return fn();
    }
}
```

### 2. Caching Strategy
```typescript
// Cache local para reducir llamadas API
class NutritionCache {
    private cache = new Map();
    private ttls = new Map();

    set(key: string, value: any, ttl: number = 300000) {
        this.cache.set(key, value);
        this.ttls.set(key, Date.now() + ttl);
    }

    get(key: string) {
        const ttl = this.ttls.get(key);
        if (!ttl || Date.now() > ttl) {
            this.cache.delete(key);
            this.ttls.delete(key);
            return null;
        }
        return this.cache.get(key);
    }

    async getOrFetch(key: string, fetcher: () => Promise<any>) {
        const cached = this.get(key);
        if (cached) return cached;

        const data = await fetcher();
        this.set(key, data);
        return data;
    }
}
```

### 3. Error Handling
```typescript
// Manejo robusto de errores
class NutritionErrorHandler {
    handle(error: any): void {
        if (error.response) {
            switch (error.response.status) {
                case 403:
                    if (error.response.data.code === 'SCREENING_REQUIRED') {
                        this.redirectToScreening();
                    } else {
                        this.showPermissionError();
                    }
                    break;

                case 429:
                    this.handleRateLimit(error.response.headers['retry-after']);
                    break;

                case 500:
                    this.showServerError();
                    this.logToSentry(error);
                    break;

                default:
                    this.showGenericError();
            }
        } else if (error.request) {
            this.handleNetworkError();
        } else {
            this.handleUnexpectedError(error);
        }
    }
}
```

## Troubleshooting

### Problemas Comunes

#### 1. "Module not enabled"
```python
# Verificar que el módulo está activo
GET /api/v1/gyms/{gym_id}/modules

# Si no está activo, activarlo (admin only)
POST /api/v1/gyms/{gym_id}/modules
{
    "module_name": "nutrition",
    "enabled": true
}
```

#### 2. "Screening expired"
```python
# Los screenings expiran en 24 horas
# Solución: Completar nuevo screening

# Verificar screening actual
GET /api/v1/nutrition/safety-screening/current

# Si expiró, crear nuevo
POST /api/v1/nutrition/safety-screening
```

#### 3. "AI generation failed"
```python
# Verificar API key de OpenAI
# Verificar límites de quota
# Revisar logs de auditoría

GET /api/v1/nutrition/ai/status

{
    "api_configured": true,
    "quota_remaining": 47,
    "last_error": null
}
```

#### 4. "Cannot follow restrictive plan"
```python
# Usuario necesita screening médico
# Verificar condiciones médicas

# Debug info
GET /api/v1/nutrition/plans/{plan_id}/requirements

{
    "requires_screening": true,
    "min_age": 18,
    "excluded_conditions": ["pregnancy", "eating_disorder"]
}
```

### Logs y Debugging

#### Habilitar Debug Mode
```python
# En desarrollo
DEBUG_NUTRITION=true
LOG_LEVEL=debug

# Logs detallados
[2024-01-15 10:23:45] DEBUG: Safety screening evaluation started
[2024-01-15 10:23:45] DEBUG: Risk score calculated: 7/10
[2024-01-15 10:23:45] DEBUG: Risk level: HIGH
[2024-01-15 10:23:45] DEBUG: Screening saved with ID: 123
```

#### Audit Logs
```python
# Revisar logs de auditoría
GET /api/v1/nutrition/audit-logs?user_id=123

[
    {
        "id": 456,
        "action": "screening.failed",
        "reason": "high_risk",
        "timestamp": "2024-01-15T10:23:45Z"
    }
]
```

---

**Siguiente:** [07_CASOS_USO.md](07_CASOS_USO.md) - Casos de uso y ejemplos prácticos