# API de Módulos - Documentación Completa

## Descripción General

El sistema de módulos permite habilitar o deshabilitar funcionalidades específicas para cada gimnasio de forma independiente. Cada gimnasio puede tener su propia configuración de módulos activos según sus necesidades y plan de suscripción.

## URL Base

```
/api/v1/modules
```

## Autenticación

Todos los endpoints requieren autenticación con token JWT de Auth0 en el header:

```
Authorization: Bearer {token}
X-Gym-ID: {gym_id}
```

---

## 📋 Endpoints Disponibles

### 1. Obtener Módulos Activos

Obtiene la lista completa de módulos disponibles y su estado de activación para el gimnasio actual.

**Endpoint:** `GET /api/v1/modules`

**Permisos:** Usuario autenticado con acceso al gym

**Headers:**
```http
Authorization: Bearer {token}
X-Gym-ID: 7
```

**Respuesta Exitosa (200):**
```json
{
  "modules": [
    {
      "code": "users",
      "name": "Gestión de Usuarios",
      "active": true,
      "is_premium": false
    },
    {
      "code": "schedule",
      "name": "Clases y Horarios",
      "active": true,
      "is_premium": false
    },
    {
      "code": "billing",
      "name": "Pagos y Facturación",
      "active": false,
      "is_premium": false
    },
    {
      "code": "nutrition",
      "name": "Planes Nutricionales",
      "active": false,
      "is_premium": true
    }
  ]
}
```

**Ejemplo de Uso:**
```bash
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/modules" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"
```

**Uso en Frontend:**
```javascript
// React/Vue/Angular
const response = await fetch('/api/v1/modules', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Gym-ID': gymId
  }
});

const { modules } = await response.json();

// Verificar si un módulo está activo
const isBillingActive = modules.find(m => m.code === 'billing')?.active;

// Filtrar módulos activos
const activeModules = modules.filter(m => m.active);

// Filtrar módulos premium
const premiumModules = modules.filter(m => m.is_premium);
```

---

### 2. Activar Módulo

Activa un módulo específico para el gimnasio actual.

**Endpoint:** `PATCH /api/v1/modules/{module_code}/activate`

**Permisos:** `ADMIN` o `OWNER` del gimnasio

**Parámetros de Ruta:**
- `module_code` (string, requerido): Código del módulo a activar

**Headers:**
```http
Authorization: Bearer {token}
X-Gym-ID: 7
```

**Respuesta Exitosa (200):**
```json
{
  "status": "success",
  "message": "Módulo billing activado correctamente"
}
```

**Errores Posibles:**
- `404 Not Found`: Módulo no encontrado
- `403 Forbidden`: Sin permisos de administrador
- `500 Internal Server Error`: Error al activar

**Ejemplo de Uso:**
```bash
curl -X PATCH "https://gymapi-eh6m.onrender.com/api/v1/modules/billing/activate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"
```

**Frontend:**
```javascript
async function activateModule(moduleCode) {
  const response = await fetch(`/api/v1/modules/${moduleCode}/activate`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-ID': gymId
    }
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return await response.json();
}

// Uso
try {
  await activateModule('billing');
  console.log('✅ Módulo activado');
} catch (error) {
  console.error('❌ Error:', error.message);
}
```

---

### 3. Desactivar Módulo

Desactiva un módulo específico para el gimnasio actual.

**Endpoint:** `PATCH /api/v1/modules/{module_code}/deactivate`

**Permisos:** `ADMIN` o `OWNER` con scope `admin:modules`

**Parámetros de Ruta:**
- `module_code` (string, requerido): Código del módulo a desactivar

**Headers:**
```http
Authorization: Bearer {token}
X-Gym-ID: 7
```

**Respuesta Exitosa (200):**
```json
{
  "status": "success",
  "message": "Módulo nutrition desactivado correctamente"
}
```

**Errores Posibles:**
- `404 Not Found`: Módulo no encontrado
- `403 Forbidden`: Sin permisos de administrador
- `500 Internal Server Error`: Error al desactivar

**Ejemplo de Uso:**
```bash
curl -X PATCH "https://gymapi-eh6m.onrender.com/api/v1/modules/nutrition/deactivate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"
```

---

## 🔐 Endpoints Especiales de Billing

El módulo de billing tiene endpoints especiales para una configuración más detallada.

### 4. Activar Módulo Billing (Avanzado)

Activa el módulo billing con validación completa de Stripe y sincronización automática.

**Endpoint:** `POST /api/v1/modules/billing/activate`

**Permisos:** `ADMIN` o `OWNER` con scope `admin:modules`

**Headers:**
```http
Authorization: Bearer {token}
X-Gym-ID: 7
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Módulo de billing activado correctamente",
  "stripe_configured": true,
  "plans_synced": 3,
  "details": {
    "stripe_account_id": "acct_xxxxx",
    "active_plans": 3,
    "active_subscriptions": 15
  }
}
```

**Errores Posibles:**
```json
{
  "detail": "Stripe no está configurado para este gimnasio. Configure primero una cuenta de Stripe."
}
```

**Ejemplo de Uso:**
```bash
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/modules/billing/activate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"
```

**Frontend:**
```javascript
async function activateBillingModule() {
  try {
    const response = await fetch('/api/v1/modules/billing/activate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId
      }
    });

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.error);
    }

    console.log(`✅ Billing activado. ${result.plans_synced} planes sincronizados`);
    return result;

  } catch (error) {
    console.error('❌ Error activando billing:', error);
    throw error;
  }
}
```

---

### 5. Desactivar Módulo Billing (Avanzado)

Desactiva el módulo billing con opción de preservar datos.

**Endpoint:** `POST /api/v1/modules/billing/deactivate`

**Permisos:** `ADMIN` o `OWNER` con scope `admin:modules`

**Query Parameters:**
- `preserve_data` (boolean, opcional, default: true): Preservar datos de Stripe

**Headers:**
```http
Authorization: Bearer {token}
X-Gym-ID: 7
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Módulo de billing desactivado correctamente",
  "data_preserved": true
}
```

**Ejemplo de Uso:**
```bash
# Desactivar preservando datos (recomendado)
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/modules/billing/deactivate?preserve_data=true" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"

# Desactivar eliminando datos (⚠️ PELIGROSO)
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/modules/billing/deactivate?preserve_data=false" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"
```

---

### 6. Obtener Estado de Billing

Obtiene información detallada sobre el estado del módulo billing.

**Endpoint:** `GET /api/v1/modules/billing/status`

**Permisos:** Usuario con scope `resource:read`

**Headers:**
```http
Authorization: Bearer {token}
X-Gym-ID: 7
```

**Respuesta Exitosa (200):**
```json
{
  "gym_id": 7,
  "gym_name": "Fitness Pro",
  "module_active": true,
  "stripe_configured": true,
  "stripe_account_status": "active",
  "capabilities": {
    "card_payments": "active",
    "transfers": "active"
  },
  "statistics": {
    "total_plans": 3,
    "active_subscriptions": 15,
    "total_revenue_cents": 150000,
    "currency": "EUR"
  },
  "last_sync": "2025-12-20T00:00:00Z"
}
```

**Ejemplo de Uso:**
```bash
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/modules/billing/status" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Gym-ID: 7"
```

**Frontend:**
```javascript
async function checkBillingStatus() {
  const response = await fetch('/api/v1/modules/billing/status', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-ID': gymId
    }
  });

  const status = await response.json();

  // Verificar si billing está completamente configurado
  const isFullyConfigured = status.module_active && status.stripe_configured;

  // Mostrar estadísticas
  console.log(`💰 Revenue: €${status.statistics.total_revenue_cents / 100}`);
  console.log(`👥 Subscriptions: ${status.statistics.active_subscriptions}`);

  return status;
}
```

---

## 📦 Módulos Disponibles

| Código | Nombre | Descripción | Premium |
|--------|--------|-------------|---------|
| `users` | Gestión de Usuarios | Gestión de miembros, entrenadores y usuarios | ❌ |
| `schedule` | Clases y Horarios | Sistema de clases grupales y gestión de horarios | ❌ |
| `events` | Eventos del Gimnasio | Creación y gestión de eventos especiales | ❌ |
| `chat` | Mensajería | Sistema de chat en tiempo real con Stream | ❌ |
| `billing` | Pagos y Facturación | Gestión de pagos, suscripciones y facturación con Stripe | ❌ |
| `health` | Tracking de Salud | Seguimiento de medidas corporales y métricas | ❌ |
| `nutrition` | Planes Nutricionales | Análisis nutricional con IA y planes de alimentación | ✅ |
| `surveys` | Encuestas y Feedback | Sistema de encuestas para recopilar feedback | ❌ |
| `equipment` | Gestión de Equipos | Control de equipamiento y mantenimiento | ❌ |
| `appointments` | Agenda de Citas | Sistema de agendamiento para entrenadores | ❌ |
| `progress` | Progreso de Clientes | Tracking de progreso y logros de clientes | ❌ |
| `classes` | Clases Grupales | Gestión de clases grupales y capacidad | ❌ |
| `stories` | Historias | Historias estilo Instagram (24h) | ❌ |
| `posts` | Publicaciones | Feed social del gimnasio | ❌ |
| `attendance` | Asistencia | Control de asistencia de miembros | ❌ |

---

## 🔒 Permisos Requeridos

| Endpoint | Rol Mínimo | Scopes Adicionales |
|----------|------------|-------------------|
| `GET /modules` | Member | - |
| `PATCH /modules/{code}/activate` | Admin | - |
| `PATCH /modules/{code}/deactivate` | Admin | `admin:modules` |
| `POST /modules/billing/activate` | Admin | `admin:modules` |
| `POST /modules/billing/deactivate` | Admin | `admin:modules` |
| `GET /modules/billing/status` | Member | `resource:read` |

---

## 💡 Casos de Uso Comunes

### 1. Verificar si un módulo está activo

```javascript
async function isModuleActive(moduleCode) {
  const response = await fetch('/api/v1/modules', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-ID': gymId
    }
  });

  const { modules } = await response.json();
  const module = modules.find(m => m.code === moduleCode);

  return module?.active || false;
}

// Uso
const canUseBilling = await isModuleActive('billing');
if (!canUseBilling) {
  alert('El módulo de billing no está activado');
}
```

### 2. Activar múltiples módulos

```javascript
async function activateModules(moduleCodes) {
  const results = await Promise.allSettled(
    moduleCodes.map(code =>
      fetch(`/api/v1/modules/${code}/activate`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Gym-ID': gymId
        }
      })
    )
  );

  const succeeded = results.filter(r => r.status === 'fulfilled');
  const failed = results.filter(r => r.status === 'rejected');

  return {
    succeeded: succeeded.length,
    failed: failed.length
  };
}

// Uso: Activar módulos esenciales
await activateModules(['users', 'schedule', 'events', 'chat']);
```

### 3. Panel de Administración de Módulos

```javascript
// Componente React completo
import React, { useState, useEffect } from 'react';

function ModulesPanel() {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadModules();
  }, []);

  async function loadModules() {
    const response = await fetch('/api/v1/modules', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId
      }
    });
    const data = await response.json();
    setModules(data.modules);
    setLoading(false);
  }

  async function toggleModule(moduleCode, currentlyActive) {
    const action = currentlyActive ? 'deactivate' : 'activate';

    try {
      await fetch(`/api/v1/modules/${moduleCode}/${action}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Gym-ID': gymId
        }
      });

      // Recargar módulos
      await loadModules();

    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  }

  if (loading) return <div>Cargando módulos...</div>;

  return (
    <div className="modules-panel">
      <h2>Módulos del Gimnasio</h2>
      {modules.map(module => (
        <div key={module.code} className="module-item">
          <div>
            <h3>{module.name}</h3>
            {module.is_premium && <span className="badge">Premium</span>}
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={module.active}
              onChange={() => toggleModule(module.code, module.active)}
            />
            <span className="slider"></span>
          </label>
        </div>
      ))}
    </div>
  );
}
```

---

## ⚠️ Consideraciones Importantes

### 1. Dependencias entre Módulos

Algunos módulos dependen de otros:
- `billing` requiere configuración de Stripe
- `appointments` funciona mejor con `schedule` activo
- `nutrition` requiere API key de OpenAI

### 2. Módulos Premium

Los módulos marcados como `is_premium: true` pueden requerir:
- Suscripción de pago
- Configuración adicional
- APIs de terceros

### 3. Desactivación de Módulos

Al desactivar un módulo:
- ✅ Los datos se preservan por defecto
- ⚠️ Las funcionalidades dejan de estar disponibles
- ⚠️ Los webhooks asociados pueden dejar de funcionar

### 4. Performance

- Los módulos se cachean en Redis
- La lista de módulos se actualiza automáticamente al activar/desactivar
- El frontend debe refrescar la lista después de cambios

---

## 🐛 Troubleshooting

### Error: "Módulo no encontrado"

**Solución:** Verificar que el `module_code` sea correcto. Códigos válidos: `users`, `billing`, `nutrition`, etc.

### Error: "Sin permisos de administrador"

**Solución:** Solo usuarios con rol `ADMIN` u `OWNER` pueden activar/desactivar módulos.

### Error: "Stripe no está configurado"

**Solución:** Configurar Stripe Connect antes de activar el módulo `billing`:
```bash
POST /api/v1/stripe-connect/accounts
```

### El módulo aparece como inactivo después de activarlo

**Solución:**
1. Verificar que la respuesta fue exitosa (200 OK)
2. Refrescar la lista de módulos con `GET /modules`
3. Limpiar caché si es necesario

---

## 📚 Recursos Adicionales

- [Guía de Configuración de Módulos](./MODULE_CONFIGURATION_GUIDE.md)
- [API de Stripe Connect](./STRIPE_CONNECT_API.md)
- [Documentación de Billing](./BILLING_MODULE.md)

---

## 🔗 Enlaces Relacionados

- **Swagger UI:** https://gymapi-eh6m.onrender.com/api/v1/docs
- **ReDoc:** https://gymapi-eh6m.onrender.com/api/v1/redoc
- **Código Fuente:** `/app/api/v1/endpoints/modules.py`
