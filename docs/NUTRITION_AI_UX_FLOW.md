# 🤖 Flujo UX - Planes Nutricionales con IA Opcional

## 🎯 Visión General

Transformar la creación de planes nutricionales en una experiencia fluida donde la IA actúa como un **asistente nutricional inteligente**, disponible cuando el usuario lo necesite, sin ser intrusiva.

## 🌟 Principios de Diseño

1. **IA como Copiloto, no como Piloto**: El usuario siempre tiene el control
2. **Seguridad sin Fricción**: Proteger salud sin comprometer experiencia
3. **Progresivo, no Abrumador**: Revelación gradual de funcionalidades
4. **Sugerencias Inteligentes**: La IA sugiere, el usuario decide
5. **Flexibilidad Total**: Poder cambiar entre manual y asistido en cualquier momento
6. **Transparencia**: Siempre claro cuando la IA está generando contenido

## ⚠️ IMPORTANTE: Seguridad y Cumplimiento Legal

Este flujo incluye validaciones médicas obligatorias para proteger a usuarios vulnerables y cumplir con requisitos legales. El "Paso 0" de seguridad es **NO NEGOCIABLE** y debe completarse antes de cualquier generación de plan.

---

## 🚀 Flujo de Creación Propuesto

### PASO 0: Gateway de Seguridad (Obligatorio - 30 segundos)

```
┌─────────────────────────────────────────────┐
│     🏥 Verificación de Seguridad            │
├─────────────────────────────────────────────┤
│                                             │
│  Por tu seguridad, confirma:               │
│                                             │
│  ¿Alguna de estas situaciones aplica?      │
│  ☐ Tengo diabetes                          │
│  ☐ Problemas cardíacos o de presión        │
│  ☐ Embarazo o lactancia                    │
│  ☐ Enfermedad renal o hepática            │
│  ☐ Historial de trastorno alimentario      │
│  ☐ Menor de 18 años                        │
│  ☑ Ninguna de las anteriores               │
│                                             │
│  ⚠️ Importante: Este sistema genera        │
│  sugerencias nutricionales con IA.         │
│  No reemplaza consulta médica profesional. │
│                                             │
│  ☐ Acepto el disclaimer y continúo         │
│                                             │
│  [Salir] [Continuar →]                      │
└─────────────────────────────────────────────┘
```

**Validaciones Automáticas**:
- Si marca condiciones médicas → Pantalla de derivación profesional
- Si es menor sin consentimiento → Solicitar email parental
- Si embarazo + pérdida peso → Bloquear y derivar

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
│     2-3 minutos        5-10 minutos         │
│                                             │
│  💡 Tip: Puedes cambiar en cualquier momento│
└─────────────────────────────────────────────┘
```

### FLUJO A: Creación Asistida por IA 🤖

#### A.1 - Cuestionario Inteligente Optimizado (2-3 minutos)

##### PASO 2: Objetivos y Perfil (1 minuto)
```
┌─────────────────────────────────────────────┐
│       🎯 Paso 1/3: Objetivo y Perfil        │
├─────────────────────────────────────────────┤
│                                             │
│  ¿Cuál es tu meta principal?               │
│  ◉ Perder peso                             │
│  ○ Ganar músculo                           │
│  ○ Mantener peso                           │
│  ○ Más energía                             │
│                                             │
│  Información básica:                       │
│  Edad: [25] años    Sexo: [▼ Masculino]    │
│  Peso: [75] kg      Altura: [175] cm       │
│                                             │
│  Nivel actividad:                          │
│  ○ Bajo (0-2 días)                         │
│  ◉ Moderado (3-5 días)                     │
│  ○ Alto (6-7 días)                         │
│                                             │
│  ╔════════════════════════════════════╗    │
│  ║ 📊 Cálculos Automáticos:            ║    │
│  ║ • IMC: 24.5 (Normal) ✅             ║    │
│  ║ • Metabolismo base: ~1,750 kcal     ║    │
│  ║ • Gasto diario: ~2,400 kcal         ║    │
│  ║ • Objetivo: 1,900 kcal/día          ║    │
│  ║   (déficit 500 kcal para -0.5kg/sem)║    │
│  ╚════════════════════════════════════╝    │
│                                             │
│  [← Cancelar]  [Siguiente →]                │
└─────────────────────────────────────────────┘
```

##### PASO 3: Restricciones y Preferencias (1 minuto)
```
┌─────────────────────────────────────────────┐
│    🚫 Paso 2/3: Restricciones y Alergias   │
├─────────────────────────────────────────────┤
│                                             │
│  Dieta especial: [▼ Ninguna               ]│
│  (Vegetariano, Vegano, Keto, Sin gluten)   │
│                                             │
│  Alergias principales (máx 10 opciones):   │
│  ☐ Frutos secos   ☐ Lácteos               │
│  ☐ Gluten         ☐ Mariscos              │
│  ☐ Huevos         ☐ Otro: [______]        │
│                                             │
│  5 ingredientes que NO quieres:            │
│  [ej: cilantro, brócoli, hígado_____]      │
│                                             │
│  Presupuesto semanal:                      │
│  ○ Bajo ($30-50)                           │
│  ◉ Moderado ($50-100)                      │
│  ○ Alto ($100+)                            │
│                                             │
│  Tiempo para cocinar:                      │
│  ○ Poco (15 min)                           │
│  ◉ Moderado (30 min)                       │
│  ○ Me gusta cocinar (45+ min)              │
│                                             │
│  ╔════════════════════════════════════╗    │
│  ║ 💡 Tip: La IA respetará todas tus   ║    │
│  ║ restricciones y preferencias        ║    │
│  ╚════════════════════════════════════╝    │
│                                             │
│  [← Anterior]  [🚀 Generar Plan con IA]    │
│                [+ Más opciones]             │
└─────────────────────────────────────────────┘
```

##### PASO 4: Preferencias Avanzadas (OPCIONAL - 30 segundos)
```
┌─────────────────────────────────────────────┐
│    ⚙️ Paso 3/3: Opciones Avanzadas         │
│         (Completamente Opcional)           │
├─────────────────────────────────────────────┤
│                                             │
│  📍 NOTA: Estos campos son opcionales.      │
│     La IA usará valores inteligentes.      │
│                                             │
│  Equipamiento especial:                    │
│  ☐ Freidora de aire                       │
│  ☐ Olla de presión                        │
│  ☐ Thermomix/Procesador                   │
│                                             │
│  Tipo de cocina preferida:                 │
│  [▼ Variada (IA decide)                   ]│
│                                             │
│  Consideraciones especiales:               │
│  ☐ Trabajo por turnos                     │
│  ☐ Viajo frecuentemente                   │
│  ☐ Cocino para familia                    │
│                                             │
│  Notas adicionales (opcional):             │
│  [________________________________]         │
│                                             │
│  ╔════════════════════════════════════╗    │
│  ║ ✨ Ya tienes suficiente info para   ║    │
│  ║ generar un excelente plan           ║    │
│  ╚════════════════════════════════════╝    │
│                                             │
│  [← Anterior]  [🚀 Generar Plan con IA]    │
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

### Opción A: Flujo Tradicional Optimizado
- Mismos pasos pero con diseño responsive
- Campos adaptados para touch
- Teclado numérico para números
- Selectores nativos del OS

### Opción B: Tinder-Style (Innovador)
```
┌─────────────────────────────────────────────┐
│         📱 Creación Rápida Móvil            │
├─────────────────────────────────────────────┤
│                                             │
│  1️⃣ Responde 5 preguntas básicas (1 min)    │
│                                             │
│  2️⃣ IA genera 20 opciones de comidas        │
│                                             │
│  3️⃣ Swipe para crear tu semana:             │
│                                             │
│         [Imagen de comida]                  │
│                                             │
│         🍽️ Pollo Teriyaki                   │
│         580 cal | 35g proteína              │
│                                             │
│     ← No me gusta    Me gusta →             │
│           ❌             ✅                  │
│                                             │
│  Progreso: ████████░░ 14/21 comidas         │
│                                             │
│  [Finalizar y Generar Plan]                 │
└─────────────────────────────────────────────┘
```

### Creación Rápida por Voz
```
🎤 "Crear plan de 1500 calorías,
    vegetariano, para perder peso,
    con comidas fáciles de preparar"

✨ Plan generado en 3 segundos
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

## 🔄 Progressive Profiling (Post-Generación)

### Captura Gradual de Información
Después de generar el primer plan, el sistema captura más datos sin fricción:

#### Día 1 - Post Generación:
```
┌─────────────────────────────────────────────┐
│   ✅ Plan generado exitosamente             │
│                                             │
│   2 preguntas rápidas para mejorar:        │
│   • ¿Cocinas para tu familia? [Sí/No]     │
│   • ¿Comes fuera frecuentemente? [Sí/No]   │
│                                             │
│   [Responder] [Ahora no]                   │
└─────────────────────────────────────────────┘
```

#### Día 7 - Primera Semana:
```
┌─────────────────────────────────────────────┐
│   📊 ¿Cómo va tu primera semana?           │
│                                             │
│   Nivel de hambre: [▓▓▓▓░░░░░░] 4/10      │
│   Energía:         [▓▓▓▓▓▓▓░░░] 7/10      │
│                                             │
│   ¿Alguna comida que no te gustó?         │
│   [________________________]               │
│                                             │
│   [Ajustar plan] [Continuar igual]         │
└─────────────────────────────────────────────┘
```

#### Día 14 - Reajuste:
```
┌─────────────────────────────────────────────┐
│   🎯 Tiempo de optimizar                   │
│                                             │
│   Peso actual: [74.5] kg                   │
│   Cambio: -0.5 kg ✅ (objetivo cumplido)   │
│                                             │
│   ¿Ajustamos las calorías?                │
│   [Mantener] [Reducir 100] [Aumentar 100]  │
└─────────────────────────────────────────────┘
```

---

## 📈 Métricas de Éxito Actualizadas

### KPIs Realistas Post-Cambios
- **65%** tasa de completion (vs 30% original)
- **3-4 min** tiempo promedio (vs 7 min original)
- **95%** detección casos de riesgo médico
- **<5%** reportes de problemas de salud
- **45%** retención a 30 días

### Métricas de Seguridad
- **100%** usuarios pasan por gateway de seguridad
- **5-10%** derivados a profesional (esperado)
- **0** incidentes médicos reportados (objetivo)

---

## 💡 Conclusión

La IA debe sentirse como un **nutricionista experto** siempre disponible, que:
- **Protege** la salud del usuario primero
- **Sugiere** sin imponer
- **Aprende** de tus preferencias gradualmente
- **Ahorra tiempo** sin sacrificar calidad ni seguridad
- **Empodera** al usuario con conocimiento

El usuario final debe pensar:
> "No estoy usando IA, tengo un asistente nutricional que me entiende y cuida mi salud"

---

*Documento actualizado con decisiones de Product Management*
*Fecha: Diciembre 2024*
*Enfoque: Seguridad + User Experience*
*Status: APROBADO para implementación*