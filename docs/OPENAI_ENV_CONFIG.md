# 🔧 Configuración de OpenAI para Nutrición con IA

## 📌 Variable de Entorno Requerida

### ⚠️ IMPORTANTE: Cambio de Variable

La variable de entorno para la API key de OpenAI es:

```bash
CHAT_GPT_MODEL=sk-proj-xxxxxxxxxxxxx
```

**NO usar** `OPENAI_API_KEY` ❌

## 📝 Archivo .env

```bash
# OpenAI Configuration
CHAT_GPT_MODEL=sk-proj-tu-api-key-aqui  # ⭐ API Key de OpenAI
OPENAI_MODEL=gpt-4o-mini                # Modelo a usar (opcional, default: gpt-4o-mini)
OPENAI_MAX_TOKENS=1500                  # Tokens máximos (opcional, default: 1500)
OPENAI_TEMPERATURE=0.1                  # Temperatura (opcional, default: 0.1)
```

## 🚀 Verificación

### 1. Verificar que la variable esté configurada:

```bash
# En terminal
echo $CHAT_GPT_MODEL

# Debería mostrar algo como:
sk-proj-xxxxxxxxxxxxx
```

### 2. Verificar en Python:

```python
import os
api_key = os.getenv("CHAT_GPT_MODEL")
if api_key:
    print("✅ CHAT_GPT_MODEL configurada correctamente")
else:
    print("❌ CHAT_GPT_MODEL no está configurada")
```

### 3. Verificar en el código:

El archivo `app/core/config.py` ahora usa:
```python
OPENAI_API_KEY: str = os.getenv("CHAT_GPT_MODEL", "")
```

## 🔍 Troubleshooting

### Error: "OPENAI_API_KEY no configurada"
**Solución**: Asegúrate de que `CHAT_GPT_MODEL` esté en tu archivo `.env`

### Error: "OPENAI_API_KEY debe empezar con sk-"
**Solución**: Verifica que el valor de `CHAT_GPT_MODEL` empiece con `sk-`

### Error: "Invalid API key"
**Solución**: Verifica que la API key sea válida en https://platform.openai.com/api-keys

## 📋 Checklist de Configuración

- [ ] Variable `CHAT_GPT_MODEL` agregada al archivo `.env`
- [ ] El valor empieza con `sk-`
- [ ] La API key es válida y activa
- [ ] El servidor se reinició después de agregar la variable
- [ ] Los endpoints de IA nutricional responden correctamente

## 🧪 Test Rápido

```bash
# Test del endpoint de generación con IA
curl -X POST "http://localhost:8000/api/v1/nutrition/meals/1/ingredients/ai-generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: 4" \
  -d '{
    "recipe_name": "Test Recipe",
    "servings": 2
  }'

# Si funciona, deberías recibir una respuesta con ingredientes generados
```

## 📝 Notas

- La variable se llama `CHAT_GPT_MODEL` por razones históricas/legacy
- Internamente el código la mapea a `OPENAI_API_KEY`
- Todos los servicios de IA nutricional usan esta configuración

---

*Actualizado: Diciembre 2024*
*Variable correcta: CHAT_GPT_MODEL*