# Fix: Validación Flexible de Parámetros en Nutrición

## Problema
Error de validación en producción cuando el usuario envía `'maintain'` en lugar de `'maintenance'`:

```
ERROR: Input should be 'bulk', 'cut', 'maintenance', 'weight_loss', 'muscle_gain' or 'performance'
Input: 'maintain'
```

## Solución Implementada

### 1. Validator para Goal con Aliases

```python
@validator('goal', pre=True)
def normalize_goal(cls, v):
    """Normaliza aliases comunes del objetivo nutricional."""
    goal_aliases = {
        'maintain': 'maintenance',
        'lose_weight': 'weight_loss',
        'gain_muscle': 'muscle_gain',
        'gain': 'muscle_gain',
        'lose': 'weight_loss',
        'build': 'muscle_gain',
        'bulking': 'bulk',
        'cutting': 'cut',
        'definition': 'cut',
        'recomp': 'performance'
    }
    v_lower = v.lower().strip()
    return goal_aliases.get(v_lower, v_lower)
```

### 2. Validator para Restricciones Dietéticas

```python
@validator('dietary_restrictions', pre=True)
def normalize_dietary_restrictions(cls, v):
    """Normaliza restricciones dietéticas a formato consistente."""
    diet_aliases = {
        'veggie': 'vegetarian',
        'veg': 'vegetarian',
        'gluten-free': 'gluten_free',
        'lactose-free': 'lactose_free',
        'dairy-free': 'lactose_free',
        # ... más aliases
    }
```

## Aliases Soportados

### Goal (Objetivo Nutricional)
| Input Usuario | Valor Normalizado |
|--------------|-------------------|
| maintain | maintenance |
| lose_weight | weight_loss |
| gain_muscle | muscle_gain |
| gain | muscle_gain |
| lose | weight_loss |
| build | muscle_gain |
| bulking | bulk |
| cutting | cut |
| definition | cut |
| recomp | performance |

### Dietary Restrictions
| Input Usuario | Valor Normalizado |
|--------------|-------------------|
| veggie | vegetarian |
| veg | vegetarian |
| gluten-free | gluten_free |
| lactose-free | lactose_free |
| dairy-free | lactose_free |
| no-gluten | gluten_free |
| no-lactose | lactose_free |
| pescatarian | vegetarian |
| mediterranean-diet | mediterranean |

## Beneficios

1. **Mayor flexibilidad**: Los usuarios pueden usar términos coloquiales
2. **Menos errores 422**: Reducción significativa de errores de validación
3. **Mejor UX**: Sistema más amigable y tolerante a variaciones
4. **Case-insensitive**: Funciona con mayúsculas/minúsculas
5. **Trim automático**: Elimina espacios en blanco

## Testing

Ejecutar pruebas:
```bash
python test_nutrition_validators.py
```

Resultado esperado:
```
✅ TODAS LAS PRUEBAS PASARON EXITOSAMENTE
• 19 aliases de goal probados
• 13 aliases de restricciones probados
• Casos extremos validados
```

## Archivos Modificados

- `app/schemas/nutrition.py` - Agregados validators con aliases
- `test_nutrition_validators.py` - Script de prueba completo

## Impacto en Producción

**ANTES:**
- Error 422 cuando usuario envía "maintain"
- Usuarios frustrados por términos exactos requeridos

**AHORA:**
- Sistema acepta variaciones comunes
- Normalización automática y transparente
- Mejor experiencia de usuario