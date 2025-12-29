# 🤖 Flujo UX - Planes Nutricionales con IA Opcional

## 🎯 Visión General

Transformar la creación de planes nutricionales en una experiencia fluida donde la IA actúa como un **asistente nutricional inteligente**, disponible cuando el usuario lo necesite, sin ser intrusiva.

## 🌟 Principios de Diseño

1. **IA como Copiloto, no como Piloto**: El usuario siempre tiene el control
2. **Progresivo, no Abrumador**: Revelación gradual de funcionalidades
3. **Sugerencias Inteligentes**: La IA sugiere, el usuario decide
4. **Flexibilidad Total**: Poder cambiar entre manual y asistido en cualquier momento
5. **Transparencia**: Siempre claro cuando la IA está generando contenido

---

## 🚀 Flujo de Creación Propuesto

### PASO 1: Inicio del Plan (Decisión Inicial)

```
┌─────────────────────────────────────────────┐
│      🎯 Crear Nuevo Plan Nutricional        │
├─────────────────────────────────────────────┤
│                                             │
│  ¿Cómo quieres crear tu plan?              │
│                                             │
│  ┌──────────────┐    ┌──────────────┐      │
│  │  🤖 Con IA   │    │ ✏️ Manual    │      │
│  │  Asistida    │    │  Tradicional │      │
│  └──────────────┘    └──────────────┘      │
│        (70%)              (30%)             │
│                                             │
│  💡 Tip: Puedes cambiar en cualquier momento│
└─────────────────────────────────────────────┘
```

### FLUJO A: Creación Asistida por IA 🤖

#### A.1 - Cuestionario Inteligente Detallado (2-3 minutos)

##### PASO 1: Objetivos y Perfil
```
┌─────────────────────────────────────────────┐
│       🎯 Paso 1/5: Objetivo Principal       │
├─────────────────────────────────────────────┤
│                                             │
│  ¿Cuál es tu meta principal?               │
│  ◉ Perder peso (-0.5 a -1kg/semana)       │
│  ○ Ganar músculo (+0.25 a +0.5kg/semana)  │
│  ○ Recomposición corporal                  │
│  ○ Mantener peso actual                    │
│  ○ Mejorar salud general                   │
│  ○ Aumentar energía y rendimiento          │
│                                             │
│  ¿Para quién es este plan?                 │
│  ◉ Para mí                                 │
│  ○ Para un cliente específico              │
│  ○ Plan general del gimnasio               │
│  ○ Grupo de entrenamiento                  │
│                                             │
│  Información básica:                       │
│  Edad: [25] años                           │
│  Sexo: [▼ Masculino]                       │
│  Peso actual: [75] kg                      │
│  Altura: [175] cm                          │
│  Nivel actividad: [▼ Moderado (3-5 días)] │
│                                             │
│  [← Cancelar]  [Siguiente →]                │
└─────────────────────────────────────────────┘
```

##### PASO 2: Restricciones y Alergias
```
┌─────────────────────────────────────────────┐
│    🚫 Paso 2/5: Restricciones y Alergias   │
├─────────────────────────────────────────────┤
│                                             │
│  Restricciones dietéticas:                 │
│  ☐ Vegetariano    ☐ Vegano                │
│  ☐ Sin gluten     ☐ Sin lácteos           │
│  ☐ Keto           ☐ Paleo                 │
│  ☐ Low FODMAP     ☐ Sin azúcar            │
│  ☐ Halal          ☐ Kosher                │
│  ☐ Pescetariano   ☐ Mediterránea          │
│                                             │
│  Alergias alimentarias:                    │
│  ☐ Frutos secos   ☐ Mariscos              │
│  ☐ Huevos         ☐ Soja                  │
│  ☐ Cacahuetes     ☐ Pescado               │
│  ☐ Trigo          ☐ Sésamo                │
│  Otras: [_____________________]            │
│                                             │
│  Intolerancias:                            │
│  ☐ Lactosa        ☐ Fructosa              │
│  ☐ Histamina      ☐ Gluten (no celíaco)   │
│  Otras: [_____________________]            │
│                                             │
│  [← Anterior]  [Siguiente →]                │
└─────────────────────────────────────────────┘
```

##### PASO 3: Ingredientes No Deseados
```
┌─────────────────────────────────────────────┐
│    ❌ Paso 3/5: Ingredientes a Evitar      │
├─────────────────────────────────────────────┤
│                                             │
│  ¿Qué ingredientes NO quieres en tu plan?  │
│                                             │
│  Por categorías:                           │
│  ├─ 🥩 Proteínas:                          │
│  │  ☐ Carne roja    ☐ Cerdo               │
│  │  ☐ Pollo         ☐ Pavo                │
│  │  ☐ Pescado azul  ☐ Pescado blanco      │
│  │  ☐ Tofu          ☐ Tempeh              │
│  │  ☐ Legumbres     ☐ Proteína en polvo   │
│  │                                         │
│  ├─ 🥬 Vegetales:                          │
│  │  ☐ Brócoli       ☐ Coliflor            │
│  │  ☐ Espinacas     ☐ Kale                │
│  │  ☐ Pimientos     ☐ Cebolla             │
│  │  ☐ Ajo           ☐ Champiñones         │
│  │  ☐ Berenjena     ☐ Calabacín           │
│  │                                         │
│  ├─ 🍚 Carbohidratos:                      │
│  │  ☐ Arroz blanco  ☐ Arroz integral      │
│  │  ☐ Pasta         ☐ Pan                 │
│  │  ☐ Avena         ☐ Quinoa              │
│  │  ☐ Patata        ☐ Batata              │
│  │                                         │
│  └─ Ingredientes específicos a evitar:     │
│     [cilantro, aceitunas, anchoas____]     │
│                                             │
│  Razón principal para evitar:              │
│  ◉ No me gusta el sabor                   │
│  ○ Difícil de conseguir                   │
│  ○ Muy caro                               │
│  ○ Alergia/intolerancia                   │
│                                             │
│  [← Anterior]  [Siguiente →]                │
└─────────────────────────────────────────────┘
```

##### PASO 4: Preferencias de Preparación
```
┌─────────────────────────────────────────────┐
│    ⏰ Paso 4/5: Estilo de Vida y Cocina    │
├─────────────────────────────────────────────┤
│                                             │
│  Tiempo disponible para cocinar:           │
│  Desayuno: [▼ 10-15 min]                   │
│  Almuerzo: [▼ 20-30 min]                   │
│  Cena: [▼ 30-45 min]                       │
│                                             │
│  ¿Cuántas veces cocinas a la semana?      │
│  ◉ Todos los días                          │
│  ○ 3-4 veces (meal prep)                  │
│  ○ 1-2 veces (batch cooking)              │
│  ○ Casi nunca (comida preparada)          │
│                                             │
│  Nivel de habilidad en cocina:             │
│  ○ Principiante (recetas simples)         │
│  ◉ Intermedio (puedo seguir recetas)      │
│  ○ Avanzado (me gusta experimentar)       │
│                                             │
│  Equipamiento disponible:                  │
│  ☑ Horno         ☑ Microondas             │
│  ☑ Estufa        ☐ Freidora de aire       │
│  ☐ Olla presión  ☐ Procesador alimentos   │
│  ☐ Batidora      ☐ Parrilla/BBQ           │
│                                             │
│  Preferencias de cocción:                  │
│  ☑ Al vapor      ☑ Asado/horno            │
│  ☑ Salteado      ☐ Frito                  │
│  ☑ Hervido       ☑ A la plancha           │
│  ☐ Crudo/Raw     ☐ Sous vide              │
│                                             │
│  [← Anterior]  [Siguiente →]                │
└─────────────────────────────────────────────┘
```

##### PASO 5: Presupuesto y Preferencias Finales
```
┌─────────────────────────────────────────────┐
│    💰 Paso 5/5: Presupuesto y Detalles     │
├─────────────────────────────────────────────┤
│                                             │
│  Presupuesto semanal para comida:          │
│  ○ Económico ($30-50 / €25-45)            │
│  ◉ Moderado ($50-100 / €45-90)            │
│  ○ Premium ($100-150 / €90-135)           │
│  ○ Sin límite (>$150 / >€135)             │
│                                             │
│  Preferencias de compra:                   │
│  ☑ Ingredientes locales/temporada         │
│  ☐ Solo productos orgánicos               │
│  ☑ Marcas genéricas aceptables            │
│  ☐ Compra a granel preferida              │
│                                             │
│  Tipo de cocina preferida:                 │
│  ☑ Mediterránea   ☑ Asiática              │
│  ☐ Mexicana       ☐ Italiana              │
│  ☐ India          ☐ Americana             │
│  ☑ Fusión         ☐ Tradicional local     │
│                                             │
│  Horarios de comida habituales:            │
│  Desayuno: [08:00]                         │
│  Snack AM: [10:30] ☐ Omitir               │
│  Almuerzo: [13:00]                         │
│  Snack PM: [16:30] ☐ Omitir               │
│  Cena: [20:00]                             │
│                                             │
│  Consideraciones especiales:               │
│  ☐ Trabajo por turnos                     │
│  ☐ Viajo frecuentemente                   │
│  ☐ Como fuera 3+ veces/semana             │
│  ☐ Comparto comidas con familia           │
│  ☐ Necesito opciones portables            │
│                                             │
│  Notas adicionales para la IA:             │
│  [Me gusta la comida picante pero no     ]│
│  [demasiado. Prefiero sabores frescos    ]│
│  [y comidas que se puedan preparar       ]│
│  [con anticipación para la semana.       ]│
│                                             │
│  🎯 Resumen de tu perfil:                  │
│  • Objetivo: Perder peso                   │
│  • Sin gluten y lácteos                   │
│  • Evitar: cilantro, cerdo                │
│  • Presupuesto moderado                   │
│  • Tiempo limitado para cocinar           │
│                                             │
│  [← Anterior]  [🤖 Generar Plan con IA]    │
└─────────────────────────────────────────────┘
```

#### A.2 - Generación Instantánea (5-10 segundos)
```
┌─────────────────────────────────────────────┐
│      ✨ Generando tu plan personalizado     │
├─────────────────────────────────────────────┤
│                                             │
│  🔄 Analizando objetivos...                │
│  ✅ Calculando macros ideales              │
│  🔄 Creando 7 días de menús...             │
│  🔄 Generando lista de compras...          │
│                                             │
│  ████████████░░░ 75%                       │
│                                             │
└─────────────────────────────────────────────┘
```

#### A.3 - Vista Previa Editable
```
┌─────────────────────────────────────────────┐
│    📋 Tu Plan: "Pérdida de Peso Saludable" │
├─────────────────────────────────────────────┤
│                                             │
│  Resumen: 1800 cal/día | 7 días            │
│                                             │
│  📅 Día 1 - Lunes                  [Editar]│
│  ├─ 🌅 Desayuno (400 cal)                  │
│  │   Avena con frutas y nueces    [🤖→✏️]  │
│  ├─ 🍎 Snack AM (150 cal)                  │
│  │   Yogurt griego con miel       [🤖→✏️]  │
│  ├─ 🍽️ Almuerzo (600 cal)                 │
│  │   Ensalada César con pollo     [🤖→✏️]  │
│  ├─ 🥤 Snack PM (150 cal)                  │
│  │   Batido de proteína           [🤖→✏️]  │
│  └─ 🌙 Cena (500 cal)                      │
│      Salmón con vegetales         [🤖→✏️]  │
│                                             │
│  [➕ Agregar Día] [🔄 Regenerar] [✅ Guardar]│
└─────────────────────────────────────────────┘
```

### FLUJO B: Creación Manual con IA Disponible ✏️

#### B.1 - Editor Manual con Asistente
```
┌─────────────────────────────────────────────┐
│         ✏️ Creando Plan Manual              │
├─────────────────────────────────────────────┤
│                                             │
│  Nombre: [Plan de Definición Muscular___]  │
│  Duración: [7] días                        │
│  Calorías objetivo: [2200] cal/día         │
│                                             │
│  📅 Día 1                                   │
│  ┌─────────────────────────────────┐       │
│  │ + Agregar Comida                │       │
│  │                                 │       │
│  │ 💡 ¿Necesitas ayuda?           │       │
│  │ [🤖 Sugerir Desayuno]          │       │
│  └─────────────────────────────────┘       │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 🎨 Funcionalidades Híbridas (Lo Mejor de Ambos Mundos)

### 1. Botón Mágico "Sugerir con IA" 🪄
Disponible en cada campo vacío:
- **Comida vacía**: "🤖 Sugerir comida balanceada"
- **Sin ingredientes**: "🤖 Generar ingredientes"
- **Sin instrucciones**: "🤖 Crear receta paso a paso"

### 2. Validación Inteligente en Tiempo Real 🔍
```
⚠️ Esta comida tiene pocas proteínas (5g)
   [🤖 Agregar fuente de proteína] [Ignorar]

✅ ¡Excelente balance de macros!
```

### 3. Chat Nutricional Contextual 💬
```
┌──────────────────────────┐
│ 🤖 Asistente Nutricional │
├──────────────────────────┤
│ Usuario: "Necesito más   │
│ opciones veganas"        │
│                          │
│ IA: "He encontrado 5     │
│ alternativas veganas     │
│ para el almuerzo:        │
│ 1. Quinoa con vegetales  │
│ 2. Tofu teriyaki...      │
│ [Ver todas →]            │
└──────────────────────────┘
```

---

## 🔄 Flujo de Edición Inteligente

### Editar Comida Existente
```
┌─────────────────────────────────────────────┐
│        🍽️ Editando: Almuerzo Día 3          │
├─────────────────────────────────────────────┤
│                                             │
│  Pollo a la plancha con arroz              │
│                                             │
│  Acciones Rápidas con IA:                  │
│  ┌──────────────────────────────────┐      │
│  │ 🔄 Hacer más saludable          │      │
│  │ 🌱 Convertir a vegetariano      │      │
│  │ ⬆️ Aumentar proteínas           │      │
│  │ ⬇️ Reducir calorías             │      │
│  │ 🎲 Alternativa similar          │      │
│  └──────────────────────────────────┘      │
│                                             │
│  [Aplicar] [Cancelar]                      │
└─────────────────────────────────────────────┘
```

---

## 📊 Análisis y Optimización con IA

### Panel de Insights
```
┌─────────────────────────────────────────────┐
│      📊 Análisis de tu Plan con IA         │
├─────────────────────────────────────────────┤
│                                             │
│  ✅ Fortalezas:                            │
│  • Balance de macros excelente             │
│  • Variedad de alimentos alta              │
│  • Cumple objetivo calórico                │
│                                             │
│  ⚠️ Sugerencias de Mejora:                 │
│  • Día 3 bajo en fibra [🤖 Corregir]       │
│  • Falta omega-3 [🤖 Agregar fuentes]      │
│  • Muy repetitivo el desayuno [🤖 Variar]  │
│                                             │
│  Puntuación Nutricional: 8.5/10 🌟         │
│                                             │
│  [🤖 Aplicar Todas las Mejoras]            │
└─────────────────────────────────────────────┘
```

---

## 🚀 Funciones Avanzadas de IA

### 1. Planificador Semanal Inteligente
```
"🤖 Generar semana completa considerando:
 • Tu agenda (días de entrenamiento)
 • Presupuesto ($50-100/semana)
 • Tiempo de cocina (30-45 min)
 • Usar ingredientes de temporada"
```

### 2. Adaptación Automática
```
"🔄 El plan se ajusta automáticamente si:
 • Cambias tu peso objetivo
 • Modificas tu nivel de actividad
 • Agregas nuevas restricciones"
```

### 3. Recetas con Foto IA
```
"📸 Sube foto de tu plato favorito
 La IA creará una versión saludable
 con los mismos sabores"
```

---

## 🎮 Gamificación y Motivación

### Logros Desbloqueables
```
🏆 "Maestro de Macros" - Plan perfecto creado
🎯 "Consistente" - 7 días sin repetir comidas
🌱 "Eco Warrior" - Plan 100% plant-based
⚡ "Speed Creator" - Plan completo en < 2 min
```

### Plantillas de la Comunidad
```
⭐ Planes Populares (Creados con IA):
1. "Definición Express" - 2.8k usos
2. "Vegano Power" - 1.5k usos
3. "Keto Simple" - 1.2k usos

[🤖 Personalizar para mí]
```

---

## 📱 Experiencia Móvil First

### Creación Rápida por Voz
```
🎤 "Crear plan de 1500 calorías,
    vegetariano, para perder peso,
    con comidas fáciles de preparar"

✨ Plan generado en 3 segundos
```

### Swipe para Decidir
```
   ← Rechazar    [🍽️ Comida]    Aceptar →
                 Pollo teriyaki
                   580 cal
```

---

## 🔐 Privacidad y Control

### Transparencia Total
```
ℹ️ Contenido Generado por IA:
• Basado en bases de datos nutricionales
• Revisado por algoritmos de seguridad
• Puedes editar todo manualmente
• Tus datos no se comparten con terceros
```

### Modo Sin IA
```
[🔒 Desactivar todas las sugerencias IA]
Crear planes 100% manuales
```

---

## 📈 Métricas de Éxito

### KPIs de Adopción
- **70%** de usuarios prueban IA en primera sesión
- **85%** satisfacción con sugerencias
- **50%** reducción en tiempo de creación
- **3x** más planes completados vs manual

### Feedback Loop
```
¿Te gustó esta sugerencia?
[👍] [👎] [🤔 Mejorar]

Tu feedback entrena la IA
```

---

## 🛠️ Implementación Progresiva

### Fase 1: MVP (Semana 1-2)
- ✅ Generar plan completo básico
- ✅ Sugerir comidas individuales
- ✅ Calcular macros automáticamente

### Fase 2: Mejoras (Semana 3-4)
- 🔄 Edición con IA
- 🔄 Validación inteligente
- 🔄 Plantillas predefinidas

### Fase 3: Avanzado (Mes 2)
- 🚀 Chat contextual
- 🚀 Análisis y optimización
- 🚀 Personalización por historial

### Fase 4: Premium (Mes 3)
- 💎 Fotos con IA
- 💎 Voz a plan
- 💎 Integración con wearables

---

## 💡 Conclusión

La IA debe sentirse como un **nutricionista experto** siempre disponible, que:
- **Sugiere** sin imponer
- **Aprende** de tus preferencias
- **Ahorra tiempo** sin sacrificar calidad
- **Empodera** al usuario con conocimiento

El usuario final debe pensar:
> "No estoy usando IA, tengo un asistente nutricional que me entiende"

---

*Documento creado para el equipo de desarrollo y UX*
*Fecha: Diciembre 2024*
*Enfoque: User Experience First*