# 🔧 Configuración Detallada de Webhooks de Stripe

## 📋 **Resumen de Webhooks Requeridos**

Tu sistema maneja **10 eventos críticos** de Stripe que necesitas configurar en el dashboard de Stripe.

### 🎯 **URL del Webhook**
```
https://tu-dominio.com/api/v1/memberships/webhooks/stripe
```

---

## 🔥 **Webhooks Críticos (OBLIGATORIOS)**

### 1. **`checkout.session.completed`** ✅
**Descripción:** Se dispara cuando un usuario completa un pago en Stripe Checkout

**Cuándo ocurre:**
- Usuario termina de pagar con tarjeta
- Pago es procesado exitosamente por Stripe
- Tanto para pagos únicos como suscripciones

**Qué hace tu sistema:**
```python
# Extrae metadatos de la sesión
user_id = metadata.get('user_id')
gym_id = int(metadata.get('gym_id'))
plan_id = int(metadata.get('plan_id'))

# Activa automáticamente la membresía
membership = await self.membership_service.activate_membership(
    user_id=user_id,
    gym_id=gym_id,
    plan_id=plan_id,
    stripe_customer_id=customer_id,
    stripe_subscription_id=subscription_id
)
```

**Importancia:** 🔴 **CRÍTICO** - Sin este webhook, las membresías no se activan automáticamente

---

### 2. **`invoice.payment_succeeded`** ✅
**Descripción:** Pago de factura exitoso (renovaciones de suscripción)

**Cuándo ocurre:**
- Renovación mensual/anual de suscripción
- Pago de factura pendiente
- Finalización de período de prueba con pago exitoso

**Qué hace tu sistema:**
```python
# Extiende el período de membresía
# Notifica al usuario sobre renovación exitosa
# Actualiza fecha de expiración
```

**Importancia:** 🟡 **IMPORTANTE** - Para renovaciones automáticas

---

### 3. **`invoice.payment_failed`** ⚠️
**Descripción:** Fallo en el pago de una factura

**Cuándo ocurre:**
- Tarjeta rechazada en renovación
- Fondos insuficientes
- Tarjeta expirada

**Qué hace tu sistema:**
```python
# Marca la membresía como morosa
# Notifica al usuario sobre el problema
# Sugiere actualizar método de pago
```

**Importancia:** 🟡 **IMPORTANTE** - Para gestionar pagos fallidos

---

### 4. **`customer.subscription.deleted`** ❌
**Descripción:** Suscripción cancelada

**Cuándo ocurre:**
- Usuario cancela su suscripción
- Administrador cancela suscripción
- Cancelación automática por impago

**Qué hace tu sistema:**
```python
# Desactiva la membresía
# Notifica al usuario sobre cancelación
# Actualiza estado en base de datos
```

**Importancia:** 🟡 **IMPORTANTE** - Para gestionar cancelaciones

---

### 5. **`customer.subscription.updated`** 🔄
**Descripción:** Cambios en una suscripción

**Cuándo ocurre:**
- Cambio de plan
- Pausa/reanudación de suscripción
- Actualización de cantidad o precio

**Qué hace tu sistema:**
```python
# Actualiza estado según el status de Stripe
status_mapping = {
    'active': True,
    'past_due': True,  # Mantener activo pero marcar como moroso
    'canceled': False,
    'unpaid': False,
    'trialing': True,
    'paused': False
}

# Envía notificaciones según el cambio
if status == 'past_due':
    await self._notify_payment_overdue(user_gym)
elif status == 'canceled':
    await self._notify_subscription_canceled(user_gym)
```

**Importancia:** 🟡 **IMPORTANTE** - Para cambios de estado

---

## 🔔 **Webhooks Adicionales (RECOMENDADOS)**

### 6. **`customer.subscription.trial_will_end`** ⏰
**Descripción:** Período de prueba terminará pronto

**Cuándo ocurre:**
- 3 días antes del fin del período de prueba
- Configurable en Stripe

**Qué hace tu sistema:**
```python
# Envía recordatorio al usuario
# Actualiza nota sobre fin de prueba
await self._notify_trial_ending(user_gym, trial_end_date)
```

---

### 7. **`invoice.payment_action_required`** 🔐
**Descripción:** Pago requiere acción del cliente (3D Secure)

**Cuándo ocurre:**
- Autenticación 3D Secure requerida
- Verificación adicional del banco

**Qué hace tu sistema:**
```python
# Notifica al usuario que debe completar la autenticación
# Envía link para completar el pago
await self._notify_payment_action_required(user_gym, invoice_id, payment_intent)
```

---

### 8. **`invoice.upcoming`** 📅
**Descripción:** Próxima factura (recordatorio)

**Cuándo ocurre:**
- 7 días antes de la próxima factura
- Configurable en Stripe

**Qué hace tu sistema:**
```python
# Envía recordatorio de próximo pago
# Verifica método de pago válido
await self._notify_upcoming_payment(user_gym, amount, period_end)
```

---

### 9. **`charge.dispute.created`** 🚨
**Descripción:** Nueva disputa/chargeback

**Cuándo ocurre:**
- Cliente disputa el pago con su banco
- Chargeback iniciado

**Qué hace tu sistema:**
```python
# Notifica a administradores
# Prepara documentación para responder
# Suspende acceso si es fraude
await self._notify_dispute_to_admins(dispute_id, amount, reason, gym_id)
```

---

### 10. **`payment_intent.payment_failed`** ❌
**Descripción:** Fallo específico de payment intent

**Cuándo ocurre:**
- Fallo en el procesamiento del pago
- Error específico del payment intent

**Qué hace tu sistema:**
```python
# Analiza razón del fallo
# Sugiere acciones al usuario
# Implementa retry inteligente
await self._notify_payment_failed(user_gym, failure_reason, decline_code)
```

---

## 🛠️ **Configuración Paso a Paso en Stripe**

### **Paso 1: Acceder al Dashboard**
1. Ve a [https://dashboard.stripe.com/webhooks](https://dashboard.stripe.com/webhooks)
2. Inicia sesión en tu cuenta de Stripe

### **Paso 2: Crear Webhook Endpoint**
1. Haz clic en **"Add endpoint"**
2. Ingresa la URL: `https://tu-dominio.com/api/v1/memberships/webhooks/stripe`
3. Selecciona **"Latest API version"**

### **Paso 3: Seleccionar Eventos**
Marca los siguientes eventos:

#### **Eventos Críticos (OBLIGATORIOS):**
- ✅ `checkout.session.completed`
- ✅ `invoice.payment_succeeded`
- ✅ `invoice.payment_failed`
- ✅ `customer.subscription.deleted`
- ✅ `customer.subscription.updated`

#### **Eventos Recomendados:**
- ✅ `customer.subscription.trial_will_end`
- ✅ `invoice.payment_action_required`
- ✅ `invoice.upcoming`
- ✅ `charge.dispute.created`
- ✅ `payment_intent.payment_failed`

### **Paso 4: Configurar Webhook**
1. Haz clic en **"Add endpoint"**
2. Copia el **Webhook Secret** (empieza con `whsec_`)
3. Agrega el secret a tu archivo `.env`:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_tu_webhook_secret_aqui
   ```

---

## 🔐 **Configuración de Seguridad**

### **Webhook Secret**
```bash
# En tu archivo .env
STRIPE_WEBHOOK_SECRET=whsec_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Obtén el webhook secret desde el Dashboard de Stripe:
# https://dashboard.stripe.com/webhooks
```

### **Verificación de Signature**
```python
# Tu sistema verifica automáticamente
event = stripe.Webhook.construct_event(
    payload, signature, settings.STRIPE_WEBHOOK_SECRET
)
```

### **Rate Limiting**
```python
# Protección contra abuso
@limiter.limit("100 per minute")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
```

---

## 🧪 **Pruebas y Verificación**

### **Script de Verificación**
```bash
python scripts/verify_webhook_setup.py
```

### **Prueba Manual en Stripe**
1. Ve a tu webhook en el dashboard
2. Haz clic en **"Send test webhook"**
3. Selecciona `checkout.session.completed`
4. Verifica que tu servidor reciba el evento

### **Logs para Debugging**
```bash
# Buscar logs de webhooks
grep "Procesando webhook de Stripe" logs/app.log

# Verificar eventos procesados
grep "checkout.session.completed" logs/app.log
```

---

## 📊 **Monitoreo de Webhooks**

### **Métricas Importantes**
- ✅ **Tasa de éxito**: > 95%
- ⏱️ **Tiempo de respuesta**: < 10 segundos
- 🔄 **Reintentos**: < 5% de casos

### **Alertas Recomendadas**
- Webhook failures > 5%
- Tiempo de respuesta > 15s
- Eventos no manejados

---

## 🚨 **Troubleshooting**

### **Webhook no se ejecuta**
1. **Verificar URL**: Debe ser accesible públicamente
2. **Verificar eventos**: Deben estar habilitados en Stripe
3. **Verificar signature**: `STRIPE_WEBHOOK_SECRET` debe ser correcto

### **Errores comunes**
```python
# Error: STRIPE_WEBHOOK_SECRET no configurado
"STRIPE_WEBHOOK_SECRET no configurado - webhook rechazado por seguridad"

# Error: Firma inválida
"Firma inválida en webhook"

# Error: Payload inválido
"Payload inválido en webhook"
```

### **Soluciones**
```bash
# Verificar configuración
python scripts/verify_webhook_setup.py

# Verificar variables de entorno
echo $STRIPE_WEBHOOK_SECRET

# Reiniciar servidor después de cambios
systemctl restart gymapi
```

---

## 📋 **Checklist Final**

### **Antes de Producción:**
- [ ] Webhook endpoint creado en Stripe
- [ ] Todos los eventos críticos seleccionados
- [ ] `STRIPE_WEBHOOK_SECRET` configurado
- [ ] URL del webhook accesible públicamente
- [ ] Certificado SSL válido
- [ ] Script de verificación ejecutado exitosamente

### **Después de Configurar:**
- [ ] Prueba manual desde Stripe dashboard
- [ ] Verificar logs de webhook
- [ ] Probar pago real de prueba
- [ ] Confirmar activación de membresía
- [ ] Verificar notificaciones al usuario

---

## 🎯 **Configuración Mínima para Funcionar**

Si solo puedes configurar algunos eventos, estos son los **ABSOLUTAMENTE CRÍTICOS**:

1. **`checkout.session.completed`** - Para activar membresías
2. **`customer.subscription.updated`** - Para cambios de estado
3. **`invoice.payment_failed`** - Para gestionar pagos fallidos

**¡Con estos 3 eventos tu sistema funcionará correctamente!**

---

## 🔗 **URLs de Configuración**

### **Stripe Dashboard:**
- [Webhooks](https://dashboard.stripe.com/webhooks)
- [API Keys](https://dashboard.stripe.com/apikeys)
- [Logs](https://dashboard.stripe.com/logs)

### **Documentación Stripe:**
- [Webhook Events](https://stripe.com/docs/api/events/types)
- [Webhook Endpoints](https://stripe.com/docs/webhooks)
- [Testing Webhooks](https://stripe.com/docs/webhooks/test)

---

## ✅ **Confirmación Final**

Una vez configurados todos los webhooks, tu sistema tendrá:

- ✅ **Activación automática** de membresías
- ✅ **Renovaciones automáticas** de suscripciones
- ✅ **Gestión de pagos fallidos**
- ✅ **Notificaciones en tiempo real**
- ✅ **Manejo de cancelaciones**
- ✅ **Alertas de disputas**
- ✅ **Recordatorios de pagos**

**¡Tu sistema de pagos estará completamente automatizado!** 