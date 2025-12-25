# Limitaciones de Stripe Connect Standard Accounts

## 🚨 Limitación Crítica: Desconexión Permanente

### El Problema

Cuando un gimnasio con **Standard Account** desconecta su cuenta desde Stripe Dashboard, **NO SE PUEDE RECONECTAR** la misma cuenta. La desconexión es **permanente e irreversible** desde el punto de vista de la plataforma.

### Por Qué Sucede

Las Standard Accounts ofrecen **control total** al usuario:

- ✅ Tienen su propio dashboard en https://dashboard.stripe.com
- ✅ Pueden gestionar sus pagos independientemente
- ✅ **Pueden revocar el acceso OAuth2 a la plataforma en cualquier momento**

Cuando revocan el acceso:
- 🔒 La autorización OAuth2 se revoca permanentemente
- 🔒 La plataforma pierde todo acceso a la cuenta
- 🔒 No podemos crear nuevos `AccountLinks` para esa cuenta
- 🔒 No podemos acceder a ningún dato de la cuenta

### Error de Stripe

Al intentar crear un `AccountLink` para una cuenta desconectada:

```
InvalidRequestError: You requested an account link for an account
that is not connected to your platform or does not exist.
```

---

## ✅ Solución: Crear Nueva Cuenta

### Flujo para Gym con Cuenta Desconectada

```
┌────────────────────────────────────────────────────────┐
│  1. GET /connection-status                              │
│     Response: can_reconnect: false                      │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  2. Explicar al admin que debe crear NUEVA cuenta      │
│     La cuenta anterior no se puede recuperar           │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  3. POST /accounts (crear nueva cuenta Standard)       │
│     Esto crea una NUEVA cuenta en Stripe               │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  4. POST /onboarding-link                              │
│     Completar onboarding de la NUEVA cuenta            │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  5. Admin completa configuración en Stripe             │
│     Nueva cuenta lista para procesar pagos             │
└────────────────────────────────────────────────────────┘
```

---

## 📊 Respuestas de API

### GET /connection-status (Cuenta Desconectada)

```json
{
  "connected": false,
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "onboarding_completed": true,
  "message": "Cuenta standard desconectada",
  "action_required": "Esta cuenta Standard fue desconectada y NO puede ser reconectada. Las cuentas Standard pueden revocar el acceso permanentemente. Debe crear una nueva cuenta usando POST /api/v1/stripe-connect/accounts.",
  "can_reconnect": false
}
```

**Campo clave:** `"can_reconnect": false` indica que NO se puede reconectar.

### POST /onboarding-link (Intento con Cuenta Desconectada)

```json
{
  "detail": "Esta cuenta Standard fue desconectada y NO puede ser reconectada. Las cuentas Standard tienen control total y pueden revocar el acceso permanentemente. Debe crear una nueva cuenta usando POST /api/v1/stripe-connect/accounts."
}
```

**Status Code:** 400 Bad Request

---

## 🔄 Comparación: Standard vs Express

| Característica | Standard Account | Express Account |
|---------------|------------------|-----------------|
| **Control del gym** | Total | Limitado |
| **Dashboard propio** | ✅ Sí | ❌ No |
| **Puede desconectar** | ✅ Sí | ❌ No |
| **Reconexión posible** | ❌ No | ✅ Sí |
| **Costo adicional** | $0 | $0 |
| **Independencia** | Total | Depende de plataforma |

### Recomendación Actual

Seguimos usando **Standard Accounts** porque:

1. ✅ Mayor control para los gyms (ventaja principal)
2. ✅ Dashboard propio (facilita gestión)
3. ✅ Independencia de la plataforma
4. ⚠️ Riesgo de desconexión es bajo en uso normal
5. ✅ Webhook `account.application.deauthorized` permite detectar desconexiones

**Trade-off aceptado:** A cambio de dar control total al gym, aceptamos que puedan desconectar permanentemente.

---

## 🛡️ Mitigación del Riesgo

### 1. Webhook de Detección

**CRÍTICO:** Configurar webhook para detectar desconexiones automáticamente.

**Evento:** `account.application.deauthorized`

**Acción:** El sistema marca la cuenta como `is_active=false` automáticamente.

**Ver:** [STRIPE_CONNECT_WEBHOOK_SETUP.md](./STRIPE_CONNECT_WEBHOOK_SETUP.md)

### 2. Validaciones en Código

✅ **Implementado:**
- `GET /connection-status` devuelve `can_reconnect: false` para Standard desconectadas
- `POST /onboarding-link` rechaza con error 400 antes de llamar a Stripe
- Manejo específico de error `InvalidRequestError` en servicio
- Mensajes claros indicando que debe crear nueva cuenta

### 3. Comunicación al Usuario

**En el frontend, mostrar:**

```
⚠️ Tu cuenta de Stripe fue desconectada

Las cuentas Standard tienen control total y pueden revocar
el acceso a la plataforma en cualquier momento.

Tu cuenta anterior no puede ser reconectada.

Para continuar procesando pagos, debes crear una nueva cuenta
de Stripe Connect.

[Crear Nueva Cuenta]
```

---

## 📝 Casos de Uso

### Caso 1: Gym Desconecta por Error

**Escenario:** Admin del gym desconecta la cuenta desde Stripe Dashboard sin querer.

**Resultado:**
- ❌ No puede "deshacer" la desconexión
- ❌ La cuenta anterior se pierde
- ✅ Debe crear nueva cuenta
- ⚠️ Pierde historial de pagos en esa cuenta

**Prevención:** Educar a admins sobre las consecuencias de desconectar.

### Caso 2: Gym Cambia de Plataforma

**Escenario:** Gym decide usar otra plataforma y desconecta su cuenta.

**Resultado:**
- ✅ Tiene control total para hacerlo (ventaja de Standard)
- ✅ Puede seguir usando su cuenta Stripe independientemente
- ✅ Si vuelve a nuestra plataforma, crea nueva cuenta

### Caso 3: Cuenta Desconectada por Stripe

**Escenario:** Stripe desconecta la cuenta por violación de ToS o fraude.

**Resultado:**
- 🔒 Cuenta permanentemente inaccesible
- ✅ Sistema detecta via webhook
- ✅ Admin debe resolver con Stripe directamente
- ⚠️ Es posible que no pueda crear nueva cuenta si está banned

---

## 🧪 Testing

### Test 1: Detectar Cuenta Desconectada

```bash
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/connection-status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 4"

# Verificar:
# - can_reconnect: false
# - message indica que NO se puede reconectar
# - action_required menciona crear nueva cuenta
```

### Test 2: Intentar Reconectar (Debe Fallar)

```bash
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/onboarding-link" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 4"

# Esperado: 400 Bad Request
# "detail": "Esta cuenta Standard fue desconectada y NO puede ser reconectada..."
```

### Test 3: Crear Nueva Cuenta

```bash
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 4" \
  -H "Content-Type: application/json" \
  -d '{"country": "US"}'

# Esperado: 200 OK
# Nueva cuenta creada exitosamente
```

---

## 🎯 Recomendaciones

### Para el Equipo de Desarrollo

1. ✅ **Implementar webhook** `account.application.deauthorized` (CRÍTICO)
2. ✅ **Validar tipo de cuenta** antes de intentar reconexión
3. ✅ **Mensajes claros** en frontend explicando la situación
4. ✅ **Logging detallado** de desconexiones para análisis
5. ⚠️ **Considerar alertas** si múltiples gyms desconectan

### Para el Equipo de Soporte

1. 📚 **Documentar proceso** de creación de nueva cuenta
2. 📚 **FAQ** sobre por qué no se puede reconectar
3. 📚 **Guía** para prevenir desconexiones accidentales
4. 📚 **Script** para diagnosticar cuentas desconectadas

### Para Admins de Gym

1. ⚠️ **NO desconectar** la cuenta desde Stripe Dashboard
2. ⚠️ **Contactar soporte** si tienen problemas con Stripe
3. ⚠️ **Entender consecuencias** de desconectar (es permanente)

---

## 📖 Referencias

- [Stripe Connect Standard Accounts](https://stripe.com/docs/connect/standard-accounts)
- [Stripe OAuth Disconnection](https://stripe.com/docs/connect/oauth-reference#get-deauthorize)
- [Account Links API](https://stripe.com/docs/api/account_links)
- [STRIPE_CONNECT_WEBHOOK_SETUP.md](./STRIPE_CONNECT_WEBHOOK_SETUP.md)
- [STRIPE_CONNECT_RECONNECTION_FIX.md](./STRIPE_CONNECT_RECONNECTION_FIX.md)

---

## ❓ FAQ

### ¿Por qué no usamos Express Accounts si tienen reconexión?

**R:** Standard Accounts dan control total al gym, lo cual es más importante que la reconexión. Es un trade-off aceptable.

### ¿Se pierde el historial de pagos al crear nueva cuenta?

**R:** No. El historial de pagos se mantiene en la cuenta original de Stripe del gym (si tienen acceso directo). Solo pierden la conexión con nuestra plataforma.

### ¿Podemos forzar reconexión?

**R:** No. Es una limitación técnica de Stripe para Standard Accounts.

### ¿Hay forma de prevenir que desconecten?

**R:** No. Es el propósito de Standard Accounts: dar control total al gym.

---

**Última actualización:** 2025-12-25
**Estado:** Implementado y documentado
