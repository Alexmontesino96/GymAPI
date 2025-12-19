# Uso de Public API Key para Endpoints Públicos

## Descripción

Algunos endpoints públicos (que no requieren autenticación de usuario) están protegidos con un API key SHA256 para prevenir abuso y spam.

## Configuración

### Backend (.env)

Generar un hash SHA256 de una clave secreta:

```bash
echo -n "tu_clave_secreta_aqui" | shasum -a 256
```

Agregar al archivo `.env`:

```bash
PUBLIC_API_KEY=el_hash_sha256_generado
```

**Ejemplo:**
```bash
# Si tu clave secreta es "mySecretKey2024"
echo -n "mySecretKey2024" | shasum -a 256
# Output: a1b2c3d4e5f6...

PUBLIC_API_KEY=a1b2c3d4e5f6...
```

### Frontend (Variables de Entorno)

El frontend debe tener la **misma clave SHA256** en una variable de entorno:

**React (.env):**
```bash
REACT_APP_PUBLIC_API_KEY=a1b2c3d4e5f6...
```

**Vue (.env):**
```bash
VUE_APP_PUBLIC_API_KEY=a1b2c3d4e5f6...
```

**Next.js (.env.local):**
```bash
NEXT_PUBLIC_API_KEY=a1b2c3d4e5f6...
```

## Endpoints Protegidos

### 1. Verificar Disponibilidad de Email

**Endpoint:** `POST /api/v1/users/check-email-availability`

**Descripción:** Verifica si un email está disponible para registro.

**Headers Requeridos:**
```json
{
  "X-API-Key": "tu_sha256_hash_aqui",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response Exitosa (200):**
```json
{
  "status": "success",
  "message": "El email está disponible."
}
```

**Response Email en Uso (200):**
```json
{
  "status": "error",
  "message": "El email ya está en uso."
}
```

**Response API Key Faltante (401):**
```json
{
  "detail": "API key requerida. Incluir header X-API-Key"
}
```

**Response API Key Inválida (401):**
```json
{
  "detail": "API key inválida"
}
```

## Ejemplos de Código

### JavaScript (Fetch)

```javascript
const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

async function checkEmailAvailability(email) {
  try {
    const response = await fetch('https://api.tu-dominio.com/api/v1/users/check-email-availability', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
      },
      body: JSON.stringify({ email })
    });

    const data = await response.json();

    if (data.status === 'success') {
      console.log('Email disponible');
      return true;
    } else {
      console.log('Email ya en uso');
      return false;
    }
  } catch (error) {
    console.error('Error verificando email:', error);
    throw error;
  }
}

// Uso
checkEmailAvailability('user@example.com')
  .then(available => {
    if (available) {
      // Continuar con el registro
    } else {
      // Mostrar error al usuario
    }
  });
```

### Axios

```javascript
import axios from 'axios';

const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

const api = axios.create({
  baseURL: 'https://api.tu-dominio.com/api/v1',
  headers: {
    'X-API-Key': API_KEY
  }
});

async function checkEmailAvailability(email) {
  try {
    const response = await api.post('/users/check-email-availability', { email });
    return response.data.status === 'success';
  } catch (error) {
    if (error.response?.status === 401) {
      console.error('API Key inválida o faltante');
    }
    throw error;
  }
}
```

### React Hook

```javascript
import { useState } from 'react';

const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

export function useEmailAvailability() {
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);

  const checkEmail = async (email) => {
    setChecking(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/users/check-email-availability', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY
        },
        body: JSON.stringify({ email })
      });

      const data = await response.json();

      if (response.ok) {
        return data.status === 'success';
      } else {
        setError(data.detail || 'Error verificando email');
        return false;
      }
    } catch (err) {
      setError('Error de conexión');
      return false;
    } finally {
      setChecking(false);
    }
  };

  return { checkEmail, checking, error };
}

// Uso en componente
function RegistrationForm() {
  const { checkEmail, checking, error } = useEmailAvailability();

  const handleEmailChange = async (email) => {
    const available = await checkEmail(email);
    if (!available) {
      // Mostrar error: email ya existe
    }
  };

  return (
    <form>
      <input
        type="email"
        onBlur={(e) => handleEmailChange(e.target.value)}
      />
      {checking && <span>Verificando...</span>}
      {error && <span className="error">{error}</span>}
    </form>
  );
}
```

### Vue 3 (Composition API)

```javascript
import { ref } from 'vue';

const API_KEY = import.meta.env.VUE_APP_PUBLIC_API_KEY;

export function useEmailAvailability() {
  const checking = ref(false);
  const error = ref(null);

  const checkEmail = async (email) => {
    checking.value = true;
    error.value = null;

    try {
      const response = await fetch('/api/v1/users/check-email-availability', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY
        },
        body: JSON.stringify({ email })
      });

      const data = await response.json();

      if (response.ok) {
        return data.status === 'success';
      } else {
        error.value = data.detail || 'Error verificando email';
        return false;
      }
    } catch (err) {
      error.value = 'Error de conexión';
      return false;
    } finally {
      checking.value = false;
    }
  };

  return { checkEmail, checking, error };
}
```

## Seguridad

### ¿Por qué SHA256?

- **No es reversible:** No se puede obtener la clave original del hash
- **Frontend seguro:** El hash se puede exponer en el código del frontend sin riesgo
- **Rate limiting:** Se combina con límites de tasa (10 req/min)
- **Previene spam:** Solo aplicaciones con el hash correcto pueden usar el endpoint

### Rotación de Claves

Para cambiar la API key:

1. Generar un nuevo hash SHA256
2. Actualizar `PUBLIC_API_KEY` en el backend
3. Actualizar la variable de entorno en todos los frontends
4. Desplegar ambos simultáneamente

### Rate Limiting

El endpoint tiene los siguientes límites:

- **10 solicitudes por minuto por IP**
- Respuesta 429 si se excede el límite

## Troubleshooting

### Error: "API key requerida. Incluir header X-API-Key"

- Verificar que el header `X-API-Key` está incluido en la solicitud
- Verificar el nombre del header (case-sensitive en algunos servidores)

### Error: "API key inválida"

- Verificar que el hash en el frontend coincide exactamente con el del backend
- Verificar que no hay espacios extra en la variable de entorno
- Generar el hash nuevamente y comparar

### Error: "PUBLIC_API_KEY no configurada en el servidor"

- El backend no tiene la variable `PUBLIC_API_KEY` en `.env`
- Reiniciar el servidor después de agregar la variable

### Error 429: "Rate limit exceeded"

- Se excedió el límite de 10 solicitudes por minuto
- Implementar debouncing en el frontend
- Esperar 60 segundos antes de reintentar

## Ejemplo Completo de Validación en Formulario

```javascript
import { useState, useEffect } from 'react';
import debounce from 'lodash.debounce';

const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

function EmailInput({ value, onChange, onAvailabilityCheck }) {
  const [status, setStatus] = useState(null); // 'checking' | 'available' | 'taken' | 'error'
  const [message, setMessage] = useState('');

  // Debounce para no verificar en cada tecla
  const checkEmailDebounced = useCallback(
    debounce(async (email) => {
      if (!email || !email.includes('@')) {
        setStatus(null);
        return;
      }

      setStatus('checking');
      setMessage('Verificando...');

      try {
        const response = await fetch('/api/v1/users/check-email-availability', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
          },
          body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (response.ok) {
          if (data.status === 'success') {
            setStatus('available');
            setMessage('✓ Email disponible');
            onAvailabilityCheck(true);
          } else {
            setStatus('taken');
            setMessage('✗ Email ya registrado');
            onAvailabilityCheck(false);
          }
        } else {
          setStatus('error');
          setMessage('Error al verificar');
          onAvailabilityCheck(false);
        }
      } catch (error) {
        setStatus('error');
        setMessage('Error de conexión');
        onAvailabilityCheck(false);
      }
    }, 500), // Esperar 500ms después de que el usuario deja de escribir
    []
  );

  useEffect(() => {
    checkEmailDebounced(value);
  }, [value, checkEmailDebounced]);

  return (
    <div className="email-input-wrapper">
      <input
        type="email"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="email@ejemplo.com"
        className={status === 'taken' ? 'error' : ''}
      />
      {status && (
        <span className={`status-message ${status}`}>
          {message}
        </span>
      )}
    </div>
  );
}
```

## Notas Adicionales

- El endpoint no requiere autenticación de usuario (es público)
- La verificación se realiza contra la base de datos local **y** Auth0
- El email se normaliza a minúsculas para la comparación
- El resultado se cachea en Redis por 5 minutos para optimizar performance
- Implementar debouncing en el frontend para evitar solicitudes excesivas
