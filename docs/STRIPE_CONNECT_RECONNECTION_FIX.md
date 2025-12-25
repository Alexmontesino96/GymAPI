# Fix: Reconexión de Cuentas Stripe Connect Desconectadas

## 📋 Problema Identificado

**Issue reportado:** El endpoint `GET /api/v1/stripe-connect/accounts/connection-status` devolvía:

```json
{
  "connected": false,
  "message": "No hay cuenta de Stripe configurada",
  "action_required": "Crear cuenta de Stripe Connect"
}
```

**Estado real en BD (Gym 4):**
```sql
SELECT stripe_account_id, is_active, onboarding_completed
FROM gym_stripe_accounts
WHERE gym_id = 4;

-- Resultado:
-- stripe_account_id: acct_1RdO0iBiqPTgRrIQ
-- is_active: false
-- onboarding_completed: true
```

**Conclusión:** La cuenta **SÍ EXISTE** pero está desconectada. La acción correcta es **RECONECTAR**, no crear una nueva cuenta.

---

## 🔍 Causa Raíz

### Problema 1: Consulta Incorrecta en Servicio

**Archivo:** `app/services/stripe_connect_service.py:538-543`

```python
# ❌ ANTES (INCORRECTO)
def get_gym_stripe_account(self, db: Session, gym_id: int):
    return db.query(GymStripeAccount).filter(
        GymStripeAccount.gym_id == gym_id,
        GymStripeAccount.is_active == True  # ← Excluye cuentas desconectadas
    ).first()
```

**Impacto:** El método devolvía `None` para cuentas desconectadas, impidiendo:
- Verificar estado real de la cuenta
- Generar links de reconexión
- Distinguir entre "no existe cuenta" vs "cuenta desconectada"

### Problema 2: Validación Incorrecta en Onboarding

**Archivo:** `app/api/v1/endpoints/stripe_connect.py:196-200`

```python
# ❌ ANTES (INCORRECTO)
if gym_account.onboarding_completed:
    raise HTTPException(
        status_code=400,
        detail="El gimnasio ya completó la configuración de Stripe"
    )
```

**Impacto:** Impedía regenerar onboarding links para cuentas desconectadas que ya habían completado el onboarding previamente.

---

## ✅ Solución Implementada

### Fix 1: Parámetro `include_inactive` en Servicio

**Archivo:** `app/services/stripe_connect_service.py:538-564`

```python
# ✅ DESPUÉS (CORRECTO)
def get_gym_stripe_account(
    self,
    db: Session,
    gym_id: int,
    include_inactive: bool = False  # ← NUEVO PARÁMETRO
) -> Optional[GymStripeAccount]:
    """
    Obtener cuenta de Stripe de un gym.

    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        include_inactive: Si es True, incluye cuentas inactivas/desconectadas
                        Útil para endpoints de diagnóstico y reconexión
    """
    query = db.query(GymStripeAccount).filter(
        GymStripeAccount.gym_id == gym_id
    )

    # Por defecto, solo devolver cuentas activas (para operaciones de pago)
    if not include_inactive:
        query = query.filter(GymStripeAccount.is_active == True)

    return query.first()
```

**Beneficios:**
- ✅ Mantiene seguridad para operaciones de pago (por defecto solo cuentas activas)
- ✅ Permite consultar cuentas desconectadas cuando es necesario
- ✅ Backward compatible (comportamiento por defecto sin cambios)

### Fix 2: Endpoint `connection-status` Actualizado

**Archivo:** `app/api/v1/endpoints/stripe_connect.py:270-299`

```python
# ✅ CORRECTO
try:
    # Consultar cuenta incluyendo inactivas para mostrar estado real
    gym_account = stripe_connect_service.get_gym_stripe_account(
        db,
        current_gym.id,
        include_inactive=True  # ✅ Incluir cuentas desconectadas
    )

    if not gym_account:
        return {
            "connected": False,
            "message": "No hay cuenta de Stripe configurada",
            "action_required": "Crear cuenta de Stripe Connect"
        }

    if not gym_account.is_active:
        # ✅ AHORA SÍ DETECTA CUENTAS DESCONECTADAS
        return {
            "connected": False,
            "account_id": gym_account.stripe_account_id,
            "account_type": gym_account.account_type,
            "onboarding_completed": gym_account.onboarding_completed,
            "message": "Cuenta desconectada - requiere reconexión",
            "action_required": (
                "Reconectar usando POST /api/v1/stripe-connect/accounts/onboarding-link. "
                "Esta cuenta fue configurada previamente pero está desconectada. "
                "El administrador debe completar el proceso de reconexión en Stripe."
            ),
            "can_reconnect": True
        }
```

**Respuesta esperada ahora (Gym 4):**
```json
{
  "connected": false,
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "onboarding_completed": true,
  "message": "Cuenta desconectada - requiere reconexión",
  "action_required": "Reconectar usando POST /api/v1/stripe-connect/accounts/onboarding-link...",
  "can_reconnect": true
}
```

### Fix 3: Endpoint `onboarding-link` para Reconexión

**Archivo:** `app/api/v1/endpoints/stripe_connect.py:186-239`

```python
# ✅ CORRECTO
try:
    # Verificar que existe cuenta (incluyendo inactivas para permitir reconexión)
    gym_account = stripe_connect_service.get_gym_stripe_account(
        db,
        current_gym.id,
        include_inactive=True  # ✅ Permitir reconectar cuentas desconectadas
    )

    if not gym_account:
        raise HTTPException(
            status_code=404,
            detail="Debe crear una cuenta de Stripe primero usando POST /api/v1/stripe-connect/accounts"
        )

    # Si la cuenta está activa Y ya completó onboarding, no necesita volver a hacerlo
    if gym_account.is_active and gym_account.onboarding_completed:
        raise HTTPException(
            status_code=400,
            detail=(
                "La cuenta ya está activa y configurada. "
                "Use GET /api/v1/stripe-connect/accounts/connection-status para verificar el estado."
            )
        )

    # Crear link de onboarding
    onboarding_url = await stripe_connect_service.create_onboarding_link(
        db, current_gym.id, refresh_url, return_url
    )

    # Determinar si es reconexión o configuración inicial
    is_reconnection = gym_account.onboarding_completed and not gym_account.is_active

    return {
        "message": (
            "Link de reconexión creado exitosamente"
            if is_reconnection
            else "Link de onboarding creado exitosamente"
        ),
        "onboarding_url": onboarding_url,
        "expires_in_minutes": 60,
        "is_reconnection": is_reconnection,  # ✅ NUEVO CAMPO
        "account_id": gym_account.stripe_account_id,
        "instructions": (
            "Autoriza nuevamente el acceso a tu cuenta de Stripe siguiendo el link. "
            "Esto reconectará tu cuenta Standard existente."
            if is_reconnection
            else "Complete la configuración de Stripe siguiendo el link. El proceso toma 5-10 minutos."
        )
    }
```

**Ejemplo de respuesta para reconexión:**
```json
{
  "message": "Link de reconexión creado exitosamente",
  "onboarding_url": "https://connect.stripe.com/setup/...",
  "expires_in_minutes": 60,
  "is_reconnection": true,
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "instructions": "Autoriza nuevamente el acceso a tu cuenta de Stripe siguiendo el link. Esto reconectará tu cuenta Standard existente."
}
```

### Fix 4: Servicio `create_onboarding_link` Actualizado

**Archivo:** `app/services/stripe_connect_service.py:138-173`

```python
# ✅ CORRECTO
async def create_onboarding_link(
    self,
    db: Session,
    gym_id: int,
    refresh_url: Optional[str] = None,
    return_url: Optional[str] = None
) -> str:
    """
    Crear link de onboarding para que el gym complete su configuración.

    Funciona tanto para configuración inicial como para RECONEXIÓN de cuentas desconectadas.

    Note:
        Este método permite generar links para cuentas inactivas,
        lo cual es necesario para reconectar Standard accounts desconectadas.
    """
    try:
        # Obtener cuenta del gym (incluyendo inactivas para permitir reconexión)
        gym_account = db.query(GymStripeAccount).filter(
            GymStripeAccount.gym_id == gym_id
        ).first()  # ✅ Ya NO filtra por is_active

        if not gym_account:
            raise ValueError(
                f"Gym {gym_id} no tiene cuenta de Stripe. "
                "Debe crear una cuenta primero."
            )

        # Stripe permite regenerar AccountLink para cuentas existentes
        account_link = stripe.AccountLink.create(
            account=gym_account.stripe_account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding"
        )

        return account_link.url
```

---

## 📊 Comparación Antes vs Después

### Escenario: Gym 4 con cuenta desconectada

| Aspecto | ❌ ANTES | ✅ DESPUÉS |
|---------|---------|-----------|
| **GET /connection-status** | "No hay cuenta configurada" | "Cuenta desconectada - requiere reconexión" |
| **account_id en response** | No incluido | `acct_1RdO0iBiqPTgRrIQ` |
| **can_reconnect** | No incluido | `true` |
| **POST /onboarding-link** | Error 404 "No hay cuenta" | ✅ Genera link de reconexión |
| **is_reconnection** | No existía | `true` |
| **Instrucciones** | "Complete configuración" | "Autoriza nuevamente el acceso" |
| **Acción del admin** | Crear nueva cuenta (duplicado) | Reconectar cuenta existente ✅ |

---

## 🧪 Testing

### Test Case 1: Cuenta Desconectada

```bash
# 1. Verificar estado
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/connection-status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 4"

# Respuesta esperada:
{
  "connected": false,
  "account_id": "acct_1RdO0iBiqPTgRrIQ",
  "account_type": "standard",
  "onboarding_completed": true,
  "message": "Cuenta desconectada - requiere reconexión",
  "can_reconnect": true
}

# 2. Generar link de reconexión
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/onboarding-link" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 4"

# Respuesta esperada:
{
  "message": "Link de reconexión creado exitosamente",
  "onboarding_url": "https://connect.stripe.com/setup/...",
  "is_reconnection": true,
  "account_id": "acct_1RdO0iBiqPTgRrIQ"
}
```

### Test Case 2: Cuenta Nueva (Primera Vez)

```bash
# 1. Verificar estado (no tiene cuenta)
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/connection-status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 5"

# Respuesta esperada:
{
  "connected": false,
  "message": "No hay cuenta de Stripe configurada",
  "action_required": "Crear cuenta de Stripe Connect"
}

# 2. Crear cuenta nueva
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 5" \
  -H "Content-Type: application/json" \
  -d '{"country": "US"}'
```

### Test Case 3: Cuenta Activa (Ya Configurada)

```bash
# Intentar generar onboarding link para cuenta activa
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect/accounts/onboarding-link" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 1"

# Respuesta esperada (400):
{
  "detail": "La cuenta ya está activa y configurada. Use GET /api/v1/stripe-connect/accounts/connection-status para verificar el estado."
}
```

---

## 🎯 Casos de Uso Cubiertos

### ✅ Caso 1: Primera Configuración
1. Gym no tiene cuenta → `POST /accounts` crea cuenta
2. `POST /onboarding-link` genera link inicial
3. Admin completa onboarding en Stripe
4. `is_reconnection: false`

### ✅ Caso 2: Reconexión Después de Desconexión
1. Gym tiene cuenta desconectada → `GET /connection-status` detecta
2. `POST /onboarding-link` genera link de reconexión
3. Admin reautoriza en Stripe
4. `is_reconnection: true`

### ✅ Caso 3: Cuenta Activa (No Requiere Acción)
1. `GET /connection-status` → `connected: true`
2. `POST /onboarding-link` → Error 400 "Ya está configurada"

### ✅ Caso 4: Detección Automática de Desconexión
1. Sistema intenta crear Payment Intent → Error PermissionError
2. `connection-status` auto-marca como inactiva
3. Devuelve instrucciones de reconexión

---

## 📝 Archivos Modificados

### Código

1. ✅ `app/services/stripe_connect_service.py`
   - `get_gym_stripe_account()`: Agregado parámetro `include_inactive`
   - `create_onboarding_link()`: Removido filtro `is_active`

2. ✅ `app/api/v1/endpoints/stripe_connect.py`
   - `get_connection_status()`: Usar `include_inactive=True`
   - `create_onboarding_link()`: Mejorada validación y response

### Documentación

3. ✅ `docs/STRIPE_CONNECT_FRONTEND_API.md`
   - Agregada sección "Flujo de Reconexión"
   - Diagramas de flujo actualizados
   - Ejemplos de reconexión

4. ✅ `docs/STRIPE_CONNECT_RECONNECTION_FIX.md` (este archivo)
   - Documentación completa del fix

---

## 🚀 Deploy

### Checklist Pre-Deploy

- [x] Código actualizado y testeado localmente
- [x] Documentación actualizada
- [x] Backward compatible (comportamiento por defecto sin cambios)
- [x] No requiere cambios en BD (solo lógica)
- [ ] Testing en staging con Gym 4
- [ ] Validar reconexión funcional en staging
- [ ] Deploy a producción
- [ ] Verificar con admin del Gym 4

### Comandos de Deploy

```bash
# 1. Commit cambios
git add .
git commit -m "fix(stripe-connect): permitir reconexión de cuentas Standard desconectadas

- Agregado parámetro include_inactive en get_gym_stripe_account()
- Endpoint connection-status ahora detecta cuentas desconectadas
- Endpoint onboarding-link permite reconexión
- Mejorados mensajes para distinguir onboarding vs reconexión
- Actualizada documentación del frontend

Fixes: #ISSUE_NUMBER"

# 2. Push a producción
git push origin main

# 3. Verificar deployment en Render
# (deploy automático si está configurado)
```

---

## 📊 Métricas de Éxito

### Post-Deploy

- [ ] Gym 4 puede generar link de reconexión exitosamente
- [ ] `GET /connection-status` devuelve información correcta
- [ ] Response incluye `is_reconnection: true` para cuentas desconectadas
- [ ] Admin puede completar proceso de reconexión
- [ ] Cuenta se marca como activa después de reconexión
- [ ] Pagos funcionan correctamente después de reconexión
- [ ] No hay regresiones en gyms con cuentas activas
- [ ] No hay regresiones en gyms sin cuenta

---

## 🔗 Referencias

- [Documentación Frontend API](./STRIPE_CONNECT_FRONTEND_API.md)
- [Documentación Webhook Setup](./STRIPE_CONNECT_WEBHOOK_SETUP.md)
- [Documentación Webhook Events](./STRIPE_CONNECT_WEBHOOK_EVENTS.md)
- [Stripe AccountLink API](https://stripe.com/docs/api/account_links)
- [Stripe Connect Standard Accounts](https://stripe.com/docs/connect/standard-accounts)

---

**Estado:** ✅ Implementado - Pendiente deploy a producción
**Fecha:** 2025-12-25
**Prioridad:** 🔴 Alta (afecta Gym 4 en producción)
