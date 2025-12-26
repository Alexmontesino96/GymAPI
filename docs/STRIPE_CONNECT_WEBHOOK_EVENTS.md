# Eventos de Webhook de Stripe Connect - Guía Completa

## 📋 Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Eventos por Prioridad](#eventos-por-prioridad)
3. [Configuración en Stripe Dashboard](#configuración-en-stripe-dashboard)
4. [Eventos Implementados](#eventos-implementados)
5. [Eventos Recomendados Adicionales](#eventos-recomendados-adicionales)
6. [Eventos Opcionales](#eventos-opcionales)
7. [Testing de Webhooks](#testing-de-webhooks)

---

## Resumen Ejecutivo

### ¿Qué eventos necesitas configurar?

**Configuración Mínima (CRÍTICO):**
```
✅ account.application.deauthorized  ← YA IMPLEMENTADO
✅ account.updated                    ← YA IMPLEMENTADO
```

**Configuración Recomendada (OPCIONAL pero útil):**
```
⚠️ account.external_account.created
⚠️ account.external_account.updated
⚠️ account.external_account.deleted
⚠️ capability.updated
```

**Configuración Completa (FULL COVERAGE):**
```
Todo lo anterior +
- person.created
- person.updated
- person.deleted
```

---

## Eventos por Prioridad

### 🔴 CRÍTICOS (Must-Have)

#### 1. `account.application.deauthorized`

**Estado:** ✅ **YA IMPLEMENTADO**

**¿Qué es?**
Se dispara cuando un gimnasio **desconecta su cuenta Standard** desde el dashboard de Stripe.

**¿Por qué es crítico?**
- Sin este evento, no sabrás cuando un gym desconecta su cuenta
- Intentarías procesar pagos con una cuenta desautorizada
- Errores 403 "account_invalid" en producción

**¿Qué hace tu sistema?**
```python
# Ver: stripe_connect_webhooks.py líneas 96-153
1. Marca gym_account.is_active = False
2. Desactiva charges_enabled y payouts_enabled
3. Log de warning estructurado
4. (TODO) Notificar a admins del gym
```

**Payload del evento:**
```json
{
  "id": "evt_xxx",
  "type": "account.application.deauthorized",
  "account": "acct_1RdO0iBiqPTgRrIQ",
  "created": 1703456789,
  "data": {
    "object": {
      "id": "acct_1RdO0iBiqPTgRrIQ",
      "object": "account"
    }
  }
}
```

**Cuándo se dispara:**
- Gym hace click en "Disconnect" en su Stripe Dashboard
- Stripe revoca acceso por violación de términos
- Stripe detecta actividad fraudulenta

---

#### 2. `account.updated`

**Estado:** ✅ **YA IMPLEMENTADO**

**¿Qué es?**
Se dispara cuando **cambia cualquier información** de la cuenta de Stripe.

**¿Por qué es crítico?**
- Sincronizar cambios de capabilities (charges_enabled, payouts_enabled)
- Detectar cuando completan onboarding
- Mantener BD actualizada con estado real de Stripe

**¿Qué hace tu sistema?**
```python
# Ver: stripe_connect_webhooks.py líneas 156-212
1. Sincroniza charges_enabled
2. Sincroniza payouts_enabled
3. Sincroniza details_submitted
4. Actualiza updated_at
5. Log de cambios importantes
```

**Payload del evento:**
```json
{
  "id": "evt_xxx",
  "type": "account.updated",
  "account": "acct_1RdO0iBiqPTgRrIQ",
  "data": {
    "object": {
      "id": "acct_1RdO0iBiqPTgRrIQ",
      "charges_enabled": true,
      "payouts_enabled": true,
      "details_submitted": true,
      "capabilities": {
        "card_payments": "active",
        "transfers": "active"
      }
    },
    "previous_attributes": {
      "charges_enabled": false
    }
  }
}
```

**Cuándo se dispara:**
- Gym completa el onboarding
- Stripe habilita/deshabilita capabilities
- Cambios en información de la cuenta
- Actualizaciones de verificación de identidad

---

### 🟡 RECOMENDADOS (Nice-to-Have)

#### 3. `account.external_account.created`

**Estado:** ❌ **NO IMPLEMENTADO** (pero fácil de agregar)

**¿Qué es?**
Se dispara cuando el gym **agrega una cuenta bancaria** o tarjeta de débito para recibir payouts.

**¿Por qué es útil?**
- Confirmar que el gym configuró su cuenta bancaria
- Auditoría de cambios de cuenta bancaria
- Detectar si agregan múltiples cuentas

**Payload del evento:**
```json
{
  "id": "evt_xxx",
  "type": "account.external_account.created",
  "account": "acct_1RdO0iBiqPTgRrIQ",
  "data": {
    "object": {
      "id": "ba_xxx",
      "object": "bank_account",
      "bank_name": "CHASE",
      "country": "US",
      "currency": "usd",
      "last4": "6789",
      "routing_number": "110000000",
      "status": "new"
    }
  }
}
```

**Implementación sugerida:**
```python
async def _handle_external_account_created(db: Session, event: dict):
    account_id = event['account']
    external_account = event['data']['object']

    gym_account = db.query(GymStripeAccount).filter(
        GymStripeAccount.stripe_account_id == account_id
    ).first()

    if gym_account:
        logger.info(
            f"💳 Nueva cuenta bancaria agregada para gym {gym_account.gym_id}: "
            f"Banco: {external_account.get('bank_name', 'N/A')}, "
            f"Últimos 4: {external_account.get('last4', 'N/A')}"
        )

        # Opcional: guardar en tabla de auditoría
        # audit_log.create(gym_id=gym_account.gym_id, event="bank_account_added", ...)
```

---

#### 4. `account.external_account.updated`

**Estado:** ❌ **NO IMPLEMENTADO**

**¿Qué es?**
Se dispara cuando el gym **actualiza su cuenta bancaria** (ej: cambia de "new" a "verified").

**¿Por qué es útil?**
- Detectar cuando Stripe verifica la cuenta bancaria
- Auditoría de cambios

**Cuándo se dispara:**
- Verificación de cuenta bancaria completa
- Cambio de cuenta bancaria por defecto
- Actualización de información de la cuenta

---

#### 5. `account.external_account.deleted`

**Estado:** ❌ **NO IMPLEMENTADO**

**¿Qué es?**
Se dispara cuando el gym **elimina una cuenta bancaria**.

**¿Por qué es útil?**
- Detectar si eliminan TODAS sus cuentas bancarias (riesgo)
- Auditoría de seguridad

**Implementación sugerida:**
```python
async def _handle_external_account_deleted(db: Session, event: dict):
    account_id = event['account']
    external_account = event['data']['object']

    gym_account = db.query(GymStripeAccount).filter(
        GymStripeAccount.stripe_account_id == account_id
    ).first()

    if gym_account:
        logger.warning(
            f"⚠️  Cuenta bancaria eliminada para gym {gym_account.gym_id}: "
            f"Últimos 4: {external_account.get('last4', 'N/A')}"
        )

        # Verificar si eliminaron todas las cuentas
        try:
            account = stripe.Account.retrieve(account_id)
            if not account.external_accounts.data:
                logger.error(
                    f"🚨 Gym {gym_account.gym_id} NO tiene cuentas bancarias! "
                    f"Payouts fallarán."
                )
                # TODO: Notificar al gym
        except Exception as e:
            logger.error(f"Error verificando external accounts: {e}")
```

---

#### 6. `capability.updated`

**Estado:** ❌ **NO IMPLEMENTADO**

**¿Qué es?**
Se dispara cuando **cambia una capability** (ej: card_payments, transfers).

**¿Por qué es útil?**
- Detectar cuando Stripe habilita/deshabilita capacidades específicas
- Más granular que `account.updated`

**Payload del evento:**
```json
{
  "id": "evt_xxx",
  "type": "capability.updated",
  "account": "acct_1RdO0iBiqPTgRrIQ",
  "data": {
    "object": {
      "id": "card_payments",
      "object": "capability",
      "status": "active",
      "requirements": {
        "current_deadline": null,
        "currently_due": [],
        "disabled_reason": null
      }
    },
    "previous_attributes": {
      "status": "pending"
    }
  }
}
```

**Cuándo se dispara:**
- Capability cambia de "pending" a "active"
- Capability deshabilitada por Stripe
- Cambios en requirements de verificación

---

### 🔵 OPCIONALES (Full Coverage)

#### 7. `person.created`

**¿Qué es?**
Se dispara cuando se **agrega una persona** a la cuenta (ej: propietario, representante legal).

**¿Por qué podría ser útil?**
- Auditoría de cambios de ownership
- Tracking de representantes legales

**¿Necesitas implementarlo?**
- ❌ No, a menos que necesites auditoría completa de personas

---

#### 8. `person.updated`

**¿Qué es?**
Se dispara cuando se **actualiza información de una persona** (ej: dirección, verificación).

**¿Necesitas implementarlo?**
- ❌ No para casos de uso normales

---

#### 9. `person.deleted`

**¿Qué es?**
Se dispara cuando se **elimina una persona** de la cuenta.

**¿Necesitas implementarlo?**
- ❌ No para casos de uso normales

---

## Configuración en Stripe Dashboard

### Paso a Paso

#### 1. Acceder a Webhooks

```
https://dashboard.stripe.com/webhooks
```

#### 2. Crear Endpoint

**URL del endpoint:**
```
Producción: https://gymapi-eh6m.onrender.com/api/v1/webhooks/stripe-connect/connect
Staging: https://staging-api.gymflow.com/api/v1/webhooks/stripe-connect/connect
```

#### 3. Seleccionar Eventos

**Configuración Mínima Recomendada:**

```
✅ account.application.deauthorized
✅ account.updated
⚠️ account.external_account.created    (recomendado)
⚠️ account.external_account.updated    (recomendado)
⚠️ account.external_account.deleted    (recomendado)
⚠️ capability.updated                  (recomendado)
```

**Screenshots:**

```
┌────────────────────────────────────────────────────┐
│ Select events to listen to                        │
├────────────────────────────────────────────────────┤
│                                                    │
│ Search for an event...                            │
│                                                    │
│ ☑ account.application.deauthorized (CRITICAL)     │
│ ☑ account.updated (CRITICAL)                      │
│ ☐ account.external_account.created                │
│ ☐ account.external_account.updated                │
│ ☐ account.external_account.deleted                │
│ ☐ capability.updated                              │
│                                                    │
│ [Add endpoint]                                     │
└────────────────────────────────────────────────────┘
```

#### 4. Copiar Webhook Secret

Después de crear el endpoint:

```
1. Click en el endpoint creado
2. Click "Reveal" en "Signing secret"
3. Copiar el secret completo (formato: whsec_...)
4. Agregar a .env:

STRIPE_CONNECT_WEBHOOK_SECRET=whsec_xxx
```

---

## Eventos Implementados

### Estado Actual del Código

**Archivo:** `/app/api/v1/endpoints/webhooks/stripe_connect_webhooks.py`

**Eventos manejados:**

| Evento | Implementado | Líneas | Acción |
|--------|--------------|--------|--------|
| `account.application.deauthorized` | ✅ | 96-153 | Marca cuenta como inactiva |
| `account.updated` | ✅ | 156-212 | Sincroniza capabilities |
| Otros | ❌ | - | Warning en logs |

**Handler principal:**
```python
# Línea 77-85
if event_type == 'account.application.deauthorized':
    await _handle_account_deauthorized(db, event)

elif event_type == 'account.updated':
    await _handle_account_updated(db, event)

else:
    logger.warning(f"⚠️  Evento de Connect no manejado: {event_type}")
```

---

## Eventos Recomendados Adicionales

### Implementación Sugerida

Para agregar los eventos recomendados, modificar `stripe_connect_webhooks.py`:

```python
# Agregar después de línea 81

elif event_type == 'account.external_account.created':
    await _handle_external_account_created(db, event)

elif event_type == 'account.external_account.updated':
    await _handle_external_account_updated(db, event)

elif event_type == 'account.external_account.deleted':
    await _handle_external_account_deleted(db, event)

elif event_type == 'capability.updated':
    await _handle_capability_updated(db, event)
```

### Handlers Sugeridos

```python
async def _handle_external_account_created(db: Session, event: dict):
    """Manejar creación de cuenta bancaria."""
    account_id = event['account']
    external_account = event['data']['object']

    gym_account = db.query(GymStripeAccount).filter(
        GymStripeAccount.stripe_account_id == account_id
    ).first()

    if gym_account:
        logger.info(
            f"💳 Cuenta bancaria agregada - Gym {gym_account.gym_id}: "
            f"{external_account.get('bank_name', 'N/A')} ****{external_account.get('last4', 'N/A')}"
        )


async def _handle_external_account_deleted(db: Session, event: dict):
    """Manejar eliminación de cuenta bancaria."""
    account_id = event['account']
    external_account = event['data']['object']

    gym_account = db.query(GymStripeAccount).filter(
        GymStripeAccount.stripe_account_id == account_id
    ).first()

    if gym_account:
        logger.warning(
            f"⚠️  Cuenta bancaria eliminada - Gym {gym_account.gym_id}: "
            f"****{external_account.get('last4', 'N/A')}"
        )


async def _handle_capability_updated(db: Session, event: dict):
    """Manejar actualización de capability."""
    account_id = event['account']
    capability = event['data']['object']

    gym_account = db.query(GymStripeAccount).filter(
        GymStripeAccount.stripe_account_id == account_id
    ).first()

    if gym_account:
        capability_id = capability['id']
        status = capability['status']
        prev_status = event['data'].get('previous_attributes', {}).get('status')

        if prev_status and prev_status != status:
            logger.info(
                f"🔄 Capability actualizada - Gym {gym_account.gym_id}: "
                f"{capability_id} {prev_status} → {status}"
            )

            # Actualizar campos según capability
            if capability_id == 'card_payments' and status == 'active':
                gym_account.charges_enabled = True
            elif capability_id == 'card_payments' and status in ['inactive', 'disabled']:
                gym_account.charges_enabled = False

            if capability_id == 'transfers' and status == 'active':
                gym_account.payouts_enabled = True
            elif capability_id == 'transfers' and status in ['inactive', 'disabled']:
                gym_account.payouts_enabled = False

            db.commit()
```

---

## Testing de Webhooks

### Stripe CLI

```bash
# 1. Instalar Stripe CLI
brew install stripe/stripe-cli/stripe

# 2. Login
stripe login

# 3. Simular eventos específicos
stripe trigger account.application.deauthorized
stripe trigger account.updated
stripe trigger account.external_account.created
stripe trigger capability.updated

# 4. Escuchar webhooks en tiempo real
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe-connect/connect

# 5. Filtrar por eventos específicos
stripe listen \
  --events account.application.deauthorized,account.updated \
  --forward-to localhost:8000/api/v1/webhooks/stripe-connect/connect
```

### Verificar en Logs

```bash
# Ver logs de webhooks
tail -f logs/app.log | grep "Stripe Connect"

# Buscar eventos específicos
grep "account.application.deauthorized" logs/app.log
grep "CUENTA DESCONECTADA" logs/app.log
```

### Dashboard de Stripe

```
1. Ir a: https://dashboard.stripe.com/webhooks
2. Click en tu endpoint
3. Tab "Logs"
4. Filtrar por tipo de evento
5. Ver requests/responses
```

---

## Matriz de Decisión

### ¿Qué eventos configurar?

| Tu Caso de Uso | Eventos Recomendados |
|----------------|---------------------|
| **Setup básico** | `account.application.deauthorized`, `account.updated` |
| **Producción standard** | Básico + `external_account.*` |
| **Full auditoría** | Todo lo anterior + `capability.updated` |
| **Compliance estricto** | Todo lo anterior + `person.*` |

---

## Checklist de Configuración

### Para Implementar Ahora

- [x] `account.application.deauthorized` - YA IMPLEMENTADO
- [x] `account.updated` - YA IMPLEMENTADO
- [ ] Configurar webhook secret en `.env`
- [ ] Verificar webhook en Stripe Dashboard
- [ ] Testing con Stripe CLI

### Para Implementar Después (Opcional)

- [ ] `account.external_account.created`
- [ ] `account.external_account.updated`
- [ ] `account.external_account.deleted`
- [ ] `capability.updated`

---

## FAQ

### ¿Debo implementar todos los eventos?

**No.** Los críticos son suficientes para la mayoría de casos:
- `account.application.deauthorized`
- `account.updated`

Los demás son opcionales y dependen de tus necesidades de auditoría.

### ¿Qué pasa si no configuro el webhook?

Sin webhook:
- ❌ No detectas cuando un gym desconecta su cuenta
- ❌ Intentas procesar pagos con cuentas desconectadas
- ❌ Errores 403 en producción
- ❌ Estado de BD inconsistente con Stripe

Con webhook:
- ✅ Detección automática de desconexiones
- ✅ BD siempre sincronizada
- ✅ Prevención de errores
- ✅ Logs estructurados para auditoría

### ¿Puedo usar el mismo webhook secret para todos los eventos?

**Sí**, un solo endpoint puede manejar múltiples tipos de eventos.

### ¿Cuánto tiempo tengo para procesar un webhook?

Stripe espera una respuesta en **30 segundos**. Si tu endpoint no responde:
- Stripe reintenta automáticamente
- Backoff exponencial (1min, 5min, 30min, etc.)
- Máximo 3 días de reintentos

### ¿Qué pasa si mi endpoint falla?

1. Stripe reintenta automáticamente
2. Puedes ver los reintentos en Dashboard
3. Después de múltiples fallos, Stripe deshabilita el webhook
4. Recibes email de alerta

---

## Resumen Final

### Configuración Recomendada AHORA

```bash
# 1. Eventos a seleccionar en Stripe Dashboard:
✅ account.application.deauthorized
✅ account.updated

# 2. URL del endpoint:
https://gymapi-eh6m.onrender.com/api/v1/webhooks/stripe-connect/connect

# 3. Copiar webhook secret y agregar a .env:
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_xxx

# 4. Testing:
stripe trigger account.application.deauthorized
stripe trigger account.updated
```

### Eventos Adicionales (Futuro)

Cuando tengas tiempo, considera agregar:
- `account.external_account.created`
- `account.external_account.deleted`
- `capability.updated`

---

**Última actualización:** 2024-12-25
**Versión:** 1.0
**Archivo relacionado:** `app/api/v1/endpoints/webhooks/stripe_connect_webhooks.py`
