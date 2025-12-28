# Análisis: Templates de Notificaciones - IA vs Admin-Managed

**Fecha:** 24 de Diciembre, 2025
**Contexto:** Sistema de notificaciones de nutrición con mensajes hardcodeados
**Objetivo:** Personalizar mensajes por gym, idioma y contexto

---

## 📋 Contexto Actual

### Problema Identificado
- ❌ Mensajes **hardcodeados** en el código
- ❌ **Solo en español**
- ❌ No personalizables por gym
- ❌ Mismo mensaje para todos los contextos
- ❌ No se aprovecha contexto del plan/meal

### Ejemplo Actual
```python
# Hardcodeado en nutrition_notification_service.py
message = f"🌅 Hora de tu desayuno - {meal_name}"
# Mismo mensaje para TODOS los gyms, TODOS los usuarios
```

---

## 🎯 Enfoque 1: Templates Generados con IA

### 📝 Descripción

Usar GPT-4o-mini (ya integrado en el sistema) para generar mensajes personalizados basados en:
- Plan nutricional del usuario
- Meal específico del día
- Contexto (racha, logros, hora del día)
- Preferencias del gym
- Idioma del usuario

### 🏗️ Arquitectura Propuesta

```python
class AINotificationGenerator:
    """Genera notificaciones personalizadas con IA."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Ya se usa en nutrición

    async def generate_meal_reminder(
        self,
        meal: Meal,
        plan: NutritionPlan,
        user_context: dict
    ) -> dict:
        """
        Genera notificación personalizada para recordatorio de comida.

        Args:
            meal: Comida del día
            plan: Plan nutricional del usuario
            user_context: {
                "streak_days": 7,
                "completed_today": 2,
                "total_today": 5,
                "language": "es",
                "gym_tone": "motivational"  # motivational, neutral, friendly
            }

        Returns:
            {
                "title": "🔥 ¡7 días de racha! Hora de tu desayuno",
                "message": "Power Breakfast te espera. ¡Sigue brillando!",
                "tone": "motivational"
            }
        """
        prompt = self._build_prompt(meal, plan, user_context)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente de nutrición que crea notificaciones "
                        "motivacionales y personalizadas para recordatorios de comidas. "
                        "Debes ser breve (máx 100 caracteres), motivacional y específico."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    def _build_prompt(self, meal, plan, context):
        """Construye prompt para IA."""
        return f"""
Genera una notificación de recordatorio de comida con este contexto:

**Comida:**
- Nombre: {meal.name}
- Tipo: {meal.meal_type}
- Descripción: {meal.description or 'N/A'}

**Plan:**
- Título: {plan.title}
- Tipo: {plan.plan_type}

**Usuario:**
- Racha: {context.get('streak_days', 0)} días
- Comidas completadas hoy: {context['completed_today']}/{context['total_today']}
- Idioma: {context['language']}
- Tono deseado: {context['gym_tone']}

**Reglas:**
1. Título: Máximo 50 caracteres, incluir emoji relevante
2. Mensaje: Máximo 100 caracteres
3. Tono: {context['gym_tone']}
4. Idioma: {context['language']}
5. Si tiene racha >3 días, mencionarlo sutilmente
6. Ser específico con el nombre de la comida

Retorna JSON:
{{
    "title": "...",
    "message": "...",
    "tone": "{context['gym_tone']}"
}}
"""
```

### ✅ Ventajas

| Ventaja | Descripción | Impacto |
|---------|-------------|---------|
| **Zero-config** | Funciona inmediatamente sin setup | ⭐⭐⭐⭐⭐ |
| **Personalización extrema** | Cada notificación única según contexto | ⭐⭐⭐⭐⭐ |
| **Multiidioma automático** | Soporta cualquier idioma sin traducción manual | ⭐⭐⭐⭐⭐ |
| **Contextual** | Considera racha, logros, hora del día | ⭐⭐⭐⭐⭐ |
| **Evoluciona solo** | Mejora con nuevos contextos sin código | ⭐⭐⭐⭐ |
| **Testing A/B fácil** | Cambiar prompt y comparar engagement | ⭐⭐⭐⭐ |
| **Tono configurable** | Motivacional, neutral, friendly por gym | ⭐⭐⭐⭐ |
| **Sin mantenimiento** | No requiere actualizar templates | ⭐⭐⭐⭐⭐ |

### ❌ Desventajas

| Desventaja | Descripción | Mitigación |
|------------|-------------|------------|
| **Costo por notificación** | ~$0.0001-0.0002 por notificación | Cache resultados comunes |
| **Latencia** | 200-500ms por generación | Pre-generar y cachear |
| **Impredecible** | Puede generar mensajes inesperados | System prompt estricto + validación |
| **Depende de API** | Si OpenAI cae, no hay notificaciones | Fallback a templates simples |
| **No 100% control** | Gym no puede editar mensaje exacto | Configurar tono/estilo |
| **Rate limits** | Límites de OpenAI API | Batch processing + cache |

### 💰 Costo Estimado

**Modelo:** GPT-4o-mini
**Precio:** $0.150 / 1M tokens input, $0.600 / 1M tokens output

**Estimación por notificación:**
- Input tokens: ~400 tokens (prompt con contexto)
- Output tokens: ~50 tokens (JSON response)
- Costo input: $0.00006
- Costo output: $0.00003
- **Total: ~$0.00009 por notificación**

**Escenario real:**
- 1 gym con 100 usuarios activos
- 3 comidas/día
- 300 notificaciones/día
- **Costo diario: $0.027 (~$0.81/mes por gym)**

**Con 50 gyms:**
- 15,000 notificaciones/día
- **Costo: $1.35/día = $40.50/mes**

**Con cache (80% hit rate):**
- **Costo real: $8/mes para 50 gyms** ✅

### 🚀 Implementación

**Complejidad:** ⭐⭐ (Baja-Media)
**Tiempo:** 1-2 días

```python
# 1. Service (nuevo)
class AINotificationService:
    async def generate_notification(self, ...):
        # Verificar cache primero
        cache_key = f"notif:{meal_id}:{context_hash}"
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Generar con IA
        result = await self._generate_with_ai(...)

        # Cachear (TTL 7 días)
        await redis.setex(cache_key, 604800, json.dumps(result))
        return result

# 2. Integración en nutrition_notification_service.py
ai_service = AINotificationService()

# En send_meal_reminder():
notification_content = await ai_service.generate_notification(
    meal=meal,
    plan=plan,
    user_context={
        "streak_days": streak_days,
        "completed_today": completed_today,
        "total_today": total_today,
        "language": user.language or "es",
        "gym_tone": gym.notification_tone or "motivational"
    }
)

# Usar contenido generado
title = notification_content["title"]
message = notification_content["message"]
```

---

## 👤 Enfoque 2: Templates Admin-Managed

### 📝 Descripción

Los administradores del gym crean y gestionan templates de notificaciones desde un panel de administración.

### 🏗️ Arquitectura Propuesta

```sql
-- Tabla de templates
CREATE TABLE notification_templates (
    id SERIAL PRIMARY KEY,
    gym_id INTEGER REFERENCES gyms(id),  -- NULL = template global
    notification_type VARCHAR(50) NOT NULL,  -- meal_reminder_breakfast, achievement, etc.
    language VARCHAR(5) DEFAULT 'es',
    title_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    tone VARCHAR(20),  -- motivational, neutral, friendly
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(gym_id, notification_type, language)
);

-- Variables disponibles en templates
CREATE TABLE template_variables (
    id SERIAL PRIMARY KEY,
    notification_type VARCHAR(50),
    variable_name VARCHAR(50),
    description TEXT,
    example_value TEXT
);

-- Ejemplos de variables
INSERT INTO template_variables VALUES
    (1, 'meal_reminder', '{{meal_name}}', 'Nombre de la comida', 'Power Breakfast'),
    (2, 'meal_reminder', '{{meal_emoji}}', 'Emoji de la comida', '🌅'),
    (3, 'meal_reminder', '{{plan_title}}', 'Título del plan', 'Plan de Ganancia Muscular'),
    (4, 'meal_reminder', '{{streak_days}}', 'Días de racha', '7'),
    (5, 'meal_reminder', '{{user_name}}', 'Nombre del usuario', 'Juan');
```

### 🎨 UI de Administración

```
┌─────────────────────────────────────────────────────────┐
│  🔔 Configuración de Notificaciones                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tipo de Notificación: [Recordatorio de Desayuno ▼]    │
│  Idioma: [Español ▼]                                    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Título (máx 50 caracteres)                        │ │
│  │ {{meal_emoji}} Hora de tu desayuno                │ │
│  │                                                    │ │
│  │ Variables disponibles:                             │ │
│  │ • {{meal_name}} - Nombre de la comida             │ │
│  │ • {{meal_emoji}} - Emoji de la comida             │ │
│  │ • {{plan_title}} - Título del plan                │ │
│  │ • {{streak_days}} - Días de racha                 │ │
│  │ • {{user_name}} - Nombre del usuario              │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Mensaje (máx 100 caracteres)                      │ │
│  │ {{meal_name}} - {{plan_title}}                    │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  [Vista Previa]  [Guardar Template]  [Test Envío]     │
│                                                         │
│  ┌─── Vista Previa ──────────────────────────────────┐ │
│  │ 🌅 Hora de tu desayuno                            │ │
│  │ Power Breakfast - Plan de Ganancia Muscular       │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### ✅ Ventajas

| Ventaja | Descripción | Impacto |
|---------|-------------|---------|
| **Control total** | Admin decide mensaje exacto | ⭐⭐⭐⭐⭐ |
| **Branding consistente** | Tono de voz del gym | ⭐⭐⭐⭐⭐ |
| **Zero costo recurrente** | No hay costo por notificación | ⭐⭐⭐⭐⭐ |
| **Predecible** | Siempre el mismo mensaje | ⭐⭐⭐⭐⭐ |
| **Offline-first** | No depende de APIs externas | ⭐⭐⭐⭐⭐ |
| **Performance** | Instantáneo (solo replace) | ⭐⭐⭐⭐⭐ |
| **Audit trail** | Historial de cambios | ⭐⭐⭐⭐ |
| **Testing fácil** | Vista previa antes de enviar | ⭐⭐⭐⭐ |

### ❌ Desventajas

| Desventaja | Descripción | Impacto |
|------------|-------------|---------|
| **Requiere setup** | Admin debe configurar cada tipo | ⭐⭐⭐⭐ |
| **Mantenimiento manual** | Actualizar templates manualmente | ⭐⭐⭐ |
| **No contextual** | Mismo mensaje sin importar racha/logros | ⭐⭐⭐⭐ |
| **Multiidioma manual** | Traducir cada template | ⭐⭐⭐⭐ |
| **Carga admin** | Gym debe dedicar tiempo a configurar | ⭐⭐⭐ |
| **Curva aprendizaje** | Admin debe entender sistema de variables | ⭐⭐ |
| **Limitado** | Solo variables predefinidas | ⭐⭐⭐ |

### 💰 Costo Estimado

**Desarrollo:**
- Modelo + migración: 2 horas
- API endpoints (CRUD): 3 horas
- UI admin: 6-8 horas
- Tests: 2 horas
- **Total: 2-3 días**

**Costo recurrente:**
- **$0/mes** (sin costo por notificación)
- Storage en BD: negligible

**Costo de tiempo admin:**
- Setup inicial: 30-60 min por gym
- Mantenimiento: 15 min/mes

### 🚀 Implementación

**Complejidad:** ⭐⭐⭐ (Media)
**Tiempo:** 2-3 días

```python
# 1. Service
class NotificationTemplateService:
    def get_template(
        self,
        gym_id: int,
        notification_type: str,
        language: str = "es"
    ) -> NotificationTemplate:
        """Obtiene template para gym o global."""
        # Intentar template del gym primero
        template = db.query(NotificationTemplate).filter(
            NotificationTemplate.gym_id == gym_id,
            NotificationTemplate.notification_type == notification_type,
            NotificationTemplate.language == language,
            NotificationTemplate.is_active == True
        ).first()

        # Fallback a template global
        if not template:
            template = db.query(NotificationTemplate).filter(
                NotificationTemplate.gym_id == None,
                NotificationTemplate.notification_type == notification_type,
                NotificationTemplate.language == language,
                NotificationTemplate.is_active == True
            ).first()

        return template

    def render_template(
        self,
        template: NotificationTemplate,
        context: dict
    ) -> dict:
        """Renderiza template con variables."""
        title = template.title_template
        message = template.body_template

        # Simple string replacement
        for key, value in context.items():
            title = title.replace(f"{{{{{key}}}}}", str(value))
            message = message.replace(f"{{{{{key}}}}}", str(value))

        return {
            "title": title,
            "message": message,
            "tone": template.tone
        }

# 2. Uso en nutrition_notification_service.py
template_service = NotificationTemplateService()

template = template_service.get_template(
    gym_id=gym_id,
    notification_type="meal_reminder_breakfast",
    language=user.language or "es"
)

content = template_service.render_template(
    template=template,
    context={
        "meal_name": meal.name,
        "meal_emoji": get_meal_emoji(meal.meal_type),
        "plan_title": plan.title,
        "streak_days": streak_days,
        "user_name": user.first_name
    }
)
```

---

## 🔄 Enfoque 3: Híbrido (Recomendado)

### 📝 Descripción

Combinar lo mejor de ambos mundos:
- **Templates admin** como base
- **IA para personalización** cuando se configura

### 🏗️ Arquitectura

```python
class HybridNotificationService:
    """Servicio híbrido: Templates + IA opcional."""

    def __init__(self):
        self.template_service = NotificationTemplateService()
        self.ai_service = AINotificationService()

    async def generate_notification(
        self,
        gym_id: int,
        notification_type: str,
        context: dict
    ) -> dict:
        """
        Genera notificación usando template o IA según configuración del gym.
        """
        # Obtener configuración del gym
        gym = db.query(Gym).filter(Gym.id == gym_id).first()

        # Verificar si gym tiene AI activado
        if gym.ai_notifications_enabled:
            try:
                # Intentar con IA
                return await self.ai_service.generate_notification(context)
            except Exception as e:
                logger.warning(f"AI failed, fallback to template: {e}")
                # Fallback a template si IA falla

        # Usar template (default)
        template = self.template_service.get_template(
            gym_id=gym_id,
            notification_type=notification_type,
            language=context.get("language", "es")
        )

        return self.template_service.render_template(template, context)
```

### ✅ Ventajas del Híbrido

| Beneficio | Descripción |
|-----------|-------------|
| **Flexibilidad** | Gym elige: templates simples o IA |
| **Fallback robusto** | Si IA falla, usa template |
| **Gradual adoption** | Empezar con templates, migrar a IA |
| **Cost control** | Solo pagar IA si gym lo activa |
| **Best of both** | Control + Personalización |

### 📊 Configuración por Gym

```python
# Tabla Gym - agregar campos
class Gym:
    # ... campos existentes ...
    ai_notifications_enabled = Column(Boolean, default=False)
    notification_tone = Column(String(20), default="motivational")  # motivational, neutral, friendly
```

---

## 📊 Comparación Directa

| Criterio | IA | Admin-Managed | Híbrido |
|----------|-----|---------------|---------|
| **Setup inicial** | ⚡ Inmediato | ⏳ 30-60 min/gym | ⏳ 30-60 min/gym |
| **Personalización** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Costo mensual (50 gyms)** | $8-40/mes | $0/mes | $4-20/mes |
| **Mantenimiento** | Zero | Manual | Manual |
| **Multiidioma** | ⚡ Auto | 🔧 Manual | ⚡ Auto |
| **Control admin** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Complejidad dev** | ⭐⭐ (1-2 días) | ⭐⭐⭐ (2-3 días) | ⭐⭐⭐⭐ (3-4 días) |
| **Performance** | 200-500ms | <10ms | 10-500ms |
| **Confiabilidad** | ⭐⭐⭐ (depende API) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Contextual** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **UX Admin** | ⭐⭐⭐⭐⭐ (zero-config) | ⭐⭐⭐ (configurar todo) | ⭐⭐⭐⭐ |
| **UX Usuario** | ⭐⭐⭐⭐⭐ (único) | ⭐⭐⭐ (genérico) | ⭐⭐⭐⭐⭐ |

---

## 💡 Recomendación Final

### 🥇 Opción Recomendada: **HÍBRIDO con prioridad IA**

**Estrategia de implementación en fases:**

### **Fase 1 (MVP - 1 semana):**
1. ✅ Implementar generación con IA (GPT-4o-mini)
2. ✅ Cache agresivo (80% hit rate)
3. ✅ Templates hardcodeados como fallback
4. ✅ Activar para 2-3 gyms beta

**Esfuerzo:** 2-3 días
**Costo:** ~$2-5/mes inicialmente

### **Fase 2 (Mejora - 2 semanas después):**
1. Agregar modelo de templates en BD
2. UI admin básico para crear/editar templates
3. Variable substitution ({{meal_name}}, etc.)
4. Configuración por gym: AI on/off

**Esfuerzo:** 3-4 días
**Costo:** $0 adicional

### **Fase 3 (Optimización - 1 mes después):**
1. Analytics de engagement por tipo de notificación
2. A/B testing: IA vs Templates
3. Fine-tuning de prompts según datos
4. Multi-idioma automático

**Esfuerzo:** 2-3 días
**Costo:** Incluido en pricing

---

## 🎯 Por qué Híbrido con IA primero?

### ✅ Razones estratégicas:

1. **Time-to-market:** IA funciona en 1-2 días vs 2-3 días templates
2. **Mejor UX inicial:** Notificaciones únicas desde día 1
3. **Zero config:** Gyms no necesitan configurar nada
4. **Escalable:** Funciona desde 1 gym hasta 1000 gyms
5. **Ya tienes OpenAI:** API key ya configurada para nutrición
6. **Costo aceptable:** $8-20/mes para 50 gyms es negligible
7. **Datos para optimizar:** Aprendes qué funciona antes de hacer UI

### ⚠️ Pero mantén templates como backup:

1. **Reliability:** Si OpenAI cae, sistema sigue funcionando
2. **Cost control:** Si creces mucho, puedes apagar IA
3. **Compliance:** Algunos gyms pueden requerir control total
4. **Testing:** Fácil comparar engagement IA vs Templates

---

## 🚀 Plan de Acción Inmediato

### **Esta semana (2-3 días):**

```python
# 1. Crear AINotificationService
class AINotificationGenerator:
    # Implementación con GPT-4o-mini
    pass

# 2. Integrar en nutrition_notification_service.py
async def send_meal_reminder(...):
    # Intentar IA primero
    try:
        content = await ai_service.generate_notification(...)
    except:
        # Fallback a hardcoded
        content = {
            "title": f"{emoji} Hora de tu {meal_type}",
            "message": f"{meal_name} - {plan_title}"
        }

# 3. Cache agresivo
@cache(ttl=604800)  # 7 días
def get_or_generate_notification(...):
    pass
```

### **Próximo mes:**
- UI admin para templates (opcional)
- Analytics de engagement
- A/B testing

---

## 📊 Impacto Esperado

### Con IA:
- 📈 **+40-60% engagement** (notificaciones contextuales)
- 📈 **+25-35% retention** (mensajes personalizados)
- 📈 **+50% multiidioma** (sin trabajo extra)
- 💰 **$8-20/mes** costo total (50 gyms)

### Con Templates:
- 📈 **+15-25% engagement** (branding consistente)
- 📈 **+10-15% retention** (mejor que hardcoded)
- 📈 **0% multiidioma** (requiere traducción manual)
- 💰 **$0/mes** costo recurrente

---

## 🏁 Conclusión

**Respuesta corta:** Empieza con **IA** (1-2 días), agrega **templates admin** después (2-3 días).

**Por qué:**
1. IA da mejor ROI inmediato
2. Ya tienes OpenAI configurado
3. Costo muy bajo ($8-20/mes)
4. Zero-config para admins
5. Puedes iterar rápido

**Templates admin son útiles para:**
- Gyms que quieren control total
- Reducir costos si creces mucho
- Compliance/regulaciones específicas
- Backup si IA falla

**La combinación híbrida es el sweet spot:**
- Mejor UX (IA personalizada)
- Mejor confiabilidad (fallback a templates)
- Mejor ROI (engagement alto, costo bajo)

---

**Recomendación final:** 🚀 **Implementa IA esta semana, evalúa en 2-4 semanas, agrega templates si es necesario.**
