# GymAPI - Tests

Este directorio contiene las pruebas para la API de GymAPI.

## Estructura de pruebas

- `api/`: Pruebas unitarias para endpoints de API
- `middleware/`: Pruebas unitarias para middleware de la aplicación
- `utils/`: Pruebas unitarias para utilidades comunes
- `events/`: Pruebas de flujo para eventos y participaciones
- `schedule/`: Pruebas de flujo para horarios, clases y sesiones
- `trainer_member/`: Pruebas de relaciones entrenador-miembro

## Pruebas de eventos

Las pruebas de eventos (`events/`) verifican la funcionalidad del sistema de gestión de eventos y participaciones:

- `test_events_flow.py`: Prueba del flujo básico de creación y gestión de eventos
- `test_events_flow_completo.py`: Prueba completa del ciclo de vida de eventos con todos los casos de uso

## Pruebas de horarios

Las pruebas de horarios (`schedule/`) verifican la funcionalidad del sistema de programación de clases:

- `test_clases_crud.py`: Prueba del CRUD básico para clases
- `test_fixed_session.py`: Prueba específica para resolver el problema de gym_id en sesiones
- `test_simple_session.py`: Prueba simple de creación y gestión de sesiones
- `test_horario_semanal.py`: Prueba completa de configuración de un horario semanal
- `test_schedule_flow.py`: Flujo completo del sistema de horarios incluyendo reservas

## Pruebas de relaciones entrenador-miembro

Las pruebas de relaciones entrenador-miembro (`trainer_member/`) verifican la funcionalidad del sistema de gestión de relaciones entre entrenadores y miembros:

- `test_trainer_member_flow.py`: Prueba completa del flujo de relaciones entre entrenadores y miembros, incluyendo:
  - Creación de relaciones
  - Obtención de relaciones (todas, por entrenador, por miembro)
  - Actualización de relaciones
  - Eliminación de relaciones

## Pruebas del sistema de chat

Las pruebas del sistema de chat (`chat/`) verifican la funcionalidad de la integración con Stream Chat y la gestión de salas de chat en la aplicación:

- `test_chat_flow.py`: Prueba completa del flujo del sistema de chat, incluyendo:
  - Obtención de información del usuario autenticado
  - Obtención de tokens de Stream Chat
  - Creación y gestión de chats directos entre usuarios
  - Creación y gestión de chats para eventos
  - Creación y gestión de salas de chat personalizadas
  - Administración de miembros en salas de chat

### Estado actual de la implementación de chat

Después de ajustar el test para que coincida con los endpoints existentes en la API, los resultados son:

- ✅ Autenticación exitosa
- ✅ Obtención del perfil de usuario
- ❌ Obtención de tokens de Stream Chat (error 500 - Internal Server Error)
- ✅ Obtención/creación de chats para eventos (funciona correctamente)
- ❌ Obtención/creación de chats directos (error 500 - Internal Server Error)
- ❌ Creación de salas personalizadas (error 500 - Internal Server Error)

El test ahora está correctamente alineado con los endpoints implementados en el backend, lo cual revela que:

1. La obtención de información de usuario funciona bien
2. La API de chat para eventos funciona correctamente
3. Las otras funciones de chat están implementadas pero presentan errores de servidor

Estos errores 500 sugieren problemas internos en la implementación que requerirán revisión del código del servidor o posibles problemas con la configuración de Stream Chat.

### Configuración de pruebas del sistema de chat

Para ejecutar las pruebas del sistema de chat, se ha implementado un enfoque con valores fijos en el código en lugar de utilizar variables de entorno:

```python
# IDs para pruebas (valores fijos)
USER_ID = 6  # ID del usuario actual (entrenador)
TARGET_USER_ID = 7  # ID del usuario con quien chatear (miembro)
EVENT_ID = 1  # ID de un evento existente
```

Para ejecutar el test de chat:
```
python -m tests.chat.test_chat_flow
```

## Ejecución de pruebas

Para ejecutar todas las pruebas:

```bash
pytest
```

Para ejecutar tests específicos:

```bash
# Ejecutar un archivo específico
pytest tests/events/test_events_flow.py

# Ejecutar pruebas en un directorio específico
pytest tests/schedule/

# Ejecutar una prueba específica
pytest tests/schedule/test_fixed_session.py -v
```

## Variables de entorno para pruebas

Las pruebas utilizan las siguientes variables de entorno:

- `TEST_DATABASE_URL`: URL de la base de datos para pruebas
- `AUTH0_DOMAIN`: Dominio de Auth0
- `AUTH0_API_AUDIENCE`: Audiencia de API en Auth0
- `AUTH0_CLIENT_ID`: ID de cliente de Auth0
- `AUTH0_CLIENT_SECRET`: Secreto de cliente de Auth0
- `TEST_AUTH_TOKEN`: Token de autenticación para pruebas (opcional)

## Pruebas Funcionales con Token Real

Las pruebas funcionales utilizan un token de autenticación real para validar los endpoints de la API sin preocuparse por el flujo de autenticación.

### Prerequisitos

- Python 3.7+
- Requests: `pip install requests`
- Un token de autenticación válido de Auth0

### Obtener un Token de Autenticación

Para obtener un token de autenticación:

1. Inicia sesión en la aplicación web
2. Abre las herramientas de desarrollador (F12 en la mayoría de navegadores)
3. Ve a la pestaña "Network" (Red)
4. Busca cualquier solicitud a la API
5. Busca el encabezado "Authorization" en la solicitud
6. Copia el token (empieza con "Bearer ")

## Tests Disponibles

### 1. Test General de Todos los Endpoints

```bash
# Ejecutar todas las pruebas con un token
python tests/functional_test.py --token "eyJhbGciOiJSU..."

# Especificar un archivo de salida personalizado
python tests/functional_test.py --token "eyJhbGciOiJSU..." --output resultados.json
```

### 2. Test Específico de Eventos (CRUD Completo)

Este test realiza un ciclo completo de operaciones sobre eventos:
- Listar eventos existentes
- Crear un nuevo evento
- Obtener detalles del evento
- Actualizar el evento
- Listar participantes
- Eliminar el evento

```bash
# Ejecutar el test de eventos
python tests/event_test.py --token "eyJhbGciOiJSU..."
```

El test muestra información detallada sobre cada paso y garantiza la limpieza de recursos incluso si hay errores durante la ejecución.

### Interpretación de Resultados

Después de ejecutar las pruebas, se mostrará un resumen en la consola:

- ✅ indica una operación exitosa (código 2XX)
- ❌ indica una operación fallida (cualquier otro código)

El test general también guarda un archivo JSON con los resultados detallados, incluyendo:
- Timestamp de la ejecución
- Resumen de pruebas exitosas y fallidas
- Detalles de cada solicitud y respuesta

## Extender las Pruebas

Para añadir nuevas pruebas:

1. Para pruebas generales: añade una nueva función `test_*` en `functional_test.py`
2. Para módulos específicos: crea un nuevo archivo como `module_test.py` siguiendo el patrón de `event_test.py`

Ejemplo de función de prueba:

```python
def test_my_feature(tester: APITester) -> None:
    """Prueba mi nueva funcionalidad."""
    print("\n🧪 Probando mi funcionalidad")
    
    # Listar elementos
    response = tester.get("my-feature")
    
    # Crear nuevo elemento
    tester.post("my-feature", json={"name": "Test"})
```

### Configuración de pruebas de relaciones entrenador-miembro

Para ejecutar las pruebas de relaciones entrenador-miembro, necesitas configurar las siguientes variables de entorno en un archivo `.env` en la raíz del proyecto:

```
TEST_AUTH_TOKEN=tu_token_auth0_valido
TEST_GYM_ID=1
TEST_TRAINER_ID=6
TEST_MEMBER_ID=7
```

Estas variables permiten personalizar los IDs utilizados en las pruebas para adaptarse a tu entorno específico.

### Configuración de pruebas del sistema de chat

Para ejecutar las pruebas del sistema de chat, debes crear un archivo `.env.test` en la raíz del proyecto con las siguientes variables:

```
TEST_AUTH_TOKEN=tu_token_auth0_valido
TEST_GYM_ID=1
TEST_USER_ID=1
TEST_TARGET_USER_ID=2
TEST_EVENT_ID=1
```

**Importante**: Para evitar conflictos con la configuración principal, estas variables deben estar en un archivo `.env.test` separado, no en el `.env` principal. 