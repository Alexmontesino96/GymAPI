# 🚨 FIX URGENTE - Error 422 en AI Generate Ingredients

## ❌ ERROR ACTUAL
```
POST /api/v1/nutrition/meals/4/ingredients/ai-generate
Status: 422 Unprocessable Entity
Error: Field required: 'recipe_name'
```

## 🔴 PROBLEMA

El frontend está enviando un request INCORRECTO:
```json
{
  "dietary_restrictions": [],
  "preferences": [],        // ❌ Campo NO EXISTE
  "servings": 1,
  "language": "es"          // ❌ Campo NO EXISTE
}
```

**FALTA**: El campo `recipe_name` que es OBLIGATORIO

## ✅ SOLUCIÓN INMEDIATA

### Request CORRECTO:
```json
{
  "recipe_name": "Pasta con pollo",     // ⭐ OBLIGATORIO (min: 3, max: 200 caracteres)
  "servings": 4,                        // Opcional (default: 4, min: 1, max: 20)
  "dietary_restrictions": [],           // Opcional
  "cuisine_type": "italiana",           // Opcional (ej: española, italiana, mexicana)
  "target_calories": 500,               // Opcional (min: 100, max: 2000)
  "notes": "Sin picante, por favor"     // Opcional (max: 500 caracteres)
}
```

## 📋 Campos del Schema AIIngredientRequest

| Campo | Tipo | Requerido | Descripción | Validación |
|-------|------|-----------|-------------|------------|
| **recipe_name** | string | ✅ SÍ | Nombre de la receta | min: 3, max: 200 chars |
| servings | integer | No (default: 4) | Número de porciones | min: 1, max: 20 |
| dietary_restrictions | array | No | Restricciones dietéticas | Lista de enums |
| cuisine_type | string | No | Tipo de cocina | max: 50 chars |
| target_calories | integer | No | Calorías objetivo por porción | min: 100, max: 2000 |
| notes | string | No | Notas adicionales | max: 500 chars |

## 🔧 Código Frontend Corregido

### JavaScript/TypeScript
```javascript
// ❌ INCORRECTO (lo que están haciendo ahora)
const requestBody = {
  dietary_restrictions: [],
  preferences: [],      // ELIMINAR - no existe
  servings: 1,
  language: 'es'       // ELIMINAR - no existe
};

// ✅ CORRECTO
const requestBody = {
  recipe_name: "Nombre de la receta",  // OBLIGATORIO
  servings: 4,
  dietary_restrictions: [],
  cuisine_type: "mexicana",  // Opcional
  target_calories: 600,      // Opcional
  notes: "Preferencia por ingredientes locales"  // Opcional
};

// Llamada a la API
const response = await fetch('/api/v1/nutrition/meals/4/ingredients/ai-generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'X-Gym-Id': '4'
  },
  body: JSON.stringify(requestBody)
});
```

### React Component Example
```jsx
const AIIngredientGenerator = ({ mealId }) => {
  const [recipeName, setRecipeName] = useState('');
  const [servings, setServings] = useState(4);
  const [loading, setLoading] = useState(false);

  const generateIngredients = async () => {
    // Validación
    if (!recipeName || recipeName.length < 3) {
      alert('El nombre de la receta debe tener al menos 3 caracteres');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `/api/v1/nutrition/meals/${mealId}/ingredients/ai-generate`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            'X-Gym-Id': gymId
          },
          body: JSON.stringify({
            recipe_name: recipeName,  // ⭐ CAMPO OBLIGATORIO
            servings: servings,
            dietary_restrictions: [],
            // NO incluir 'preferences' ni 'language'
          })
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Error generating ingredients');
      }

      const data = await response.json();
      // Procesar respuesta...
    } catch (error) {
      console.error('Error:', error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="text"
        value={recipeName}
        onChange={(e) => setRecipeName(e.target.value)}
        placeholder="Nombre de la receta (ej: Paella de mariscos)"
        minLength={3}
        maxLength={200}
        required
      />
      <input
        type="number"
        value={servings}
        onChange={(e) => setServings(parseInt(e.target.value))}
        min={1}
        max={20}
      />
      <button onClick={generateIngredients} disabled={loading}>
        {loading ? 'Generando...' : 'Generar con IA'}
      </button>
    </div>
  );
};
```

## 🎯 Response Esperado (200 OK)

```json
{
  "success": true,
  "ingredients": [
    {
      "name": "Pasta penne",
      "quantity": 400,
      "unit": "gr",
      "calories_per_unit": 3.5,
      "protein_g_per_unit": 0.13,
      "carbs_g_per_unit": 0.71,
      "fat_g_per_unit": 0.015,
      "fiber_g_per_unit": 0.03,
      "notes": "Pasta seca",
      "confidence_score": 0.95
    },
    {
      "name": "Pechuga de pollo",
      "quantity": 500,
      "unit": "gr",
      "calories_per_unit": 1.65,
      "protein_g_per_unit": 0.31,
      "carbs_g_per_unit": 0,
      "fat_g_per_unit": 0.036,
      "fiber_g_per_unit": 0,
      "notes": "Sin piel",
      "confidence_score": 0.98
    }
  ],
  "recipe_instructions": "1. Hervir agua con sal...",
  "estimated_prep_time": 30,
  "difficulty_level": "intermediate",
  "total_estimated_calories": 2225,
  "confidence_score": 0.92,
  "model_used": "gpt-4o-mini",
  "generation_time_ms": 1250
}
```

## ⚠️ Restricciones Dietéticas Válidas

Si quieres usar `dietary_restrictions`, estos son los valores válidos:
- `"vegetarian"`
- `"vegan"`
- `"gluten_free"`
- `"dairy_free"`
- `"nut_free"`
- `"low_sodium"`
- `"low_carb"`
- `"keto"`
- `"paleo"`
- `"halal"`
- `"kosher"`

## 🔍 Debugging

Si sigues teniendo error 422, revisa:

1. **recipe_name es obligatorio** - No puede ser null, undefined o string vacío
2. **Mínimo 3 caracteres** en recipe_name
3. **NO enviar campos que no existen** como `preferences` o `language`
4. **servings debe ser entero** entre 1 y 20
5. **target_calories** si lo envías, debe ser entre 100 y 2000

## 📱 Test con cURL

```bash
# Test correcto del endpoint
curl -X POST "http://localhost:8000/api/v1/nutrition/meals/4/ingredients/ai-generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Gym-Id: 4" \
  -d '{
    "recipe_name": "Ensalada César con Pollo",
    "servings": 2,
    "dietary_restrictions": [],
    "cuisine_type": "americana",
    "target_calories": 450
  }'
```

---

**🚨 ACCIÓN REQUERIDA**: Actualizar el frontend para incluir el campo `recipe_name` y eliminar campos inexistentes (`preferences`, `language`).

*Fix creado por: Claude Code Assistant*
*Fecha: 28 de Diciembre 2024*