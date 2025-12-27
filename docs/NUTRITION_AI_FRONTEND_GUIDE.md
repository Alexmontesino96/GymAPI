# 🤖 GUÍA DE INTEGRACIÓN - IA NUTRICIONAL PARA FRONTEND

## 📋 RESUMEN RÁPIDO

La API de nutrición con IA permite generar automáticamente ingredientes y recetas detalladas para cualquier comida usando GPT-4o-mini. Esta guía explica cómo integrarlo en el frontend.

---

## 1️⃣ ENDPOINT PRINCIPAL DE IA

### 🎯 **Generar Ingredientes con IA**

```http
POST /api/v1/nutrition/meals/{meal_id}/generate-ingredients
```

**Headers requeridos:**
```http
Authorization: Bearer {token}
Content-Type: application/json
X-Gym-ID: 4
```

**Request Body:**
```json
{
  "dietary_restrictions": [
    "vegetarian",      // Opciones: vegetarian, vegan, gluten_free, dairy_free, nut_free
    "gluten_free"      // keto, paleo, low_carb, high_protein, halal, kosher
  ],
  "preferences": [
    "high_protein",    // Preferencias adicionales del usuario
    "low_sugar"
  ],
  "servings": 1,       // Número de porciones (default: 1)
  "language": "es"     // Idioma de respuesta: es, en, pt (default: es)
}
```

### ✅ **Response Exitosa (200 OK):**

```json
{
  "status": "success",
  "message": "Ingredientes generados exitosamente con IA",
  "data": {
    "meal_id": 123,
    "ingredients": [
      {
        "id": 456,
        "name": "Pechuga de pollo",
        "quantity": 150,
        "unit": "gr",
        "calories_per_unit": 1.65,        // Calorías por gramo
        "protein_g_per_unit": 0.31,       // Proteína por gramo
        "carbs_g_per_unit": 0.0,          // Carbohidratos por gramo
        "fat_g_per_unit": 0.036,          // Grasa por gramo
        "fiber_g_per_unit": 0.0,          // Fibra por gramo
        "notes": "Sin piel, a la plancha",
        "order": 1
      },
      {
        "id": 457,
        "name": "Arroz integral",
        "quantity": 80,
        "unit": "gr",
        "calories_per_unit": 1.11,
        "protein_g_per_unit": 0.025,
        "carbs_g_per_unit": 0.23,
        "fat_g_per_unit": 0.009,
        "fiber_g_per_unit": 0.018,
        "notes": "Cocido",
        "order": 2
      },
      {
        "id": 458,
        "name": "Brócoli",
        "quantity": 200,
        "unit": "gr",
        "calories_per_unit": 0.34,
        "protein_g_per_unit": 0.028,
        "carbs_g_per_unit": 0.066,
        "fat_g_per_unit": 0.004,
        "fiber_g_per_unit": 0.026,
        "notes": "Al vapor",
        "order": 3
      }
    ],
    "recipe_instructions": "1. Cocinar el arroz integral en agua hirviendo durante 20 minutos.\n2. Mientras tanto, sazonar la pechuga de pollo con sal, pimienta y hierbas.\n3. Cocinar el pollo a la plancha 6-7 minutos por lado.\n4. Cocinar el brócoli al vapor durante 5 minutos.\n5. Servir todo junto y disfrutar.",
    "total_nutrition": {
      "calories": 455.5,
      "protein_g": 52.9,
      "carbs_g": 31.6,
      "fat_g": 6.5,
      "fiber_g": 6.64
    },
    "estimated_prep_time": 25,
    "difficulty_level": "beginner",    // beginner, intermediate, advanced
    "ai_confidence_score": 0.95,       // 0-1, qué tan segura está la IA
    "generated_at": "2024-12-26T18:30:00Z"
  }
}
```

---

## 2️⃣ OTROS ENDPOINTS RELACIONADOS

### 📝 **Obtener Comida con Ingredientes**

```http
GET /api/v1/nutrition/meals/{meal_id}
```

**Response:**
```json
{
  "id": 123,
  "name": "Almuerzo Power",
  "meal_type": "lunch",
  "description": "Almuerzo alto en proteína para ganancia muscular",
  "target_calories": 450,
  "target_protein_g": 50,
  "target_carbs_g": 30,
  "target_fat_g": 7,
  "ingredients": [...],  // Array vacío si no tiene ingredientes
  "has_ingredients": false,
  "can_generate_with_ai": true
}
```

### ➕ **Agregar Ingredientes Manualmente**

```http
POST /api/v1/nutrition/meals/{meal_id}/ingredients
```

**Request:**
```json
{
  "name": "Aceite de oliva",
  "quantity": 10,
  "unit": "ml",
  "calories_per_unit": 8.84,
  "protein_g_per_unit": 0,
  "carbs_g_per_unit": 0,
  "fat_g_per_unit": 1,
  "fiber_g_per_unit": 0,
  "notes": "Extra virgen"
}
```

### 🗑️ **Eliminar Todos los Ingredientes**

```http
DELETE /api/v1/nutrition/meals/{meal_id}/ingredients
```

---

## 3️⃣ MANEJO DE ERRORES

### ❌ **Error 400 - Bad Request**

```json
{
  "detail": "La comida ya tiene ingredientes. Elimínalos primero antes de generar nuevos."
}
```

**Causas comunes:**
- La comida ya tiene ingredientes (debe eliminarlos primero)
- Parámetros inválidos en el request

### ❌ **Error 404 - Not Found**

```json
{
  "detail": "Meal not found"
}
```

### ❌ **Error 429 - Rate Limit**

```json
{
  "detail": "Límite de solicitudes de IA excedido. Intenta en unos minutos."
}
```

**Recomendación:** Implementar retry con exponential backoff

### ❌ **Error 500 - Error de IA**

```json
{
  "detail": "Error generando ingredientes con IA: {mensaje específico}"
}
```

**Posibles mensajes:**
- "OpenAI API key no configurada" → Contactar admin
- "Timeout al generar respuesta" → Reintentar
- "Respuesta inválida de IA" → Reintentar o usar modo manual

### ❌ **Error 503 - Servicio No Disponible**

```json
{
  "detail": "El servicio de IA no está disponible temporalmente"
}
```

---

## 4️⃣ FLUJO COMPLETO DE INTEGRACIÓN

### **Flujo Recomendado en el Frontend:**

```javascript
// 1. Verificar si la comida tiene ingredientes
const meal = await getMeal(mealId);

if (meal.has_ingredients) {
  // Preguntar al usuario si quiere reemplazarlos
  const confirm = await showConfirmDialog(
    "Esta comida ya tiene ingredientes. ¿Deseas reemplazarlos con IA?"
  );

  if (confirm) {
    // Eliminar ingredientes existentes
    await deleteIngredients(mealId);
  } else {
    return; // Cancelar
  }
}

// 2. Mostrar opciones de personalización
const options = await showAIOptionsDialog({
  dietary_restrictions: [],
  preferences: [],
  servings: 1,
  language: getUserLanguage()
});

// 3. Generar con IA (con loading state)
setLoading(true);
try {
  const result = await generateIngredientsWithAI(mealId, options);

  // 4. Mostrar resultados
  displayIngredients(result.data.ingredients);
  displayRecipe(result.data.recipe_instructions);
  displayNutrition(result.data.total_nutrition);

  // 5. Opción de regenerar si no le gusta
  if (await showRegenerateOption()) {
    // Eliminar y volver a generar
    await deleteIngredients(mealId);
    // Repetir paso 3
  }

} catch (error) {
  handleAIError(error);
} finally {
  setLoading(false);
}
```

### **Función de Manejo de Errores:**

```javascript
function handleAIError(error) {
  switch(error.status) {
    case 400:
      // Comida ya tiene ingredientes
      showToast("Elimina los ingredientes actuales primero", "warning");
      break;

    case 429:
      // Rate limit
      showToast("Demasiadas solicitudes. Intenta en unos minutos", "warning");
      // Implementar retry automático después de 60 segundos
      setTimeout(() => retryGeneration(), 60000);
      break;

    case 500:
      // Error de IA
      if (error.message.includes("API key")) {
        showToast("IA no configurada. Contacta al administrador", "error");
      } else {
        showToast("Error generando ingredientes. Intenta nuevamente", "error");
        showManualOption(); // Ofrecer agregar ingredientes manualmente
      }
      break;

    case 503:
      // Servicio no disponible
      showToast("Servicio temporalmente no disponible", "warning");
      showManualOption();
      break;

    default:
      showToast("Error inesperado. Intenta nuevamente", "error");
  }
}
```

---

## 5️⃣ COMPONENTE REACT EJEMPLO

```jsx
import { useState } from 'react';
import { generateIngredientsWithAI } from '../api/nutrition';

function AIIngredientGenerator({ mealId, mealName, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState({
    dietary_restrictions: [],
    preferences: [],
    servings: 1,
    language: 'es'
  });

  const dietaryOptions = [
    { value: 'vegetarian', label: '🥬 Vegetariano' },
    { value: 'vegan', label: '🌱 Vegano' },
    { value: 'gluten_free', label: '🌾 Sin Gluten' },
    { value: 'dairy_free', label: '🥛 Sin Lácteos' },
    { value: 'keto', label: '🥑 Keto' },
    { value: 'paleo', label: '🦴 Paleo' },
    { value: 'high_protein', label: '💪 Alta Proteína' },
    { value: 'low_carb', label: '🍞 Bajo en Carbos' }
  ];

  const handleGenerate = async () => {
    setLoading(true);

    try {
      const response = await generateIngredientsWithAI(mealId, options);

      // Mostrar preview de ingredientes
      const confirmed = await showIngredientsPreview(response.data);

      if (confirmed) {
        onSuccess(response.data);
        showToast('✅ Ingredientes generados con éxito', 'success');
      }
    } catch (error) {
      handleAIError(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-generator-card">
      <h3>🤖 Generar Ingredientes con IA</h3>
      <p>Para: {mealName}</p>

      <div className="options-section">
        <h4>Restricciones Dietéticas</h4>
        <div className="checkbox-group">
          {dietaryOptions.map(option => (
            <label key={option.value}>
              <input
                type="checkbox"
                value={option.value}
                checked={options.dietary_restrictions.includes(option.value)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setOptions({
                      ...options,
                      dietary_restrictions: [...options.dietary_restrictions, option.value]
                    });
                  } else {
                    setOptions({
                      ...options,
                      dietary_restrictions: options.dietary_restrictions.filter(
                        r => r !== option.value
                      )
                    });
                  }
                }}
              />
              {option.label}
            </label>
          ))}
        </div>
      </div>

      <div className="servings-section">
        <label>
          Porciones:
          <input
            type="number"
            min="1"
            max="10"
            value={options.servings}
            onChange={(e) => setOptions({...options, servings: e.target.value})}
          />
        </label>
      </div>

      <button
        onClick={handleGenerate}
        disabled={loading}
        className="generate-btn"
      >
        {loading ? (
          <>
            <Spinner /> Generando con IA...
          </>
        ) : (
          <>
            ✨ Generar Ingredientes
          </>
        )}
      </button>

      {loading && (
        <div className="loading-tips">
          <p>💡 Esto puede tomar 10-15 segundos...</p>
          <p>📊 La IA está calculando valores nutricionales precisos</p>
        </div>
      )}
    </div>
  );
}
```

---

## 6️⃣ TIPS Y MEJORES PRÁCTICAS

### ✅ **DO's (Hacer):**

1. **Validar antes de generar:**
   ```javascript
   // Siempre verificar si ya tiene ingredientes
   if (meal.has_ingredients) {
     // Pedir confirmación para reemplazar
   }
   ```

2. **Mostrar loading state detallado:**
   ```javascript
   // Dar feedback mientras genera
   setLoadingMessage("Analizando requerimientos nutricionales...");
   // Cambiar mensaje después de 3 segundos
   setTimeout(() => {
     setLoadingMessage("Generando receta personalizada...");
   }, 3000);
   ```

3. **Cachear respuestas localmente:**
   ```javascript
   // Guardar en localStorage para reusar
   localStorage.setItem(`ai_meal_${mealId}`, JSON.stringify(response));
   ```

4. **Implementar retry con backoff:**
   ```javascript
   async function generateWithRetry(mealId, options, retries = 3) {
     for (let i = 0; i < retries; i++) {
       try {
         return await generateIngredientsWithAI(mealId, options);
       } catch (error) {
         if (error.status === 429 && i < retries - 1) {
           await sleep(Math.pow(2, i) * 1000); // 1s, 2s, 4s
           continue;
         }
         throw error;
       }
     }
   }
   ```

### ❌ **DON'Ts (No hacer):**

1. **No generar sin confirmar:**
   ```javascript
   // MAL - genera directamente
   generateIngredientsWithAI(mealId);

   // BIEN - confirma primero
   if (await confirmGeneration()) {
     generateIngredientsWithAI(mealId);
   }
   ```

2. **No ignorar errores de rate limit:**
   ```javascript
   // MAL - reintentar inmediatamente
   while (true) {
     try {
       await generate();
       break;
     } catch {}
   }

   // BIEN - esperar entre reintentos
   await sleep(60000); // Esperar 1 minuto
   ```

3. **No generar múltiples veces seguidas:**
   ```javascript
   // Deshabilitar botón después de generar
   setGenerateButtonDisabled(true);
   setTimeout(() => setGenerateButtonDisabled(false), 5000);
   ```

---

## 7️⃣ INFORMACIÓN TÉCNICA

### **Modelo de IA:**
- **Modelo:** GPT-4o-mini (OpenAI)
- **Temperature:** 0.1 (respuestas precisas y consistentes)
- **Max tokens:** 1,500
- **Timeout:** 30 segundos

### **Límites:**
- **Por usuario:** 10 generaciones/día
- **Por gimnasio:** 500 generaciones/día
- **Global:** Monitoreo de costos mensual

### **Validaciones de la IA:**
- Calorías máximas por unidad: 9 kcal/g
- Proteína máxima por unidad: 1 g/g
- Coherencia de macronutrientes (P*4 + C*4 + F*9 ≈ calorías)
- Unidades válidas: gr, ml, cups, tbsp, tsp, oz, kg, l

### **Idiomas soportados:**
- `es` - Español (default)
- `en` - Inglés
- `pt` - Portugués

---

## 8️⃣ CASOS DE USO ESPECIALES

### **Comidas Vegetarianas/Veganas:**
```json
{
  "dietary_restrictions": ["vegan"],
  "preferences": ["high_protein"],
  "language": "es"
}
// La IA generará alternativas como tofu, tempeh, legumbres
```

### **Dieta Keto:**
```json
{
  "dietary_restrictions": ["keto"],
  "preferences": ["high_fat"],
  "language": "es"
}
// La IA limitará carbohidratos a <5% del total calórico
```

### **Multiple Restricciones:**
```json
{
  "dietary_restrictions": ["gluten_free", "dairy_free", "nut_free"],
  "preferences": ["high_protein"],
  "language": "es"
}
// La IA buscará opciones que cumplan TODAS las restricciones
```

---

## 9️⃣ TROUBLESHOOTING

| Problema | Causa | Solución |
|----------|-------|----------|
| "OpenAI API key no configurada" | Backend sin API key | Admin debe configurar `OPENAI_API_KEY` en .env |
| "La comida ya tiene ingredientes" | Ingredientes existentes | Eliminar con DELETE antes de generar |
| Timeout frecuente | Servidor sobrecargado | Implementar retry o usar horario de menor carga |
| Valores nutricionales incorrectos | Error de IA | Regenerar o ajustar manualmente |
| "Rate limit exceeded" | Muchas solicitudes | Esperar 1 minuto o implementar queue |

---

## 📞 SOPORTE

Para problemas técnicos o preguntas:
- **Endpoint de health check:** `GET /api/v1/health`
- **Logs:** Revisar console.log para detalles de errores
- **Contacto Backend:** Revisar si `OPENAI_API_KEY` está configurada

---

*Última actualización: 26 de Diciembre 2024*
*API Version: 1.0*
*Modelo IA: GPT-4o-mini*