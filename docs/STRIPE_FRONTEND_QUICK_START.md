# 🚀 Quick Start - Integración Stripe Connect (Frontend)

## 📌 Resumen en 30 segundos

**Qué cambió**:
- ✅ Ahora el backend actualiza automáticamente el estado de Stripe después del onboarding
- ✅ Agregamos endpoints para recibir el callback de Stripe
- ✅ Ya no necesitas actualizar manualmente después de configurar

**Qué necesitas hacer en el frontend**:
1. Crear página de configuración de Stripe
2. Llamar a los endpoints de API en el orden correcto
3. Implementar polling o escuchar cuando el usuario regresa de Stripe
4. Mostrar el estado actual (conectado/desconectado/configurando)

---

## 🎯 Flujo Visual

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Usuario va a "Configuración de Pagos"                           │
│     ↓                                                                │
│  2. Frontend llama: GET /stripe-connect/accounts/status             │
│     ↓                                                                │
│  3. Si no existe cuenta → POST /stripe-connect/accounts             │
│     ↓                                                                │
│  4. Frontend obtiene link: POST /stripe-connect/accounts/           │
│     onboarding-link                                                  │
│     ↓                                                                │
│  5. Abre ventana de Stripe con el link                              │
│     ↓                                                                │
│  6. Usuario completa formulario en Stripe (5-10 min)                │
│     ↓                                                                │
│  7. Stripe redirige a: /admin/stripe/return?gym_id=X                │
│     ↓                                                                │
│  8. Backend actualiza estado AUTOMÁTICAMENTE ✨                      │
│     ↓                                                                │
│  9. Frontend detecta cambio (polling cada 5 seg)                    │
│     ↓                                                                │
│  10. Muestra: "✅ Stripe configurado exitosamente!"                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 💻 Código Mínimo Necesario

### 1. Verificar Estado Actual

```typescript
async function checkStripeStatus() {
  const response = await fetch('/api/v1/stripe-connect/accounts/status', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'x-gym-id': gymId.toString()
    }
  });

  if (response.status === 404) {
    return 'not_configured'; // No tiene cuenta
  }

  const data = await response.json();

  if (data.onboarding_completed && data.charges_enabled) {
    return 'connected'; // Todo listo ✅
  }

  return 'onboarding'; // Pendiente de completar
}
```

### 2. Crear Cuenta (si no existe)

```typescript
async function createStripeAccount() {
  await fetch('/api/v1/stripe-connect/accounts', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'x-gym-id': gymId.toString(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      country: 'US',
      account_type: 'standard'
    })
  });
}
```

### 3. Obtener Link y Abrir Ventana

```typescript
async function startOnboarding() {
  // Obtener link
  const response = await fetch('/api/v1/stripe-connect/accounts/onboarding-link', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'x-gym-id': gymId.toString()
    }
  });

  const { url } = await response.json();

  // Abrir ventana de Stripe
  const stripeWindow = window.open(url, 'stripe', 'width=800,height=900');

  // Iniciar polling
  startPolling(stripeWindow);
}
```

### 4. Detectar Cuando Completa (Polling)

```typescript
function startPolling(stripeWindow) {
  const interval = setInterval(async () => {
    // Verificar estado cada 5 segundos
    const status = await checkStripeStatus();

    if (status === 'connected') {
      // ¡Listo! 🎉
      clearInterval(interval);
      stripeWindow?.close();
      showSuccess('¡Stripe configurado exitosamente!');
    }

    // Si cerró la ventana, detener polling
    if (stripeWindow && stripeWindow.closed) {
      clearInterval(interval);
    }
  }, 5000);
}
```

---

## 🎨 UI Recomendada

### Estado: No Configurado
```
┌──────────────────────────────────────────┐
│  📦  Stripe no configurado               │
│                                          │
│  Conecta Stripe para aceptar pagos de   │
│  eventos y membresías.                   │
│                                          │
│  [ Conectar Stripe ]                     │
└──────────────────────────────────────────┘
```

### Estado: Configurando
```
┌──────────────────────────────────────────┐
│  ⏳  Configuración pendiente              │
│                                          │
│  Completa la configuración de Stripe    │
│  para empezar a aceptar pagos.           │
│                                          │
│  [ Continuar configuración ]             │
└──────────────────────────────────────────┘
```

### Estado: Conectado
```
┌──────────────────────────────────────────┐
│  ✅  Stripe configurado                   │
│                                          │
│  ID: acct_1SiPILBXxTrYKecy               │
│  Cargos:  ✓ Habilitados                 │
│  Retiros: ✓ Habilitados                 │
│                                          │
│  [ Abrir Dashboard de Stripe → ]        │
└──────────────────────────────────────────┘
```

---

## 📋 Endpoints de API

| Método | Endpoint | Para qué sirve |
|--------|----------|----------------|
| `GET` | `/stripe-connect/accounts/status` | Ver estado actual |
| `POST` | `/stripe-connect/accounts` | Crear cuenta nueva |
| `POST` | `/stripe-connect/accounts/onboarding-link` | Obtener link de configuración |
| `GET` | `/stripe-connect/accounts/connection-status` | Verificar si sigue conectada |

**Headers obligatorios en todos**:
```
Authorization: Bearer {token}
x-gym-id: {gym_id}
```

---

## 🧪 Probar en Desarrollo

### 1. Configurar variable de entorno en backend
```bash
# En .env del backend
FRONTEND_URL=http://localhost:3000
```

### 2. Datos de prueba en Stripe

Al completar el formulario de Stripe (modo test), usa:

- **SSN**: `000-00-0000`
- **Routing number**: `110000000`
- **Account number**: `000123456789`
- **DOB**: `01/01/1990`

### 3. Verificar que funciona

```bash
# 1. Crear cuenta
curl -X POST "http://localhost:8000/api/v1/stripe-connect/accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-gym-id: 4" \
  -H "Content-Type: application/json" \
  -d '{"country":"US","account_type":"standard"}'

# 2. Obtener link
curl -X POST "http://localhost:8000/api/v1/stripe-connect/accounts/onboarding-link" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-gym-id: 4"

# 3. Después de completar, verificar
curl "http://localhost:8000/api/v1/stripe-connect/accounts/status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-gym-id: 4"
```

---

## ⚠️ Casos Edge Importantes

### 1. Link expirado (1 hora)
- El usuario tiene **1 hora** para completar el formulario
- Si expira, debe solicitar un nuevo link
- Stripe redirige automáticamente a `/admin/stripe/reauth`

### 2. Usuario cierra ventana sin completar
- El polling detectará que `onboarding_completed: false`
- Mostrar botón "Continuar configuración"
- Pueden reabrir el link

### 3. Standard Accounts pueden desconectarse
- El gym puede revocar acceso desde su dashboard de Stripe
- Si eso pasa, **NO** se puede reconectar
- Deben crear una cuenta nueva

Para detectar esto:
```typescript
const response = await fetch('/api/v1/stripe-connect/accounts/connection-status');
const data = await response.json();

if (!data.connected && data.account_type === 'standard') {
  alert('Tu cuenta fue desconectada. Debes crear una nueva cuenta.');
}
```

---

## 🚨 Troubleshooting

### "Error 404 al verificar estado"
✅ Normal si no tiene cuenta todavía. Crear cuenta primero.

### "Link no abre"
- Verificar que no haya bloqueador de pop-ups
- Probar con `window.location.href = url` en lugar de `window.open()`

### "Estado no se actualiza después de completar"
- Verificar que `FRONTEND_URL` esté configurado en backend
- Revisar logs del backend: `grep "Onboarding completado" logs.txt`
- Llamar manualmente a `GET /accounts/status` para forzar actualización

### "Dice que no puede procesar pagos"
- Verificar `charges_enabled: true` en la respuesta de `/status`
- Si es `false`, el onboarding no está completo
- Reabrir link y completar verificación

---

## ✅ Checklist de Implementación

Frontend debe tener:

- [ ] Página de configuración de Stripe (`/admin/stripe-setup`)
- [ ] Botón "Conectar Stripe" cuando no está configurado
- [ ] Llamada a `POST /accounts` para crear cuenta
- [ ] Llamada a `POST /accounts/onboarding-link` para obtener link
- [ ] `window.open()` para abrir ventana de Stripe
- [ ] Polling cada 5 segundos para detectar cambios
- [ ] Indicador visual de estado (no configurado/configurando/conectado)
- [ ] Manejo de errores (link expirado, cuenta desconectada, etc.)
- [ ] Testing con datos de prueba de Stripe

---

## 📞 Ayuda

Si algo no funciona:

1. **Ver logs del backend** (debe decir "Onboarding completado para gym X")
2. **Verificar en Swagger**: `https://gymapi-eh6m.onrender.com/api/v1/docs`
3. **Revisar documentación completa**: `FRONTEND_STRIPE_ONBOARDING_GUIDE.md`

**Endpoint de debug**:
```bash
curl "http://localhost:8000/api/v1/stripe-connect/accounts/connection-status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-gym-id: 4"
```

---

## 🎯 TL;DR

**3 pasos**:
1. Crear cuenta: `POST /stripe-connect/accounts`
2. Obtener link: `POST /stripe-connect/accounts/onboarding-link`
3. Polling cada 5 seg hasta que `onboarding_completed: true`

**El backend hace el resto automáticamente** ✨

---

Última actualización: 26 Diciembre 2024
