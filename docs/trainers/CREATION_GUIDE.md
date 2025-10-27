# Guía Completa de Creación de Gyms y Trainers

## 📋 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Creación de Gimnasios (Gym)](#creación-de-gimnasios-gym)
3. [Creación de Trainers](#creación-de-trainers)
4. [Comparación de Métodos](#comparación-de-métodos)
5. [Validaciones y Requisitos](#validaciones-y-requisitos)
6. [Flujos Completos](#flujos-completos)
7. [Troubleshooting](#troubleshooting)

---

## Introducción

GymAPI soporta dos tipos de workspaces que se crean de manera diferente:

| Tipo | Creación | Uso Principal |
|------|----------|---------------|
| **Gym** | Admin/Script | Gimnasios tradicionales con staff |
| **Trainer** | Self-service API | Entrenadores personales independientes |

**Diferencia clave:**
- **Gyms**: Creados por administradores del sistema
- **Trainers**: Los usuarios se auto-registran vía API pública

---

## Creación de Gimnasios (Gym)

Los gimnasios deben ser creados por administradores del sistema, ya que representan instalaciones físicas que requieren verificación.

### Método 1: Script CLI (Recomendado)

El método más fácil y seguro para crear gimnasios.

#### Uso Básico

```bash
python scripts/create_gym.py \
  --name "CrossFit Downtown" \
  --subdomain "crossfit-downtown" \
  --owner-email "admin@crossfit.com" \
  --owner-first-name "Juan" \
  --owner-last-name "Pérez"
```

#### Uso Completo (con todos los parámetros)

```bash
python scripts/create_gym.py \
  --name "CrossFit Downtown" \
  --subdomain "crossfit-downtown" \
  --owner-email "admin@crossfit.com" \
  --owner-first-name "Juan" \
  --owner-last-name "Pérez" \
  --owner-password "SecurePassword123!" \
  --address "Av. Reforma 123, CDMX" \
  --phone "+525512345678" \
  --timezone "America/Mexico_City"
```

#### Salida del Script

```
======================================================================
🏢 CREANDO NUEVO GIMNASIO
======================================================================

1️⃣  Verificando disponibilidad del subdomain 'crossfit-downtown'...
   ✅ Subdomain disponible

2️⃣  Verificando usuario 'admin@crossfit.com'...
   ⚠️  Usuario no existe, creando nuevo usuario...

3️⃣  Creando usuario en Auth0...
   ✅ Usuario creado en Auth0: auth0|507f1f77bcf86cd799439011

4️⃣  Creando usuario en base de datos...
   ✅ Usuario creado (ID: 123)

5️⃣  Creando gimnasio 'CrossFit Downtown'...
   ✅ Gimnasio creado (ID: 456)

6️⃣  Asociando usuario como OWNER del gimnasio...
   ✅ Asociación creada

======================================================================
✅ GIMNASIO CREADO EXITOSAMENTE
======================================================================

📊 Resumen:
   • Gimnasio ID: 456
   • Nombre: CrossFit Downtown
   • Subdomain: crossfit-downtown
   • Tipo: gym
   • URL: https://crossfit-downtown.gymapi.com
   • Timezone: America/Mexico_City

👤 Owner:
   • User ID: 123
   • Email: admin@crossfit.com
   • Nombre: Juan Pérez
   • Auth0 ID: auth0|507f1f77bcf86cd799439011
   • Rol: OWNER

🚀 Próximos pasos:
   1. El owner debe verificar su email en Auth0
   2. Configurar módulos activos para el gimnasio
   3. Agregar staff (trainers, admins)
   4. Agregar miembros
```

### Método 2: API Endpoint (Administrativo)

Para integraciones o interfaces de admin.

#### Endpoint

```http
POST /api/v1/admin/gyms
Authorization: Bearer {SUPER_ADMIN_TOKEN}
Content-Type: application/json
```

#### Request Body

```json
{
  "name": "CrossFit Downtown",
  "subdomain": "crossfit-downtown",
  "owner": {
    "email": "admin@crossfit.com",
    "first_name": "Juan",
    "last_name": "Pérez",
    "password": "SecurePassword123!"
  },
  "gym_info": {
    "address": "Av. Reforma 123, CDMX",
    "phone": "+525512345678",
    "timezone": "America/Mexico_City",
    "description": "Box de CrossFit en el centro de la ciudad"
  }
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "gym_id": 456,
    "subdomain": "crossfit-downtown",
    "name": "CrossFit Downtown",
    "type": "gym",
    "owner": {
      "user_id": 123,
      "email": "admin@crossfit.com",
      "name": "Juan Pérez",
      "role": "OWNER"
    },
    "urls": {
      "app": "https://crossfit-downtown.gymapi.com",
      "api": "https://api.gymapi.com"
    }
  }
}
```

### Método 3: SQL Directo (Solo para Testing)

Para desarrollo o testing local.

```sql
-- 1. Crear el gimnasio
INSERT INTO gyms (name, subdomain, type, timezone, is_active)
VALUES ('CrossFit Downtown', 'crossfit-downtown', 'gym', 'America/Mexico_City', true)
RETURNING id;
-- Supongamos que retorna id = 456

-- 2. Crear usuario (si no existe)
INSERT INTO "user" (email, first_name, last_name, is_active)
VALUES ('admin@crossfit.com', 'Juan', 'Pérez', true)
RETURNING id;
-- Supongamos que retorna id = 123

-- 3. Asociar usuario como OWNER
INSERT INTO user_gyms (user_id, gym_id, role)
VALUES (123, 456, 'OWNER');
```

---

## Creación de Trainers

Los trainers se auto-registran a través de un endpoint público sin necesidad de admin.

### Método 1: API Pública (Recomendado)

Este es el método principal y recomendado.

#### Endpoint

```http
POST /api/v1/auth/register-trainer
Content-Type: application/json
```

**⚠️ IMPORTANTE:** No requiere autenticación (endpoint público)

#### Request Body Mínimo

```json
{
  "email": "juan.perez@email.com",
  "firstName": "Juan",
  "lastName": "Pérez",
  "password": "SecurePass123!",
  "specialties": ["CrossFit", "Nutrición Deportiva"]
}
```

#### Request Body Completo

```json
{
  "email": "juan.perez@email.com",
  "firstName": "Juan",
  "lastName": "Pérez",
  "password": "SecurePass123!",
  "phone": "+525512345678",
  "specialties": [
    "CrossFit",
    "Nutrición Deportiva",
    "Entrenamiento Funcional"
  ],
  "bio": "Coach certificado con 10 años de experiencia en CrossFit y nutrición deportiva. Especializado en pérdida de peso y ganancia muscular.",
  "maxClients": 30,
  "certifications": [
    {
      "name": "CrossFit Level 2",
      "year": 2021,
      "institution": "CrossFit Inc"
    },
    {
      "name": "Nutrición Deportiva",
      "year": 2020,
      "institution": "ISSN"
    }
  ],
  "timezone": "America/Mexico_City"
}
```

#### Response Exitosa (201 Created)

```json
{
  "success": true,
  "message": "Trainer registrado exitosamente",
  "data": {
    "user_id": 789,
    "workspace_id": 101,
    "subdomain": "juan-perez-training",
    "email": "juan.perez@email.com",
    "workspace_type": "personal_trainer",
    "workspace_url": "https://juan-perez-training.gymapi.com",
    "auth0_user_id": "auth0|507f1f77bcf86cd799439011",
    "max_clients": 30,
    "specialties": [
      "CrossFit",
      "Nutrición Deportiva",
      "Entrenamiento Funcional"
    ],
    "next_steps": {
      "verify_email": true,
      "complete_profile": false,
      "setup_payment": true
    }
  }
}
```

#### Ejemplo con cURL

```bash
curl -X POST https://api.gymapi.com/api/v1/auth/register-trainer \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan.perez@email.com",
    "firstName": "Juan",
    "lastName": "Pérez",
    "password": "SecurePass123!",
    "specialties": ["CrossFit", "Nutrición"],
    "maxClients": 30
  }'
```

#### Ejemplo con JavaScript/Fetch

```javascript
const response = await fetch('https://api.gymapi.com/api/v1/auth/register-trainer', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    email: 'juan.perez@email.com',
    firstName: 'Juan',
    lastName: 'Pérez',
    password: 'SecurePass123!',
    specialties: ['CrossFit', 'Nutrición'],
    maxClients: 30
  })
});

const data = await response.json();
console.log('Trainer creado:', data);
```

### Método 2: Script CLI (Para Testing/Admin)

Útil para desarrollo o cuando necesitas crear trainers programáticamente.

#### Uso

```bash
python scripts/setup_trainer.py \
  --email "juan.perez@email.com" \
  --first-name "Juan" \
  --last-name "Pérez" \
  --specialties "CrossFit,Nutrición,Funcional" \
  --max-clients 30 \
  --timezone "America/Mexico_City"
```

#### Con Certificaciones

```bash
python scripts/setup_trainer.py \
  --email "juan.perez@email.com" \
  --first-name "Juan" \
  --last-name "Pérez" \
  --specialties "CrossFit,Nutrición" \
  --certifications '[{"name":"CrossFit L2","year":2021}]' \
  --bio "Coach con 10 años de experiencia" \
  --max-clients 30
```

---

## Comparación de Métodos

### Gyms (Gimnasios)

| Método | Requiere Admin | Crea Auth0 | Validaciones | Uso Recomendado |
|--------|----------------|------------|--------------|-----------------|
| Script CLI | ✅ | ✅ | ✅ | Setup inicial, testing |
| API Admin | ✅ | ✅ | ✅ | Integraciones, UI admin |
| SQL Directo | ✅ | ❌ | ❌ | Solo testing local |

**Recomendación:** Usar **Script CLI** para la mayoría de casos.

### Trainers (Entrenadores)

| Método | Requiere Admin | Crea Auth0 | Validaciones | Uso Recomendado |
|--------|----------------|------------|--------------|-----------------|
| API Pública | ❌ | ✅ | ✅ | Producción, self-service |
| Script CLI | ✅ | ❌ | ✅ | Testing, batch creation |

**Recomendación:** Usar **API Pública** en producción.

---

## Validaciones y Requisitos

### Para Gimnasios (Gym)

#### Campos Requeridos

| Campo | Tipo | Validación | Ejemplo |
|-------|------|------------|---------|
| `name` | string | 3-255 caracteres | "CrossFit Downtown" |
| `subdomain` | string | 3-100 chars, alfanumérico + guiones | "crossfit-downtown" |
| `owner_email` | string | Email válido | "admin@crossfit.com" |
| `owner_first_name` | string | 2-100 caracteres | "Juan" |
| `owner_last_name` | string | 2-100 caracteres | "Pérez" |

#### Campos Opcionales

| Campo | Tipo | Default | Ejemplo |
|-------|------|---------|---------|
| `address` | string | NULL | "Av. Reforma 123, CDMX" |
| `phone` | string | NULL | "+525512345678" |
| `timezone` | string | "UTC" | "America/Mexico_City" |
| `description` | string | NULL | "Box de CrossFit..." |

#### Validaciones Automáticas

- ✅ Subdomain único (no puede existir otro)
- ✅ Email único (si crea nuevo usuario)
- ✅ Timezone válido (debe existir en la base de datos de timezones)
- ✅ Formato de teléfono internacional

### Para Trainers

#### Campos Requeridos

| Campo | Tipo | Validación | Ejemplo |
|-------|------|------------|---------|
| `email` | string | Email válido | "trainer@example.com" |
| `firstName` | string | 2-100 caracteres | "María" |
| `lastName` | string | 2-100 caracteres | "García" |
| `password` | string | Min 8 chars, mayúscula, número | "SecurePass123!" |
| `specialties` | array | Mínimo 1 especialidad | ["Yoga", "Pilates"] |

#### Campos Opcionales

| Campo | Tipo | Default | Ejemplo |
|-------|------|---------|---------|
| `phone` | string | NULL | "+525512345678" |
| `bio` | string | NULL | "Coach con 10 años..." |
| `maxClients` | integer | 30 | 50 |
| `certifications` | array | [] | [{"name": "...", "year": 2020}] |
| `timezone` | string | "UTC" | "America/Mexico_City" |

#### Validaciones Automáticas

- ✅ Email disponible (validación en tiempo real)
- ✅ Password seguro (Auth0 requirements)
- ✅ Subdomain único (generado automáticamente: `nombre-apellido-training`)
- ✅ Manejo de colisiones (agrega sufijo numérico si existe)
- ✅ `maxClients` entre 1-200

---

## Flujos Completos

### Flujo 1: Crear Gym con Owner Nuevo

```
1. Admin ejecuta script:
   └─> python scripts/create_gym.py --name "Gym" --subdomain "gym" --owner-email "...

2. Sistema verifica subdomain disponible
   ├─> ✅ Disponible → Continúa
   └─> ❌ Ocupado → Error

3. Sistema verifica si usuario existe
   ├─> Usuario existe:
   │   └─> Verifica que no sea owner de otro gym
   └─> Usuario NO existe:
       ├─> Crea en Auth0
       └─> Crea en BD local

4. Sistema crea Gym
   └─> type = 'gym'

5. Sistema crea UserGym
   └─> role = OWNER

6. Envía email de bienvenida (Auth0)

7. Owner verifica email y accede
```

### Flujo 2: Trainer se Auto-registra

```
1. Trainer completa formulario en frontend
   └─> https://gymapi.com/register/trainer

2. Frontend valida en tiempo real:
   ├─> Email disponible (GET /auth/trainer/check-email/{email})
   └─> Campos completos

3. Frontend envía POST /auth/register-trainer

4. Backend valida y crea:
   ├─> Usuario en Auth0
   ├─> User en BD
   ├─> Gym (type=personal_trainer)
   └─> UserGym (role=OWNER)

5. Backend genera subdomain único:
   ├─> Base: nombre-apellido-training
   └─> Si existe: nombre-apellido-training-2

6. Sistema envía email de verificación

7. Trainer verifica email

8. Trainer accede a dashboard personalizado
```

### Flujo 3: Agregar Staff a un Gym

```
1. Owner/Admin del gym accede a panel

2. Va a "Staff" → "Agregar Trainer"

3. Ingresa email del trainer

4. Sistema verifica:
   ├─> Usuario existe:
   │   └─> Crea UserGym con role=TRAINER
   └─> Usuario NO existe:
       ├─> Envía invitación por email
       └─> Usuario crea cuenta al aceptar

5. Trainer aparece en lista de staff

6. Trainer puede ver miembros asignados
```

---

## Troubleshooting

### Error: "Subdomain ya existe"

**Problema:**
```
ValueError: El subdomain 'crossfit-downtown' ya está en uso
```

**Solución:**
1. Verifica subdominios existentes:
   ```sql
   SELECT id, name, subdomain FROM gyms WHERE subdomain LIKE 'crossfit%';
   ```
2. Usa un subdomain diferente o agrega sufijo:
   - `crossfit-downtown-polanco`
   - `crossfit-downtown-2`

### Error: "Email ya registrado"

**Para Gyms:**
```
Usuario ya existe pero ya es owner de otro gym
```

**Solución:**
- Usa un email diferente para el owner
- O verifica que el usuario existente no tenga conflictos

**Para Trainers:**
```json
{
  "detail": "Email ya registrado",
  "available": false,
  "has_workspace": true
}
```

**Solución:**
- El usuario ya tiene un workspace de trainer
- Debe hacer login en lugar de registro
- O usar otro email

### Error: "Password no cumple requisitos"

```json
{
  "detail": "Password must be at least 8 characters and contain uppercase, lowercase, and number"
}
```

**Solución:**
Asegurar que el password tenga:
- ✅ Mínimo 8 caracteres
- ✅ Al menos 1 mayúscula
- ✅ Al menos 1 minúscula
- ✅ Al menos 1 número
- ✅ (Recomendado) Al menos 1 carácter especial

### Error: "Timezone inválido"

```
ValueError: Timezone 'America/Mexico' is not valid
```

**Solución:**
Usar timezones válidos de la base de datos IANA:
```python
# Válidos:
"America/Mexico_City"
"America/New_York"
"Europe/Madrid"
"America/Los_Angeles"

# Inválidos:
"Mexico"
"EST"
"PST"
```

### Error: Auth0 No Disponible

```
Error creando usuario en Auth0: Connection refused
```

**Solución:**
1. Verificar credenciales de Auth0 en `.env`:
   ```bash
   AUTH0_DOMAIN=your-domain.auth0.com
   AUTH0_CLIENT_ID=your-client-id
   AUTH0_CLIENT_SECRET=your-secret
   ```

2. Si no es crítico para testing:
   - El script continúa sin `auth0_id`
   - Usuario puede crearse manualmente después en Auth0

---

## Mejores Prácticas

### Para Crear Gimnasios

1. **Verifica antes de crear:**
   ```bash
   # Ver gyms existentes
   psql $DATABASE_URL -c "SELECT id, name, subdomain FROM gyms;"
   ```

2. **Usa subdominios descriptivos:**
   ✅ `crossfit-downtown`
   ✅ `fitstudio-polanco`
   ❌ `gym1`
   ❌ `test`

3. **Configura timezone correcto:**
   - Importante para clases programadas
   - Usa el timezone del país/ciudad del gym

4. **Documenta el owner:**
   - Guarda las credenciales de forma segura
   - Comparte info de login con el propietario

### Para Crear Trainers

1. **Valida email en tiempo real:**
   ```javascript
   const checkEmail = async (email) => {
     const res = await fetch(`/api/v1/auth/trainer/check-email/${email}`);
     return res.json(); // { available: true/false }
   };
   ```

2. **Pide especialidades específicas:**
   ✅ "CrossFit", "Nutrición Deportiva", "Pérdida de Peso"
   ❌ "Entrenamiento", "Fitness"

3. **Sugiere un buen subdomain:**
   - Genera automáticamente: `nombre-apellido-training`
   - Permite personalizar si lo desea

4. **Configura `maxClients` realista:**
   - 1-a-1 presencial: 20-30 clientes
   - Online: 30-50 clientes
   - Programación remota: 50-100 clientes

---

## Recursos Adicionales

- [API Documentation](./TRAINER_API_DOCUMENTATION.md) - Referencia completa de endpoints
- [Trainers vs Gyms Guide](./TRAINERS_VS_GYMS.md) - Diferencias detalladas
- [Integration Guide](./TRAINER_INTEGRATION_GUIDE.md) - Guía de frontend
- [Scripts Directory](/scripts) - Scripts de utilidad

---

**Última actualización:** Octubre 2025
**Versión:** 1.0.0
**Autor:** GymAPI Team
