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