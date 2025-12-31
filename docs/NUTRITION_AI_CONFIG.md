# 🤖 Configuración del Sistema de IA para Nutrición

## 📋 Variables de Entorno Requeridas

### OpenAI API Key
```env
# IMPORTANTE: Usar CHAT_GPT_MODEL como nombre de la variable
CHAT_GPT_MODEL=sk-...  # Tu API key de OpenAI

# Modelo a utilizar (opcional, default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# Otros parámetros opcionales
OPENAI_MAX_TOKENS=3500
OPENAI_TEMPERATURE=0.7
```

## 🔧 Configuración en el Código

### Servicio de IA (`app/services/nutrition_ai_service.py`)
```python
class NutritionAIService:
    def __init__(self):
        # La API key se obtiene de la variable CHAT_GPT_MODEL
        self.api_key = os.getenv("CHAT_GPT_MODEL")

        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            logger.warning("OpenAI API key not configured (CHAT_GPT_MODEL)")
            # Sistema usa generación mock si no hay API key
```

### Config Principal (`app/core/config.py`)
```python
class Settings(BaseSettings):
    # Internamente se mapea a OPENAI_API_KEY pero usa CHAT_GPT_MODEL como fuente
    OPENAI_API_KEY: str = os.getenv("CHAT_GPT_MODEL", "")
```

## 🚀 Verificación de Configuración

### 1. Verificar Variable de Entorno
```bash
# En terminal
echo $CHAT_GPT_MODEL

# Debe mostrar algo como: sk-proj-...
```

### 2. Verificar en Python
```python
import os
api_key = os.getenv("CHAT_GPT_MODEL")
if api_key and api_key.startswith("sk-"):
    print("✅ API Key configurada correctamente")
else:
    print("❌ API Key no configurada o inválida")
```

### 3. Test del Servicio
```bash
# Ejecutar test de generación
python test_nutrition_ai_generation.py
```

## 📊 Costos y Límites

### Modelo GPT-4o-mini
- **Input**: $0.15 / 1M tokens
- **Output**: $0.60 / 1M tokens
- **Costo promedio por plan**: ~$0.002 USD

### Estimación Mensual
Para un gimnasio activo:
- 100 planes generados/mes: ~$0.20 USD
- 500 planes generados/mes: ~$1.00 USD
- 1000 planes generados/mes: ~$2.00 USD

## 🔒 Seguridad

### Mejores Prácticas
1. **NUNCA** commitear la API key en el código
2. **SIEMPRE** usar variables de entorno
3. **ROTAR** la key periódicamente
4. **LIMITAR** el uso con rate limiting
5. **MONITOREAR** costos en dashboard de OpenAI

### Ejemplo de .env.example
```env
# OpenAI Configuration
CHAT_GPT_MODEL=sk-...  # Reemplazar con tu API key real
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=3500
OPENAI_TEMPERATURE=0.7
```

## 🐛 Troubleshooting

### Error: "OpenAI API key not configured"
**Causa**: La variable `CHAT_GPT_MODEL` no está configurada
**Solución**:
```bash
export CHAT_GPT_MODEL="sk-tu-api-key-aqui"
```

### Error: "Invalid API key"
**Causa**: La API key es incorrecta o expirada
**Solución**:
1. Verificar en https://platform.openai.com/api-keys
2. Generar nueva key si es necesario
3. Actualizar variable CHAT_GPT_MODEL

### Sistema usa Mock en lugar de OpenAI
**Causa**: API key no configurada, sistema cae a modo mock
**Verificar**:
```python
# En logs debe aparecer:
# WARNING: OpenAI API key not configured (CHAT_GPT_MODEL)
# WARNING: Using mock generation - OpenAI not configured
```

## 📈 Monitoreo

### Dashboard de OpenAI
- URL: https://platform.openai.com/usage
- Verificar consumo diario
- Configurar alertas de límites

### Logs del Sistema
```python
# El servicio registra cada generación:
logger.info(f"Plan nutricional generado: ID {plan_id}, costo ${cost}")
```

### Métricas en Base de Datos
- Cada generación se registra con metadata
- Incluye tokens usados y costo estimado
- Permite análisis de uso por gimnasio

## ✅ Checklist de Configuración

- [ ] Variable `CHAT_GPT_MODEL` configurada en `.env`
- [ ] API key empieza con `sk-`
- [ ] Test de generación funciona
- [ ] Límites de rate configurados
- [ ] Monitoreo de costos activo
- [ ] Logs configurados correctamente
- [ ] Fallback a mock funciona sin API key

---

**Última actualización**: Diciembre 2024
**Versión**: 1.0.0