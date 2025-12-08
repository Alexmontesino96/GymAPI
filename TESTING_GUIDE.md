# 🧪 Guía de Testing - Migración Async

Esta guía explica cómo ejecutar los tests de integración para validar la migración async módulo por módulo.

---

## 📋 Prerequisitos

1. **Python 3.11+** instalado
2. **Dependencias de testing** instaladas:
```bash
pip install pytest pytest-asyncio httpx
```

3. **Tokens de Auth0** válidos para:
   - Admin
   - Trainer
   - Member

---

## 🔑 Obtener Tokens de Auth0

### Opción 1: Desde el Dashboard de Auth0

1. Ir a Auth0 Dashboard → Applications → Tu App
2. Ir a "APIs" → "Auth0 Management API"
3. Generar token con los scopes necesarios

### Opción 2: Login Manual (Recomendado)

1. Hacer login en tu app con cada tipo de usuario
2. Capturar el token desde las DevTools del browser:
   - Chrome DevTools → Application → Storage → Local Storage
   - Buscar el token en las cookies o localStorage

### Opción 3: API Request

```bash
curl --request POST \
  --url https://YOUR_DOMAIN.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id":"YOUR_CLIENT_ID",
    "client_secret":"YOUR_CLIENT_SECRET",
    "audience":"YOUR_API_AUDIENCE",
    "grant_type":"client_credentials"
  }'
```

---

## 🚀 Ejecución de Tests

### Método 1: Con Variables de Entorno (Recomendado)

```bash
# Configurar tokens
export TEST_ADMIN_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
export TEST_TRAINER_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
export TEST_MEMBER_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
export TEST_GYM_ID="1"
export TEST_API_BASE_URL="https://gymapi-production.up.railway.app"

# Ejecutar todos los tests
python run_integration_tests.py
```

### Método 2: Con Argumentos de Línea de Comando

```bash
python run_integration_tests.py \
  --admin-token "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  --trainer-token "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  --member-token "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  --gym-id 1 \
  --base-url "https://gymapi-production.up.railway.app"
```

### Método 3: Con archivo .env

Crear archivo `.env.test`:
```bash
TEST_ADMIN_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
TEST_TRAINER_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
TEST_MEMBER_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
TEST_GYM_ID=1
TEST_API_BASE_URL=https://gymapi-production.up.railway.app
```

Luego cargar y ejecutar:
```bash
source .env.test  # o `export $(cat .env.test | xargs)` en Linux
python run_integration_tests.py
```

---

## 📦 Ejecutar Módulos Específicos

### Todos los módulos (default)
```bash
python run_integration_tests.py
```

### Solo módulos críticos (1-4)
```bash
python run_integration_tests.py --modules 1 2 3 4
```

### Solo un módulo específico
```bash
python run_integration_tests.py --modules 1  # Solo Auth
python run_integration_tests.py --modules 4  # Solo Schedule
```

### Modo verbose (más detalles)
```bash
python run_integration_tests.py --verbose
```

---

## 📊 Módulos Disponibles

| # | Módulo | Prioridad | Descripción |
|---|--------|-----------|-------------|
| 1 | Auth | 🔴 CRÍTICO | Autenticación y autorización |
| 2 | Users | 🔴 CRÍTICO | Gestión de usuarios y perfiles |
| 3 | Gyms | 🔴 CRÍTICO | Gestión de gimnasios y membresías |
| 4 | Schedule | 🔴 CRÍTICO | Clases, reservas y participaciones |
| 5 | Events | 🟡 IMPORTANTE | Eventos y participación |

---

## 🔍 Interpretando Resultados

### Test Exitoso ✅
```
test_get_my_profile PASSED
✅ Perfil obtenido: user@example.com
```

### Test Fallido ❌
```
test_get_my_profile FAILED
❌ Expected 200, got 500
Response: {"detail": "AttributeError: 'AsyncSession' object has no attribute 'query'"}
```

### Métricas de Performance 📊
```
📊 TIEMPOS DE RESPUESTA:
   GET /sessions: 85ms promedio
   GET /categories: 42ms promedio
✅ Todos los tiempos dentro del target (<500ms)
```

---

## 🐛 Debugging de Errores

### Error: Token Inválido
```
❌ Expected 200, got 401
Response: {"detail": "Invalid token"}
```

**Solución**: Regenerar token (pueden expirar)

### Error: AsyncSession
```
❌ AttributeError: 'AsyncSession' object has no attribute 'query'
```

**Solución**: Hay un método sync siendo llamado con AsyncSession.
Revisar el stacktrace y corregir el método.

### Error: Timeout
```
❌ Request timeout after 30s
```

**Solución**:
- Verificar que la API esté corriendo
- Aumentar timeout en `test_config.py`

---

## 📈 Criterios de Éxito

Para considerar la migración completa y exitosa:

- ✅ **100% de tests pasando** en módulos críticos (1-4)
- ✅ **>95% de tests pasando** en módulos importantes (5-8)
- ✅ **0 errores de AsyncSession** en todos los módulos
- ✅ **Tiempos de respuesta P95 <500ms** en endpoints críticos
- ✅ **No errores en logs de producción** después del deploy

---

## 🔄 Workflow Recomendado

### 1. Ejecutar Tests Iniciales
```bash
python run_integration_tests.py --modules 1 2 3 4
```

### 2. Identificar Errores
- Revisar output de tests
- Identificar patrones de error
- Listar archivos a corregir

### 3. Corregir Código
```bash
# Ejemplo: Corregir método sync con AsyncSession
# ANTES:
user = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)

# DESPUÉS:
user = await async_gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
```

### 4. Re-ejecutar Tests
```bash
python run_integration_tests.py --modules 3  # Solo el módulo corregido
```

### 5. Repetir hasta Verde
Iterar pasos 2-4 hasta que todos los tests pasen

### 6. Deploy a Producción
```bash
git add -A
git commit -m "fix(async): corregir módulo X según tests"
git push origin feature/async-phase2-repositories-week1
```

### 7. Monitorear Producción
- Verificar logs en Render
- Ejecutar tests contra producción
- Monitorear métricas de performance

---

## 📝 Notas Importantes

### ⚠️ Tests contra Producción
Estos tests se ejecutan contra la **API de producción real**.

**Precauciones**:
- No crear datos de test excesivos
- Limpiar datos de test después de ejecutar
- Usar un gym de test dedicado si es posible
- No ejecutar tests durante horarios pico

### 🔒 Seguridad de Tokens
- **NUNCA** commitear tokens en git
- **NUNCA** compartir tokens públicamente
- Regenerar tokens después de usarlos en tests
- Usar tokens con permisos mínimos necesarios

### 📊 Métricas de Performance
Los tests miden tiempos de respuesta:
- Target: P95 <500ms
- Alarma: P95 >1000ms
- Crítico: P95 >2000ms

---

## 🆘 Troubleshooting

### Problema: No encuentro mis tokens
**Solución**: Sigue la sección "Obtener Tokens de Auth0" arriba

### Problema: Tests fallan con 403 Forbidden
**Solución**: Verificar que el token tenga los scopes correctos

### Problema: Tests muy lentos
**Solución**:
- Verificar conexión a internet
- Ejecutar contra API local si es posible
- Reducir número de tests con `--modules`

### Problema: Muchos tests fallando
**Solución**:
- Empezar por módulos críticos (1-4)
- Corregir un módulo a la vez
- Usar `--verbose` para más detalles

---

## 📞 Contacto y Soporte

Si encuentras problemas o necesitas ayuda:

1. Revisar logs en `tests/integration/test_*.py`
2. Verificar ASYNC_MIGRATION_TEST_PLAN.md
3. Revisar documentación de FastAPI async
4. Consultar con el equipo de desarrollo

---

## 🎯 Checklist Final

Antes de considerar la migración completa:

- [ ] Todos los tests de módulos críticos (1-4) pasan
- [ ] Tiempos de respuesta dentro del target
- [ ] No hay errores de AsyncSession en logs
- [ ] API funciona correctamente en producción
- [ ] Usuarios reportan funcionamiento normal
- [ ] Métricas de performance mejoradas vs sync
- [ ] Documentación actualizada
- [ ] Equipo capacitado en debugging async

---

**¡Buena suerte con la migración! 🚀**
