# 📚 API de Entrenadores Personales - Documentación Completa

**Versión**: 1.0.0
**Última actualización**: 2024-01-24
**Base URL**: `/api/v1`

---

## 📑 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Autenticación](#autenticación)
3. [Endpoints](#endpoints)
   - [Registro de Entrenadores](#registro-de-entrenadores)
   - [Validaciones](#validaciones)
   - [Contexto del Workspace](#contexto-del-workspace)
4. [Modelos de Datos](#modelos-de-datos)
5. [Ejemplos Completos](#ejemplos-completos)
6. [Casos de Uso](#casos-de-uso)
7. [Errores y Troubleshooting](#errores-y-troubleshooting)
8. [Rate Limiting](#rate-limiting)
9. [Testing](#testing)

---

## 🎯 Introducción

La API de Entrenadores Personales permite crear y gestionar workspaces dedicados para entrenadores individuales. Cada entrenador obtiene:

- ✅ **Workspace personal** aislado (tipo `personal_trainer`)
- ✅ **Usuario con rol TRAINER** y permisos de OWNER
- ✅ **8 módulos esenciales** activados automáticamente
- ✅ **Stripe Connect** configurado (opcional)
- ✅ **UI adaptativa** basada en contexto
- ✅ **Sin planes de pago predeterminados** (máxima flexibilidad)

### Diferencias vs Gimnasios Tradicionales

| Característica | Gimnasio Tradicional | Entrenador Personal |
|----------------|----------------------|---------------------|
| Tipo | `gym` | `personal_trainer` |
| Múltiples trainers | ✅ Sí | ❌ No (solo el owner) |
| Clases grupales | ✅ Sí | ⚠️ Opcional |
| Gestión de equipos | ✅ Sí | ❌ No |
| Agenda de citas | ⚠️ Opcional | ✅ Sí |
| Límite de clientes | ❌ No | ✅ Sí (configurable) |
| Planes de pago | Membresías | Sesiones/Paquetes |

---

## 🔐 Autenticación

### Endpoints Públicos (No Requieren Autenticación)

```http
POST   /api/v1/auth/register-trainer
GET    /api/v1/auth/trainer/check-email/{email}
GET    /api/v1/auth/trainer/validate-subdomain/{subdomain}
```

### Endpoints Protegidos (Requieren Autenticación)

```http
GET    /api/v1/context/workspace
GET    /api/v1/context/workspace/stats
```

**Headers Requeridos**:
```http
Authorization: Bearer {ACCESS_TOKEN}
X-Gym-ID: {GYM_ID}
```

---

## 🚀 Endpoints

### Registro de Entrenadores

#### POST `/auth/register-trainer`

Crea un nuevo entrenador personal con workspace completo.

**Rate Limiting**: 5 requests/hora, 20 requests/día por IP

**Request Body**:
```json
{
  "email": "string (required)",
  "first_name": "string (required, 2-50 chars)",
  "last_name": "string (required, 2-50 chars)",
  "phone": "string (optional, formato: +525512345678)",
  "specialties": ["string"] (optional, max 10 items),
  "certifications": [
    {
      "name": "string (required)",
      "year": "integer (optional, 1990-2030)",
      "institution": "string (optional)",
      "credential_id": "string (optional)"
    }
  ] (optional),
  "timezone": "string (optional, default: America/Mexico_City)",
  "max_clients": "integer (optional, 1-200, default: 30)",
  "bio": "string (optional, max 500 chars)"
}
```

**Ejemplo de Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register-trainer" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan.perez@trainer.com",
    "first_name": "Juan",
    "last_name": "Pérez",
    "phone": "+525512345678",
    "specialties": ["CrossFit", "Nutrición Deportiva", "Entrenamiento Funcional"],
    "certifications": [
      {
        "name": "NASM-CPT",
        "year": 2020,
        "institution": "National Academy of Sports Medicine"
      },
      {
        "name": "Precision Nutrition Level 1",
        "year": 2021
      }
    ],
    "timezone": "America/Mexico_City",
    "max_clients": 25,
    "bio": "Entrenador certificado con 5 años de experiencia en CrossFit y nutrición deportiva."
  }'
```

**Response 201 Created**:
```json
{
  "success": true,
  "message": "Espacio de trabajo creado exitosamente",
  "workspace": {
    "id": 42,
    "name": "Entrenamiento Personal Juan Pérez",
    "subdomain": "juan-perez",
    "type": "personal_trainer",
    "email": "juan.perez@trainer.com",
    "timezone": "America/Mexico_City",
    "specialties": ["CrossFit", "Nutrición Deportiva", "Entrenamiento Funcional"],
    "max_clients": 25
  },
  "user": {
    "id": 101,
    "email": "juan.perez@trainer.com",
    "name": "Juan Pérez",
    "role": "TRAINER"
  },
  "modules_activated": [
    "users",
    "chat",
    "health",
    "nutrition",
    "billing",
    "appointments",
    "progress",
    "surveys"
  ],
  "payment_plans": [],
  "stripe_onboarding_url": "https://connect.stripe.com/setup/s/...",
  "next_steps": [
    "Completar onboarding de Stripe para recibir pagos",
    "Completar configuración de perfil",
    "Crear planes de pago personalizados",
    "Agregar primeros clientes",
    "Configurar horario de disponibilidad"
  ]
}
```

**Errores Posibles**:

**400 Bad Request** - Email ya registrado:
```json
{
  "detail": {
    "success": false,
    "message": "El usuario juan.perez@trainer.com ya tiene un workspace de entrenador (ID: 42)",
    "error_code": "WORKSPACE_EXISTS",
    "details": {
      "email": "juan.perez@trainer.com"
    }
  }
}
```

**400 Bad Request** - Validación fallida:
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**429 Too Many Requests** - Rate limit excedido:
```json
{
  "detail": "Rate limit exceeded"
}
```

**500 Internal Server Error** - Error del servidor:
```json
{
  "detail": {
    "success": false,
    "message": "Error interno al crear el workspace. Por favor intente nuevamente.",
    "error_code": "INTERNAL_ERROR",
    "details": {
      "email": "juan.perez@trainer.com"
    }
  }
}
```

---

### Validaciones

#### GET `/auth/trainer/check-email/{email}`

Verifica si un email está disponible para registro.

**Rate Limiting**: 30 requests/minuto

**Ejemplo de Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/auth/trainer/check-email/juan.perez@trainer.com"
```

**Response 200 OK** - Email disponible:
```json
{
  "available": true,
  "message": "Email disponible"
}
```

**Response 200 OK** - Email no disponible:
```json
{
  "available": false,
  "message": "Email ya registrado",
  "has_workspace": true,
  "details": {
    "user_id": 101,
    "is_trainer": true
  }
}
```

---

#### GET `/auth/trainer/validate-subdomain/{subdomain}`

Valida si un subdomain está disponible.

**Rate Limiting**: 30 requests/minuto

**Ejemplo de Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/auth/trainer/validate-subdomain/juan-perez"
```

**Response 200 OK** - Subdomain disponible:
```json
{
  "valid": true,
  "available": true,
  "message": "Subdomain disponible",
  "subdomain": "juan-perez"
}
```

**Response 200 OK** - Formato inválido:
```json
{
  "valid": false,
  "available": false,
  "message": "Formato inválido. Use solo letras minúsculas, números y guiones (3-50 caracteres)"
}
```

**Response 200 OK** - Subdomain ya en uso:
```json
{
  "valid": true,
  "available": false,
  "message": "Subdomain ya en uso",
  "subdomain": "juan-perez"
}
```

---

### Contexto del Workspace

#### GET `/context/workspace`

Obtiene información completa del workspace para adaptar la UI.

**Autenticación**: Requerida
**Headers**:
```http
Authorization: Bearer {token}
X-Gym-ID: {gym_id}
```

**Ejemplo de Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/context/workspace" \
  -H "Authorization: Bearer eyJ..." \
  -H "X-Gym-ID: 42"
```

**Response 200 OK** - Entrenador Personal:
```json
{
  "workspace": {
    "id": 42,
    "name": "Entrenamiento Personal Juan Pérez",
    "type": "personal_trainer",
    "is_personal_trainer": true,
    "display_name": "Juan Pérez",
    "entity_label": "Espacio de Trabajo",
    "timezone": "America/Mexico_City",
    "email": "juan.perez@trainer.com",
    "phone": "+525512345678",
    "address": null,
    "max_clients": 25,
    "specialties": ["CrossFit", "Nutrición Deportiva"]
  },
  "terminology": {
    "gym": "espacio de trabajo",
    "member": "cliente",
    "members": "clientes",
    "trainer": "asistente",
    "class": "sesión",
    "classes": "sesiones",
    "schedule": "agenda",
    "membership": "plan de entrenamiento",
    "event": "cita"
  },
  "features": {
    "chat": true,
    "notifications": true,
    "health_tracking": true,
    "nutrition": true,
    "show_multiple_trainers": false,
    "show_equipment_management": false,
    "show_class_schedule": false,
    "show_appointments": true,
    "show_client_progress": true,
    "show_session_packages": true,
    "simplified_billing": true,
    "max_clients_limit": true,
    "personal_branding": true
  },
  "navigation": [
    {"id": "dashboard", "label": "Dashboard", "icon": "home", "path": "/"},
    {"id": "clients", "label": "Mis Clientes", "icon": "users", "path": "/clients"},
    {"id": "appointments", "label": "Agenda", "icon": "calendar", "path": "/appointments"},
    {"id": "nutrition", "label": "Planes Nutricionales", "icon": "apple", "path": "/nutrition"},
    {"id": "progress", "label": "Progreso", "icon": "chart-line", "path": "/progress"},
    {"id": "payments", "label": "Pagos", "icon": "credit-card", "path": "/payments"},
    {"id": "chat", "label": "Mensajes", "icon": "message-circle", "path": "/chat"},
    {"id": "analytics", "label": "Estadísticas", "icon": "bar-chart", "path": "/analytics"},
    {"id": "settings", "label": "Configuración", "icon": "settings", "path": "/settings"}
  ],
  "quick_actions": [
    {
      "id": "add_client",
      "label": "Nuevo Cliente",
      "icon": "user-plus",
      "color": "primary",
      "action": "modal:add-client"
    },
    {
      "id": "schedule_session",
      "label": "Agendar Sesión",
      "icon": "calendar-plus",
      "color": "success",
      "action": "modal:schedule-session"
    },
    {
      "id": "create_nutrition_plan",
      "label": "Plan Nutricional",
      "icon": "clipboard",
      "color": "info",
      "action": "navigate:/nutrition/new"
    },
    {
      "id": "record_payment",
      "label": "Registrar Pago",
      "icon": "dollar-sign",
      "color": "warning",
      "action": "modal:record-payment"
    }
  ],
  "branding": {
    "logo_url": null,
    "primary_color": "#28a745",
    "secondary_color": "#6c757d",
    "accent_color": "#ffc107",
    "app_title": "Juan Pérez",
    "app_subtitle": "Entrenamiento Personalizado",
    "theme": "trainer",
    "show_logo": true,
    "compact_mode": true
  },
  "user_context": {
    "id": 101,
    "email": "juan.perez@trainer.com",
    "name": "Juan Pérez",
    "photo_url": null,
    "role": "OWNER",
    "role_label": "entrenador principal",
    "permissions": [
      "gym:read", "gym:write", "gym:delete",
      "members:read", "members:write", "members:delete",
      "billing:read", "billing:write",
      "settings:read", "settings:write",
      "analytics:read",
      "all:*"
    ]
  },
  "api_version": "1.0.0",
  "environment": "production"
}
```

---

#### GET `/context/workspace/stats`

Obtiene estadísticas del workspace actual.

**Autenticación**: Requerida
**Cache**: 5 minutos

**Ejemplo de Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/context/workspace/stats" \
  -H "Authorization: Bearer eyJ..." \
  -H "X-Gym-ID: 42"
```

**Response 200 OK** - Estadísticas de Entrenador:
```json
{
  "type": "trainer",
  "metrics": {
    "active_clients": 15,
    "max_clients": 25,
    "capacity_percentage": 60.0,
    "sessions_this_week": 23,
    "avg_sessions_per_client": 1.53,
    "client_retention_rate": 95.0,
    "revenue_this_month": 45000.00
  }
}
```

**Response 200 OK** - Estadísticas de Gimnasio:
```json
{
  "type": "gym",
  "metrics": {
    "total_members": 150,
    "active_trainers": 5,
    "active_classes": 20,
    "occupancy_rate": 75.0,
    "member_growth_rate": 5.2,
    "revenue_this_month": 250000.00
  }
}
```

---

## 📊 Modelos de Datos

### TrainerRegistrationRequest

```typescript
interface TrainerRegistrationRequest {
  // Información básica (requerida)
  email: string;              // Email válido
  first_name: string;         // 2-50 caracteres
  last_name: string;          // 2-50 caracteres

  // Información opcional
  phone?: string;             // Formato: +525512345678
  specialties?: string[];     // Máx 10 especialidades, 2-50 chars c/u
  certifications?: {
    name: string;             // Requerido
    year?: number;            // 1990-2030
    institution?: string;
    credential_id?: string;
  }[];
  timezone?: string;          // Default: America/Mexico_City
  max_clients?: number;       // 1-200, default: 30
  bio?: string;               // Máx 500 caracteres
}
```

### TrainerRegistrationResponse

```typescript
interface TrainerRegistrationResponse {
  success: boolean;           // Siempre true
  message: string;

  workspace: {
    id: number;
    name: string;
    subdomain: string;
    type: "personal_trainer";
    email: string;
    timezone: string;
    specialties: string[];
    max_clients: number;
  };

  user: {
    id: number;
    email: string;
    name: string;
    role: "TRAINER";
  };

  modules_activated: string[];
  payment_plans: string[];    // Vacío (se crean manualmente)
  stripe_onboarding_url?: string;
  next_steps: string[];
}
```

### WorkspaceContext

```typescript
interface WorkspaceContext {
  workspace: {
    id: number;
    name: string;
    type: "gym" | "personal_trainer";
    is_personal_trainer: boolean;
    display_name: string;
    entity_label: string;
    timezone: string;
    email: string;
    phone?: string;
    address?: string;
    max_clients?: number;
    specialties?: string[];
  };

  terminology: Record<string, string>;
  features: Record<string, boolean>;
  navigation: MenuItem[];
  quick_actions: QuickAction[];
  branding: BrandingConfig;
  user_context: UserContext;
  api_version: string;
  environment: string;
}
```

---

## 💡 Ejemplos Completos

### Flujo Completo de Registro

```javascript
// 1. Validar email antes de mostrar formulario
async function checkEmailAvailability(email) {
  const response = await fetch(
    `http://localhost:8000/api/v1/auth/trainer/check-email/${email}`
  );
  const data = await response.json();

  if (!data.available) {
    throw new Error('Email ya registrado');
  }

  return true;
}

// 2. Registrar entrenador
async function registerTrainer(trainerData) {
  const response = await fetch(
    'http://localhost:8000/api/v1/auth/register-trainer',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(trainerData)
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail.message || 'Error en registro');
  }

  return await response.json();
}

// 3. Usar el resultado
async function onSubmitRegistration(formData) {
  try {
    // Validar email
    await checkEmailAvailability(formData.email);

    // Registrar
    const result = await registerTrainer({
      email: formData.email,
      first_name: formData.firstName,
      last_name: formData.lastName,
      phone: formData.phone,
      specialties: formData.specialties,
      certifications: formData.certifications,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      max_clients: formData.maxClients || 30,
      bio: formData.bio
    });

    // Guardar workspace ID y user ID
    localStorage.setItem('gym_id', result.workspace.id);
    localStorage.setItem('user_id', result.user.id);

    // Redirigir a Stripe si es necesario
    if (result.stripe_onboarding_url) {
      window.location.href = result.stripe_onboarding_url;
    } else {
      // Redirigir al dashboard
      window.location.href = '/dashboard';
    }

  } catch (error) {
    console.error('Error en registro:', error);
    showError(error.message);
  }
}
```

### Obtener Contexto y Adaptar UI

```javascript
// 1. Obtener contexto después del login
async function loadWorkspaceContext(token, gymId) {
  const response = await fetch(
    'http://localhost:8000/api/v1/context/workspace',
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId
      }
    }
  );

  if (!response.ok) {
    throw new Error('Error cargando contexto');
  }

  return await response.json();
}

// 2. Adaptar UI basada en contexto
async function setupUI(context) {
  // Actualizar terminología
  document.querySelector('.members-label').textContent =
    context.terminology.members; // "clientes" vs "miembros"

  // Configurar navegación
  renderNavigation(context.navigation);

  // Mostrar/ocultar features
  if (!context.features.show_equipment_management) {
    document.querySelector('.equipment-section').style.display = 'none';
  }

  if (context.features.show_appointments) {
    document.querySelector('.appointments-section').style.display = 'block';
  }

  // Aplicar branding
  document.documentElement.style.setProperty(
    '--primary-color',
    context.branding.primary_color
  );

  document.querySelector('.app-title').textContent =
    context.branding.app_title;

  // Mostrar quick actions
  renderQuickActions(context.quick_actions);
}

// 3. Implementar
async function initApp() {
  const token = localStorage.getItem('auth_token');
  const gymId = localStorage.getItem('gym_id');

  try {
    const context = await loadWorkspaceContext(token, gymId);
    await setupUI(context);
  } catch (error) {
    console.error('Error inicializando app:', error);
  }
}
```

---

## 📝 Casos de Uso

### Caso 1: Registro de Entrenador con Certificaciones

**Escenario**: María, entrenadora de CrossFit, quiere registrarse

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register-trainer" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "maria.gonzalez@crossfit.com",
    "first_name": "María",
    "last_name": "González",
    "phone": "+525587654321",
    "specialties": [
      "CrossFit",
      "Levantamiento Olímpico",
      "Movilidad"
    ],
    "certifications": [
      {
        "name": "CrossFit Level 2 Trainer",
        "year": 2021,
        "institution": "CrossFit Inc.",
        "credential_id": "CF-L2-12345"
      },
      {
        "name": "USA Weightlifting Level 1",
        "year": 2020,
        "institution": "USA Weightlifting"
      }
    ],
    "timezone": "America/Mexico_City",
    "max_clients": 20,
    "bio": "Entrenadora CrossFit Level 2 con especialización en levantamiento olímpico. Enfoque en técnica y prevención de lesiones."
  }'
```

**Resultado**: Workspace creado con ID 43, subdomain `maria-gonzalez`

---

### Caso 2: Validación de Email en Tiempo Real

**Escenario**: Formulario de registro con validación en tiempo real

```javascript
// Debounced email validation
const validateEmail = debounce(async (email) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/auth/trainer/check-email/${email}`
  );
  const data = await response.json();

  const emailInput = document.querySelector('#email');
  const feedback = document.querySelector('#email-feedback');

  if (data.available) {
    emailInput.classList.add('is-valid');
    emailInput.classList.remove('is-invalid');
    feedback.textContent = '✓ Email disponible';
    feedback.className = 'valid-feedback';
  } else {
    emailInput.classList.add('is-invalid');
    emailInput.classList.remove('is-valid');
    feedback.textContent = '✗ Email ya registrado';
    feedback.className = 'invalid-feedback';
  }
}, 500);

document.querySelector('#email').addEventListener('input', (e) => {
  validateEmail(e.target.value);
});
```

---

### Caso 3: Dashboard Adaptado para Entrenador

**Escenario**: Cargar dashboard con métricas específicas de entrenador

```javascript
async function loadTrainerDashboard(token, gymId) {
  // Obtener estadísticas
  const statsResponse = await fetch(
    'http://localhost:8000/api/v1/context/workspace/stats',
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId
      }
    }
  );

  const stats = await statsResponse.json();

  if (stats.type === 'trainer') {
    // Renderizar métricas de entrenador
    document.querySelector('#active-clients').textContent =
      stats.metrics.active_clients;

    document.querySelector('#capacity').textContent =
      `${stats.metrics.capacity_percentage.toFixed(0)}%`;

    document.querySelector('#sessions-week').textContent =
      stats.metrics.sessions_this_week;

    document.querySelector('#revenue-month').textContent =
      `$${stats.metrics.revenue_this_month.toLocaleString('es-MX')}`;

    // Mostrar barra de capacidad
    document.querySelector('#capacity-bar').style.width =
      `${stats.metrics.capacity_percentage}%`;

    // Actualizar gráficas específicas de entrenador
    updateClientProgressChart();
    updateSessionFrequencyChart();
  }
}
```

---

## ⚠️ Errores y Troubleshooting

### Error: "Email ya registrado"

**Código**: `EMAIL_EXISTS` o `WORKSPACE_EXISTS`

**Solución**:
1. Verificar si el usuario puede iniciar sesión con ese email
2. Si olvidó su contraseña, usar flujo de recuperación
3. Si es un error, contactar soporte

```bash
# Verificar si el email existe
curl -X GET "http://localhost:8000/api/v1/auth/trainer/check-email/test@trainer.com"
```

---

### Error: "Rate limit exceeded"

**Código**: `429 Too Many Requests`

**Causa**: Excediste el límite de 5 registros/hora o 20/día

**Solución**:
1. Esperar una hora antes de reintentar
2. En desarrollo, usar diferentes IPs o VPN
3. En producción, implementar caché en frontend

---

### Error: "Formato de teléfono inválido"

**Causa**: Teléfono no está en formato internacional

**Solución**:
```javascript
// Validar y formatear teléfono
function formatPhone(phone) {
  // Eliminar espacios y guiones
  let clean = phone.replace(/[\s-]/g, '');

  // Agregar + si no lo tiene
  if (!clean.startsWith('+')) {
    clean = '+52' + clean; // Agregar código de país México
  }

  return clean;
}

// Uso
const phone = formatPhone('55 1234 5678');
// Resultado: '+525512345678'
```

---

### Error: "Stripe not configured"

**Causa**: Variables de entorno de Stripe no configuradas

**Solución**:
1. El registro continuará sin Stripe
2. Configurar Stripe más tarde en settings
3. Agregar variables de entorno:
```bash
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 🚦 Rate Limiting

### Límites por Endpoint

| Endpoint | Límite | Ventana |
|----------|--------|---------|
| `/auth/register-trainer` | 5 requests | 1 hora |
| `/auth/register-trainer` | 20 requests | 1 día |
| `/auth/trainer/check-email/{email}` | 30 requests | 1 minuto |
| `/auth/trainer/validate-subdomain/{subdomain}` | 30 requests | 1 minuto |
| `/context/workspace` | 60 requests | 1 minuto |
| `/context/workspace/stats` | 60 requests | 1 minuto |

### Headers de Rate Limit

```http
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 4
X-RateLimit-Reset: 1640995200
```

### Manejo en Frontend

```javascript
async function registerWithRetry(data, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch('/api/v1/auth/register-trainer', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: {'Content-Type': 'application/json'}
      });

      if (response.status === 429) {
        // Rate limit excedido
        const retryAfter = response.headers.get('Retry-After') || 60;
        console.log(`Rate limit, esperando ${retryAfter}s...`);
        await sleep(retryAfter * 1000);
        continue;
      }

      return await response.json();

    } catch (error) {
      if (i === maxRetries - 1) throw error;
    }
  }
}
```

---

## 🧪 Testing

### Test 1: Registro Exitoso

```bash
# Request
curl -X POST "http://localhost:8000/api/v1/auth/register-trainer" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test.trainer@example.com",
    "first_name": "Test",
    "last_name": "Trainer",
    "specialties": ["Test"]
  }'

# Expected Response: 201 Created
# Verificar: workspace.id, user.id, modules_activated
```

### Test 2: Email Duplicado

```bash
# Request (segundo intento con mismo email)
curl -X POST "http://localhost:8000/api/v1/auth/register-trainer" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test.trainer@example.com",
    "first_name": "Test",
    "last_name": "Trainer"
  }'

# Expected Response: 400 Bad Request
# error_code: "WORKSPACE_EXISTS"
```

### Test 3: Validación de Email

```bash
# Request
curl -X GET "http://localhost:8000/api/v1/auth/trainer/check-email/test.trainer@example.com"

# Expected Response: 200 OK
# available: false
# has_workspace: true
```

### Test 4: Contexto del Workspace

```bash
# Request
curl -X GET "http://localhost:8000/api/v1/context/workspace" \
  -H "Authorization: Bearer {token}" \
  -H "X-Gym-ID: 42"

# Expected Response: 200 OK
# workspace.type: "personal_trainer"
# features.show_appointments: true
# features.show_equipment_management: false
```

### Test Suite Completo (Python)

```python
import pytest
import requests

BASE_URL = "http://localhost:8000/api/v1"

def test_register_trainer():
    """Test registro exitoso"""
    response = requests.post(
        f"{BASE_URL}/auth/register-trainer",
        json={
            "email": "pytest@trainer.com",
            "first_name": "PyTest",
            "last_name": "Trainer",
            "specialties": ["Testing"]
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["workspace"]["type"] == "personal_trainer"
    assert "users" in data["modules_activated"]

def test_duplicate_email():
    """Test email duplicado"""
    response = requests.post(
        f"{BASE_URL}/auth/register-trainer",
        json={
            "email": "pytest@trainer.com",
            "first_name": "PyTest",
            "last_name": "Trainer"
        }
    )

    assert response.status_code == 400
    data = response.json()
    assert "WORKSPACE_EXISTS" in str(data)

def test_check_email_availability():
    """Test verificación de email"""
    response = requests.get(
        f"{BASE_URL}/auth/trainer/check-email/available@trainer.com"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True

def test_invalid_phone_format():
    """Test formato de teléfono inválido"""
    response = requests.post(
        f"{BASE_URL}/auth/register-trainer",
        json={
            "email": "phone.test@trainer.com",
            "first_name": "Phone",
            "last_name": "Test",
            "phone": "invalid-phone"
        }
    )

    assert response.status_code == 422  # Validation error
```

---

## 📚 Recursos Adicionales

### Swagger UI
```
http://localhost:8000/api/v1/docs
```

### ReDoc
```
http://localhost:8000/api/v1/redoc
```

### OpenAPI Schema
```
http://localhost:8000/api/v1/openapi.json
```

### Scripts de Ejemplo

```bash
# Registro desde CLI
python scripts/setup_trainer.py juan@trainer.com Juan Pérez

# Aplicar migración
python scripts/apply_trainer_migration.py --force

# Revertir migración
python scripts/apply_trainer_migration.py --rollback
```

---

## 📞 Soporte

Para dudas o problemas:
- Consultar documentación en `/api/v1/docs`
- Revisar logs en `logs/app.log`
- Crear issue en GitHub
- Contactar soporte técnico

---

**Versión**: 1.0.0
**Última actualización**: 2024-01-24
**Autor**: Claude Code
**Licencia**: Propiedad de GymAPI