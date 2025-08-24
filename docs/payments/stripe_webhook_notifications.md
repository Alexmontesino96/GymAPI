# 📡 Sistema de Notificaciones de Webhooks de Stripe

## 🔄 Flujo Completo de Notificaciones

### ¿Cómo funciona?

**SÍ, el backend recibe notificaciones automáticas de Stripe cuando un usuario paga a través del link administrativo.**

## 📋 Eventos Manejados

### 1. **`checkout.session.completed`** ✅
- **Cuándo**: Cuando el usuario completa el pago en Stripe
- **Qué hace**: 
  - Extrae metadatos de la sesión (user_id, gym_id, plan_id)
  - Activa automáticamente la membresía
  - Actualiza la base de datos con información de Stripe
  - Envía notificación de bienvenida al usuario

### 2. **`invoice.payment_succeeded`** ✅
- **Cuándo**: Renovación automática de suscripción exitosa
- **Qué hace**:
  - Extiende el período de membresía
  - Notifica al usuario sobre renovación exitosa

### 3. **`invoice.payment_failed`** ✅
- **Cuándo**: Fallo en renovación de suscripción
- **Qué hace**:
  - Marca la membresía como morosa
  - Notifica al usuario sobre el problema
  - Sugiere actualizar método de pago

### 4. **`customer.subscription.deleted`** ✅
- **Cuándo**: Suscripción cancelada
- **Qué hace**:
  - Desactiva la membresía
  - Notifica al usuario sobre cancelación

### 5. **`customer.subscription.updated`** ✅
- **Cuándo**: Cambios en la suscripción
- **Qué hace**:
  - Actualiza estado de membresía
  - Maneja pausas, reactivaciones, etc.

## 🔧 Configuración del Webhook

### Endpoint del Webhook
```
POST /api/v1/memberships/webhooks/stripe
```

### Eventos Críticos Requeridos
```
- checkout.session.completed
- invoice.payment_succeeded
- invoice.payment_failed
- customer.subscription.deleted
- customer.subscription.updated
- customer.subscription.trial_will_end
- invoice.payment_action_required
- charge.dispute.created
- payment_intent.payment_failed
```

## 🔐 Seguridad

### Verificación de Signature
```python
# El webhook verifica la signature de Stripe
signature = request.headers.get('stripe-signature')
event = stripe.Webhook.construct_event(
    payload, signature, settings.STRIPE_WEBHOOK_SECRET
)
```

### Rate Limiting
```python
@limiter.limit("100 per minute")
```

## 🎯 Flujo Específico para Links Administrativos

### 1. **Administrador crea link**
```python
POST /api/v1/memberships/admin/create-payment-link
```

### 2. **Usuario paga**
- Stripe procesa el pago
- Genera evento `checkout.session.completed`

### 3. **Webhook recibe notificación**
```python
{
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_...",
            "metadata": {
                "user_id": "123",
                "gym_id": "456",
                "plan_id": "789",
                "admin_email": "admin@gym.com",
                "created_by": "admin",
                "notes": "Membresía especial"
            }
        }
    }
}
```

### 4. **Backend procesa automáticamente**
```python
async def handle_webhook(payload, signature):
    # Verifica signature
    # Extrae metadatos
    # Activa membresía
    # Envía notificaciones
```

## 📱 Notificaciones Enviadas

### Al Usuario
- ✅ "¡Membresía activada exitosamente!"
- 🔄 "Tu suscripción se ha renovado"
- ⚠️ "Problema con tu pago"
- ❌ "Suscripción cancelada"

### A Administradores
- 🚨 "Nueva disputa de pago"
- ⚠️ "Error procesando webhook"
- 📊 "Resumen de pagos"

## 🛠️ Herramientas de Verificación

### Script de Verificación
```bash
python scripts/verify_webhook_setup.py
```

### Verificaciones que realiza:
- ✅ Conexión con Stripe
- ✅ Webhooks configurados
- ✅ Eventos críticos habilitados
- ✅ Webhook secret configurado
- ✅ Endpoint accesible

## 🔍 Monitoreo y Logs

### Logs del Sistema
```python
logger.info(f"Webhook de Stripe procesado: {event_type}")
logger.info(f"Membresía activada para usuario {user_id}")
logger.error(f"Error procesando webhook: {error}")
```

### Stripe Dashboard
- Ve a https://dashboard.stripe.com/webhooks
- Revisa el historial de webhooks
- Verifica entregas exitosas/fallidas

## 🚨 Troubleshooting

### Webhook no se ejecuta
1. **Verificar URL**: Debe ser accesible públicamente
2. **Verificar eventos**: Deben estar habilitados en Stripe
3. **Verificar signature**: STRIPE_WEBHOOK_SECRET debe ser correcto

### Pago no activa membresía
1. **Revisar logs**: Buscar errores en el procesamiento
2. **Verificar metadatos**: Deben incluir user_id, gym_id, plan_id
3. **Verificar usuario**: Debe existir en la base de datos

### Notificaciones no se envían
1. **Verificar OneSignal**: Configuración correcta
2. **Verificar player_id**: Usuario debe tener token válido
3. **Revisar logs**: Errores en el servicio de notificaciones

## 📊 Métricas y Monitoreo

### Webhooks Procesados
- Total de webhooks recibidos
- Webhooks exitosos vs fallidos
- Tiempo de procesamiento

### Activaciones Automáticas
- Membresías activadas automáticamente
- Errores en activación
- Tiempo promedio de activación

## 🔄 Flujo de Recuperación

### Si el webhook falla:
1. **Stripe reintenta** automáticamente
2. **Logs registran** el error
3. **Administradores reciben** alerta
4. **Procesamiento manual** si es necesario

### Endpoint de recuperación:
```python
POST /api/v1/memberships/purchase/success?session_id=cs_...
```

## 🎯 Casos de Uso Específicos

### Link Administrativo
```python
# Metadatos extendidos para tracking
metadata = {
    "user_id": "123",
    "gym_id": "456", 
    "plan_id": "789",
    "admin_email": "admin@gym.com",
    "created_by": "admin",
    "notes": "Membresía especial",
    "expires_at": "2024-02-15T10:00:00Z"
}
```

### Activación Automática
```python
# El webhook activa automáticamente
membership = await membership_service.activate_membership(
    user_id=user_id,
    gym_id=gym_id,
    plan_id=plan_id,
    stripe_customer_id=customer_id,
    stripe_subscription_id=subscription_id
)
```

## ✅ Confirmación Final

**¡SÍ! El sistema está completamente configurado para recibir notificaciones automáticas de Stripe cuando un usuario paga a través del link administrativo.**

- ✅ Webhook endpoint configurado
- ✅ Eventos críticos manejados
- ✅ Activación automática de membresía
- ✅ Notificaciones al usuario
- ✅ Logging completo
- ✅ Manejo de errores
- ✅ Herramientas de verificación 