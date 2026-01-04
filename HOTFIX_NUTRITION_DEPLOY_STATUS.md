# 🚨 HOTFIX: Error 500 en Listado de Planes Nutricionales

## Estado Actual

### ❌ Error en Producción
```
TypeError: NutritionPlanService.list_nutrition_plans() got an unexpected keyword argument 'page'
Endpoint: GET /api/v1/nutrition/plans?per_page=100
Línea: app/api/v1/endpoints/nutrition.py:154
```

### ✅ Fix Aplicado en GitHub
- **Commit**: `c990f88` - hotfix(nutrition): corregir parámetros en list_nutrition_plans
- **Push**: Exitoso a main
- **Timestamp**: Hace ~10 minutos

### 🔄 Estado del Despliegue

**El código corregido está en GitHub pero NO en producción aún.**

## Problema Identificado

El endpoint estaba pasando parámetros incorrectos:
- ❌ `page`, `per_page`, `user_id` (no existen en el servicio)
- ✅ `skip`, `limit` (parámetros correctos)

## Solución Implementada

```python
# ANTES (Error)
plans, total = service.list_nutrition_plans(
    gym_id=current_gym.id,
    filters=filters,
    page=page,         # ❌
    per_page=per_page, # ❌
    user_id=db_user.id # ❌
)

# DESPUÉS (Correcto)
skip = (page - 1) * per_page
limit = per_page
plans, total = service.list_nutrition_plans(
    gym_id=current_gym.id,
    filters=filters,
    skip=skip,    # ✅
    limit=limit   # ✅
)
```

## Acción Requerida

### Opción 1: Esperar Deploy Automático
Render.com debería detectar el cambio y desplegar automáticamente:
- Tiempo estimado: 5-10 minutos desde el push
- Build Docker: ~3-4 minutos
- Health checks: ~1 minuto
- Swap de versiones: ~1 minuto

### Opción 2: Trigger Manual de Deploy

1. **Ir a Render Dashboard**
   - https://dashboard.render.com
   - Buscar servicio "gymapi"

2. **Verificar Estado del Deploy**
   - Si hay un deploy en progreso, esperar
   - Si el último deploy es antiguo, hacer click en "Manual Deploy"

3. **Seleccionar Branch**
   - Branch: `main`
   - Commit: `c990f88` o más reciente

### Opción 3: Verificar por API
```bash
# Verificar si el error persiste
curl -X GET "https://tu-api.onrender.com/api/v1/nutrition/plans?per_page=10" \
  -H "Authorization: Bearer TU_TOKEN"

# Si devuelve 500, el deploy no se ha completado
# Si devuelve 200, el fix está aplicado
```

## Verificación Post-Deploy

Una vez desplegado, verificar:

1. **Endpoint de listado funciona**
   ```
   GET /api/v1/nutrition/plans
   Status: 200 OK
   ```

2. **Logs sin errores**
   - No más `TypeError`
   - No más stack traces

3. **Paginación correcta**
   - Parámetros `page` y `per_page` funcionando
   - Respuesta con estructura correcta

## Commits Relacionados

```bash
c990f88 hotfix(nutrition): corregir parámetros en list_nutrition_plans
57df8d0 feat(nutrition): agregar logging detallado de respuestas de IA
f1887bf feat(nutrition): agregar control de LangChain por configuración
```

## Notas Importantes

1. **El código está correcto en GitHub** - El fix ya está aplicado y pusheado
2. **El problema es de despliegue** - Render no ha actualizado la versión en producción
3. **No se requieren más cambios de código** - Solo esperar o forzar el deploy

## Contacto y Soporte

Si el deploy no se ejecuta automáticamente después de 15 minutos:
1. Verificar configuración de webhooks en Render
2. Verificar que el auto-deploy esté habilitado
3. Hacer deploy manual desde el dashboard

---

**Última actualización**: Enero 4, 2026 - 04:15 UTC
**Estado**: ⏳ Esperando deploy en producción