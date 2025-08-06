# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos de Desarrollo

### Servidor de Desarrollo
```bash
python app_wrapper.py              # Punto de entrada recomendado con verificación de dependencias
python -m uvicorn main:app --reload # Alternativa directa
```

### Testing
```bash
pytest -v tests/                   # Ejecutar todos los tests con verbose
./tests.sh                         # Script de tests personalizado
pytest tests/api/test_*.py -v      # Tests específicos de API
pytest -k "test_name" -v           # Test individual por nombre
```

### Base de Datos
```bash
alembic revision --autogenerate -m "descripción"  # Nueva migración
alembic upgrade head                               # Aplicar migraciones
alembic downgrade -1                              # Revertir migración
```

### Docker
```bash
docker-compose up                   # Levantar PostgreSQL y Redis locales
```

## Arquitectura del Proyecto

### Stack Tecnológico
- **FastAPI 0.105.0** - Framework web principal con auto-documentación
- **PostgreSQL + SQLAlchemy 2.0** - Base de datos con ORM moderno
- **Redis** - Cache y gestión de sesiones
- **Auth0** - Autenticación JWT con roles y scopes
- **Stream Chat** - Sistema de chat en tiempo real
- **Stripe** - Procesamiento de pagos y suscripciones
- **OneSignal** - Notificaciones push basadas en roles

### Estructura Multi-tenant
El sistema maneja múltiples gimnasios con aislamiento completo de datos:
- Middleware de tenant authentication automático
- Cache separado por `gym_id`
- Validación cross-gym en todos los endpoints
- Tokens de Stream Chat con prefijos de gimnasio

### Patrón Arquitectónico
**Clean Architecture en capas:**
```
Endpoints (API) → Services (Business Logic) → Repositories (Data Access) → Models (Database)
```

### Módulos Activables
Sistema de módulos que se pueden habilitar/deshabilitar por gimnasio. Usar la factoría `module_enabled()` para verificar disponibilidad antes de acceder a funcionalidades.

### Sistema de Permisos
Roles jerárquicos: **Miembro** < **Entrenador** < **Administrador** < **Super Admin**
- Integración con scopes de Auth0
- Verificación granular a nivel de endpoint y servicio
- Decorador `@require_permission()` para proteger recursos

## Configuración Crítica

### Variables de Entorno
- Todas las claves de API están externalizadas
- Archivo `.env.test` separado para testing
- Configuración específica por entorno (desarrollo/producción)

### Testing con Tokens Reales
Los tests funcionales usan tokens de Auth0 reales definidos en `.env.test`. Renovar periódicamente para evitar expiración.

## Servicios Externos Integrados

### Stream Chat
- Multi-tenant con prefijos de gimnasio
- Webhooks de autorización en tiempo real
- Canales seguros por roles

### Stripe
- Suscripciones con ciclos de facturación personalizables
- Webhooks seguros para sincronización de estado
- Gestión de métodos de pago

### OpenAI
- GPT-4o-mini para IA nutricional
- Análisis de imágenes de comidas
- Generación de planes personalizados

## Consideraciones Especiales

### Performance
- Caching inteligente con Redis y TTLs configurables
- Rate limiting por endpoint con SlowAPI
- Profiling middleware para optimización

### Seguridad
- Validación estricta de acceso multi-tenant
- Sanitización de entrada en todos los endpoints
- Logs estructurados para auditoría

### Background Tasks
- APScheduler para tareas programadas
- AWS SQS para colas de mensajes asíncronas
- Health checks automáticos

## Deployment

### Plataformas Soportadas
- **Render.com** (principal) - usar `render.yaml`
- **Heroku** (alternativa) - usar `Procfile`
- **Docker** - containerizado para portabilidad

### Comandos de Lint/Type Check
```bash
# El proyecto no tiene comandos de lint específicos configurados
# Verificar con pytest que incluye validación de tipos vía Pydantic
pytest -v
```

## Middlewares y Flujo de Peticiones

### Orden de Middlewares (aplicado de abajo hacia arriba)
1. **CORSMiddleware** - Manejo de CORS
2. **ProfilingMiddleware** - Solo en modo debug para endpoints específicos
3. **TenantAuthMiddleware** - Autenticación multi-tenant automática 
4. **RateLimitMiddleware** - Limitación de tasa con SlowAPI
5. **TimingMiddleware** - Medición de tiempo de respuesta
6. **Custom Logging Middleware** - Log detallado de peticiones/respuestas

### Flujo de Autenticación Multi-tenant
- Extracción automática del `gym_id` desde el token JWT
- Inyección de dependencia `current_gym_id` disponible en todos los endpoints
- Validación cross-gym automática en servicios y repositorios
- Cache segmentado por gimnasio usando prefijos `gym:{gym_id}:`

## Patrones de Implementación Críticos

### Factory Pattern para Módulos
```python
from app.core.dependencies import module_enabled
# Usar antes de acceder a funcionalidades opcionales
if not module_enabled(gym_id, "nutrition"):
    raise HTTPException(status_code=404, detail="Módulo no disponible")
```

### Patrón Repository con Cache
- Todos los repositorios extienden `BaseRepository`
- Cache automático con TTL configurable
- Invalidación inteligente por patrones de clave
- Fallback a base de datos si Redis falla

### Gestión de Dependencias Críticas
- `app_wrapper.py` verifica e instala dependencias faltantes automáticamente
- Usado como punto de entrada principal en lugar de `main.py` directo
- Manejo robusto de fallos de importación de módulos críticos

## Servicios Externos y Configuración

### Variables de Entorno Críticas
Definidas en `app/core/config.py` con validación Pydantic:
- `DATABASE_URL` - PostgreSQL con connection pooling
- `REDIS_URL` - Cache y sesiones
- `AUTH0_*` - Configuración completa de Auth0
- `STREAM_*` - Stream Chat con multi-tenancy
- `STRIPE_*` - Pagos y suscripciones
- `OPENAI_API_KEY` - IA nutricional
- `AWS_*` - SQS para colas asíncronas
- `ONESIGNAL_*` - Notificaciones push

### Background Jobs con APScheduler
- Inicializado en `app.main:lifespan`
- Jobs definidos en `app/core/scheduler.py`
- Manejo de timezone por gimnasio
- Cleanup automático de datos temporales

## Testing y Debugging

### Estructura de Tests
- `tests/api/` - Tests de endpoints con tokens reales de Auth0
- `tests/chat/` - Flujos completos de Stream Chat
- `tests/events/` - Lógica de eventos y cache
- `tests/schedule/` - Sistema de horarios y participaciones
- `conftest.py` - Fixtures compartidas y configuración

### Profiling y Optimización
- Middleware de profiling para endpoints específicos
- Perfiles guardados en `profiles/` con análisis detallado
- Métricas de performance en logs estructurados

### Scripts de Mantenimiento
Ubicados en `scripts/` para operaciones administrativas:
- `backup_database.py` - Backups automatizados
- `migrate_*.py` - Migraciones de datos específicas  
- `test_*.py` - Scripts de verificación de servicios
- `security_audit.py` - Auditoría de seguridad