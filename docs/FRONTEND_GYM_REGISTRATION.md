# Documentación para Frontend: Creación de Gimnasio

## 📋 Tabla de Contenidos
- [Resumen General](#resumen-general)
- [Endpoint](#endpoint)
- [Flujo Completo](#flujo-completo)
- [Request Schema](#request-schema)
- [Response Schema](#response-schema)
- [Códigos de Error](#códigos-de-error)
- [Validaciones del Frontend](#validaciones-del-frontend)
- [Ejemplos de Implementación](#ejemplos-de-implementación)
- [Análisis de Seguridad](#análisis-de-seguridad)
- [Casos de Uso](#casos-de-uso)
- [Problemas Conocidos](#problemas-conocidos)

---

## 🎯 Resumen General

Este endpoint permite crear un nuevo gimnasio con su dueño de forma completamente automática, sin necesidad de redireccionar a Auth0.

### ¿Qué Crea Automáticamente?
1. ✅ Usuario en Auth0 con contraseña
2. ✅ Usuario en base de datos local con rol `ADMIN`
3. ✅ Gimnasio tipo `gym` (no personal trainer)
4. ✅ Relación usuario-gimnasio como `OWNER`
5. ✅ 9 módulos esenciales activados
6. ✅ Email de verificación enviado automáticamente

### Características Principales
- 🔒 **Sin autenticación**: Endpoint público para registro
- ⚡ **Rate limiting**: 5/hora, 20/día por IP
- 🔄 **Rollback completo**: Si falla, revierte TODO (BD + Auth0)
- 📧 **Email automático**: Auth0 envía verificación al usuario
- 🌍 **Multi-timezone**: Soporte completo de zonas horarias

---

## 🔌 Endpoint

### URL
```
POST /api/v1/auth/register-gym-owner
```

### Headers
```http
Content-Type: application/json
```

**⚠️ IMPORTANTE:** Este endpoint NO requiere token de autenticación.

### Rate Limiting
```
X-RateLimit-Limit: 5/hora, 20/día
X-RateLimit-Remaining: (número de requests restantes)
X-RateLimit-Reset: (timestamp de reset)
```

Si excedes el límite, recibirás:
```http
HTTP/1.1 429 Too Many Requests
```

---

## 🔄 Flujo Completo

### Diagrama de Flujo
```
┌─────────────────────────────────────────────────────────┐
│ 1. Frontend envía POST con datos del owner y gym       │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Validaciones Pydantic                                │
│    • Email formato válido                               │
│    • Contraseña: 8+ chars, mayúscula, minúscula, número│
│    • Teléfono formato internacional                     │
│    • Timezone válido (pytz)                             │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Verificar Email Único                                │
│    • BD Local: SELECT * FROM users WHERE email = ?      │
│    • Auth0: GET /api/v2/users?q=email:"..."            │
│    ❌ Si existe → 400 EMAIL_EXISTS                      │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Crear Usuario en Auth0                               │
│    POST https://{domain}/api/v2/users                   │
│    {                                                     │
│      "email": "...",                                     │
│      "password": "...",  ← Hasheado por Auth0           │
│      "connection": "Username-Password-Authentication",   │
│      "verify_email": true  ← Envía email automático     │
│    }                                                     │
│    ✅ Retorna: auth0_user_id                            │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Crear Usuario en BD Local                            │
│    INSERT INTO users (auth0_id, email, role=ADMIN, ...) │
│    • Guarda auth0_id para sincronización                │
│    • role = ADMIN (rol local)                           │
│    • is_active = true                                   │
│    ⚠️ db.flush() - NO commit todavía                    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 6. Crear Gimnasio                                       │
│    • Generar subdomain único: "fitness-pro-mexico"      │
│    • type = "gym" (gimnasio tradicional)                │
│    • INSERT INTO gyms (name, subdomain, timezone, ...)  │
│    ⚠️ db.flush() - NO commit todavía                    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 7. Crear Relación UserGym                               │
│    INSERT INTO user_gyms (user_id, gym_id, role=OWNER)  │
│    • role = OWNER (rol específico del gym)              │
│    • membership_type = "owner"                          │
│    ⚠️ db.flush() - NO commit todavía                    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 8. Activar Módulos Esenciales                           │
│    INSERT INTO gym_modules (9 módulos):                 │
│    • users, schedule, events, chat, billing             │
│    • health, nutrition, surveys, equipment              │
│    ⚠️ db.flush() - NO commit todavía                    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 9. COMMIT TRANSACCIONAL                                 │
│    db.commit()                                          │
│    ✅ Si éxito → 201 Created                            │
│    ❌ Si falla → Rollback completo (paso 10)            │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│ 10. Respuesta Exitosa                                   │
│     {                                                    │
│       "success": true,                                  │
│       "gym": {...},                                     │
│       "user": {...},                                    │
│       "modules_activated": [...],                       │
│       "next_steps": [...]                               │
│     }                                                   │
└─────────────────────────────────────────────────────────┘
```

### ⚠️ Rollback en Caso de Error
Si falla en **cualquier paso 5-9**:
1. `db.rollback()` - Revierte TODAS las operaciones en BD local
2. `DELETE /api/v2/users/{auth0_user_id}` - Elimina usuario de Auth0
3. Retorna `500 INTERNAL_ERROR`

**Ejemplo:** Si falla al crear el gimnasio (paso 6):
- ✅ Usuario de Auth0 eliminado
- ✅ Usuario de BD local no guardado (rollback)
- ✅ Estado consistente: como si nunca hubiera pasado nada

---

## 📝 Request Schema

### Campos Requeridos

```typescript
interface GymOwnerRegistrationRequest {
  // Información del Dueño (Requeridos)
  email: string;           // Email válido
  password: string;        // 8-128 caracteres
  first_name: string;      // 2-50 caracteres
  last_name: string;       // 2-50 caracteres

  // Información del Gimnasio (Requeridos)
  gym_name: string;        // 3-255 caracteres

  // Campos Opcionales
  phone?: string;          // Formato internacional
  gym_address?: string;    // Max 255 caracteres
  gym_phone?: string;      // Formato internacional
  gym_email?: string;      // Email válido
  timezone?: string;       // Default: "America/Mexico_City"
}
```

### Validaciones Detalladas

#### 1️⃣ Email (`email`)
- **Formato:** RFC 5322 compliant
- **Validación:** Debe ser único (BD local + Auth0)
- **Ejemplo válido:** `"owner@gimnasio.com"`
- **Ejemplo inválido:** `"owner@gimnasio"` (sin dominio)

#### 2️⃣ Contraseña (`password`)
- **Longitud:** 8-128 caracteres
- **Requisitos:**
  - ✅ Al menos 1 mayúscula (`A-Z`)
  - ✅ Al menos 1 minúscula (`a-z`)
  - ✅ Al menos 1 número (`0-9`)
- **Ejemplo válido:** `"SecurePass123"`
- **Ejemplo inválido:** `"weakpass"` (sin mayúscula ni número)

**⚠️ IMPORTANTE:** La contraseña se envía en texto plano por HTTPS y es hasheada automáticamente por Auth0. **NUNCA** se guarda en BD local.

#### 3️⃣ Teléfono (`phone`, `gym_phone`)
- **Formato:** Internacional con código de país
- **Regex:** `^\+?[1-9]\d{1,14}$`
- **Ejemplo válido:** `"+525512345678"` (México)
- **Ejemplo inválido:** `"5512345678"` (sin código de país)
- **Opcional:** Puede ser `null`

#### 4️⃣ Timezone (`timezone`)
- **Formato:** Timezone de pytz
- **Default:** `"America/Mexico_City"`
- **Ejemplos válidos:**
  - `"America/Los_Angeles"`
  - `"Europe/Madrid"`
  - `"Asia/Tokyo"`
- **Ejemplo inválido:** `"GMT-5"` (usar formato pytz)

#### 5️⃣ Nombre del Gimnasio (`gym_name`)
- **Longitud:** 3-255 caracteres
- **Uso:** Se auto-genera `subdomain` a partir de este nombre
- **Ejemplo:** `"Fitness Pro México"` → `"fitness-pro-mexico"`

### Ejemplo Completo de Request

```json
{
  "email": "owner@fitnesspro.com",
  "password": "SecurePass123",
  "first_name": "Juan",
  "last_name": "Pérez",
  "phone": "+525512345678",
  "gym_name": "Fitness Pro México",
  "gym_address": "Av. Reforma 123, Col. Centro, CDMX",
  "gym_phone": "+525587654321",
  "gym_email": "contacto@fitnesspro.com",
  "timezone": "America/Mexico_City"
}
```

### Ejemplo Mínimo de Request

```json
{
  "email": "owner@gym.com",
  "password": "SecurePass123",
  "first_name": "Juan",
  "last_name": "Pérez",
  "gym_name": "Mi Gimnasio"
}
```

---

## ✅ Response Schema

### Respuesta Exitosa (201 Created)

```typescript
interface GymOwnerRegistrationResponse {
  success: boolean;              // Siempre true
  message: string;               // Mensaje de éxito

  gym: {
    id: number;                  // ID del gimnasio creado
    name: string;                // Nombre del gimnasio
    subdomain: string;           // Subdomain único generado
    type: string;                // Siempre "gym"
    timezone: string;            // Zona horaria configurada
    is_active: boolean;          // Siempre true
  };

  user: {
    id: number;                  // ID del usuario en BD local
    email: string;               // Email del usuario
    name: string;                // Nombre completo
    role: string;                // Siempre "ADMIN"
  };

  modules_activated: string[];   // Array de módulos activados
  stripe_setup_required: boolean; // Siempre true
  next_steps: string[];          // Pasos sugeridos
}
```

### Ejemplo de Respuesta Exitosa

```json
{
  "success": true,
  "message": "Gimnasio y usuario creados exitosamente",
  "gym": {
    "id": 42,
    "name": "Fitness Pro México",
    "subdomain": "fitness-pro-mexico",
    "type": "gym",
    "timezone": "America/Mexico_City",
    "is_active": true
  },
  "user": {
    "id": 123,
    "email": "owner@fitnesspro.com",
    "name": "Juan Pérez",
    "role": "ADMIN"
  },
  "modules_activated": [
    "users",
    "schedule",
    "events",
    "chat",
    "billing",
    "health",
    "nutrition",
    "surveys",
    "equipment"
  ],
  "stripe_setup_required": true,
  "next_steps": [
    "Verificar email haciendo clic en el enlace enviado",
    "Configurar Stripe Connect para pagos",
    "Configurar horarios del gimnasio",
    "Crear clases y horarios",
    "Agregar primeros miembros"
  ]
}
```

---

## ❌ Códigos de Error

### 1️⃣ Validación de Campos (422 Unprocessable Entity)

**Cuándo:** Datos inválidos en el request (antes de llegar al servicio)

```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "La contraseña debe contener al menos una mayúscula",
      "type": "value_error"
    }
  ]
}
```

**Ejemplos de casos:**
- Contraseña débil (sin mayúscula, número, etc.)
- Email con formato inválido
- Teléfono sin código de país
- Timezone no válido
- Campos requeridos faltantes

**Cómo manejarlo en frontend:**
```typescript
if (error.status === 422) {
  // Mostrar errores de validación campo por campo
  error.detail.forEach(err => {
    showFieldError(err.loc[1], err.msg);
  });
}
```

### 2️⃣ Email Duplicado (400 Bad Request)

**Cuándo:** El email ya está registrado (BD local o Auth0)

```json
{
  "detail": {
    "success": false,
    "message": "El email owner@fitnesspro.com ya está registrado",
    "error_code": "EMAIL_EXISTS",
    "details": {
      "email": "owner@fitnesspro.com",
      "gym_name": "Fitness Pro México"
    }
  }
}
```

**Cómo manejarlo:**
```typescript
if (error.status === 400 && error.detail.error_code === 'EMAIL_EXISTS') {
  showError("Este email ya está registrado. ¿Quieres iniciar sesión?");
  redirectToLogin();
}
```

### 3️⃣ Validación General (400 Bad Request)

**Cuándo:** Otras validaciones de negocio

```json
{
  "detail": {
    "success": false,
    "message": "Error de validación",
    "error_code": "VALIDATION_ERROR",
    "details": {
      "email": "owner@gym.com",
      "gym_name": "Test Gym"
    }
  }
}
```

**Códigos de error posibles:**
- `EMAIL_EXISTS` - Email ya registrado
- `WEAK_PASSWORD` - Contraseña no cumple requisitos
- `VALIDATION_ERROR` - Error genérico de validación

### 4️⃣ Rate Limit Excedido (429 Too Many Requests)

**Cuándo:** Más de 5 requests/hora o 20/día desde la misma IP

```json
{
  "detail": "Rate limit exceeded"
}
```

**Headers de respuesta:**
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640000000
Retry-After: 3600
```

**Cómo manejarlo:**
```typescript
if (error.status === 429) {
  const retryAfter = error.headers['retry-after'];
  showError(`Demasiados intentos. Intenta de nuevo en ${retryAfter} segundos`);
  disableFormFor(retryAfter);
}
```

### 5️⃣ Error Interno (500 Internal Server Error)

**Cuándo:** Error en el servidor (BD, Auth0, etc.)

```json
{
  "detail": {
    "success": false,
    "message": "Error interno al crear el gimnasio. Por favor intente nuevamente.",
    "error_code": "INTERNAL_ERROR",
    "details": {
      "email": "owner@gym.com",
      "gym_name": "Test Gym"
    }
  }
}
```

**⚠️ IMPORTANTE:** Si recibes este error, el rollback ya se ejecutó automáticamente. El usuario NO fue creado ni en Auth0 ni en la BD.

**Cómo manejarlo:**
```typescript
if (error.status === 500) {
  showError("Ocurrió un error. Por favor intenta de nuevo.");
  logErrorToMonitoring(error);
  // Usuario puede intentar de nuevo sin problemas
}
```

### 6️⃣ Servicio No Disponible (503 Service Unavailable)

**Cuándo:** Auth0 no responde o está caído

```json
{
  "detail": "Error al crear usuario en Auth0: Connection timeout"
}
```

---

## 🎨 Validaciones del Frontend

### Validación en Tiempo Real (antes de enviar)

```typescript
// 1. Email
const validateEmail = (email: string): boolean => {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email);
};

// 2. Contraseña
const validatePassword = (password: string): {
  valid: boolean;
  errors: string[];
} => {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push("Mínimo 8 caracteres");
  }
  if (!/[A-Z]/.test(password)) {
    errors.push("Debe contener al menos una mayúscula");
  }
  if (!/[a-z]/.test(password)) {
    errors.push("Debe contener al menos una minúscula");
  }
  if (!/\d/.test(password)) {
    errors.push("Debe contener al menos un número");
  }

  return {
    valid: errors.length === 0,
    errors
  };
};

// 3. Teléfono (opcional)
const validatePhone = (phone: string | null): boolean => {
  if (!phone) return true; // Opcional
  const cleaned = phone.replace(/[\s-]/g, '');
  return /^\+?[1-9]\d{1,14}$/.test(cleaned);
};

// 4. Timezone
const VALID_TIMEZONES = [
  'America/Mexico_City',
  'America/Los_Angeles',
  'America/New_York',
  // ... agregar más según necesidad
];

const validateTimezone = (tz: string): boolean => {
  return VALID_TIMEZONES.includes(tz);
};
```

### Indicadores Visuales de Fortaleza de Contraseña

```typescript
const getPasswordStrength = (password: string): {
  score: number;
  label: string;
  color: string;
} => {
  let score = 0;

  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++; // Símbolos especiales

  if (score <= 2) return { score, label: 'Débil', color: 'red' };
  if (score <= 4) return { score, label: 'Media', color: 'orange' };
  return { score, label: 'Fuerte', color: 'green' };
};
```

---

## 💻 Ejemplos de Implementación

### React + TypeScript

```typescript
import { useState } from 'react';

interface GymRegistrationForm {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  gym_name: string;
  gym_address: string;
  gym_phone: string;
  gym_email: string;
  timezone: string;
}

const GymRegistration: React.FC = () => {
  const [form, setForm] = useState<GymRegistrationForm>({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: '',
    gym_name: '',
    gym_address: '',
    gym_phone: '',
    gym_email: '',
    timezone: 'America/Mexico_City'
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        'https://api.tudominio.com/api/v1/auth/register-gym-owner',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(form)
        }
      );

      if (!response.ok) {
        const errorData = await response.json();

        // Manejar diferentes tipos de error
        if (response.status === 422) {
          // Errores de validación
          setError(errorData.detail[0].msg);
        } else if (response.status === 400) {
          // Email duplicado u otro error de negocio
          setError(errorData.detail.message);
        } else if (response.status === 429) {
          // Rate limit
          setError('Demasiados intentos. Por favor espera un momento.');
        } else {
          setError('Error al crear el gimnasio. Por favor intenta de nuevo.');
        }
        return;
      }

      const data = await response.json();

      // Éxito - Mostrar mensaje y redirigir
      alert(data.message);

      // Redirigir a página de verificación de email
      window.location.href = '/verify-email?email=' + encodeURIComponent(data.user.email);

    } catch (err) {
      setError('Error de conexión. Verifica tu internet.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Campos del formulario */}
      <input
        type="email"
        value={form.email}
        onChange={e => setForm({ ...form, email: e.target.value })}
        required
      />

      <input
        type="password"
        value={form.password}
        onChange={e => setForm({ ...form, password: e.target.value })}
        required
        minLength={8}
      />

      {/* ... más campos ... */}

      {error && <div className="error">{error}</div>}

      <button type="submit" disabled={loading}>
        {loading ? 'Creando...' : 'Crear Gimnasio'}
      </button>
    </form>
  );
};
```

### Vue 3 + Composition API

```vue
<script setup lang="ts">
import { ref, reactive } from 'vue';

interface GymRegistrationForm {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  gym_name: string;
  timezone: string;
}

const form = reactive<GymRegistrationForm>({
  email: '',
  password: '',
  first_name: '',
  last_name: '',
  phone: '',
  gym_name: '',
  timezone: 'America/Mexico_City'
});

const loading = ref(false);
const error = ref<string | null>(null);

const submitRegistration = async () => {
  loading.value = true;
  error.value = null;

  try {
    const response = await fetch('/api/v1/auth/register-gym-owner', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    });

    if (!response.ok) {
      const errorData = await response.json();
      error.value = errorData.detail?.message || 'Error al crear gimnasio';
      return;
    }

    const data = await response.json();

    // Redirigir a dashboard
    window.location.href = `/dashboard/${data.gym.id}`;

  } catch (err) {
    error.value = 'Error de conexión';
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <form @submit.prevent="submitRegistration">
    <!-- Campos del formulario -->
  </form>
</template>
```

---

## 🔒 Análisis de Seguridad

### ✅ Fortalezas de Seguridad

1. **Contraseña Nunca se Guarda Localmente**
   - ✅ Solo se envía a Auth0
   - ✅ Auth0 la hashea con bcrypt
   - ✅ Backend nunca la almacena

2. **Email de Verificación Obligatorio**
   - ✅ `verify_email: true` en Auth0
   - ✅ Usuario debe verificar antes de usar la cuenta
   - ✅ Previene registros con emails falsos

3. **Rate Limiting Estricto**
   - ✅ 5 registros/hora por IP
   - ✅ 20 registros/día por IP
   - ✅ Previene spam y ataques de fuerza bruta

4. **Validaciones Robustas**
   - ✅ Email único verificado en 2 lugares (BD + Auth0)
   - ✅ Contraseña con requisitos mínimos
   - ✅ Timezone validado contra lista oficial

5. **Rollback Transaccional Completo**
   - ✅ Si falla, TODO se revierte
   - ✅ Incluye eliminación de usuario en Auth0
   - ✅ Estado siempre consistente

### ⚠️ Consideraciones de Seguridad

1. **Contraseña en Tránsito**
   - ⚠️ Viaja en texto plano por HTTPS
   - ✅ **Mitigación:** HTTPS es obligatorio en producción
   - ✅ Auth0 la hashea inmediatamente al recibirla

2. **Email de Verificación**
   - ⚠️ Si Auth0 no puede enviar email, usuario se crea pero no puede login
   - ✅ **Mitigación:** Configurar correctamente email provider en Auth0

3. **Race Condition en Subdomain**
   - ⚠️ Dos registros simultáneos podrían generar mismo subdomain
   - ✅ **Mitigación:** UNIQUE constraint en BD causará error y rollback

4. **Exposición de Información**
   - ⚠️ Error 400 revela si un email existe
   - ⚠️ **Implicación:** Enumeration attack posible
   - ✅ **Mitigación:** Rate limiting previene enumeración masiva

### 🔐 Recomendaciones de Implementación

1. **HTTPS Obligatorio**
   ```nginx
   # Forzar HTTPS en Nginx
   if ($scheme != "https") {
       return 301 https://$host$request_uri;
   }
   ```

2. **CORS Configurado**
   ```python
   # Solo permitir dominios específicos
   ALLOWED_ORIGINS = [
       "https://app.tudominio.com",
       "https://www.tudominio.com"
   ]
   ```

3. **Logging de Seguridad**
   - ✅ Loguear intentos fallidos (sin incluir contraseñas)
   - ✅ Monitorear rate limiting
   - ✅ Alertas de múltiples fallos

---

## 📱 Casos de Uso

### Caso 1: Registro Exitoso Simple

**Escenario:** Usuario completa todos los campos requeridos correctamente

```
1. Usuario ingresa datos válidos
2. Click en "Crear Gimnasio"
3. Frontend valida campos
4. Envía POST al endpoint
5. Backend crea todo exitosamente
6. Retorna 201 con datos
7. Frontend muestra: "¡Registro exitoso! Revisa tu email para verificar tu cuenta"
8. Redirige a página de verificación de email
```

### Caso 2: Email Duplicado

**Escenario:** Usuario intenta registrarse con email ya existente

```
1. Usuario ingresa datos con email existente
2. Click en "Crear Gimnasio"
3. Envía POST al endpoint
4. Backend detecta email duplicado en paso 3 del flujo
5. Retorna 400 EMAIL_EXISTS
6. Frontend muestra: "Este email ya está registrado. ¿Quieres iniciar sesión?"
7. Botón para ir a login
```

### Caso 3: Contraseña Débil

**Escenario:** Usuario ingresa contraseña sin mayúsculas

```
1. Usuario ingresa "weakpass123"
2. Frontend valida en tiempo real
3. Muestra indicador "Contraseña débil - Falta mayúscula"
4. Usuario intenta enviar
5. Frontend bloquea envío
6. Usuario corrige a "Weakpass123"
7. Validación pasa, envía POST
8. Éxito
```

### Caso 4: Rate Limit Excedido

**Escenario:** Spammer intenta crear múltiples gimnasios

```
1. Spammer envía 6 requests en 1 hora
2. Primeras 5 requests procesadas normalmente
3. Request #6 recibe 429 Too Many Requests
4. Frontend muestra: "Demasiados intentos. Intenta en 45 minutos"
5. Deshabilita formulario temporalmente
6. Muestra countdown
```

### Caso 5: Error de Auth0

**Escenario:** Auth0 temporalmente no disponible

```
1. Usuario ingresa datos válidos
2. Envía POST
3. Backend intenta crear usuario en Auth0
4. Auth0 retorna timeout
5. Backend ejecuta rollback automático
6. Retorna 500 INTERNAL_ERROR
7. Frontend muestra: "Error temporal. Por favor intenta de nuevo"
8. Usuario puede reintentar inmediatamente (no se creó nada)
```

---

## ⚠️ Problemas Conocidos

### 1. Email Verification No Garantizada

**Problema:** Si Auth0 no puede enviar email (mal configurado), el usuario se crea pero no recibe verificación.

**Impacto:** Usuario no puede iniciar sesión hasta verificar.

**Solución Temporal:**
- Admin puede re-enviar email de verificación desde Auth0 Dashboard
- O marcar email como verificado manualmente

**Solución Permanente:**
- Configurar correctamente email provider en Auth0 (SendGrid, etc.)
- Implementar webhook para detectar emails no enviados

### 2. Subdomain Generado Puede Ser Largo

**Problema:** Nombres de gimnasios largos generan subdomains largos.

**Ejemplo:** `"Centro de Acondicionamiento Físico y Bienestar Integral"` → `"centro-de-acondicionamiento-fisico-y-bienestar-integral"` (truncado a 50 chars)

**Impacto:** Subdomain puede no ser descriptivo.

**Workaround Frontend:**
- Sugerir al usuario un "nombre corto" para el subdomain
- Permitir editar subdomain antes de enviar

### 3. Race Condition en Subdomain

**Problema:** Dos usuarios registran gimnasios con el mismo nombre al mismo tiempo.

**Probabilidad:** Muy baja (requiere milisegundos de diferencia)

**Mitigación:** UNIQUE constraint en BD + rollback automático

**Resultado:** Uno de los dos recibirá error 500 y deberá reintentar

### 4. Rate Limiting Compartido por IP

**Problema:** Usuarios en la misma red (ej: gimnasio, oficina) comparten el mismo límite.

**Impacto:** Si alguien spamea, afecta a todos en esa IP.

**Solución Temporal:** Aumentar límite diario a 20 (ya implementado)

**Solución Futura:** Rate limiting por email además de IP

---

## 🎯 Checklist de Integración

### Backend

- [ ] Variables de entorno configuradas
  - [ ] `AUTH0_DOMAIN`
  - [ ] `AUTH0_MGMT_CLIENT_ID`
  - [ ] `AUTH0_MGMT_CLIENT_SECRET`
- [ ] Database connection activa
- [ ] Redis activo (para rate limiting)
- [ ] Email provider configurado en Auth0
- [ ] HTTPS habilitado en producción
- [ ] CORS configurado con dominios permitidos

### Frontend

- [ ] Validaciones en tiempo real implementadas
- [ ] Indicador de fortaleza de contraseña
- [ ] Manejo de todos los códigos de error (422, 400, 429, 500, 503)
- [ ] Loading states durante el registro
- [ ] Mensajes de error user-friendly
- [ ] Redirección post-registro a verificación de email
- [ ] Rate limiting visible (deshabilitar botón si excede)
- [ ] HTTPS forzado

### Testing

- [ ] Registro exitoso con campos mínimos
- [ ] Registro exitoso con todos los campos
- [ ] Email duplicado rechazado
- [ ] Contraseña débil rechazada
- [ ] Teléfono inválido rechazado
- [ ] Rate limiting funciona
- [ ] Rollback funciona si falla BD
- [ ] Rollback funciona si falla Auth0
- [ ] Subdomain se genera correctamente
- [ ] Módulos se activan automáticamente

---

## 📚 Referencias

- [Auth0 Management API v2 - Create User](https://auth0.com/docs/api/management/v2/users/post-users)
- [Auth0 Email Verification](https://auth0.com/docs/users/user-account-linking/verify-email)
- [Pytz Timezones](https://pypi.org/project/pytz/)
- [RFC 5322 - Email Format](https://datatracker.ietf.org/doc/html/rfc5322)

---

## 🆘 Soporte

Si encuentras problemas no documentados:

1. Verificar logs del backend
2. Verificar configuración de Auth0
3. Probar con curl para aislar si es problema de frontend
4. Revisar rate limiting (esperar 1 hora)
5. Contactar al equipo de backend

---

**Última actualización:** Diciembre 2024
**Versión API:** v1
**Endpoint:** `/api/v1/auth/register-gym-owner`
