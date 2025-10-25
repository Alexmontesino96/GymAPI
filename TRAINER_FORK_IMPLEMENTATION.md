# 🏋️ TRAINER FORK - Plan de Implementación Detallado
## Fork del GymAPI para Soporte de Entrenadores Personales

**Fecha de Inicio**: 2024-01-24
**Versión**: 1.0.0-trainer
**Branch**: `feature/trainer-support`

---

## 📊 RESUMEN EJECUTIVO

### Objetivo
Adaptar el sistema GymAPI existente para soportar entrenadores personales individuales, tratando a cada entrenador como un "gimnasio de un solo entrenador" con funcionalidades optimizadas.

### Estrategia
- **Un único codebase** con diferenciación por tipo
- **Cambios mínimos** al código existente
- **100% compatible** con gimnasios actuales
- **Time to market**: 7 días

### Principios de Diseño
1. **No romper funcionalidad existente**
2. **Reutilizar máximo código posible**
3. **Lógica condicional solo donde sea necesario**
4. **UI/UX adaptativa automática**

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

### 🔵 Base de Datos
- [ ] Crear migración para agregar campo `type` a tabla `gyms`
- [ ] Agregar campos específicos de entrenador
- [ ] Crear índices para optimización
- [ ] Actualizar modelos SQLAlchemy
- [ ] Actualizar schemas Pydantic

### 🟢 Backend - Core
- [ ] Actualizar `app/models/gym.py` con GymType enum
- [ ] Modificar `app/schemas/gym.py` con campos nuevos
- [ ] Adaptar `TenantAuthMiddleware` para entrenadores
- [ ] Crear servicio de configuración contextual

### 🟡 Backend - Endpoints
- [ ] Crear endpoint `/register-trainer` para onboarding
- [ ] Adaptar `/dashboard/summary` con lógica condicional
- [ ] Crear `/context/workspace` para UI adaptativa
- [ ] Modificar `/users` → `/clients` alias para entrenadores

### 🟠 Scripts y Utilidades
- [ ] Script `setup_trainer.py` para onboarding automatizado
- [ ] Script de migración para convertir gym existente
- [ ] Utilidades de testing para entrenadores
- [ ] Script de verificación post-deployment

### 🔴 Testing
- [ ] Tests unitarios para GymType
- [ ] Tests de integración para flujo de entrenador
- [ ] Tests de dashboard adaptativo
- [ ] Tests de permisos y acceso

### 🟣 Documentación
- [ ] Actualizar README con modo entrenador
- [ ] Documentar API changes
- [ ] Guía de onboarding para entrenadores
- [ ] Troubleshooting guide

---

## 🗂️ ESTRUCTURA DE ARCHIVOS A MODIFICAR

```
GymApi/
├── alembic/versions/
│   └── 2024_01_24_add_gym_type.py          [NUEVO]
├── app/
│   ├── models/
│   │   └── gym.py                          [MODIFICAR]
│   ├── schemas/
│   │   └── gym.py                          [MODIFICAR]
│   ├── core/
│   │   ├── config.py                       [MODIFICAR]
│   │   └── trainer_config.py               [NUEVO]
│   ├── middleware/
│   │   └── tenant_auth.py                  [MODIFICAR]
│   ├── api/v1/endpoints/
│   │   ├── trainer_auth.py                 [NUEVO]
│   │   ├── dashboard.py                    [MODIFICAR]
│   │   ├── context.py                      [NUEVO]
│   │   └── users.py                        [MODIFICAR]
│   └── services/
│       └── trainer_setup.py                [NUEVO]
├── scripts/
│   ├── setup_trainer.py                    [NUEVO]
│   └── migrate_to_trainer.py               [NUEVO]
└── tests/
    └── test_trainer/
        ├── test_trainer_setup.py           [NUEVO]
        ├── test_trainer_dashboard.py       [NUEVO]
        └── test_trainer_flow.py            [NUEVO]
```

---

## 📝 TAREAS DETALLADAS

### TAREA 1: Migración de Base de Datos
**Archivo**: `alembic/versions/2024_01_24_add_gym_type.py`
**Prioridad**: CRÍTICA
**Tiempo estimado**: 2 horas

**Cambios**:
1. Agregar enum `gym_type_enum` con valores ['gym', 'personal_trainer']
2. Agregar columna `type` a tabla `gyms` (default: 'gym')
3. Agregar columnas opcionales:
   - `trainer_specialties` (JSON)
   - `trainer_certifications` (JSON)
   - `max_clients` (INTEGER)
4. Crear índice `idx_gyms_type` para optimización

**SQL**:
```sql
CREATE TYPE gym_type_enum AS ENUM ('gym', 'personal_trainer');
ALTER TABLE gyms ADD COLUMN type gym_type_enum NOT NULL DEFAULT 'gym';
ALTER TABLE gyms ADD COLUMN trainer_specialties JSON;
ALTER TABLE gyms ADD COLUMN trainer_certifications JSON;
ALTER TABLE gyms ADD COLUMN max_clients INTEGER;
CREATE INDEX idx_gyms_type ON gyms(type);
```

---

### TAREA 2: Actualizar Modelo Gym
**Archivo**: `app/models/gym.py`
**Prioridad**: CRÍTICA
**Tiempo estimado**: 1 hora

**Cambios**:
1. Importar y definir `GymType` enum
2. Agregar campo `type` con default `GymType.GYM`
3. Agregar campos opcionales de entrenador
4. Agregar propiedades helper (`is_personal_trainer`, `is_traditional_gym`)

---

### TAREA 3: Script de Onboarding
**Archivo**: `scripts/setup_trainer.py`
**Prioridad**: ALTA
**Tiempo estimado**: 3 horas

**Funcionalidades**:
1. Crear usuario con rol TRAINER
2. Crear "gimnasio personal" con type='personal_trainer'
3. Asignar como OWNER del gimnasio
4. Configurar Stripe Connect
5. Activar módulos esenciales
6. Crear planes de pago default

---

### TAREA 4: Dashboard Adaptativo
**Archivo**: `app/api/v1/endpoints/dashboard.py`
**Prioridad**: ALTA
**Tiempo estimado**: 2 horas

**Cambios**:
1. Detectar tipo de gimnasio
2. Si es `personal_trainer`, retornar dashboard simplificado
3. Métricas relevantes: clientes, sesiones, ingresos
4. Quick actions contextuales

---

### TAREA 5: Endpoint de Contexto
**Archivo**: `app/api/v1/endpoints/context.py`
**Prioridad**: MEDIA
**Tiempo estimado**: 1 hora

**Funcionalidad**:
Endpoint que retorna configuración para que el frontend adapte la UI:
- Terminología (gimnasio vs espacio de trabajo)
- Features habilitadas/deshabilitadas
- Menú de navegación
- Branding

---

### TAREA 6: Middleware Simplificado
**Archivo**: `app/middleware/tenant_auth.py`
**Prioridad**: MEDIA
**Tiempo estimado**: 2 horas

**Cambios**:
1. Detectar si el gym es tipo 'personal_trainer'
2. Si el usuario es el owner, simplificar permisos
3. Auto-inyectar gym_id para entrenadores

---

### TAREA 7: Tests
**Directorio**: `tests/test_trainer/`
**Prioridad**: ALTA
**Tiempo estimado**: 3 horas

**Tests a crear**:
1. Test de creación de workspace
2. Test de dashboard adaptativo
3. Test de flujo completo (crear → agregar cliente → sesión → pago)
4. Test de permisos

---

## 🚀 ORDEN DE IMPLEMENTACIÓN

### DÍA 1: Base y Modelos
1. ✅ Crear este documento de planificación
2. ⏳ Crear migración de base de datos
3. ⏳ Actualizar modelo Gym
4. ⏳ Actualizar schemas

### DÍA 2: Core Backend
5. ⏳ Script de onboarding
6. ⏳ Servicio de configuración
7. ⏳ Actualizar middleware

### DÍA 3: Endpoints
8. ⏳ Endpoint registro de entrenador
9. ⏳ Dashboard adaptativo
10. ⏳ Endpoint de contexto

### DÍA 4: Adaptaciones
11. ⏳ Alias de endpoints
12. ⏳ Lógica condicional en servicios
13. ⏳ Optimizaciones de caché

### DÍA 5: Testing
14. ⏳ Tests unitarios
15. ⏳ Tests de integración
16. ⏳ Documentación

### DÍA 6: Refinamiento
17. ⏳ Bug fixes
18. ⏳ Optimizaciones
19. ⏳ Preparación para deploy

### DÍA 7: Deployment
20. ⏳ Deploy a staging
21. ⏳ Verificación final
22. ⏳ Deploy a producción

---

## 🔧 COMANDOS DE DESARROLLO

```bash
# Crear branch de desarrollo
git checkout -b feature/trainer-support

# Generar migración
alembic revision --autogenerate -m "Add gym type for trainer support"

# Aplicar migración
alembic upgrade head

# Ejecutar script de onboarding
python scripts/setup_trainer.py juan@trainer.com Juan Pérez

# Ejecutar tests de entrenador
pytest tests/test_trainer/ -v

# Verificar cambios
python scripts/verify_trainer_implementation.py
```

---

## 📊 MÉTRICAS DE ÉXITO

### Funcionales
- [ ] Un entrenador puede registrarse en < 2 minutos
- [ ] Dashboard carga en < 500ms
- [ ] 100% de tests pasando
- [ ] Sin regresiones en funcionalidad de gimnasios

### Técnicas
- [ ] Queries con índice type ejecutan en < 10ms
- [ ] Cache hit rate > 80% para dashboards
- [ ] Zero downtime durante deployment
- [ ] Logs estructurados para debugging

### Negocio
- [ ] 10 entrenadores onboarded en primera semana
- [ ] NPS > 8 de entrenadores beta
- [ ] < 5 tickets de soporte por entrenador

---

## ⚠️ RIESGOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Migración falla en producción | Baja | Alto | Backup completo antes de migrar |
| Confusión de UI | Media | Medio | Testing exhaustivo con usuarios |
| Performance degradada | Baja | Medio | Índices y cache optimizado |
| Stripe Connect issues | Media | Alto | Fallback a pagos manuales |

---

## 📞 PUNTOS DE CONTACTO

- **Tech Lead**: Implementación técnica
- **Product Manager**: Validación de features
- **QA**: Plan de testing
- **DevOps**: Deployment strategy
- **Support**: Preparación para onboarding

---

## 📈 SEGUIMIENTO DE PROGRESO

### Progreso Actual: **10%**

- [x] Documento de planificación
- [ ] Migración de BD
- [ ] Modelos actualizados
- [ ] Script onboarding
- [ ] Dashboard adaptativo
- [ ] Testing completo
- [ ] Documentación
- [ ] Deploy staging
- [ ] Deploy producción

**Última actualización**: 2024-01-24 10:00 AM

---

## 🎯 PRÓXIMOS PASOS INMEDIATOS

1. **AHORA**: Crear migración de base de datos
2. **SIGUIENTE**: Actualizar modelo Gym
3. **DESPUÉS**: Implementar script de onboarding

---

*Este documento se actualizará conforme avance la implementación*