# Servidor Dedicado para Entrenadores Personales
## Setup con Cambios Mínimos

### 🎯 Estrategia: Fork Mínimo para Entrenadores

Crear una instancia separada del servidor con modificaciones específicas para entrenadores personales, manteniendo 95% del código base.

---

## 📐 ARQUITECTURA PROPUESTA

```
┌─────────────────────────┐     ┌─────────────────────────┐
│   GymAPI (Original)     │     │  TrainerAPI (Fork)      │
│   api.gymapp.com        │     │  api.trainerapp.com     │
├─────────────────────────┤     ├─────────────────────────┤
│   - Gimnasios           │     │   - Entrenadores        │
│   - Multi-trainer       │     │   - Un solo trainer     │
│   - Módulos completos   │     │   - Módulos esenciales  │
└─────────────────────────┘     └─────────────────────────┘
         │                               │
         ▼                               ▼
    PostgreSQL                      PostgreSQL
    (gym_db)                      (trainer_db)
```

---

## 🚀 PLAN DE IMPLEMENTACIÓN

### Fase 1: Setup Inicial (1 día)

#### 1.1 Clonar y Configurar
```bash
# Clonar repositorio
git clone https://github.com/tu-repo/GymApi.git TrainerAPI
cd TrainerAPI

# Crear rama para version de trainers
git checkout -b trainer-version

# Actualizar configuración
cp .env.example .env.trainer
```

#### 1.2 Configuración de Base de Datos
```python
# .env.trainer
DATABASE_URL=postgresql://user:pass@localhost:5432/trainerdb
APP_NAME=TrainerAPI
APP_MODE=trainer  # Nueva variable para identificar modo
```

#### 1.3 Docker Compose para Desarrollo
```yaml
# docker-compose.trainer.yml
version: '3.8'
services:
  trainer-api:
    build: .
    ports:
      - "8001:8000"  # Puerto diferente
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@trainer-db:5432/trainerdb
      - APP_MODE=trainer

  trainer-db:
    image: postgres:14
    ports:
      - "5433:5432"  # Puerto diferente
    environment:
      - POSTGRES_DB=trainerdb
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres

  trainer-redis:
    image: redis:7
    ports:
      - "6380:6379"  # Puerto diferente
```

---

## 📝 CAMBIOS MÍNIMOS DE CÓDIGO

### 1. Configuración Base (app/core/config.py)
```python
class Settings(BaseSettings):
    # Agregar configuración de modo
    APP_MODE: str = "gym"  # "gym" o "trainer"

    # Configuración condicional
    @property
    def app_title(self):
        return "TrainerAPI" if self.APP_MODE == "trainer" else "GymAPI"

    @property
    def app_description(self):
        if self.APP_MODE == "trainer":
            return "Plataforma para Entrenadores Personales"
        return "Sistema de Gestión de Gimnasios"
```

### 2. Middleware Simplificado (app/middleware/tenant_auth.py)
```python
class TenantAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # En modo trainer, auto-asignar gym_id del trainer
        if settings.APP_MODE == "trainer":
            user = await get_current_user(request)
            if user:
                # Obtener el único "gym" del trainer
                trainer_gym = db.query(UserGym).filter(
                    UserGym.user_id == user.id,
                    UserGym.role == GymRoleType.OWNER
                ).first()

                if trainer_gym:
                    # Auto-inject gym_id, no requiere header
                    request.state.gym_id = trainer_gym.gym_id
                    request.headers._list.append(
                        (b"x-gym-id", str(trainer_gym.gym_id).encode())
                    )

        # Continuar con flujo normal
        return await call_next(request)
```

### 3. Auto-Setup para Trainers (app/api/v1/endpoints/auth.py)
```python
@router.post("/register-trainer")
async def register_trainer(
    trainer_data: TrainerRegister,
    db: Session = Depends(get_db)
):
    """Registro simplificado para entrenadores"""

    # 1. Crear usuario
    user = User(
        email=trainer_data.email,
        first_name=trainer_data.first_name,
        last_name=trainer_data.last_name,
        role=UserRole.TRAINER
    )
    db.add(user)

    # 2. Crear "gym" personal automáticamente
    gym = Gym(
        name=f"Entrenamiento Personal {user.first_name} {user.last_name}",
        type="personal_trainer",  # Campo nuevo o reutilizado
        email=user.email,
        phone=trainer_data.phone,
        timezone=trainer_data.timezone or "America/Mexico_City"
    )
    db.add(gym)

    # 3. Crear relación UserGym como OWNER
    user_gym = UserGym(
        user_id=user.id,
        gym_id=gym.id,
        role=GymRoleType.OWNER
    )
    db.add(user_gym)

    # 4. Setup Stripe automático
    stripe_account = stripe.Account.create(
        type="express",
        country="MX",
        email=user.email,
        capabilities={"transfers": {"requested": True}}
    )

    gym_stripe = GymStripeAccount(
        gym_id=gym.id,
        stripe_account_id=stripe_account.id
    )
    db.add(gym_stripe)

    # 5. Activar módulos esenciales
    essential_modules = ["users", "chat", "health", "nutrition", "payments"]
    for module in essential_modules:
        gym_module = GymModule(
            gym_id=gym.id,
            module_code=module,
            is_active=True
        )
        db.add(gym_module)

    db.commit()
    return {"message": "Trainer registered successfully", "gym_id": gym.id}
```

### 4. UI Adaptations (app/api/v1/endpoints/gyms.py)
```python
@router.get("/my-workspace")
async def get_my_workspace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener workspace del trainer (su 'gym' personal)"""

    if settings.APP_MODE == "trainer":
        # Retornar datos simplificados para trainer
        workspace = db.query(Gym).join(UserGym).filter(
            UserGym.user_id == current_user.id,
            UserGym.role == GymRoleType.OWNER
        ).first()

        return {
            "id": workspace.id,
            "name": workspace.name,
            "type": "personal_trainer",
            "trainer": {
                "name": f"{current_user.first_name} {current_user.last_name}",
                "email": current_user.email,
                "photo": current_user.photo_url
            },
            "stats": {
                "active_clients": count_active_members(workspace.id),
                "sessions_this_week": count_sessions_week(workspace.id),
                "revenue_month": calculate_revenue_month(workspace.id)
            }
        }

    # Modo gym normal
    return get_gym_details(...)
```

### 5. Simplificar Endpoints No Necesarios
```python
# app/api/v1/api.py

from app.core.config import settings

api_router = APIRouter()

# Endpoints comunes
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(chat.router, prefix="/chat")
api_router.include_router(health.router, prefix="/health")
api_router.include_router(nutrition_router, prefix="/nutrition")
api_router.include_router(memberships.router, prefix="/memberships")

# Endpoints solo para gimnasios
if settings.APP_MODE == "gym":
    api_router.include_router(gyms.router, prefix="/gyms")
    api_router.include_router(schedule_router, prefix="/schedule")
    api_router.include_router(classes.router, prefix="/classes")
    api_router.include_router(equipment.router, prefix="/equipment")

# Endpoints solo para trainers
if settings.APP_MODE == "trainer":
    api_router.include_router(trainer_workspace.router, prefix="/workspace")
    api_router.include_router(appointments.router, prefix="/appointments")
    api_router.include_router(client_progress.router, prefix="/progress")
```

### 6. Dashboard Personalizado
```python
# app/api/v1/endpoints/dashboard.py

@router.get("/dashboard")
async def get_dashboard(
    current_gym: Gym = Depends(get_current_gym),
    db: Session = Depends(get_db)
):
    if settings.APP_MODE == "trainer":
        return {
            "type": "trainer_dashboard",
            "metrics": {
                "total_clients": count_clients(current_gym.id),
                "active_clients": count_active_clients(current_gym.id),
                "sessions_today": count_sessions_today(current_gym.id),
                "revenue_month": calculate_revenue(current_gym.id),
                "pending_payments": count_pending_payments(current_gym.id),
                "upcoming_sessions": get_upcoming_sessions(current_gym.id, limit=5)
            },
            "quick_actions": [
                {"action": "add_client", "label": "Agregar Cliente"},
                {"action": "schedule_session", "label": "Agendar Sesión"},
                {"action": "create_plan", "label": "Crear Plan Nutricional"}
            ]
        }

    # Dashboard de gimnasio normal
    return get_gym_dashboard(...)
```

---

## 🔧 SCRIPTS DE MIGRACIÓN

### migrate_to_trainer.py
```python
#!/usr/bin/env python
"""Script para convertir un gym existente en workspace de trainer"""

import sys
from app.db.session import SessionLocal
from app.models import Gym, UserGym, GymModule

def convert_gym_to_trainer(gym_id: int):
    db = SessionLocal()

    # 1. Actualizar tipo de gym
    gym = db.query(Gym).filter(Gym.id == gym_id).first()
    if gym:
        gym.type = "personal_trainer"

        # 2. Desactivar módulos no necesarios
        unnecessary_modules = ["equipment", "classes", "staff"]
        db.query(GymModule).filter(
            GymModule.gym_id == gym_id,
            GymModule.module_code.in_(unnecessary_modules)
        ).update({"is_active": False})

        # 3. Limpiar datos no necesarios
        # ...

        db.commit()
        print(f"Gym {gym_id} converted to trainer workspace")

if __name__ == "__main__":
    convert_gym_to_trainer(int(sys.argv[1]))
```

---

## 🚢 DEPLOYMENT

### 1. Heroku (Opción Rápida)
```bash
# Crear app separada
heroku create trainer-api-app

# Configurar buildpacks
heroku buildpacks:set heroku/python

# Deploy
git push heroku trainer-version:main

# Variables de entorno
heroku config:set APP_MODE=trainer
heroku config:set DATABASE_URL=...
```

### 2. Docker (Producción)
```dockerfile
# Dockerfile.trainer
FROM python:3.11-slim

ENV APP_MODE=trainer

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app_wrapper.py"]
```

### 3. Render.com
```yaml
# render.trainer.yaml
services:
  - type: web
    name: trainer-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python app_wrapper.py"
    envVars:
      - key: APP_MODE
        value: trainer
      - key: DATABASE_URL
        fromDatabase:
          name: trainer-db
          property: connectionString

databases:
  - name: trainer-db
    databaseName: trainerdb
    user: trainer_user
```

---

## 📊 VENTAJAS DE ESTE ENFOQUE

### ✅ Beneficios
1. **Separación completa**: No afecta servidor de gimnasios
2. **Customización fácil**: Cambios específicos para trainers
3. **Escalabilidad independiente**: Cada servidor escala según su demanda
4. **Testing aislado**: No riesgo de afectar gimnasios en producción
5. **Tiempo de implementación**: 2-3 días máximo
6. **Rollback simple**: Si algo falla, no afecta gimnasios

### ⚠️ Consideraciones
1. **Mantenimiento dual**: Dos codebases (aunque 95% compartido)
2. **Sincronización**: Features nuevas deben agregarse a ambos
3. **Costos de infraestructura**: Dos servidores, dos BDs

---

## 🎯 CRONOGRAMA DE IMPLEMENTACIÓN

### Día 1
- ✅ Clonar repositorio
- ✅ Configurar entorno trainer
- ✅ Crear base de datos separada
- ✅ Implementar cambios de config.py

### Día 2
- ✅ Modificar middleware para auto-gym
- ✅ Crear endpoint registro trainer
- ✅ Adaptar dashboard
- ✅ Testing local

### Día 3
- ✅ Deploy a staging
- ✅ Testing con datos reales
- ✅ Ajustes finales
- ✅ Documentación

---

## 🔄 SINCRONIZACIÓN FUTURA

```bash
# Script para sincronizar cambios del repo principal
#!/bin/bash
# sync_from_main.sh

git fetch upstream main
git checkout trainer-version
git merge upstream/main --no-commit

# Revisar conflictos en archivos clave
# - app/core/config.py
# - app/middleware/tenant_auth.py
# - app/api/v1/api.py

git commit -m "Sync from main gym repo"
```

---

## 💡 PRÓXIMOS PASOS

1. **Validación de concepto**: 2-3 días desarrollo
2. **Beta con 5 trainers**: 1 semana
3. **Feedback e iteración**: 1 semana
4. **Launch oficial**: 2 semanas total

Con este approach, tendrías un **servidor completamente funcional para trainers en 3 días**, manteniendo toda la funcionalidad core y sin riesgo para el sistema de gimnasios existente.