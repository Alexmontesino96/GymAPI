# 🔍 **Criterios de Inclusión Automática de Planes Nutricionales**

## 📋 **Resumen Ejecutivo**

El sistema de nutrition aplica **filtros automáticos** en todos los endpoints para determinar qué planes son visibles para cada usuario. Estos criterios garantizan **seguridad**, **relevancia** y **experiencia de usuario** optimizada.

---

## 🚪 **Filtros Básicos (Siempre Aplicados)**

### ✅ **Planes INCLUIDOS Automáticamente:**
1. **Planes del gimnasio actual** (`gym_id` coincide)
2. **Planes activos** (`is_active = true`)
3. **Planes válidos** (no eliminados/soft-deleted)

### ❌ **Planes EXCLUIDOS Automáticamente:**
1. **Planes de otros gimnasios** (diferentes `gym_id`)
2. **Planes desactivados** (`is_active = false`)
3. **Planes eliminados** (marcados como inactivos)

---

## 🔐 **Filtros de Visibilidad (Por Permisos)**

### 📊 **GET /plans** - Lista Principal

#### **Usuario Logueado:**
```sql
WHERE (
    plan.is_public = TRUE 
    OR plan.creator_id = current_user_id
)
```

**✅ Incluye:**
- ✅ **Todos los planes públicos** del gimnasio
- ✅ **Planes privados propios** (creados por el usuario)

**❌ Excluye:**
- ❌ **Planes privados de otros** (no creados por el usuario)
- ❌ **Planes que solo sigues** pero no creaste (privados)

#### **Usuario No Logueado:**
```sql
WHERE plan.is_public = TRUE
```

**✅ Incluye:**
- ✅ **Solo planes públicos**

**❌ Excluye:**
- ❌ **Todos los planes privados**

### 📊 **GET /plans/{id}** - Detalles del Plan

**Control de Acceso Granular:**

```python
if not plan.is_public and user_id:
    if plan.creator_id != user_id:
        # Verificar si es seguidor activo
        is_follower = check_active_follower(plan_id, user_id)
        if not is_follower:
            raise PermissionError("Sin acceso")
```

**✅ Acceso Permitido:**
- ✅ **Creador del plan** (siempre)
- ✅ **Planes públicos** (cualquier usuario)
- ✅ **Seguidores activos** de planes privados

**❌ Acceso Denegado:**
- ❌ **Planes privados** sin ser creador ni seguidor
- ❌ **Ex-seguidores** (is_active = false)

---

## 🔀 **Filtros del Sistema Híbrido**

### 📅 **GET /dashboard** - Dashboard Personalizado

#### **Planes que Sigue el Usuario:**
```sql
JOIN nutrition_plan_followers 
WHERE follower.user_id = current_user_id 
AND follower.is_active = TRUE
```

**✅ Incluye:**
- ✅ **Planes que sigue activamente**
- ✅ **Categorizados por tipo** (template, live, archived)

**❌ Excluye:**
- ❌ **Planes que dejó de seguir**
- ❌ **Planes disponibles** (se muestran en sección separada)

#### **Planes Disponibles:**
```sql
WHERE plan.is_public = TRUE 
AND plan.id NOT IN (followed_plan_ids)
LIMIT 10
```

**✅ Incluye:**
- ✅ **Planes públicos no seguidos**
- ✅ **Limitado a 10** (performance)

**❌ Excluye:**
- ❌ **Planes ya seguidos**
- ❌ **Planes privados de otros**

### 🍽️ **GET /today** - Plan de Hoy

**Lógica de Prioridad:**
1. **Buscar entre planes seguidos activos**
2. **Encontrar plan con contenido para HOY**
3. **Si no hay, mostrar próximo plan a empezar**

**✅ Incluye:**
- ✅ **Solo planes seguidos activamente**
- ✅ **Con contenido para la fecha actual**

**❌ Excluye:**
- ❌ **Planes no seguidos**
- ❌ **Planes sin contenido para hoy**

---

## 🏷️ **Filtros Específicos por Tipo de Plan**

### 📋 **Template Plans:**
**✅ Incluidos Siempre:**
- ✅ Disponibles **permanentemente**
- ✅ **Sin restricciones** de fecha
- ✅ **Acceso inmediato** al seguir

### 🔴 **Live Plans:**
**Filtros de Estado:**
```python
if filters.status == PlanStatus.NOT_STARTED:
    WHERE plan_type = 'live' AND live_start_date > TODAY

elif filters.status == PlanStatus.RUNNING:
    WHERE plan_type = 'live' AND is_live_active = TRUE

elif filters.status == PlanStatus.FINISHED:
    WHERE plan_type = 'live' AND is_live_active = FALSE 
    AND live_end_date IS NOT NULL
```

**✅ Incluidos por Estado:**
- ✅ **NOT_STARTED:** Live futuros
- ✅ **RUNNING:** Live activos
- ✅ **FINISHED:** Live terminados

**❌ Excluidos:**
- ❌ **Live inactivos** sin fecha fin
- ❌ **Live con fechas inválidas**

### 📚 **Archived Plans:**
**✅ Incluidos:**
- ✅ **Funcionan como templates**
- ✅ **Con datos históricos preservados**
- ✅ **Referencia al plan live original**

---

## 🔍 **Filtros Adicionales del Usuario**

### **Filtros Opcionales (Query Parameters):**

#### **🎯 Por Características:**
- `goal`: loss, gain, bulk, cut, maintain
- `difficulty_level`: beginner, intermediate, advanced
- `budget_level`: low, medium, high
- `dietary_restrictions`: vegetarian, vegan, etc.

#### **👤 Por Creador:**
- `creator_id`: Planes de entrenador específico

#### **🔍 Por Búsqueda:**
- `search_query`: Buscar en título/descripción

#### **🏷️ Por Tipo Híbrido:**
- `plan_type`: template, live, archived
- `status`: not_started, running, finished
- `is_live_active`: true/false

#### **📅 Por Duración:**
- `duration_days_min`: Mínimo días
- `duration_days_max`: Máximo días

---

## 📊 **Casos Especiales**

### **🔄 GET /plans/hybrid - Vista Categorizada:**
**Separación Automática:**
- **Live:** `plan_type = 'live'` (hasta 50)
- **Template:** `plan_type = 'template'` (hasta 50)  
- **Archived:** `plan_type = 'archived'` (hasta 50)

### **📈 GET /plans/{id}/analytics - Solo Creadores:**
```python
if plan.creator_id != current_user_id:
    raise PermissionError("Solo el creador puede ver analytics")
```

### **⚡ Actualización Automática de Estados:**
**Live Plans:**
- ✅ **Estado actualizado** automáticamente en cada consulta
- ✅ **is_live_active** calculado en tiempo real
- ✅ **current_day** según fecha global del plan

---

## 🎯 **Resumen de Inclusión por Endpoint**

| Endpoint | Planes Públicos | Planes Privados Propios | Planes Privados Seguidos | Otros Privados |
|----------|----------------|-------------------------|--------------------------|----------------|
| `GET /plans` | ✅ Sí | ✅ Sí | ❌ No | ❌ No |
| `GET /plans/{id}` | ✅ Sí | ✅ Sí | ✅ Sí | ❌ No |
| `GET /dashboard` | ✅ Disponibles | ✅ Si seguidos | ✅ Si seguidos | ❌ No |
| `GET /today` | ❌ No | ✅ Si seguidos | ✅ Si seguidos | ❌ No |
| `GET /plans/hybrid` | ✅ Sí | ✅ Sí | ❌ No | ❌ No |

---

## 💡 **Recomendaciones de Uso**

### **Para Usuarios Finales:**
- **Explorar:** Usar `GET /plans` con filtros
- **Seguimiento:** Usar `GET /dashboard` para planes activos
- **Hoy:** Usar `GET /today` para comidas del día

### **Para Entrenadores:**
- **Crear:** Solo planes que quieran compartir públicamente
- **Privados:** Para clientes específicos que seguirán manualmente
- **Analytics:** Solo disponibles en planes propios

### **Para Administradores:**
- **Visibilidad:** Mismas reglas que usuarios regulares
- **Control:** A través de activación/desactivación de módulos 