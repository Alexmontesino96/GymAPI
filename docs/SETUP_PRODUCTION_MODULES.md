# Configuración de Módulos en Producción

## Problema

Al registrar un nuevo gym owner, solo se activaron 4 de 8 módulos esperados porque los módulos no existían en la tabla `modules` de producción.

## Solución

Ejecutar el script de setup de módulos esenciales en el servidor de producción.

## Opción 1: Via Render Shell (Recomendado)

1. Ir a [Render Dashboard](https://dashboard.render.com)
2. Seleccionar el servicio **gymapi-eh6m**
3. Click en **Shell** en el menú lateral
4. Ejecutar:

```bash
python scripts/setup_essential_modules.py
```

5. Verificar output:

```
================================================================================
CONFIGURACIÓN DE MÓDULOS ESENCIALES
================================================================================
✅ Módulo 'health' creado
✅ Módulo 'surveys' creado
✅ Módulo 'equipment' creado
✅ Módulo 'appointments' creado
✅ Módulo 'progress' creado
✅ Módulo 'classes' creado
✅ Módulo 'attendance' creado

📊 Resumen:
  - Módulos creados: 7
  - Ya existentes: 8
  - Total: 15
```

## Opción 2: Via Conexión Directa a BD

Si tienes acceso directo a la base de datos PostgreSQL:

```bash
psql $DATABASE_URL -c "
INSERT INTO modules (code, name, description, is_premium, created_at, updated_at)
VALUES
  ('health', 'Tracking de Salud', 'Seguimiento de medidas corporales y métricas de salud', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('surveys', 'Encuestas y Feedback', 'Sistema de encuestas para recopilar feedback de miembros', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('equipment', 'Gestión de Equipos', 'Control de equipamiento y mantenimiento', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('appointments', 'Agenda de Citas', 'Sistema de agendamiento para entrenadores personales', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('progress', 'Progreso de Clientes', 'Tracking de progreso y logros de clientes', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('classes', 'Clases Grupales', 'Gestión de clases grupales y capacidad', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('attendance', 'Asistencia', 'Control de asistencia de miembros', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO NOTHING;
"
```

## Opción 3: Automatizar en Deploy

Agregar al archivo `render.yaml`:

```yaml
services:
  - type: web
    name: gymapi
    env: python
    buildCommand: "pip install -r requirements.txt && python scripts/setup_essential_modules.py"
    startCommand: "python app_wrapper.py"
```

O crear un script `scripts/post_deploy.sh`:

```bash
#!/bin/bash
echo "Running post-deploy setup..."
python scripts/setup_essential_modules.py
echo "Post-deploy setup complete"
```

## Verificación

Para verificar que los módulos se crearon correctamente:

```bash
# Via Render Shell
python -c "
from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
result = db.execute(text('SELECT code, name FROM modules ORDER BY code'))
for row in result:
    print(f'{row[0]:<20} {row[1]}')
db.close()
"
```

Deberías ver todos los 16 módulos:

```
appointments         Agenda de Citas
attendance           Asistencia
billing              Facturación y Pagos
chat                 Chat
classes              Clases Grupales
equipment            Gestión de Equipos
events               Eventos
health               Tracking de Salud
nutrition            Planes Nutricionales
posts                Publicaciones
progress             Progreso de Clientes
relationships        Relaciones
schedule             Horarios y Clases
stories              Historias
surveys              Encuestas y Feedback
users                Usuarios
```

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'greenlet'"

El script ya está optimizado para no usar async. Si aún aparece, ejecutar:

```bash
pip install greenlet
python scripts/setup_essential_modules.py
```

### Error: "relation modules does not exist"

Ejecutar migraciones primero:

```bash
alembic upgrade head
python scripts/setup_essential_modules.py
```

### Error: "duplicate key value violates unique constraint"

Algunos módulos ya existen. Esto es normal, el script lo maneja automáticamente mostrando:

```
ℹ️  Módulo 'users' ya existe
```

## Módulos Creados

Este script crea los siguientes módulos si no existen:

| Código | Nombre | Descripción | Premium |
|--------|--------|-------------|---------|
| users | Gestión de Usuarios | Gestión de miembros, entrenadores y usuarios | No |
| schedule | Clases y Horarios | Sistema de clases grupales y gestión de horarios | No |
| events | Eventos del Gimnasio | Creación y gestión de eventos especiales | No |
| chat | Mensajería | Sistema de chat en tiempo real con Stream | No |
| billing | Pagos y Facturación | Gestión de pagos, suscripciones y facturación con Stripe | No |
| **health** | **Tracking de Salud** | **Seguimiento de medidas corporales y métricas de salud** | **No** |
| nutrition | Planes Nutricionales | Análisis nutricional con IA y planes de alimentación | Sí |
| **surveys** | **Encuestas y Feedback** | **Sistema de encuestas para recopilar feedback de miembros** | **No** |
| **equipment** | **Gestión de Equipos** | **Control de equipamiento y mantenimiento** | **No** |
| **appointments** | **Agenda de Citas** | **Sistema de agendamiento para entrenadores personales** | **No** |
| **progress** | **Progreso de Clientes** | **Tracking de progreso y logros de clientes** | **No** |
| **classes** | **Clases Grupales** | **Gestión de clases grupales y capacidad** | **No** |
| stories | Historias | Historias estilo Instagram (24h) | No |
| posts | Publicaciones | Feed social del gimnasio | No |
| **attendance** | **Asistencia** | **Control de asistencia de miembros** | **No** |

**Nota:** Los módulos en negrita son los que se crean con este script (faltaban en el sistema inicial).

## Impacto

Después de ejecutar este script, el endpoint `/api/v1/auth/register-gym-owner` activará todos los módulos esperados:

**Para gym tradicional (gym_type="gym"):**
- 9 módulos activos: users, schedule, events, chat, billing, health, nutrition, surveys, equipment

**Para entrenador personal (gym_type="personal_trainer"):**
- 8 módulos activos: users, chat, health, nutrition, billing, appointments, progress, surveys

## Frecuencia de Ejecución

- **Primera vez:** Ejecutar manualmente
- **Nuevos módulos:** Ejecutar cuando se agreguen nuevos módulos al sistema
- **Post-deploy:** Opcional, puede automatizarse para ejecutar en cada deploy
