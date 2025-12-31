# 🎯 Casos de Uso - Sistema de Nutrición

## 📋 Tabla de Contenidos
- [Casos de Uso para Members](#casos-de-uso-para-members)
- [Casos de Uso para Trainers](#casos-de-uso-para-trainers)
- [Casos de Uso para Admins](#casos-de-uso-para-admins)
- [Escenarios Especiales](#escenarios-especiales)
- [Flujos de Error](#flujos-de-error)
- [Casos de Éxito](#casos-de-éxito)

## Casos de Uso para Members

### UC-M1: Primer Uso del Sistema
**Actor:** Member nuevo en el sistema de nutrición
**Objetivo:** Comenzar a usar el módulo de nutrición de forma segura

```
FLUJO PRINCIPAL:
1. Member accede a sección Nutrición
2. Sistema muestra planes disponibles públicos
3. Member selecciona plan "Pérdida de peso 1500cal"
4. Sistema detecta plan restrictivo (<1800 cal)
5. Sistema solicita evaluación médica
6. Member completa formulario de screening
7. Sistema evalúa riesgo (BAJO)
8. Member acepta disclaimer
9. Sistema permite seguir el plan
10. Member comienza a recibir su plan diario

DATOS DE EJEMPLO:
- Usuario: María, 28 años
- Objetivo: Perder 5kg
- Sin condiciones médicas
- IMC: 26 (sobrepeso leve)
- Resultado: Aprobado con advertencias nutricionales
```

### UC-M2: Seguimiento Diario de Comidas
**Actor:** Member activo con plan asignado
**Objetivo:** Registrar progreso diario

```
TIMELINE DIARIO:
08:00 - Notificación push: "🍳 Hora del desayuno"
08:30 - Member abre app
      - Ve desayuno planificado: Avena con frutas (380 cal)
      - Marca 90% completado
      - Sube foto del plato

13:00 - Notificación: "🥗 Hora del almuerzo"
13:15 - Member en restaurante
      - Toma foto de su comida
      - Sistema analiza con IA: ~650 cal detectadas
      - Member confirma y registra

19:00 - Notificación: "🍽️ Hora de la cena"
19:30 - Member prepara cena según plan
      - Marca 100% completado
      - Ve resumen del día: 1,485 cal (98% del objetivo)

22:00 - Sistema genera resumen diario
      - Calorías: 1,485/1,500 ✅
      - Proteína: 75g/70g ✅
      - Agua: 7/8 vasos ⚠️
      - Sugerencia: "Aumentar hidratación mañana"
```

### UC-M3: Cambio de Plan por Evento Especial
**Actor:** Member con evento social
**Objetivo:** Ajustar plan temporalmente

```
ESCENARIO:
- Viernes: Member tiene boda el sábado
- Necesita flexibilidad en el plan

FLUJO:
1. Member solicita "día libre" en app
2. Sistema sugiere:
   - Reducir 200 cal viernes
   - Día libre sábado (maintenance)
   - Reducir 200 cal domingo
3. Member acepta ajuste
4. Sistema recalcula semana
5. Mantiene déficit semanal total

RESULTADO:
- Flexibilidad sin perder progreso
- Adherencia mejorada al plan
- Usuario satisfecho
```

### UC-M4: Usuario con Restricciones Médicas
**Actor:** Member con diabetes tipo 2
**Objetivo:** Seguir plan seguro para su condición

```
SCREENING INICIAL:
{
  "age": 45,
  "medical_conditions": ["diabetes_tipo_2"],
  "takes_medications": true,
  "medication_list": "Metformina 850mg"
}

EVALUACIÓN:
- Risk Level: MEDIUM
- Can Proceed: YES
- Warnings: [
    "Monitorear glucosa regularmente",
    "Evitar ayunos prolongados",
    "Consultar con médico si hay cambios"
  ]

PLAN ADAPTADO:
- 5-6 comidas pequeñas/día
- Carbohidratos complejos
- Índice glucémico bajo
- Sin azúcares simples
- Horarios fijos de comida

SEGUIMIENTO ESPECIAL:
- Recordatorios de medición de glucosa
- Alertas si salta comidas
- Reporte mensual para médico
```

## Casos de Uso para Trainers

### UC-T1: Creación de Plan Personalizado
**Actor:** Trainer con 5 clientes nuevos
**Objetivo:** Crear planes individualizados eficientemente

```
PROCESO BATCH CON IA:
1. Trainer accede a "Generar Planes con IA"
2. Selecciona múltiples clientes:
   - Juan: Ganancia muscular, 3000 cal
   - Ana: Pérdida peso, 1600 cal
   - Carlos: Mantenimiento, 2200 cal
   - Laura: Definición, 1800 cal
   - Pedro: Rendimiento, 2800 cal

3. Para cada cliente, especifica:
   - Objetivo principal
   - Restricciones alimentarias
   - Presupuesto aproximado
   - Nivel de cocina

4. Sistema genera 5 planes en paralelo
   - Tiempo total: 15 segundos
   - Costo: $0.01 USD total

5. Trainer revisa y ajusta cada plan
6. Asigna planes a clientes
7. Clientes reciben notificación

MÉTRICAS:
- Tiempo ahorrado: 4 horas vs manual
- Satisfacción clientes: 95%
- Adherencia a 30 días: 78%
```

### UC-T2: Monitoreo de Progreso Grupal
**Actor:** Trainer con grupo de 20 members
**Objetivo:** Identificar quién necesita ayuda

```
DASHBOARD SEMANAL:
┌─────────────────────────────────────┐
│ RESUMEN GRUPAL - Semana 4          │
├─────────────────────────────────────┤
│ ✅ Alta adherencia (>80%): 12      │
│ ⚠️  Media adherencia (50-80%): 6   │
│ ❌ Baja adherencia (<50%): 2       │
└─────────────────────────────────────┘

ACCIONES AUTOMÁTICAS:
- Sistema identifica 2 usuarios en riesgo
- Envía alerta a trainer
- Trainer contacta usuarios:

  CONVERSACIÓN CON USUARIO EN RIESGO:
  Trainer: "Hola María, veo que has tenido dificultades esta semana"
  María: "Sí, el trabajo ha sido caótico"
  Trainer: "Ajustemos tu plan a 3 comidas principales por ahora"
  María: "Eso sería más manejable, gracias"

  RESULTADO:
  - Plan simplificado temporalmente
  - Adherencia mejora a 75% siguiente semana
```

### UC-T3: Ajuste Masivo por Temporada
**Actor:** Trainer preparando verano
**Objetivo:** Transicionar clientes a fase definición

```
TIMELINE:
MARZO (12 semanas antes de verano):
1. Trainer selecciona 15 clientes objetivo
2. Aplica template "Definición Verano":
   - Reducción calórica progresiva
   - Aumento cardio
   - Ciclado de carbohidratos

3. Sistema genera ajustes individuales:
   for cliente in clientes:
       nuevo_plan = calcular_definicion(
           peso_actual=cliente.weight,
           grasa_corporal=cliente.body_fat,
           semanas_disponibles=12
       )

4. Envío masivo con mensaje personalizado:
   "¡Hola {nombre}! Comenzamos tu preparación
    para verano. Tu nuevo plan tiene {calorias} cal
    con enfoque en definición. ¿Listo? 💪"

5. Tracking semanal automático:
   - Semana 1-4: -0.5kg/semana promedio
   - Semana 5-8: -0.4kg/semana
   - Semana 9-12: -0.3kg/semana
   - Total: -5.4kg promedio, -3% grasa corporal
```

### UC-T4: Gestión de Consultas con IA
**Actor:** Trainer con 50+ clientes
**Objetivo:** Responder consultas eficientemente

```
SISTEMA DE CONSULTAS ASISTIDO:

CONSULTA ENTRANTE:
Cliente: "¿Puedo cambiar el pollo del almuerzo por atún?"

PROCESO:
1. IA analiza consulta
2. Sugiere respuesta a trainer:
   "Sí, puedes cambiar 150g pollo por 130g atún
    para mantener las proteínas. Las calorías
    serán similares (±20 cal)."

3. Trainer revisa y aprueba con un click
4. Cliente recibe respuesta en <2 minutos

ESTADÍSTICAS DIARIAS:
- Consultas recibidas: 47
- Respondidas con IA assist: 38 (80%)
- Requirieron atención manual: 9 (20%)
- Tiempo promedio respuesta: 3 min
- Satisfacción: 4.7/5
```

## Casos de Uso para Admins

### UC-A1: Configuración Inicial del Módulo
**Actor:** Admin de gimnasio nuevo
**Objetivo:** Activar y configurar nutrición

```
CHECKLIST DE CONFIGURACIÓN:
□ Activar módulo nutrición ($50/mes)
□ Configurar integraciones:
  ✓ OpenAI API key
  ✓ Límites de generación (50/mes)
  ✓ Tipos de planes permitidos

□ Establecer políticas:
  ✓ Screening obligatorio: SÍ
  ✓ Edad mínima: 16 años
  ✓ Requiere disclaimer: SÍ

□ Asignar permisos:
  ✓ 3 trainers con acceso IA
  ✓ 1 nutricionista supervisor

□ Crear planes base:
  ✓ Importar 10 templates
  ✓ Personalizar con logo gym

□ Configurar notificaciones:
  ✓ Horarios por defecto
  ✓ Mensajes personalizados

TIEMPO TOTAL SETUP: 30 minutos
```

### UC-A2: Auditoría Mensual de Costos
**Actor:** Admin controlando presupuesto
**Objetivo:** Optimizar costos del módulo

```
REPORTE MENSUAL - ENERO 2025:
┌────────────────────────────────────────┐
│ COSTOS NUTRICIÓN                      │
├────────────────────────────────────────┤
│ Suscripción base:         $50.00      │
│ Generaciones IA:           $2.35      │
│ - Plans generados: 156                │
│ - Análisis imágenes: 423              │
│                                        │
│ TOTAL:                    $52.35      │
└────────────────────────────────────────┘

ANÁLISIS DE USO:
- Members activos: 89/120 (74%)
- Plans más populares:
  1. Pérdida peso 1500cal (34 usuarios)
  2. Ganancia muscular 3000cal (28 usuarios)
  3. Mantenimiento flexible (27 usuarios)

- Trainers más activos:
  1. Carlos: 67 generaciones
  2. Ana: 52 generaciones
  3. Luis: 37 generaciones

OPTIMIZACIONES APLICADAS:
✓ Cache de planes similares (ahorro: $0.80)
✓ Límite diario por trainer (5 generaciones)
✓ Reutilización de templates base

ROI ESTIMADO:
- Ingresos adicionales: $890 (nuevos members)
- Retención mejorada: 8% más
- ROI: 1,700%
```

### UC-A3: Gestión de Crisis - Usuario con Problema Médico
**Actor:** Admin manejando situación delicada
**Objetivo:** Responder adecuadamente a emergencia

```
ALERTA RECIBIDA:
"Usuario reporta mareos siguiendo plan 1200 cal"

PROTOCOLO DE RESPUESTA:
1. INMEDIATO (< 5 min):
   - Suspender plan automáticamente
   - Notificar a trainer asignado
   - Contactar usuario

2. EVALUACIÓN (< 30 min):
   - Revisar screening médico
   - Verificar adherencia al plan
   - Consultar historial

3. ACCIÓN:
   - Recomendar consulta médica
   - Ofrecer reembolso si aplica
   - Documentar incidente

4. SEGUIMIENTO:
   - Crear ticket de soporte
   - Actualizar políticas si necesario
   - Entrenar staff sobre caso

5. PREVENCIÓN:
   - Ajustar algoritmo de screening
   - Agregar warning adicional
   - Review mensual de casos similares

RESULTADO:
- Usuario atendido satisfactoriamente
- Sin consecuencias legales
- Mejora en protocolos de seguridad
```

### UC-A4: Lanzamiento de Reto Nutricional
**Actor:** Admin organizando evento del gym
**Objetivo:** Crear reto de 30 días para engagement

```
CONFIGURACIÓN DEL RETO:
Nombre: "Transformación Verano 2025"
Duración: 30 días
Premio: 3 meses gratis
Participantes objetivo: 50

SETUP TÉCNICO:
1. Crear plan especial "Reto Verano"
2. Configurar tracking especial:
   - Fotos semanales
   - Medidas corporales
   - Check-ins diarios

3. Automatizar comunicación:
   Día 1: "¡Bienvenido al reto! Tu plan está listo"
   Día 7: "Primera semana completada 💪"
   Día 14: "¡Mitad del camino! Sigue así"
   Día 21: "Última semana, ¡vamos!"
   Día 30: "¡Felicidades! Resultados en 24h"

4. Dashboard de competencia:
   - Ranking por % adherencia
   - Ranking por % pérdida peso
   - Ranking por engagement

RESULTADOS:
- 73 inscritos (146% objetivo)
- 52 completaron (71%)
- Pérdida promedio: 3.2kg
- Ganador: -5.1kg + 95% adherencia
- Nuevos members post-reto: 12
- Ingresos adicionales: $1,800
```

## Escenarios Especiales

### ES-1: Menor de Edad Requiere Consentimiento
```
CASO: Usuario de 16 años quiere seguir plan

FLUJO:
1. Sistema detecta edad < 18
2. Solicita email del padre/tutor
3. Envía correo con link único
4. Padre revisa plan y términos
5. Padre aprueba con firma digital
6. Sistema activa acceso al menor
7. Notificaciones copian al padre

SEGURIDAD:
- Token único expira en 48h
- Verificación doble email
- Registro completo en audit log
```

### ES-2: Embarazada Solicita Plan
```
DETECCIÓN:
screening.is_pregnant = true

RESPUESTA AUTOMÁTICA:
"Felicidades por tu embarazo 🤱

Por tu seguridad, recomendamos:
- Consultar con tu obstetra
- Plan especial embarazo (2,200+ cal)
- Sin restricciones calóricas
- Énfasis en ácido fólico, hierro, calcio

¿Tienes autorización médica? [Sí] [No]"

SI AUTORIZA:
- Plan especial maternidad
- Sin opciones pérdida peso
- Alertas de nutrientes críticos
```

### ES-3: Usuario Cambia de Gimnasio
```
ESCENARIO:
Usuario migra de Gym A → Gym B

PROCESO:
1. Usuario solicita "exportar datos"
2. Sistema genera:
   - Historial PDF
   - Datos JSON
   - Progreso gráficos

3. En nuevo gimnasio:
   - Opción "importar historial"
   - Mantiene preferencias
   - Nuevo screening (políticas diferentes)

PRIVACIDAD:
- Gym anterior no retiene datos
- Usuario controla su información
- Cumple GDPR/LGPD
```

## Flujos de Error

### ERR-1: Fallo en Generación IA
```
ERROR: OpenAI API timeout

MANEJO:
1. Retry automático (3 intentos)
2. Si falla:
   - Ofrecer template similar
   - Crédito para regenerar
   - Notificar admin

MENSAJE USUARIO:
"Hubo un problema generando tu plan.
 Mientras lo solucionamos, te ofrecemos
 estos planes similares: [...]

 También agregamos un crédito para
 regenerar cuando gustes."
```

### ERR-2: Screening Médico Crítico
```
DETECCIÓN:
risk_level = CRITICAL

BLOQUEO TOTAL:
"Por tu seguridad, no podemos continuar.

 Detectamos condiciones que requieren
 supervisión médica profesional:
 - [Lista de condiciones]

 Te recomendamos consultar con:
 - Médico general
 - Nutricionista clínico
 - Endocrinólogo

 El gimnasio puede referirte a
 profesionales de confianza."

ACCIONES:
- No permite override
- Registra en log permanente
- Notifica a admin
- Ofrece recursos alternativos
```

### ERR-3: Discrepancia en Tracking
```
PROBLEMA:
Usuario reporta 1,200 cal
IA detecta 2,000 cal en fotos

RESOLUCIÓN:
1. Sistema muestra discrepancia
2. Pregunta al usuario:
   "Detectamos diferencia en registro.
    ¿Qué prefieres hacer?
    [Mantener mi registro]
    [Usar análisis IA]
    [Promediar ambos]"

3. Aprende de decisión
4. Mejora precisión futura
```

## Casos de Éxito

### ÉXITO-1: Transformación Completa
```
USUARIO: Roberto, 35 años
INICIO: 95kg, 28% grasa
OBJETIVO: Perder 15kg

TIMELINE:
Mes 1: -4kg (Adherencia 85%)
Mes 2: -3kg (Adherencia 82%)
Mes 3: -3kg (Adherencia 88%)
Mes 4: -3kg (Adherencia 90%)
Mes 5: -2kg (Adherencia 92%)

FINAL: 80kg, 18% grasa

CLAVES DEL ÉXITO:
✓ Plan realista y sostenible
✓ Ajustes semanales con trainer
✓ Días libres planificados
✓ Soporte de comunidad
✓ Métricas más allá del peso

TESTIMONIO:
"No solo perdí peso, cambié mi
 relación con la comida. El sistema
 me enseñó a comer, no a hacer dieta."
```

### ÉXITO-2: Gimnasio Aumenta Retención
```
GYM: FitLife Centro
ANTES: 65% retención anual
DESPUÉS: 78% retención anual

FACTORES:
- Valor agregado sin costo extra
- Diferenciación vs competencia
- Mayor engagement diario
- Resultados medibles
- Comunidad más activa

MÉTRICAS:
- Members usando nutrición: 67%
- Satisfacción: 4.6/5
- Referencias nuevas: +23%
- Ingreso mensual: +$3,400
- ROI: 2,100% en 6 meses

CEO: "El módulo de nutrición transformó
      nuestro negocio. No es un gasto,
      es la mejor inversión que hicimos."
```

### ÉXITO-3: Trainer Escala Su Negocio
```
TRAINER: Ana López
ANTES: 20 clientes, 40h/semana
AHORA: 60 clientes, 35h/semana

CÓMO:
1. Automatización con IA (ahorra 10h/semana)
2. Templates reutilizables
3. Seguimiento automatizado
4. Consultas asistidas por IA
5. Grupos con planes similares

INGRESOS:
- Antes: $2,000/mes
- Ahora: $5,500/mes
- Horas trabajadas: -12%
- Satisfacción personal: +100%

"La IA no me reemplazó, me potenció.
 Ahora me enfoco en lo importante:
 la conexión humana y motivación."
```

---

**Siguiente:** [08_DECISION_PM.md](08_DECISION_PM.md) - Resumen ejecutivo para Product Manager