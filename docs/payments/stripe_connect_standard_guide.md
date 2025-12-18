# Guía Completa: Stripe Connect Standard Accounts

## Índice
1. [Visión General](#visión-general)
2. [Diferencias entre Tipos de Cuenta](#diferencias-entre-tipos-de-cuenta)
3. [Flujo de Onboarding](#flujo-de-onboarding)
4. [Endpoints de API](#endpoints-de-api)
5. [Manejo de Desconexión](#manejo-de-desconexión)
6. [Configuración de Webhooks](#configuración-de-webhooks)
7. [Troubleshooting](#troubleshooting)

---

## Visión General

### ¿Qué es Stripe Connect?

Stripe Connect permite que cada gimnasio tenga su propia cuenta de Stripe separada, manteniendo aislamiento total de pagos y cumplimiento regulatorio.

### Cambio a Standard Accounts (Diciembre 2024)

**Tipo anterior**: Express Accounts
**Tipo actual**: **Standard Accounts** (default desde diciembre 2024)

**Razón del cambio**: Los gimnasios solicitaron:
- Mayor autonomía en gestión de pagos
- Dashboard propio de Stripe
- Capacidad de desconectarse de la plataforma si lo desean

---

## Diferencias entre Tipos de Cuenta

### Express Accounts (Anterior)

✅ **Ventajas**:
- Onboarding simplificado
- Dashboard embebido limitado
- Mayor control de la plataforma sobre la cuenta
- Onboarding más rápido

❌ **Desventajas**:
- No pueden acceder directamente al dashboard completo de Stripe
- Requieren login links temporales (60 min)
- No pueden desconectarse fácilmente
- Menos independencia

**Caso de uso**: Plataformas que quieren mantener control total sobre la experiencia del usuario.

---

### Standard Accounts (Actual - RECOMENDADO)

✅ **Ventajas**:
- **Dashboard propio**: Acceso directo a https://dashboard.stripe.com
- **Independencia total**: Pueden desconectarse de la plataforma cuando quieran
- **Control completo**: Gestión total de su cuenta de Stripe
- **Sin restricciones**: Acceso a todas las funcionalidades de Stripe
- **Pueden conectar cuenta existente**: Via OAuth (opcional)

❌ **Desventajas**:
- Onboarding ligeramente más completo (5-10 minutos)
- Pueden desconectarse sin previo aviso (requiere webhook)
- Menos control de la plataforma

**Caso de uso**: Gimnasios establecidos que quieren autonomía y control sobre sus pagos.

---

### Custom Accounts

⚠️ **No implementado actualmente**

Requiere implementación completa de compliance por parte de la plataforma. Solo usar si necesitas UI completamente personalizada.

---

## Flujo de Onboarding

### Paso 1: Crear Cuenta

**Endpoint**: `POST /api/v1/stripe-connect/accounts`

**Request**:
```bash
curl -X POST https://api.gymapi.com/api/v1/stripe-connect/accounts \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "US",
    "account_type": "standard"
  }'
```

**Response**:
```json
{
  "message": "Cuenta creada exitosamente",
  "account_id": "acct_xxx",
  "account_type": "standard",
  "country": "US",
  "onboarding_completed": false,
  "charges_enabled": false,
  "payouts_enabled": false,
  "status": "created"
}
```

**Notas**:
- Si no se especifica `account_type`, se usa "standard" por defecto
- La cuenta se crea en Stripe pero aún no está lista para procesar pagos

---

### Paso 2: Generar Link de Onboarding

**Endpoint**: `POST /api/v1/stripe-connect/accounts/onboarding-link`

**Request**:
```bash
curl -X POST https://api.gymapi.com/api/v1/stripe-connect/accounts/onboarding-link \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_url": "https://app.gymapi.com/admin/stripe/reauth",
    "return_url": "https://app.gymapi.com/admin/stripe/complete"
  }'
```

**Response**:
```json
{
  "message": "Link de onboarding creado exitosamente",
  "onboarding_url": "https://connect.stripe.com/setup/s/abc123...",
  "expires_in_minutes": 60,
  "instructions": "Complete la configuración siguiendo el link. Válido por 1 hora."
}
```

**Notas**:
- El link expira en 1 hora
- Si expira, puedes generar uno nuevo
- `refresh_url`: A dónde redirigir si el usuario sale antes de terminar
- `return_url`: A dónde redirigir cuando complete

---

### Paso 3: Completar Onboarding en Stripe

El admin abre el `onboarding_url` y completa:

1. **Información del negocio**
   - Nombre legal del gimnasio
   - Dirección física
   - Descripción del negocio
   - Sitio web

2. **Información bancaria**
   - Cuenta bancaria para recibir pagos
   - Routing number / IBAN según país

3. **Verificación de identidad**
   - ID del representante legal
   - Verificación de documentos

**Tiempo estimado**: 5-10 minutos

---

### Paso 4: Verificación Automática

Una vez completado, Stripe redirige a `return_url` y el sistema verifica automáticamente.

**Endpoint**: `GET /api/v1/stripe-connect/accounts/status`

**Response (completado)**:
```json
{
  "account_id": "acct_xxx",
  "account_type": "standard",
  "country": "US",
  "currency": "USD",
  "onboarding_completed": true,
  "charges_enabled": true,
  "payouts_enabled": true,
  "details_submitted": true,
  "is_active": true,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Estados importantes**:
- `charges_enabled: true` → Puede procesar pagos ✅
- `payouts_enabled: true` → Puede recibir transferencias ✅
- `onboarding_completed: true` → Configuración completa ✅

---

## Endpoints de API

### GET `/accounts/connection-status` 🆕

Verifica si la cuenta sigue conectada (importante para Standard).

**Response (conectada)**:
```json
{
  "connected": true,
  "account_id": "acct_xxx",
  "account_type": "standard",
  "can_disconnect": true,
  "direct_dashboard_access": true,
  "charges_enabled": true,
  "payouts_enabled": true,
  "message": "Cuenta conectada y funcionando"
}
```

**Response (desconectada)**:
```json
{
  "connected": false,
  "account_id": "acct_xxx",
  "account_type": "standard",
  "message": "Cuenta desconectada o inactiva",
  "action_required": "Reconectar cuenta o crear nueva"
}
```

**Cuándo usar**:
- Antes de procesar pagos
- En dashboard admin (mostrar estado)
- Debugging de problemas de pagos

---

### POST `/accounts/dashboard-link` (Mejorado)

Información de acceso al dashboard según tipo de cuenta.

**Response para Standard**:
```json
{
  "message": "Acceso directo al dashboard disponible (Standard Account)",
  "dashboard_url": "https://dashboard.stripe.com",
  "direct_access": true,
  "account_type": "standard",
  "account_id": "acct_xxx",
  "note": "Con Standard accounts tiene acceso directo a Stripe...",
  "instructions": "1. Vaya a https://dashboard.stripe.com\n2. Inicie sesión..."
}
```

**Response para Express**:
```json
{
  "message": "Link de acceso al dashboard creado exitosamente",
  "dashboard_url": "https://connect.stripe.com/express/abc123...",
  "direct_access": false,
  "account_type": "express",
  "expires_in_minutes": 60,
  "instructions": "El link es válido por 60 minutos"
}
```

**Diferencia clave**:
- **Standard**: URL directa a stripe.com (no expira)
- **Express**: Login link temporal (expira en 60 min)

---

## Manejo de Desconexión

### ⚠️ IMPORTANTE: Standard Accounts pueden Desconectarse

A diferencia de Express, los gimnasios con Standard accounts pueden:
1. Ir a https://dashboard.stripe.com/settings/applications
2. Buscar tu aplicación
3. Hacer clic en "Disconnect"

**Consecuencia**: La plataforma pierde acceso a la cuenta inmediatamente.

---

### Webhook de Desconexión (CRÍTICO)

**Endpoint**: `POST /api/v1/webhooks/stripe-connect/connect`

**Evento**: `account.application.deauthorized`

**Qué hace el sistema automáticamente**:
1. ✅ Recibe webhook de Stripe
2. ✅ Verifica firma del webhook (seguridad)
3. ✅ Marca `gym_account.is_active = False`
4. ✅ Marca `charges_enabled = False`
5. ✅ Marca `payouts_enabled = False`
6. ✅ Registra en logs
7. 🔜 Notifica a administradores del gym (TODO)

**Ejemplo de evento**:
```json
{
  "type": "account.application.deauthorized",
  "account": "acct_xxx",
  "created": 1672531200
}
```

**Handler completo**: `app/api/v1/endpoints/webhooks/stripe_connect_webhooks.py`

---

### ¿Qué pasa cuando se desconecta?

1. **Pagos se deshabilitan automáticamente**
   - No se pueden crear nuevas suscripciones
   - Suscripciones existentes no se renuevan
   - Checkouts fallan

2. **Estado en BD se actualiza**
   - `is_active: false`
   - `charges_enabled: false`
   - `payouts_enabled: false`

3. **Administradores son notificados**
   - (Cuando se implemente notificación)

4. **Para reconectar**:
   - Crear nueva cuenta de Stripe, O
   - Contactar a soporte para reautorizar

---

## Configuración de Webhooks

### Webhook de Pagos (Existente)

**URL**: `https://tu-dominio.com/api/v1/memberships/webhooks/stripe`

**Eventos**:
- `checkout.session.completed`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.deleted`
- `customer.subscription.updated`
- (y otros 5+ eventos)

**Secret**: `STRIPE_WEBHOOK_SECRET` en .env

---

### Webhook de Connect (NUEVO - OBLIGATORIO)

**URL**: `https://tu-dominio.com/api/v1/webhooks/stripe-connect/connect`

**Eventos**:
- ✅ `account.application.deauthorized` (CRÍTICO)
- ✅ `account.updated` (recomendado)

**Secret**: `STRIPE_CONNECT_WEBHOOK_SECRET` en .env

**Pasos para configurar**:

1. Ir a https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Ingresar URL: `https://tu-dominio.com/api/v1/webhooks/stripe-connect/connect`
4. Seleccionar eventos:
   - `account.application.deauthorized`
   - `account.updated`
5. Click "Add endpoint"
6. Copiar "Signing secret" (empieza con `whsec_`)
7. Agregar a `.env`:
   ```bash
   STRIPE_CONNECT_WEBHOOK_SECRET=whsec_xxx
   ```
8. Reiniciar servidor

**Verificación**:
```bash
# Ver logs para confirmar que webhook se recibe
tail -f logs/app.log | grep "stripe_connect"
```

---

## Troubleshooting

### Problema: "Cuenta desconectada o inactiva"

**Síntomas**:
- Checkouts fallan
- Dashboard link no funciona
- `GET /accounts/connection-status` retorna `connected: false`

**Causa**: El gimnasio desconectó su cuenta Standard desde Stripe dashboard

**Solución**:
1. Verificar en logs: `grep "desautorizada" logs/app.log`
2. Contactar al gimnasio y preguntarle
3. Opciones:
   - Crear nueva cuenta de Stripe
   - Reautorizar cuenta existente (contactar Stripe Support)

---

### Problema: Webhook no se recibe

**Síntomas**:
- Cuenta se desconecta pero BD sigue mostrando `is_active: true`
- No hay logs de webhook

**Diagnóstico**:
```bash
# Verificar variable de entorno
echo $STRIPE_CONNECT_WEBHOOK_SECRET

# Verificar endpoint público
curl -X POST https://tu-dominio.com/api/v1/webhooks/stripe-connect/connect \
  -H "Content-Type: application/json" \
  -d '{"test": "ping"}'
# Debe retornar 400 (missing signature) NO 404
```

**Soluciones**:
1. Verificar que `STRIPE_CONNECT_WEBHOOK_SECRET` está configurado en `.env`
2. Verificar que el endpoint es público (sin autenticación)
3. Verificar en Stripe Dashboard → Webhooks → Ver logs de intentos
4. Verificar firewall/proxy no bloquea requests de Stripe

---

### Problema: Onboarding link expiró

**Síntomas**:
- Link de onboarding muestra error 404 o "expired"

**Solución**:
```bash
# Generar nuevo link (puedes hacerlo cuantas veces quieras)
curl -X POST https://api.gymapi.com/api/v1/stripe-connect/accounts/onboarding-link \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Nota**: Los links de onboarding expiran en 1 hora por seguridad.

---

### Problema: `charges_enabled: false` después de onboarding

**Causa**: Stripe está revisando la cuenta o requiere información adicional

**Diagnóstico**:
```bash
# Verificar estado
curl https://api.gymapi.com/api/v1/stripe-connect/accounts/status \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Soluciones**:
1. Revisar email del gimnasio (Stripe envía notificaciones)
2. Acceder al dashboard de Stripe y ver requirements
3. Completar información faltante
4. Esperar aprobación de Stripe (puede tomar 24-48h en algunos casos)

---

## Mensajes para Usuarios

### Al crear cuenta Standard

```
¡Bienvenido a Stripe Connect!

Has seleccionado una cuenta Standard de Stripe. Esto te da:

✅ Acceso completo a tu dashboard en stripe.com
✅ Control total de tu cuenta
✅ Independencia de la plataforma
✅ Reportes y análisis detallados

Haz clic en el link para completar la configuración (5-10 minutos).
```

---

### Al acceder al dashboard (Standard)

```
Tu cuenta Standard te permite acceder directamente a:

🔗 https://dashboard.stripe.com

Puedes iniciar sesión en cualquier momento con tus credenciales de Stripe.
No necesitas login links temporales.
```

---

### Si desconectan la cuenta

```
⚠️ Tu cuenta de Stripe se ha desconectado de la plataforma.

Esto significa:
❌ Los pagos están deshabilitados
❌ No puedes crear nuevas suscripciones
❌ Las suscripciones existentes no se renuevan

Para reactivar:
1. Crea una nueva cuenta de Stripe, O
2. Contacta a soporte para reconectar tu cuenta existente

Si desconectaste por error, podemos ayudarte a reconectar.
```

---

## Recursos Adicionales

**Documentación oficial de Stripe**:
- [Connect Standard Accounts](https://docs.stripe.com/connect/standard-accounts)
- [Connect Onboarding](https://docs.stripe.com/connect/onboarding)
- [Connect Webhooks](https://docs.stripe.com/connect/webhooks)
- [Account Links](https://docs.stripe.com/connect/account-links)

**Archivos del proyecto**:
- Endpoint: `app/api/v1/endpoints/stripe_connect.py`
- Servicio: `app/services/stripe_connect_service.py`
- Webhooks: `app/api/v1/endpoints/webhooks/stripe_connect_webhooks.py`
- Modelos: `app/models/stripe_profile.py`

---

## Changelog

**Diciembre 2024**:
- ✅ Cambio de default: Express → Standard
- ✅ Implementación de webhook de desconexión
- ✅ Nuevo endpoint `GET /accounts/connection-status`
- ✅ Mejora de endpoint `POST /accounts/dashboard-link` con lógica para Standard
- ✅ Documentación completa

**Anteriormente**:
- Express Accounts como default
- Sin manejo de desconexiones
