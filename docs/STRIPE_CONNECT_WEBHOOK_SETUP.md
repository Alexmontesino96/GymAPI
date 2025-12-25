# Configuración de Webhook de Stripe Connect

## ¿Por qué es crítico este webhook?

Standard Accounts pueden **desconectarse voluntariamente** de la plataforma desde su Stripe Dashboard. El webhook `account.application.deauthorized` detecta esto automáticamente y marca la cuenta como inactiva en nuestra base de datos.

### Sin este webhook:

- ❌ Cuentas desconectadas seguirían apareciendo como activas en BD
- ❌ Errores 403 `account_invalid` en producción sin previo aviso
- ❌ Pagos de eventos fallando sin explicación clara para el usuario
- ❌ Requiere verificación manual constante

### Con el webhook configurado:

- ✅ Detección automática de desconexiones en tiempo real
- ✅ Cuenta marcada como inactiva inmediatamente
- ✅ Logs estructurados para auditoría
- ✅ Sistema previene errores antes de que ocurran
- ✅ (Futuro) Notificaciones automáticas a administradores

---

## Pasos de Configuración

### 1. Acceder a Stripe Dashboard

- **URL:** https://dashboard.stripe.com/webhooks
- Login con credenciales de administrador de Stripe
- Si tienes múltiples cuentas, asegúrate de estar en la cuenta correcta

### 2. Crear Nuevo Endpoint

1. Click en **"Add endpoint"** (botón azul en la esquina superior derecha)

2. **Configurar URL del endpoint:**
   - **Producción:** `https://api.tu-dominio.com/api/v1/webhooks/stripe-connect/connect`
   - **Staging:** `https://staging-api.tu-dominio.com/api/v1/webhooks/stripe-connect/connect`
   - **Desarrollo local (con ngrok):** `https://tu-subdominio.ngrok.io/api/v1/webhooks/stripe-connect/connect`

   > **Nota:** Para desarrollo local, usa ngrok:
   > ```bash
   > ngrok http 8000
   > # Copia la URL HTTPS que te da ngrok
   > ```

3. **Descripción (recomendada):**
   ```
   Webhook para detectar desconexiones y actualizaciones de cuentas de Stripe Connect (Standard Accounts)
   ```

### 3. Seleccionar Eventos

Marca los siguientes eventos en la lista:

#### Eventos Críticos:

- ✅ **`account.application.deauthorized`** (CRÍTICO)
  - Se dispara cuando un gimnasio con Standard Account desconecta su cuenta
  - Acción: Marca automáticamente `is_active=False` en BD

#### Eventos Recomendados:

- ✅ **`account.updated`** (Recomendado)
  - Se dispara cuando cambia información de la cuenta (onboarding, capabilities, etc.)
  - Acción: Sincroniza `charges_enabled`, `payouts_enabled`, `details_submitted`

### 4. Copiar Webhook Secret

1. Después de crear el endpoint, Stripe muestra el **"Signing secret"**
2. Click en **"Reveal"** para ver el secret completo
3. Formato del secret: `whsec_...` (ejemplo: `whsec_abc123xyz789...`)
4. **Copiar el secret completo** - lo necesitarás para el siguiente paso

> **Importante:** Este secret es como una contraseña. Guárdalo de forma segura y no lo compartas públicamente.

### 5. Agregar a Variables de Entorno

Agrega el webhook secret a tu archivo `.env`:

```bash
# Webhook de Stripe Connect (para detectar desconexiones)
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_abc123xyz789...
```

**Archivos a modificar según entorno:**

- **Producción:** `.env` en el servidor
- **Staging:** `.env.staging`
- **Desarrollo:** `.env` local

### 6. Reiniciar Servidor

Para que el servidor tome la nueva variable de entorno:

```bash
# Con Docker
docker-compose restart

# Con systemd
sudo systemctl restart gymapi

# En desarrollo
# Ctrl+C y volver a ejecutar: python app_wrapper.py
```

### 7. Verificar Configuración

Ejecuta el script de verificación:

```bash
python scripts/verify_stripe_connect_webhook.py
```

**Salida esperada:**

```
======================================================================
VERIFICACIÓN DE WEBHOOK DE STRIPE CONNECT
======================================================================

📋 PASO 1: Verificando variable de entorno...
✅ STRIPE_CONNECT_WEBHOOK_SECRET configurado
   Valor: whsec_abc123...xyz9

📋 PASO 2: Verificando endpoint de webhook...
✅ Archivo de webhook existe
   Ubicación: /app/api/v1/endpoints/webhooks/stripe_connect_webhooks.py

======================================================================
RESUMEN
======================================================================

✅ Configuración básica OK

⚠️  IMPORTANTE: Asegúrate de que el webhook esté configurado en Stripe Dashboard
   para que las desconexiones se detecten automáticamente.
```

---

## Eventos Manejados por el Sistema

### `account.application.deauthorized`

**¿Cuándo se dispara?**
- Cuando un gimnasio con Standard Account desconecta su cuenta desde Stripe Dashboard
- Cuando revocan el acceso a la aplicación

**Acción del sistema:**

1. Recibe el evento de Stripe
2. Verifica la firma del webhook (seguridad)
3. Busca la cuenta en BD por `stripe_account_id`
4. Marca como inactiva:
   ```python
   gym_account.is_active = False
   gym_account.charges_enabled = False
   gym_account.payouts_enabled = False
   ```
5. Log de warning con detalles
6. Commit a BD
7. (TODO) Notificar a administradores del gym

**Código:** Ver `/app/api/v1/endpoints/webhooks/stripe_connect_webhooks.py` líneas 96-153

**Ejemplo de payload:**

```json
{
  "id": "evt_...",
  "type": "account.application.deauthorized",
  "account": "acct_1RdO0iBiqPTgRrIQ",
  "created": 1703456789,
  "data": {
    "object": {
      "id": "acct_1RdO0iBiqPTgRrIQ",
      ...
    }
  }
}
```

### `account.updated`

**¿Cuándo se dispara?**
- Cuando el gym completa o actualiza su onboarding
- Cuando Stripe habilita/deshabilita capabilities (charges, payouts)
- Cuando cambian detalles de la cuenta

**Acción del sistema:**

1. Recibe el evento de Stripe
2. Verifica la firma del webhook
3. Busca la cuenta en BD
4. Sincroniza campos importantes:
   ```python
   gym_account.charges_enabled = account_data["charges_enabled"]
   gym_account.payouts_enabled = account_data["payouts_enabled"]
   gym_account.onboarding_completed = account_data["details_submitted"]
   ```
5. Log de cambios importantes
6. Actualiza `updated_at`
7. Commit a BD

**Código:** Ver líneas 156-212 del mismo archivo

---

## Testing

### Test Manual con Stripe Dashboard

1. **Crear cuenta de prueba:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/stripe-connect/accounts \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json"
   ```

2. **Completar onboarding** (obtener link y completar)

3. **Desconectar cuenta:**
   - Ir a Stripe Dashboard
   - Buscar la cuenta conectada
   - Click en "Disconnect" o "Revoke access"

4. **Verificar que BD se actualizó:**
   ```sql
   SELECT gym_id, stripe_account_id, is_active, charges_enabled
   FROM gym_stripe_accounts
   WHERE stripe_account_id = 'acct_xxx';
   -- Debería mostrar is_active = false
   ```

### Test con Stripe CLI

#### 1. Instalar Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows
scoop install stripe

# Linux
# Descargar desde: https://github.com/stripe/stripe-cli/releases
```

#### 2. Login

```bash
stripe login
# Abrirá navegador para autenticar
```

#### 3. Simular evento de desconexión

```bash
stripe trigger account.application.deauthorized
```

**Salida esperada:**

```
Setting up fixture for: account.application.deauthorized
Running fixture for: account.application.deauthorized
Trigger succeeded! Check dashboard for event details.
```

#### 4. Escuchar webhooks en tiempo real (desarrollo)

```bash
# Forwarding de webhooks a tu servidor local
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe-connect/connect

# Salida:
# > Ready! Your webhook signing secret is whsec_xxx (^C to quit)
```

Copia el `whsec_xxx` y agrégalo a tu `.env` local.

#### 5. Verificar logs

```bash
# En otra terminal, monitorea los logs
tail -f logs/app.log | grep "CUENTA DESCONECTADA"

# O busca eventos específicos
grep "account.application.deauthorized" logs/app.log
```

---

## Troubleshooting

### Error: "Webhook not configured"

**Síntoma:** Eventos no se procesan, logs muestran "Webhook signature verification failed"

**Solución:**

1. Verificar que `STRIPE_CONNECT_WEBHOOK_SECRET` esté en `.env`
2. Verificar que el valor sea correcto (copiar completo desde Stripe)
3. Reiniciar servidor después de agregar la variable
4. Verificar con: `python scripts/verify_stripe_connect_webhook.py`

### Error: "Invalid signature"

**Síntoma:** Logs muestran `stripe.error.SignatureVerificationError`

**Causas posibles:**

1. **Secret incorrecto:**
   - Verificar que copiaste el secret completo desde Stripe
   - No debe tener espacios al inicio/final
   - Formato correcto: `whsec_...`

2. **Endpoint incorrecto:**
   - Verificar que la URL en Stripe Dashboard coincida exactamente con tu endpoint
   - Incluir `/api/v1/webhooks/stripe-connect/connect`

3. **Webhook de producción en desarrollo:**
   - Webhooks de producción usan un secret diferente
   - Usa Stripe CLI para desarrollo local

**Solución:**

```bash
# Verificar el secret en Stripe Dashboard
# 1. Ir a Webhooks
# 2. Click en tu endpoint
# 3. Click "Reveal" en Signing secret
# 4. Comparar con el valor en .env
```

### Webhook no se dispara

**Síntoma:** Desconectas una cuenta pero `is_active` sigue en `true`

**Verificaciones:**

1. **URL accesible públicamente:**
   ```bash
   # El endpoint debe ser accesible desde internet
   curl https://api.tu-dominio.com/api/v1/webhooks/stripe-connect/connect
   # Debe responder (aunque sea error 400 por falta de firma)
   ```

2. **Ambiente correcto:**
   - Producción usa webhook de producción
   - Test mode usa webhook de test mode
   - No mezclar los dos

3. **Eventos seleccionados:**
   - Verificar que `account.application.deauthorized` esté marcado en Stripe

4. **Logs en Stripe Dashboard:**
   - Ir a Dashboard > Developers > Webhooks
   - Click en tu endpoint
   - Tab "Logs" muestra intentos de entrega
   - Verificar errores de entrega

### Desarrollo local (localhost)

**Problema:** Stripe no puede enviar webhooks a `localhost`

**Solución: Usar ngrok**

```bash
# 1. Instalar ngrok
brew install ngrok  # macOS
# O descargar de: https://ngrok.com/download

# 2. Iniciar tunnel
ngrok http 8000

# 3. Copiar URL HTTPS (ej: https://abc123.ngrok.io)

# 4. Configurar webhook en Stripe con:
https://abc123.ngrok.io/api/v1/webhooks/stripe-connect/connect

# 5. Usar Stripe CLI (alternativa más simple):
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe-connect/connect
```

---

## Monitoreo y Mantenimiento

### Query para verificar cuentas desconectadas

```sql
-- Cuentas marcadas como inactivas (potencialmente desconectadas)
SELECT
    gym_id,
    stripe_account_id,
    account_type,
    is_active,
    charges_enabled,
    updated_at,
    EXTRACT(EPOCH FROM (NOW() - updated_at))/3600 as hours_since_update
FROM gym_stripe_accounts
WHERE is_active = false
ORDER BY updated_at DESC;
```

### Logs estructurados a buscar

```bash
# Desconexiones detectadas
grep "CUENTA DESCONECTADA" logs/app.log

# Webhooks recibidos
grep "account.application.deauthorized" logs/app.log

# Errores de webhook
grep "SignatureVerificationError" logs/app.log

# Sincronizaciones exitosas
grep "account.updated" logs/app.log
```

### Alertas recomendadas

**1. Alerta de cuenta desconectada:**

```python
# En el webhook handler, después de marcar como inactiva:
send_alert(
    level="WARNING",
    title=f"Cuenta Stripe desconectada - Gym {gym_id}",
    message=f"Account {account_id} ha sido desautorizada",
    channel="#stripe-alerts"
)
```

**2. Webhook fallido:**

Si Stripe no puede entregar el webhook después de múltiples reintentos, configurar alerta en Stripe Dashboard.

---

## Configuración Avanzada

### Múltiples entornos (Producción + Staging)

Si tienes múltiples entornos, necesitas webhooks separados:

**Producción (Live mode):**

```bash
# .env.production
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_live_xxx

# Endpoint en Stripe (Live mode):
# https://api.produccion.com/api/v1/webhooks/stripe-connect/connect
```

**Staging (Test mode):**

```bash
# .env.staging
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_test_xxx

# Endpoint en Stripe (Test mode):
# https://api.staging.com/api/v1/webhooks/stripe-connect/connect
```

### Rate Limiting

El endpoint de webhook NO debe tener rate limiting agresivo, ya que Stripe puede enviar múltiples eventos rápidamente.

Verificar en `app/middleware/rate_limit.py` que el endpoint esté excluido o tenga límite alto.

### Retry Logic

Stripe reintenta webhooks fallidos automáticamente:

- Primer reintento: inmediato
- Siguientes: con backoff exponencial
- Máximo: 3 días

Si tu endpoint falla consistentemente, Stripe eventualmente deshabilitará el webhook y enviará email de alerta.

---

## FAQ

### ¿Qué pasa si no configuro el webhook?

El sistema seguirá funcionando, pero:
- Cuentas desconectadas NO se marcarán como inactivas automáticamente
- Debes ejecutar `diagnose_gym_stripe_account.py` manualmente para cada gym
- Mayor riesgo de errores 403 en producción

### ¿Puedo usar el mismo webhook secret en múltiples entornos?

**No.** Cada webhook en Stripe tiene su propio secret único. Producción y staging deben tener secrets diferentes.

### ¿Qué eventos adicionales debería agregar?

Opcionalmente puedes agregar:

- `account.external_account.created` - Cuando agregan cuenta bancaria
- `account.external_account.updated` - Cuando actualizan cuenta bancaria
- `capability.updated` - Cuando cambian capabilities

Pero `account.application.deauthorized` y `account.updated` son los críticos.

### ¿Cómo sé si el webhook está funcionando?

1. **Verificar logs en Stripe Dashboard:**
   - Ir a Webhooks > Tu endpoint > Tab "Logs"
   - Deberías ver requests exitosos (status 200)

2. **Simular con Stripe CLI:**
   ```bash
   stripe trigger account.application.deauthorized
   ```

3. **Verificar BD después de desconexión real:**
   ```sql
   SELECT is_active FROM gym_stripe_accounts WHERE gym_id = X;
   -- Debe ser false si se desconectó
   ```

### ¿Puedo probar sin desconectar una cuenta real?

Sí, usa Stripe CLI:

```bash
stripe trigger account.application.deauthorized
```

Esto simula el evento sin desconectar ninguna cuenta real.

---

## Próximos Pasos

Una vez configurado el webhook:

1. ✅ Ejecutar `python scripts/verify_stripe_connect_webhook.py`
2. ✅ Probar con Stripe CLI: `stripe trigger account.application.deauthorized`
3. ✅ Verificar logs del servidor para confirmar recepción
4. ✅ Verificar BD para confirmar que `is_active` se actualiza
5. ✅ Documentar el webhook secret en tu gestor de secretos (1Password, Vault, etc.)
6. ⏳ (Futuro) Implementar notificaciones a admins cuando se desconecta cuenta
7. ⏳ (Futuro) Dashboard en frontend mostrando estado de conexión de Stripe

---

## Referencias

- [Stripe Connect Webhooks Documentation](https://stripe.com/docs/connect/webhooks)
- [Stripe CLI Documentation](https://stripe.com/docs/stripe-cli)
- [Webhook Best Practices](https://stripe.com/docs/webhooks/best-practices)
- [Testing Webhooks](https://stripe.com/docs/webhooks/test)

---

**Última actualización:** 2025-12-25
**Autor:** Sistema GymAPI
**Versión:** 1.0
