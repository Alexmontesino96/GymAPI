# API de Stripe Connect - Documentación para Frontend

## 📖 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Flujo Completo de Integración](#flujo-completo-de-integración)
3. [Endpoints Disponibles](#endpoints-disponibles)
4. [Ejemplos de Integración](#ejemplos-de-integración)
5. [Manejo de Errores](#manejo-de-errores)
6. [Estados de la Cuenta](#estados-de-la-cuenta)

---

## Introducción

Esta API permite a los administradores de gimnasios configurar y gestionar su cuenta de **Stripe Connect** para procesar pagos de eventos.

### ¿Qué es Stripe Connect?

Stripe Connect permite que cada gimnasio tenga su **propia cuenta de Stripe independiente**:

- ✅ Dashboard propio en https://dashboard.stripe.com
- ✅ Control total sobre sus pagos y transferencias
- ✅ Independencia de la plataforma (pueden desconectar cuando quieran)
- ✅ Los pagos van **directamente** a su cuenta bancaria

### Tipo de Cuenta: Standard

Por defecto, se crean **Standard Accounts** que ofrecen:

| Característica | Standard Account |
|---------------|------------------|
| Dashboard propio | ✅ Sí |
| Control total | ✅ Sí |
| Puede desconectar | ✅ Sí |
| Costos extra | ❌ No ($0 adicional) |
| Dinero va directo al gym | ✅ Sí |

---

## Flujo Completo de Integración

### Diagrama de Flujo - Configuración Inicial

```
┌────────────────────────────────────────────────────────────┐
│  PASO 1: Verificar si ya tiene cuenta                      │
│  GET /api/v1/stripe-connect/accounts/connection-status     │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ ¿Tiene cuenta?   │
              └──────────────────┘
                /              \
               Sí              No
               │                │
               ▼                ▼
    ┌─────────────────┐   ┌────────────────────────┐
    │ ¿Conectada?     │   │ PASO 2: Crear Cuenta  │
    └─────────────────┘   │ POST /accounts         │
        /          \      └────────────────────────┘
       Sí          No               │
       │            │               ▼
       │            │      ┌────────────────────────┐
       │            │      │ PASO 3: Onboarding    │
       │            │      │ POST /onboarding-link  │
       │            │      └────────────────────────┘
       │            │               │
       │            │               ▼
       │            │      ┌────────────────────────┐
       │            └─────>│ Admin completa flow   │
       │                   │ en Stripe (5-10 min)  │
       ▼                   └────────────────────────┘
┌─────────────────┐                │
│ ✅ LISTO        │<───────────────┘
│ Puede procesar  │
│ pagos           │
└─────────────────┘
```

### Flujo de Reconexión (Standard Accounts)

Las **Standard Accounts** pueden desconectarse voluntariamente desde su Stripe Dashboard. Cuando esto sucede:

```
┌────────────────────────────────────────────────────────────┐
│  Admin intenta procesar pago                                │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ Error 400:       │
              │ "Cuenta          │
              │  desconectada"   │
              └──────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  RECONEXIÓN: Usar el MISMO flujo de onboarding             │
│  POST /api/v1/stripe-connect/accounts/onboarding-link      │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ Response:        │
              │ {                │
              │   is_reconnection│
              │   = true,        │
              │   account_id,    │
              │   onboarding_url │
              │ }                │
              └──────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Admin autoriza nuevamente el acceso en Stripe             │
│  (proceso más rápido - solo reautorización)                │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ ✅ RECONECTADO   │
              │ Cuenta activa    │
              │ nuevamente       │
              └──────────────────┘
```

**IMPORTANTE para reconexión:**
- ✅ NO crear cuenta nueva (`POST /accounts`) - usar la existente
- ✅ Usar `POST /onboarding-link` - funciona para reconexión
- ✅ El sistema detecta automáticamente si es reconexión
- ✅ Response incluye `is_reconnection: true`
- ✅ Proceso más rápido (solo reautorización, no configuración completa)

---

## Endpoints Disponibles

### Base URL

```
https://gymapi-eh6m.onrender.com/api/v1/stripe-connect
```

### Autenticación

Todos los endpoints requieren:

```http
Authorization: Bearer <token>
X-Gym-ID: <gym_id>
```

**Permisos:** Solo administradores del gimnasio pueden acceder.

---

## 1. Verificar Estado de Conexión

### `GET /accounts/connection-status`

Verifica si el gimnasio tiene una cuenta de Stripe y si está conectada.

**Este endpoint debe ser el PRIMERO que llames** para determinar el estado actual.

#### Request

```http
GET /api/v1/stripe-connect/accounts/connection-status
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Gym-ID: 4
```

#### Response - Cuenta Conectada ✅

```json
{
  "connected": true,
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "charges_enabled": true,
  "payouts_enabled": true,
  "can_disconnect": true,
  "direct_dashboard_access": true,
  "message": "Cuenta conectada y funcionando",
  "onboarding_completed": true,
  "details_submitted": true
}
```

#### Response - Sin Cuenta ❌

```json
{
  "connected": false,
  "message": "No hay cuenta de Stripe configurada",
  "action_required": "Crear cuenta de Stripe Connect"
}
```

#### Response - Cuenta Desconectada ⚠️

```json
{
  "connected": false,
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "message": "Cuenta desconectada o inactiva",
  "action_required": "Reconectar cuenta o crear nueva"
}
```

#### Uso en Frontend

```typescript
interface ConnectionStatus {
  connected: boolean;
  account_id?: string;
  account_type?: string;
  charges_enabled?: boolean;
  payouts_enabled?: boolean;
  can_disconnect?: boolean;
  direct_dashboard_access?: boolean;
  message: string;
  onboarding_completed?: boolean;
  details_submitted?: boolean;
  action_required?: string;
}

async function checkStripeConnection(): Promise<ConnectionStatus> {
  const response = await fetch(
    'https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/connection-status',
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId,
      }
    }
  );

  return await response.json();
}

// Uso
const status = await checkStripeConnection();

if (!status.connected) {
  if (status.action_required === "Crear cuenta de Stripe Connect") {
    // Mostrar botón "Configurar Stripe"
    showSetupButton();
  } else {
    // Mostrar botón "Reconectar Stripe"
    showReconnectButton();
  }
} else if (!status.charges_enabled) {
  // Mostrar mensaje: "Completa la configuración de Stripe"
  showOnboardingIncomplete();
} else {
  // ✅ Todo OK
  showStripeActive();
}
```

---

## 2. Crear Cuenta de Stripe

### `POST /accounts`

Crea una nueva cuenta de Stripe Connect para el gimnasio.

**Cuándo llamar:** Cuando `connection-status` retorna `"action_required": "Crear cuenta de Stripe Connect"`.

#### Request

```http
POST /api/v1/stripe-connect/accounts
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Gym-ID: 4
Content-Type: application/json

{
  "country": "US",
  "account_type": "standard"
}
```

**Query Parameters (opcionales):**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `country` | string | `"US"` | Código ISO del país (ej: "MX", "ES") |
| `account_type` | string | `"standard"` | Tipo de cuenta (dejar en "standard") |

#### Response - Cuenta Creada ✅

```json
{
  "message": "Cuenta de Stripe creada exitosamente",
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "country": "US",
  "onboarding_completed": false,
  "charges_enabled": false,
  "payouts_enabled": false,
  "status": "created"
}
```

#### Response - Cuenta Ya Existe ℹ️

```json
{
  "message": "El gimnasio ya tiene una cuenta de Stripe configurada",
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "country": "US",
  "onboarding_completed": true,
  "charges_enabled": true,
  "payouts_enabled": true,
  "status": "already_exists"
}
```

#### Errores

**400 Bad Request:**
```json
{
  "detail": "Ya existe una cuenta activa para este gimnasio"
}
```

**403 Forbidden:**
```json
{
  "detail": "Solo administradores pueden crear cuentas de Stripe"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error interno del servidor"
}
```

#### Uso en Frontend

```typescript
interface CreateAccountResponse {
  message: string;
  account_id: string;
  account_type: string;
  country: string;
  onboarding_completed: boolean;
  charges_enabled: boolean;
  payouts_enabled: boolean;
  status: 'created' | 'updated' | 'already_exists';
}

async function createStripeAccount(
  country: string = 'US'
): Promise<CreateAccountResponse> {
  const response = await fetch(
    `https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts?country=${country}&account_type=standard`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId,
        'Content-Type': 'application/json',
      }
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error creando cuenta');
  }

  return await response.json();
}

// Uso
try {
  const account = await createStripeAccount('US');

  if (account.status === 'created' || account.status === 'updated') {
    // ✅ Cuenta creada
    // Siguiente paso: generar link de onboarding
    const onboardingLink = await createOnboardingLink();
    window.open(onboardingLink.onboarding_url, '_blank');
  } else if (account.status === 'already_exists') {
    // Ya tiene cuenta
    if (!account.onboarding_completed) {
      // Necesita completar onboarding
      const onboardingLink = await createOnboardingLink();
      window.open(onboardingLink.onboarding_url, '_blank');
    }
  }
} catch (error) {
  console.error('Error:', error);
  showError('No se pudo crear la cuenta de Stripe');
}
```

---

## 3. Generar Link de Onboarding

### `POST /accounts/onboarding-link`

Genera un link seguro para que el administrador complete la configuración de Stripe.

**Cuándo llamar:** Después de crear la cuenta o cuando `onboarding_completed: false`.

#### Request

```http
POST /api/v1/stripe-connect/accounts/onboarding-link
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Gym-ID: 4
Content-Type: application/json

{
  "refresh_url": "https://app.gymflow.com/admin/stripe/reauth",
  "return_url": "https://app.gymflow.com/admin/stripe/success"
}
```

**Body Parameters (opcionales):**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `refresh_url` | string | URL a donde redirigir si el link expira |
| `return_url` | string | URL a donde redirigir después de completar |

> **Nota:** Si no se proporcionan, se usan URLs por defecto del backend.

#### Response - Link Generado ✅

```json
{
  "message": "Link de onboarding creado exitosamente",
  "onboarding_url": "https://connect.stripe.com/setup/s/acct_1RdO0iBiqPTgRrIQ/AbC123xyz...",
  "expires_in_minutes": 60,
  "instructions": "Complete la configuración de Stripe siguiendo el link. El proceso toma 5-10 minutos."
}
```

#### Errores

**404 Not Found:**
```json
{
  "detail": "Debe crear una cuenta de Stripe primero"
}
```

**400 Bad Request:**
```json
{
  "detail": "El gimnasio ya completó la configuración de Stripe"
}
```

**429 Too Many Requests:**
```json
{
  "detail": "Demasiadas solicitudes. Límite: 5 por minuto"
}
```

#### Uso en Frontend

```typescript
interface OnboardingLinkResponse {
  message: string;
  onboarding_url: string;
  expires_in_minutes: number;
  instructions: string;
}

async function createOnboardingLink(
  returnUrl?: string,
  refreshUrl?: string
): Promise<OnboardingLinkResponse> {
  const body: any = {};
  if (returnUrl) body.return_url = returnUrl;
  if (refreshUrl) body.refresh_url = refreshUrl;

  const response = await fetch(
    'https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/onboarding-link',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId,
        'Content-Type': 'application/json',
      },
      body: Object.keys(body).length > 0 ? JSON.stringify(body) : undefined
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error generando link');
  }

  return await response.json();
}

// Uso
async function startStripeOnboarding() {
  try {
    const link = await createOnboardingLink(
      'https://app.gymflow.com/admin/stripe/success',
      'https://app.gymflow.com/admin/stripe/reauth'
    );

    // Abrir en nueva ventana
    window.open(link.onboarding_url, '_blank');

    // Mostrar mensaje
    showMessage({
      type: 'info',
      title: 'Completa la configuración en Stripe',
      message: link.instructions,
      duration: 10000
    });

    // Opcional: polling para detectar cuando termine
    startPollingOnboardingStatus();

  } catch (error) {
    console.error('Error:', error);
    showError('No se pudo generar el link de configuración');
  }
}

// Polling para detectar cuando completa el onboarding
function startPollingOnboardingStatus() {
  const interval = setInterval(async () => {
    const status = await checkStripeConnection();

    if (status.onboarding_completed && status.charges_enabled) {
      clearInterval(interval);

      // ✅ Onboarding completado
      showSuccess('¡Stripe configurado correctamente!');
      refreshPage();
    }
  }, 5000); // Verificar cada 5 segundos

  // Cancelar después de 10 minutos
  setTimeout(() => clearInterval(interval), 600000);
}
```

---

## 4. Obtener Estado de la Cuenta

### `GET /accounts/status`

Obtiene información detallada de la cuenta de Stripe desde la API de Stripe.

**Diferencia con `connection-status`:**
- `connection-status` → verifica BD + conexión (rápido)
- `status` → obtiene datos frescos desde Stripe API (más lento pero actualizado)

#### Request

```http
GET /api/v1/stripe-connect/accounts/status
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Gym-ID: 4
```

#### Response - Cuenta Activa ✅

```json
{
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "country": "US",
  "currency": "USD",
  "onboarding_completed": true,
  "charges_enabled": true,
  "payouts_enabled": true,
  "details_submitted": true,
  "is_active": true,
  "created_at": "2024-12-01T10:30:00Z",
  "updated_at": "2024-12-20T15:45:00Z"
}
```

#### Errores

**404 Not Found:**
```json
{
  "detail": "El gimnasio no tiene cuenta de Stripe configurada"
}
```

#### Uso en Frontend

```typescript
interface StripeAccountStatus {
  account_id: string;
  account_type: string;
  country: string;
  currency: string;
  onboarding_completed: boolean;
  charges_enabled: boolean;
  payouts_enabled: boolean;
  details_submitted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

async function getAccountStatus(): Promise<StripeAccountStatus> {
  const response = await fetch(
    'https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/status',
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId,
      }
    }
  );

  if (!response.ok) {
    throw new Error('No se pudo obtener el estado de la cuenta');
  }

  return await response.json();
}
```

---

## Ejemplos de Integración

### Componente React Completo

```typescript
import React, { useState, useEffect } from 'react';

interface StripeSetupProps {
  gymId: number;
  token: string;
}

const StripeSetup: React.FC<StripeSetupProps> = ({ gymId, token }) => {
  const [status, setStatus] = useState<'loading' | 'connected' | 'disconnected' | 'not_configured'>('loading');
  const [accountInfo, setAccountInfo] = useState<any>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    checkConnection();
  }, []);

  async function checkConnection() {
    try {
      const response = await fetch(
        `${API_URL}/stripe-connect/accounts/connection-status`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Gym-ID': String(gymId),
          }
        }
      );

      const data = await response.json();
      setAccountInfo(data);

      if (data.connected && data.charges_enabled) {
        setStatus('connected');
      } else if (data.connected && !data.charges_enabled) {
        setStatus('disconnected'); // Onboarding incompleto
      } else {
        setStatus('not_configured');
      }
    } catch (error) {
      console.error('Error checking connection:', error);
    }
  }

  async function setupStripe() {
    setIsProcessing(true);

    try {
      // Paso 1: Crear cuenta
      const createResponse = await fetch(
        `${API_URL}/stripe-connect/accounts?country=US&account_type=standard`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Gym-ID': String(gymId),
            'Content-Type': 'application/json',
          }
        }
      );

      if (!createResponse.ok) {
        throw new Error('Error creando cuenta');
      }

      // Paso 2: Generar link de onboarding
      const linkResponse = await fetch(
        `${API_URL}/stripe-connect/accounts/onboarding-link`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Gym-ID': String(gymId),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            return_url: `${window.location.origin}/admin/stripe/success`,
            refresh_url: `${window.location.origin}/admin/stripe/reauth`
          })
        }
      );

      if (!linkResponse.ok) {
        throw new Error('Error generando link');
      }

      const linkData = await linkResponse.json();

      // Paso 3: Abrir ventana de Stripe
      window.open(linkData.onboarding_url, '_blank');

      // Paso 4: Polling para detectar cuando termine
      const interval = setInterval(async () => {
        const statusCheck = await fetch(
          `${API_URL}/stripe-connect/accounts/connection-status`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'X-Gym-ID': String(gymId),
            }
          }
        );

        const statusData = await statusCheck.json();

        if (statusData.onboarding_completed && statusData.charges_enabled) {
          clearInterval(interval);
          setStatus('connected');
          checkConnection();
        }
      }, 5000);

      // Cancelar polling después de 10 minutos
      setTimeout(() => clearInterval(interval), 600000);

    } catch (error) {
      console.error('Error:', error);
      alert('Error configurando Stripe');
    } finally {
      setIsProcessing(false);
    }
  }

  if (status === 'loading') {
    return <div>Verificando estado de Stripe...</div>;
  }

  if (status === 'connected') {
    return (
      <div className="stripe-connected">
        <h3>✅ Stripe Configurado</h3>
        <p>Tu cuenta de Stripe está conectada y funcionando.</p>
        <div className="account-info">
          <p><strong>Account ID:</strong> {accountInfo.account_id}</p>
          <p><strong>Tipo:</strong> {accountInfo.account_type}</p>
          <p><strong>Pagos habilitados:</strong> {accountInfo.charges_enabled ? 'Sí' : 'No'}</p>
        </div>
        <a
          href="https://dashboard.stripe.com"
          target="_blank"
          className="btn-secondary"
        >
          Ver Dashboard de Stripe
        </a>
      </div>
    );
  }

  if (status === 'disconnected') {
    return (
      <div className="stripe-disconnected">
        <h3>⚠️ Configuración Incompleta</h3>
        <p>Tu cuenta de Stripe necesita completar la configuración.</p>
        <button
          onClick={setupStripe}
          disabled={isProcessing}
          className="btn-primary"
        >
          {isProcessing ? 'Generando link...' : 'Completar Configuración'}
        </button>
      </div>
    );
  }

  return (
    <div className="stripe-not-configured">
      <h3>Configurar Stripe</h3>
      <p>
        Stripe te permite procesar pagos de eventos de forma segura.
        Los pagos van directamente a tu cuenta bancaria.
      </p>
      <button
        onClick={setupStripe}
        disabled={isProcessing}
        className="btn-primary"
      >
        {isProcessing ? 'Configurando...' : 'Configurar Stripe'}
      </button>
    </div>
  );
};

export default StripeSetup;
```

---

## Estados de la Cuenta

### Matriz de Estados

| `connected` | `onboarding_completed` | `charges_enabled` | UI a Mostrar | Acción |
|-------------|------------------------|-------------------|--------------|--------|
| `false` | - | - | "Configurar Stripe" | Crear cuenta + onboarding |
| `true` | `false` | `false` | "Completar configuración" | Generar onboarding link |
| `true` | `true` | `false` | "Verificando..." | Esperar o contactar soporte |
| `true` | `true` | `true` | "✅ Stripe activo" | Ninguna |

---

## Manejo de Errores

### Errores Comunes y Soluciones

#### 1. Error 403 - "Solo administradores pueden crear cuentas"

**Causa:** El usuario no es administrador del gimnasio.

**Solución Frontend:**
```typescript
if (response.status === 403) {
  showError('Solo administradores pueden configurar Stripe');
  // Redirigir a página de inicio
}
```

#### 2. Error 404 - "Debe crear una cuenta primero"

**Causa:** Se intentó generar onboarding link sin crear cuenta.

**Solución Frontend:**
```typescript
async function ensureAccountExists() {
  try {
    await createStripeAccount();
  } catch (error) {
    if (error.status === 400 && error.detail.includes('ya existe')) {
      // OK, la cuenta ya existe
      return true;
    }
    throw error;
  }
  return true;
}

async function startOnboarding() {
  await ensureAccountExists();
  const link = await createOnboardingLink();
  window.open(link.onboarding_url, '_blank');
}
```

#### 3. Error 429 - "Demasiadas solicitudes"

**Causa:** Rate limit excedido (5 requests/min para onboarding link).

**Solución Frontend:**
```typescript
let lastOnboardingRequest = 0;

async function createOnboardingLinkSafe() {
  const now = Date.now();
  const timeSinceLastRequest = now - lastOnboardingRequest;

  if (timeSinceLastRequest < 12000) { // 12 segundos entre requests
    showError('Por favor espera unos segundos antes de intentar de nuevo');
    return null;
  }

  lastOnboardingRequest = now;
  return await createOnboardingLink();
}
```

#### 4. Link de Onboarding Expirado

**Causa:** Los links expiran después de 60 minutos.

**Solución Frontend:**
```typescript
function handleExpiredLink() {
  showMessage({
    type: 'warning',
    title: 'Link expirado',
    message: 'El link de configuración expiró. Generando uno nuevo...'
  });

  // Generar nuevo link automáticamente
  createOnboardingLinkSafe().then(link => {
    if (link) {
      window.open(link.onboarding_url, '_blank');
    }
  });
}
```

---

## Testing

### Ambiente de Testing

Para testing, usa:

```typescript
const API_URL = process.env.NODE_ENV === 'production'
  ? 'https://gymapi-eh6m.onrender.com/api/v1'
  : 'http://localhost:8000/api/v1';
```

### Stripe Test Mode

Las cuentas creadas en modo test de Stripe (con `sk_test_xxx`) son solo para testing y NO procesan pagos reales.

---

## Checklist de Integración

### Para el Desarrollador Frontend

- [ ] Implementar endpoint de verificación de estado
- [ ] Implementar creación de cuenta
- [ ] Implementar generación de onboarding link
- [ ] Manejar casos de cuenta ya existente
- [ ] Manejar casos de onboarding incompleto
- [ ] Implementar polling para detectar onboarding completado
- [ ] Manejar errores 403, 404, 429
- [ ] Mostrar información de cuenta cuando esté conectada
- [ ] Link a dashboard de Stripe (https://dashboard.stripe.com)
- [ ] Testing en modo test de Stripe

---

## Soporte

Si tienes preguntas o problemas:

1. **Documentación adicional:**
   - `docs/STRIPE_CONNECT_WEBHOOK_SETUP.md` - Configuración de webhooks
   - Stripe Connect Docs: https://stripe.com/docs/connect

2. **Errores comunes:** Ver sección [Manejo de Errores](#manejo-de-errores)

3. **Contacto:** Reportar issues en GitHub

---

**Última actualización:** 2024-12-25
**Versión de la API:** v1
**Autor:** GymAPI Team
