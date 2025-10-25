# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start
```bash
# 1. Configuración inicial
cp .env.example .env              # Configurar variables de entorno (crítico: configurar TODAS las APIs)
python -m venv env                # Crear entorno virtual
source env/bin/activate           # Activar entorno virtual Python 3.11+
pip install -r requirements.txt   # Instalar dependencias

# 2. Servicios locales con Docker
docker-compose up -d              # Levantar PostgreSQL (puerto 5432) y Redis (puerto 6379)
docker-compose ps                 # Verificar servicios corriendo

# 3. Base de datos
alembic upgrade head              # Aplicar todas las migraciones a la BD
python -m app.create_tables       # Crear tablas iniciales (si es primera vez)

# 4. Iniciar servidor
python app_wrapper.py             # RECOMENDADO - Verifica e instala dependencias automáticamente
# Alternativa: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Testing
pytest -v tests/                  # Ejecutar todos los tests con tokens reales de Auth0
./tests.sh                        # Script wrapper alternativo
```

## Comandos de Desarrollo

### Servidor de Desarrollo
```bash
python app_wrapper.py                 # Punto de entrada RECOMENDADO - verifica e instala dependencias faltantes
uvicorn app.main:app --reload        # Alternativa directa si todas las dependencias están instaladas
python -m uvicorn main:app --reload  # Desde directorio raíz (legacy)
```

### Testing
```bash
pytest -v tests/                      # Ejecutar suite completa con verbose
./tests.sh                            # Script wrapper para pytest
pytest tests/api/test_*.py -v        # Tests de API específicos
pytest tests/chat/ -v                 # Tests de Stream Chat
pytest tests/events/ -v               # Tests de eventos y cache
pytest -k "test_function_name"       # Test individual por nombre
pytest --cov=app tests/              # Con coverage report
```

### Base de Datos (Alembic)
```bash
alembic revision --autogenerate -m "descripción"  # Generar nueva migración
alembic upgrade head                               # Aplicar todas las migraciones pendientes
alembic downgrade -1                              # Revertir última migración
alembic history                                    # Ver historial completo
alembic current                                    # Ver migración actual aplicada
```

### Docker
```bash
docker-compose up -d                  # Levantar servicios en background
docker-compose down                   # Detener y eliminar contenedores
docker-compose ps                     # Ver estado de servicios
docker-compose logs -f db             # Ver logs de PostgreSQL
docker-compose logs -f redis          # Ver logs de Redis
```

## Arquitectura del Proyecto

### Stack Tecnológico
- **FastAPI 0.105.0** - Framework web con documentación automática OpenAPI
- **PostgreSQL 14+ con SQLAlchemy 2.0** - ORM moderno con soporte async
- **Redis 7** - Cache distribuido y gestión de sesiones
- **Auth0** - Autenticación JWT con RBAC (Role-Based Access Control)
- **Stream Chat 4.23** - Sistema de chat multi-tenant en tiempo real
- **Stripe** - Pagos, suscripciones y ciclos de facturación
- **OneSignal** - Notificaciones push segmentadas por roles
- **OpenAI GPT-4o-mini** - IA para módulo nutricional
- **APScheduler** - Tareas programadas y jobs en background
- **AWS SQS** - Colas de mensajes para procesamiento asíncrono

### Arquitectura Multi-tenant
Sistema completamente aislado por gimnasio (`gym_id`):
- **TenantAuthMiddleware** - Extracción automática de `gym_id` desde JWT
- **Cache Redis** - Prefijos `gym:{gym_id}:` para aislamiento total
- **Validación cross-gym** - Verificación automática en servicios y repositorios
- **Stream Chat** - Usuarios con prefijos `gym_{gym_id}_user_{user_id}`

### Patrón Clean Architecture
```
API Endpoints → Services (Business Logic) → Repositories (Data + Cache) → Models (SQLAlchemy)
         ↓              ↓                            ↓                         ↓
    Schemas/DTOs   Domain Rules              Redis Cache              PostgreSQL
```

### Módulos del Sistema
- **Auth** - Autenticación y autorización con Auth0
- **Users** - Gestión de usuarios y perfiles con QR codes
- **Events** - Eventos del gimnasio con participación y notificaciones
- **Schedule** - Clases, horarios y reservas con capacidad dinámica
- **Chat** - Mensajería con Stream Chat (grupos, directos, canales)
- **Billing** - Facturación Stripe con múltiples ciclos de pago
- **Nutrition** - Análisis nutricional con IA y tracking de comidas
- **Surveys** - Sistema de encuestas y feedback
- **Metrics** - Estadísticas y reportes del gimnasio
- **Health** - Tracking de medidas corporales y progreso

### Sistema de Permisos Jerárquico
- **Member** - Acceso básico a funcionalidades del gimnasio
- **Trainer** - Gestión de miembros asignados + permisos de Member
- **Admin** - Gestión completa del gimnasio + permisos de Trainer
- **Super Admin** - Acceso cross-gym + todos los permisos

Implementación con scopes de Auth0 y decorador `@require_permission()`

## Middleware Pipeline

### Orden de Ejecución (de abajo hacia arriba)
1. **CORSMiddleware** - Manejo de CORS para orígenes permitidos
2. **SecurityHeadersMiddleware** - Headers de seguridad HTTP
3. **ProfilingMiddleware** - Profiling opcional para debugging (solo DEBUG_MODE)
4. **TenantAuthMiddleware** - Autenticación multi-tenant y extracción de gym_id
5. **RateLimitMiddleware** - Límites de tasa con SlowAPI
6. **TimingMiddleware** - Medición de tiempos de respuesta

### Flujo de Request Multi-tenant
1. Token JWT incluye `gym_id` en custom claims
2. TenantAuthMiddleware extrae y valida automáticamente
3. `request.state.gym` y `request.state.user` disponibles en endpoints
4. Validación cross-gym automática en servicios
5. Cache segmentado con prefijos `gym:{gym_id}:`

## Configuración de Entorno

### Variables de Entorno Críticas
Archivo `.env` debe incluir (ver `.env.example` para plantilla completa):

**Base de datos:**
- **DATABASE_URL** - PostgreSQL connection string (usar Transaction Pooler para Supabase puerto 6543)
  - Formato: `postgresql://user:pass@host:6543/postgres?pgbouncer=true&schema=public`
- **POSTGRES_*** - User, password, server, port, db (para desarrollo local)

**Cache:**
- **REDIS_URL** - Redis para cache y sesiones
  - Formato: `redis://:password@localhost:6379/0`
- **REDIS_HOST**, **REDIS_PORT**, **REDIS_DB**, **REDIS_PASSWORD** - Configuración individual

**Autenticación:**
- **AUTH0_DOMAIN** - Tu dominio Auth0 (ej: `tu-app.auth0.com`)
- **AUTH0_API_AUDIENCE** - Audience de tu API (ej: `https://api.tu-app.com`)
- **AUTH0_CLIENT_ID** - Client ID de tu aplicación Auth0
- **AUTH0_CLIENT_SECRET** - Client Secret de tu aplicación
- **AUTH0_CALLBACK_URL** - URL de callback para auth
- **AUTH0_ALLOWED_REDIRECT_URIS** - JSON array de URIs permitidas
- **ADMIN_SECRET_KEY** - Clave secreta para operaciones admin

**Servicios externos:**
- **STREAM_API_KEY** - API key de Stream Chat
- **STREAM_API_SECRET** - API secret de Stream Chat
- **STRIPE_API_KEY** - Stripe secret key (sk_live_... o sk_test_...)
- **STRIPE_WEBHOOK_SECRET** - Webhook secret de Stripe (whsec_...)
- **OPENAI_API_KEY** - Para módulo de nutrición con IA
- **ONESIGNAL_APP_ID** - ID de app OneSignal
- **ONESIGNAL_REST_API_KEY** - API key de OneSignal
- **AWS_ACCESS_KEY_ID** - Credencial AWS para SQS
- **AWS_SECRET_ACCESS_KEY** - Secret AWS para SQS
- **AWS_REGION** - Región AWS (default: us-east-1)

**Testing:**
- **TEST_AUTH_TOKEN** - Token válido de Auth0 para tests
- **TEST_GYM_ID** - ID de gimnasio para tests (default: 1)
- **TEST_TRAINER_ID** - ID de entrenador para tests
- **TEST_MEMBER_ID** - ID de miembro para tests

### Testing con Tokens Reales
- Tests usan tokens Auth0 reales desde `.env.test`
- Renovar tokens periódicamente para evitar expiración
- Configurar `TEST_GYM_ID`, `TEST_TRAINER_ID`, `TEST_MEMBER_ID`

## Servicios Externos

### Stream Chat (Mensajería)
- **Multi-tenancy**: Usuarios con formato `gym_{gym_id}_user_{user_id}`
- **Tipos de canales**: `messaging` (grupos), `direct` (1-1), `team` (canales públicos)
- **Webhooks**: Autorización en tiempo real en `/api/v1/webhooks/stream/`
- **Tokens**: Generados con permisos específicos por rol

### Stripe (Pagos)
- **Productos**: Membresías con múltiples ciclos (mensual, trimestral, semestral, anual)
- **Webhooks**: Sincronización automática en `/api/v1/webhooks/stripe/`
- **Customer Portal**: Autogestión de suscripciones
- **Payment Links**: Generación dinámica para nuevos miembros

### OpenAI (Nutrición)
- **Modelo**: GPT-4o-mini para análisis nutricional
- **Funciones**: Análisis de imágenes de comidas, cálculo de macros
- **Cache**: Resultados cacheados para optimización de costos

### OneSignal (Notificaciones)
- **Segmentación**: Por roles (admin, trainer, member)
- **Eventos**: Clases próximas, eventos del gimnasio, recordatorios
- **Scheduling**: Integrado con APScheduler para envíos programados

## Optimizaciones de Performance

### Sistema de Cache
- **Redis Cache**: TTLs configurables por tipo de dato
- **Patrón Repository**: Cache automático en capa de datos
- **Invalidación inteligente**: Por patrones de clave
- **Fallback robusto**: Sistema funciona sin Redis

### Rate Limiting
- **SlowAPI**: Límites configurables por endpoint
- **Defaults**: 60 req/min general, 10 req/min para auth
- **Headers**: X-RateLimit-* para transparencia

### Profiling (DEBUG_MODE)
- **Middleware opcional**: Activado con `?profile=true`
- **Perfiles guardados**: En directorio `profiles/`
- **Métricas**: Tiempo DB, Redis hits/misses, latencias

## Background Jobs

### APScheduler
- **Inicialización**: En `app.main:lifespan`
- **Jobs configurados**: Notificaciones de clases, limpieza de cache
- **Timezone-aware**: Configuración por gimnasio

### AWS SQS
- **Colas**: Procesamiento asíncrono de tareas pesadas
- **DLQ**: Dead Letter Queue para reintentos
- **Integración**: Via boto3 con credenciales IAM

## Deployment

### Plataformas Soportadas

#### 1. Render.com (Principal)
- **Configuración:** `render.yaml`
- **Servicios:** Web (Docker), PostgreSQL, Redis
- **Deploy:** Push a GitHub, deploy automático

#### 2. Heroku
- **Configuración:** `Procfile`
- **Comando:** `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT`
- **Buildpack:** Python
- **Add-ons:** Heroku Postgres, Heroku Redis

```bash
# Deploy a Heroku
heroku create tu-app-gymapi
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
heroku config:set AUTH0_DOMAIN=tu-dominio.auth0.com
heroku config:set STREAM_API_KEY=tu-api-key
# ... configurar todas las variables de .env
git push heroku main
heroku run alembic upgrade head
```

#### 3. Docker
- **Dockerfile:** Multi-stage build con Python 3.11-slim
- **Compose:** PostgreSQL + Redis + App
- **Build:** `docker build -t gymapi .`
- **Run:** `docker run -p 8000:8000 --env-file .env gymapi`

### Punto de Entrada
```bash
# SIEMPRE usar app_wrapper.py en producción
python app_wrapper.py  # Verifica e instala dependencias críticas automáticamente
```

### Health Checks
- **Endpoint**: `GET /` - Status básico
- **Endpoint**: `GET /api/v1/health` - Check detallado con DB/Redis

### Variables de Producción
- `DEBUG_MODE=False` - Desactivar debugging
- `TRUST_PROXY_HEADERS=True` - Para servicios tras proxy
- `SQLALCHEMY_ECHO=False` - Desactivar logs SQL


## API Documentation

### Endpoints de Documentación
- **Swagger UI**: http://localhost:8000/api/v1/docs - Interfaz interactiva OAuth2
- **ReDoc**: http://localhost:8000/api/v1/redoc - Documentación detallada
- **OpenAPI**: http://localhost:8000/api/v1/openapi.json - Spec JSON

### Módulos de API (Base: `/api/v1/`)
- **auth/** - Autenticación Auth0 y gestión de permisos
- **users/** - Perfiles, QR codes, gestión de usuarios
- **events/** - Eventos del gimnasio con participación
- **schedule/** - Clases, horarios, reservas con capacidad dinámica
- **chat/** - Mensajería Stream Chat multi-tenant
- **billing/** - Stripe: pagos, suscripciones, customer portal
- **nutrition/** - IA nutricional: análisis de comidas, planes
- **surveys/** - Encuestas y feedback con estadísticas
- **metrics/** - Dashboard de estadísticas del gimnasio
- **health/** - Tracking corporal y progreso fitness
- **trainer-members/** - Gestión de miembros por entrenador
- **notifications/** - OneSignal push notifications

## Patrones de Código Críticos

### Verificación de Módulos Activados
```python
from app.core.dependencies import module_enabled

if not await module_enabled(db, gym_id, "nutrition"):
    raise HTTPException(status_code=404, detail="Módulo no disponible")
```

### Patrón Repository con Cache
```python
class MyRepository(BaseRepository):
    async def get_with_cache(self, id: int):
        # Cache automático con TTL
        cache_key = f"gym:{gym_id}:entity:{id}"
        return await self.get_cached(cache_key, ttl=300)
```

### Verificación Multi-tenant
```python
# En endpoints - automático via TenantAuthMiddleware
@router.get("/resource")
async def get_resource(
    gym_id: int = Depends(get_current_gym_id),  # Inyectado automáticamente
    user: User = Depends(get_current_user)
):
    # gym_id ya validado y seguro
```

### Manejo de Transacciones
```python
async with db.begin():  # Auto-commit o rollback
    # Operaciones múltiples atómicas
    await repository.create(entity)
    await cache.invalidate(pattern)
```


## Testing

### Estructura de Tests
```
tests/
├── api/           # Tests de endpoints con Auth0 real
├── chat/          # Tests de Stream Chat multi-tenant
├── events/        # Tests de eventos y participación
├── schedule/      # Tests de clases y reservas
├── services/      # Tests unitarios de servicios
├── conftest.py    # Fixtures y configuración global
└── .env.test      # Tokens y configuración de test
```

### Scripts de Mantenimiento
En directorio `scripts/` (53 scripts disponibles) para operaciones administrativas:

**Base de datos y migraciones:**
```bash
python scripts/apply_migrations_prod.py      # Aplicar migraciones en producción
python scripts/check_database_schema.py      # Verificar esquema de BD
python scripts/backup_database.py            # Crear backup de BD
python scripts/quick_migrate.py              # Migración rápida con alembic
python scripts/migrate_session_timezone.py   # Migrar timezones de sesiones
```

**Stream Chat:**
```bash
python scripts/check_stream_status.py        # Verificar estado de Stream
python scripts/cleanup_stream_inconsistencies.py  # Limpiar inconsistencias
python scripts/migrate_stream_multitenants.py     # Migrar a multi-tenant
python scripts/fix_direct_chat_memberships.py     # Arreglar membresías directas
python scripts/delete_all_stream_chats.py         # Limpiar todos los chats (CUIDADO)
```

**Stripe y pagos:**
```bash
python scripts/migrate_existing_stripe_data.py    # Migrar datos existentes
python scripts/verify_stripe_config.py            # Verificar configuración
python scripts/test_stripe_payments.py            # Probar flujo de pagos
python scripts/cleanup_duplicate_stripe_accounts.py  # Limpiar duplicados
python scripts/check_billing_module.py            # Verificar módulo de billing
```

**Auth0 y usuarios:**
```bash
python scripts/generate_qr_for_existing_users.py  # Generar QR codes
python scripts/sync_roles_to_auth0.py             # Sincronizar roles
python scripts/migrate_to_auth0_roles.py          # Migrar a roles Auth0
```

**Testing y verificación:**
```bash
python scripts/security_audit.py             # Auditoría de seguridad
python scripts/test_multi_tenant_validation.py  # Validar multi-tenancy
python scripts/test_rate_limiting.py         # Probar rate limiting
python scripts/test_nutrition_system.py      # Probar sistema nutricional
```

**Tracking y analytics:**
```bash
python scripts/add_app_usage_tracking.py     # Agregar tracking de uso de app
python scripts/migrate_survey_system.py      # Migrar sistema de encuestas
```

## Troubleshooting

### Database Connection Issues
```bash
docker-compose ps              # Verificar PostgreSQL corriendo
docker-compose logs db         # Ver logs de errores
# Para Supabase: usar Transaction Pooler URL (puerto 6543)
```

### Redis Connection Issues
```bash
docker-compose ps redis        # Verificar Redis corriendo
docker-compose logs redis      # Ver logs de Redis
redis-cli ping                 # Test conexión local
redis-cli -h localhost -p 6379 ping  # Test con host/puerto específico

# Si Redis requiere password:
redis-cli -a tu_password ping

# Verificar configuración en código:
# app/db/redis_client.py maneja connection pooling automáticamente
# El sistema tiene fallback automático si Redis no está disponible
```

### Redis Configuration
```python
# Variables de entorno para Redis:
REDIS_URL=redis://localhost:6379/0          # Sin password
REDIS_URL=redis://:password@localhost:6379/0  # Con password

# O configuración individual:
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=optional_password

# Connection pooling automático en app/db/redis_client.py:
# - Max connections: 50
# - Socket timeout: 2 segundos
# - Retry on timeout: habilitado
# - Health check interval: 30 segundos
```

### Import/Dependency Issues
```bash
python app_wrapper.py          # Auto-instala dependencias faltantes
which python                   # Verificar env virtual activo
pip install -r requirements.txt --force-reinstall  # Reinstalar todo
```

### Auth0 Token Issues
- Verificar `AUTH0_DOMAIN` y `AUTH0_API_AUDIENCE` correctos
- Tokens en `.env.test` deben renovarse periódicamente
- Verificar scopes en Auth0 Dashboard

### Stream Chat Issues
- Verificar `STREAM_API_KEY` y `STREAM_API_SECRET`
- Usuarios deben tener formato `gym_{id}_user_{id}`
- Ejecutar `scripts/check_stream_status.py` para diagnóstico