# Guía Frontend: Verificación de Email Disponible

## ⚠️ CAMBIO IMPORTANTE

El endpoint `/api/v1/users/check-email-availability` **YA NO REQUIERE TOKEN DE AUTENTICACIÓN**.

Ahora usa un **API key estático** en el header para seguridad.

---

## 📋 Resumen del Cambio

| Antes | Ahora |
|-------|-------|
| ❌ Requería token Auth0 | ✅ Requiere API key en header |
| ❌ Solo usuarios autenticados | ✅ Endpoint público |
| Header: `Authorization: Bearer <token>` | Header: `X-API-Key: <sha256_hash>` |

---

## 🔑 Configuración

### 1. Agregar API Key a Variables de Entorno

**React (.env o .env.local):**
```bash
REACT_APP_PUBLIC_API_KEY=651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989
```

**Vue (.env):**
```bash
VUE_APP_PUBLIC_API_KEY=651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989
```

**Next.js (.env.local):**
```bash
NEXT_PUBLIC_API_KEY=651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989
```

**⚠️ IMPORTANTE:** El hash es el mismo en backend y frontend.

---

## 🚀 Cómo Usarlo

### Endpoint

```
POST /api/v1/users/check-email-availability
```

### Headers Requeridos

```javascript
{
  "Content-Type": "application/json",
  "X-API-Key": "651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989"
}
```

### Body

```json
{
  "email": "usuario@ejemplo.com"
}
```

---

## 📤 Respuestas del Endpoint

### ✅ Email Disponible (200 OK)

```json
{
  "status": "success",
  "message": "El email está disponible."
}
```

**Acción:** Permitir continuar con el registro.

---

### ❌ Email Ya Registrado (200 OK)

```json
{
  "status": "error",
  "message": "El email ya está en uso."
}
```

**Acción:** Mostrar error al usuario indicando que debe usar otro email.

---

### 🔒 API Key Faltante (401 Unauthorized)

```json
{
  "detail": "API key requerida. Incluir header X-API-Key"
}
```

**Causa:** No se envió el header `X-API-Key`.
**Solución:** Verificar que el header esté presente en la request.

---

### 🔒 API Key Inválida (401 Unauthorized)

```json
{
  "detail": "API key inválida"
}
```

**Causa:** El hash enviado no coincide con el del backend.
**Solución:** Verificar que el valor en `.env` sea exactamente:
```
651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989
```

---

### ⚡ Rate Limit Excedido (429 Too Many Requests)

```json
{
  "detail": "Rate limit exceeded"
}
```

**Causa:** Más de 10 solicitudes por minuto desde la misma IP.
**Solución:** Implementar debouncing en el frontend (ver ejemplo abajo).

---

### ❌ Email Inválido (422 Unprocessable Entity)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**Causa:** El formato del email es inválido.
**Solución:** Validar formato de email en el frontend antes de enviar.

---

### 🔥 Error Interno (500 Internal Server Error)

```json
{
  "detail": "Error interno"
}
```

**Causa:** Error en el servidor.
**Solución:** Reintentar después de unos segundos o contactar a backend.

---

## 💻 Ejemplos de Código

### Ejemplo 1: Fetch Básico

```javascript
const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

async function checkEmail(email) {
  const response = await fetch('https://api.tudominio.com/api/v1/users/check-email-availability', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY  // ← Nuevo header requerido
    },
    body: JSON.stringify({ email })
  });

  const data = await response.json();

  if (response.ok) {
    if (data.status === 'success') {
      console.log('✅ Email disponible');
      return true;
    } else {
      console.log('❌ Email ya registrado');
      return false;
    }
  } else {
    console.error('Error:', data.detail);
    throw new Error(data.detail);
  }
}

// Uso
checkEmail('nuevo@ejemplo.com')
  .then(disponible => {
    if (disponible) {
      // Permitir registro
    } else {
      // Mostrar error
    }
  })
  .catch(error => {
    // Manejar error
  });
```

---

### Ejemplo 2: Axios con Manejo de Errores

```javascript
import axios from 'axios';

const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

const api = axios.create({
  baseURL: 'https://api.tudominio.com/api/v1',
  headers: {
    'X-API-Key': API_KEY
  }
});

async function checkEmailAvailability(email) {
  try {
    const { data } = await api.post('/users/check-email-availability', { email });

    return {
      available: data.status === 'success',
      message: data.message
    };
  } catch (error) {
    if (error.response) {
      // Errores del servidor (4xx, 5xx)
      const status = error.response.status;
      const detail = error.response.data.detail;

      if (status === 401) {
        throw new Error('Error de configuración: API key inválida');
      } else if (status === 429) {
        throw new Error('Demasiadas solicitudes. Intenta en 1 minuto.');
      } else if (status === 422) {
        throw new Error('Email inválido');
      } else {
        throw new Error('Error al verificar email');
      }
    } else {
      // Error de red
      throw new Error('Error de conexión');
    }
  }
}

// Uso
checkEmailAvailability('test@ejemplo.com')
  .then(({ available, message }) => {
    if (available) {
      console.log('Email disponible');
    } else {
      console.log('Email en uso');
    }
  })
  .catch(error => {
    console.error(error.message);
  });
```

---

### Ejemplo 3: React Hook con Debouncing

```javascript
import { useState, useCallback } from 'react';
import debounce from 'lodash.debounce';

const API_KEY = process.env.REACT_APP_PUBLIC_API_KEY;

export function useEmailCheck() {
  const [checking, setChecking] = useState(false);
  const [available, setAvailable] = useState(null);
  const [error, setError] = useState(null);

  const checkEmail = useCallback(
    debounce(async (email) => {
      // Reset estados
      setChecking(true);
      setError(null);
      setAvailable(null);

      // Validación básica
      if (!email || !email.includes('@')) {
        setChecking(false);
        return;
      }

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
          setAvailable(data.status === 'success');
        } else {
          if (response.status === 429) {
            setError('Demasiadas solicitudes. Espera un minuto.');
          } else if (response.status === 401) {
            setError('Error de configuración del sistema');
          } else {
            setError('Error al verificar email');
          }
        }
      } catch (err) {
        setError('Error de conexión');
      } finally {
        setChecking(false);
      }
    }, 500), // Esperar 500ms después de que el usuario deje de escribir
    []
  );

  return { checkEmail, checking, available, error };
}

// Uso en componente
function RegistrationForm() {
  const [email, setEmail] = useState('');
  const { checkEmail, checking, available, error } = useEmailCheck();

  const handleEmailChange = (e) => {
    const newEmail = e.target.value;
    setEmail(newEmail);
    checkEmail(newEmail); // Verifica automáticamente con debounce
  };

  return (
    <div>
      <input
        type="email"
        value={email}
        onChange={handleEmailChange}
        placeholder="tu@email.com"
      />

      {checking && <span>Verificando...</span>}

      {available === true && (
        <span className="success">✓ Email disponible</span>
      )}

      {available === false && (
        <span className="error">✗ Email ya registrado</span>
      )}

      {error && <span className="error">{error}</span>}
    </div>
  );
}
```

---

### Ejemplo 4: Vue 3 Composable

```javascript
import { ref } from 'vue';

const API_KEY = import.meta.env.VUE_APP_PUBLIC_API_KEY;

export function useEmailCheck() {
  const checking = ref(false);
  const available = ref(null);
  const error = ref(null);

  const checkEmail = async (email) => {
    checking.value = true;
    error.value = null;
    available.value = null;

    if (!email || !email.includes('@')) {
      checking.value = false;
      return;
    }

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
        available.value = data.status === 'success';
      } else {
        if (response.status === 429) {
          error.value = 'Demasiadas solicitudes. Espera un minuto.';
        } else if (response.status === 401) {
          error.value = 'Error de configuración del sistema';
        } else {
          error.value = 'Error al verificar email';
        }
      }
    } catch (err) {
      error.value = 'Error de conexión';
    } finally {
      checking.value = false;
    }
  };

  return { checkEmail, checking, available, error };
}
```

---

## ✅ Checklist de Implementación

- [ ] Agregar `REACT_APP_PUBLIC_API_KEY` (o equivalente) a `.env`
- [ ] Verificar que el valor sea exactamente: `651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989`
- [ ] Actualizar código para usar header `X-API-Key` en lugar de `Authorization`
- [ ] Remover dependencia de token Auth0 para este endpoint
- [ ] Implementar debouncing para evitar rate limiting (500ms recomendado)
- [ ] Manejar todos los códigos de error (401, 422, 429, 500)
- [ ] Validar formato de email en frontend antes de enviar
- [ ] Probar en dev con emails existentes y nuevos
- [ ] Verificar que funcione sin estar logueado

---

## 🐛 Troubleshooting

### Error: "API key inválida"

**Solución:**
1. Verificar `.env`: `REACT_APP_PUBLIC_API_KEY=651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989`
2. Reiniciar el servidor de desarrollo (`npm start` o `yarn dev`)
3. Verificar que no hay espacios extra en el valor

### Error: "API key requerida"

**Solución:**
1. Verificar que el header se está enviando: `'X-API-Key': process.env.REACT_APP_PUBLIC_API_KEY`
2. Verificar que la variable de entorno está definida: `console.log(process.env.REACT_APP_PUBLIC_API_KEY)`

### Error 429 constante

**Solución:**
1. Implementar debouncing (esperar 500ms después de que el usuario deje de escribir)
2. No verificar en cada tecla presionada
3. Considerar verificar solo cuando el input pierde foco (`onBlur`)

---

## 📞 Contacto

Si tienes dudas sobre la implementación, contacta al equipo de backend.

**API Key actual:** `651d21af5715e6c47e115e3e4c7bef57b3c3b334030ad42ab1c02c4aaca59989`

---

## 📚 Documentación Completa

Para ejemplos más avanzados y casos de uso adicionales, consulta:
- `docs/PUBLIC_API_KEY_USAGE.md` - Documentación técnica completa
