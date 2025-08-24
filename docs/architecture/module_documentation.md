# Documentación de Módulos GymAPI

## Visión General de la Arquitectura

GymAPI está diseñada siguiendo una arquitectura en capas que separa claramente las responsabilidades y facilita el mantenimiento y la escalabilidad. La aplicación está estructurada siguiendo los principios de Arquitectura Limpia (Clean Architecture), organizando el código en módulos con responsabilidades bien definidas.

## Estructura de Directorios

```
app/
├── api/
│   └── v1/
│       ├── api.py                   # Configuración principal de la API 
│       └── endpoints/               # Endpoints de la API agrupados por dominio
│           ├── auth.py              # Endpoints de autenticación
│           ├── auth/                # Submódulos de autenticación
│           ├── chat.py              # Sistema de chat
│           ├── events.py            # Gestión de eventos
│           ├── schedule.py          # Horarios del gimnasio
│           ├── schedule/            # Submódulos de programación
│           ├── trainer_member.py    # Relaciones entrenador-miembro
│           └── users.py             # Gestión de usuarios
├── core/                            # Componentes centrales de la aplicación
│   ├── auth0_fastapi.py            # Integración con Auth0
│   ├── config.py                   # Configuración de la aplicación
│   └── security.py                 # Funciones de seguridad
├── db/                              # Capa de acceso a datos
│   ├── base.py                     # Clase base para modelos SQLAlchemy
│   └── session.py                  # Gestión de sesiones de base de datos
├── models/                          # Modelos SQLAlchemy
├── repositories/                    # Repositorios para acceso a datos
├── schemas/                         # Esquemas Pydantic para validación y serialización
├── services/                        # Servicios para la lógica de negocio
└── utils/                           # Utilidades generales
```

## Capas de la Aplicación

### 1. Capa de Presentación - API Endpoints

Los endpoints se encuentran en el directorio `app/api/v1/endpoints/` y representan la interfaz externa de la API. Cada endpoint:

- Define rutas HTTP utilizando FastAPI
- Gestiona la autenticación y autorización
- Valida datos de entrada usando esquemas Pydantic
- Delega la lógica de negocio a los servicios
- Maneja errores y formatea respuestas

Los endpoints están organizados por dominio funcional (usuarios, eventos, programación, etc.) para mantener una estructura coherente y facilitar la navegación.

### 2. Capa de Lógica de Negocio - Servicios

Los servicios se encuentran en el directorio `app/services/` y contienen la lógica de negocio central. Cada servicio:

- Implementa operaciones específicas del dominio
- Coordina operaciones entre múltiples repositorios
- Aplica reglas de negocio y validaciones
- Es independiente de los detalles de implementación de API o base de datos

### 3. Capa de Acceso a Datos - Repositorios

Los repositorios se encuentran en el directorio `app/repositories/` y encapsulan todas las operaciones de acceso a datos. Cada repositorio:

- Proporciona métodos CRUD para un modelo específico
- Implementa consultas especializadas
- Abstrae los detalles de la base de datos
- Maneja transacciones y mantenimiento de la integridad de los datos

### 4. Capa de Datos - Modelos y Esquemas

La aplicación utiliza dos tipos de modelos:

- **Modelos SQLAlchemy** (`app/models/`): Definen la estructura de la base de datos y las relaciones entre entidades.
- **Esquemas Pydantic** (`app/schemas/`): Definen la estructura de los datos para la validación de entrada/salida y documentación de la API.

## Patrón de Diseño por Módulo

Cada módulo funcional (usuarios, eventos, etc.) sigue el mismo patrón de diseño:

### Ejemplo: Módulo de Eventos

1. **Endpoint** (`app/api/v1/endpoints/events.py`):
   - Define rutas HTTP para operaciones CRUD de eventos
   - Gestiona permisos basados en roles y scopes
   - Llama a los servicios apropiados

2. **Servicio** (`app/services/event.py`):
   - Implementa la lógica de negocio para eventos
   - Gestiona reglas como límites de participantes, verificación de fechas, etc.
   - Coordina entre repositorios de eventos y otros relacionados

3. **Repositorio** (`app/repositories/event.py`):
   - Proporciona operaciones CRUD para eventos
   - Implementa consultas específicas como búsqueda por fecha, tipo, etc.

4. **Modelos**:
   - Modelo SQLAlchemy (`app/models/event.py`): Define la estructura de la tabla en la base de datos
   - Esquemas Pydantic (`app/schemas/event.py`): Define la estructura para validación de API

## Gestión de Autenticación y Autorización

La autenticación se gestiona a través de Auth0 con una integración personalizada:

- `app/core/auth0_fastapi.py`: Integra Auth0 con FastAPI
- La autorización se realiza en dos niveles:
  1. Nivel de endpoint: Verificación de scopes en tokens JWT
  2. Nivel de servicio: Verificación de propiedad de recursos y roles

## Convenciones de Nomenclatura

- **Endpoints**: Verbos en infinitivo que describen la acción (create_user, get_events)
- **Servicios**: Métodos que describen la acción de negocio (register_user_to_event)
- **Repositorios**: Métodos que describen la operación de datos (get_user_by_email)
- **Modelos**: Sustantivos en singular que representan la entidad (User, Event, ClassSession)

## Gestión de Errores

La gestión de errores se realiza de manera consistente en toda la aplicación:

1. Errores de validación: Gestionados automáticamente por Pydantic
2. Errores de negocio: Lanzados como excepciones desde los servicios
3. Errores HTTP: Convertidos en respuestas adecuadas en los endpoints

## Extensibilidad

La aplicación está diseñada para ser extensible:

- **Versionado de API**: La estructura permite agregar nuevas versiones de API
- **Nuevos módulos**: Pueden agregarse siguiendo el mismo patrón de diseño
- **Cambios en la base de datos**: Gestionados a través de migraciones Alembic 