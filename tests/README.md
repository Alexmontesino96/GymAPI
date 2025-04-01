# GymAPI - Pruebas Funcionales

Este directorio contiene pruebas para verificar el funcionamiento de GymAPI.

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