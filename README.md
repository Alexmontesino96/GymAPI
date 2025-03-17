# GymAPI

API para gestión de gimnasios desarrollada con FastAPI, PostgreSQL y Auth0.

## Características

- Autenticación integrada con Auth0
- Gestión de eventos y participaciones
- Sistema de chat con Stream.io
- API RESTful para integración con frontends web y móviles
- Roles de usuario (administrador, entrenador, miembro)

## Tecnologías

- FastAPI: Framework web de Python de alto rendimiento
- SQLAlchemy: ORM para interactuar con la base de datos
- PostgreSQL: Base de datos relacional
- Auth0: Servicio de autenticación y autorización
- Stream.io: Servicio de chat en tiempo real
- Pydantic: Validación de datos y serialización

## Configuración del Entorno

1. Clona el repositorio:
   ```bash
   git clone https://github.com/tu-usuario/GymAPI.git
   cd GymAPI
   ```

2. Crea un entorno virtual e instala dependencias:
   ```bash
   python -m venv env
   source env/bin/activate  # En Windows: env\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copia el archivo de variables de entorno de ejemplo:
   ```bash
   cp .env.example .env
   ```

4. Edita el archivo `.env` con tus credenciales:
   - Configura tus credenciales de Auth0
   - Configura tu URL de base de datos
   - Añade tu API Key y Secret de Stream.io

5. Crea las tablas de la base de datos:
   ```bash
   python -m app.create_tables
   ```

6. Inicia la aplicación:
   ```bash
   python -m uvicorn main:app --reload
   ```

## Documentación API

La documentación de la API está disponible en:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Estructura del Proyecto

```
app/
├── api/              # Endpoints de la API
├── core/             # Configuración y utilidades principales
├── db/               # Configuración de la base de datos
├── models/           # Modelos SQLAlchemy
├── repositories/     # Acceso a la base de datos
├── schemas/          # Esquemas Pydantic para validación
└── services/         # Lógica de negocio
```

## Endpoints Principales

- `/api/v1/auth/`: Autenticación y permisos
- `/api/v1/users/`: Gestión de usuarios
- `/api/v1/events/`: Gestión de eventos
- `/api/v1/chat/`: Funcionalidad de chat (Stream.io)

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles. 