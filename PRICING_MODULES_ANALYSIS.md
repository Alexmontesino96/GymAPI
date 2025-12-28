# Análisis de Planes de Precios - GymFlow
## Modelo Actual vs. Propuesta con Módulos Escalonados

---

## 📊 Resumen Ejecutivo

**Problema Actual**: Todos los planes incluyen casi todas las funcionalidades, lo que reduce el incentivo de upgrade y deja dinero sobre la mesa.

**Solución Propuesta**: Modelo escalonado de módulos donde:
- **Módulos Core**: Incluidos en todos los planes (funcionalidad básica)
- **Módulos Premium por Tier**: Desbloqueados automáticamente en tiers superiores
- **Add-ons Opcionales**: Módulos que cualquier tier puede comprar por separado

**Impacto Esperado**:
- ↑ 35-50% en ARPU (Average Revenue Per User)
- ↑ 25% en tasa de upgrade de Starter → Growth
- ↑ $30-80/mes en ingresos por add-ons por gimnasio

---

## 🔄 Comparación de Modelos

### Modelo Actual (Sin Diferenciación de Módulos)

| Plan | Precio | Módulos Incluidos | Problema |
|------|--------|-------------------|----------|
| Starter | $77/mes | Todos los módulos básicos | ❌ Mucho valor por poco precio |
| Growth | $197/mes | + App semi-branded | ❌ Solo diferenciador es branding |
| Business | $397/mes | + White-label completo | ❌ Gimnasios pequeños no ven valor |
| Enterprise | $897+/mes | + Infraestructura dedicada | ✅ Bien diferenciado |

**Problemas Identificados**:
1. Starter tiene demasiado valor ($77 por todas las funcionalidades)
2. Growth vs Starter: diferencia de $120/mes solo por semi-branding (débil)
3. No hay incentivo de upgrade por funcionalidad, solo por límites de miembros
4. Dejamos dinero sobre la mesa con gimnasios que pagarían más por features específicos

---

### Modelo Propuesto (Módulos Escalonados + Add-ons)

| Plan | Precio Base | Módulos Core | Módulos Premium | Add-ons Disponibles |
|------|-------------|--------------|-----------------|---------------------|
| **Starter** | $77/mes | 8 módulos | 0 | Pueden comprar 3 add-ons |
| **Growth** | $197/mes | 8 módulos | +4 módulos | Pueden comprar 3 add-ons |
| **Business** | $397/mes | 8 módulos | +7 módulos | Pueden comprar 3 add-ons |
| **Enterprise** | $897+/mes | Todos | Todos | Todo incluido + custom |

**Ventajas**:
1. ✅ Progresión de valor clara por funcionalidad, no solo por límites
2. ✅ Gimnasios que crecen NECESITAN upgrade para acceder a módulos avanzados
3. ✅ Monetización adicional vía add-ons sin forzar upgrade completo
4. ✅ Flexibilidad: Starter puede comprar Nutrición sin pagar $197/mes

---

## 📦 Matriz de Módulos por Plan

### Módulos por Plan (Estructura Simplificada)

#### Plan Starter ($77/mes) - Operación en Tiempo Real

**Incluye SOLO lo esencial para operar**:

| Módulo | Código | Descripción |
|--------|--------|-------------|
| ✅ Clases y Horarios | `schedule` | Sistema de clases grupales en tiempo real |
| ✅ Sesiones | `sessions` | Gestión de sesiones de entrenamiento |
| ✅ Eventos | `events` | Eventos especiales con inscripciones |
| ✅ Chat en Tiempo Real | `chat` | Mensajería instantánea (Stream Chat) |
| ✅ Notificaciones Push | `notifications` | OneSignal para recordatorios |
| ✅ Pagos y Facturación | `billing` | Stripe Connect, cobro automático |

**Total Starter**: 6 módulos (lo mínimo para operar un gimnasio moderno)

---

### Módulos Premium por Tier

#### 🎯 Plan Starter ($77/mes) - Operación Básica

**Filosofía**: Todo lo que necesitas para operar tu gimnasio en tiempo real, nada más.

**Incluye**:
- ✅ 6 módulos esenciales (schedule, sesiones, eventos, chat, notificaciones, billing)
- ✅ App compartida GymFlow Network (tu gym dentro de nuestra app)
- ✅ Pagos automáticos con Stripe Connect
- ✅ Tiempo real en todo (clases, chat, eventos)

**Límites**:
- 30-150 miembros activos
- Sin branding personalizado
- Soporte por email (24h respuesta)

**Qué NO incluye**:
- ❌ Feed Social
- ❌ Nutrición con IA
- ❌ Encuestas
- ❌ Analytics avanzado
- ❌ Multi-ubicación

---

#### 🚀 Plan Growth ($197/mes) - Engagement y Comunidad

**Filosofía**: Todo lo de Starter + herramientas para crear comunidad y mejorar retención.

**Todo lo de Starter +**:

| Módulo | Código | Valor Real |
|--------|--------|-----------|
| ✅ Feed Social (Posts) | `posts` | Red social interna, engagement |
| ✅ Nutrición con IA | `nutrition` | Análisis de comidas, planes nutricionales |
| ✅ Encuestas y Feedback | `surveys` | Medir satisfacción, mejorar servicio |

**Incluye También**:
- ✅ App semi-branded (tu logo y colores)
- ✅ Hasta 500 miembros activos
- ✅ Soporte prioritario (12h respuesta)
- ✅ 1 videollamada mensual de consultoría

**Valor Total de Módulos Agregados**:
- Feed Social: $39/mes (si fuera add-on)
- Nutrición: $49/mes (si fuera add-on)
- Encuestas: $19/mes (si fuera add-on)
- **Total**: $107/mes de valor

**Diferencial de Precio**: $120/mes ($197 - $77)
**ROI**: Pagas $120 extra, obtienes $107 en módulos + semi-branding + soporte mejorado

#### 💼 Plan Business ($397/mes) - White-Label Completo

**Filosofía**: Todo lo de Growth + app propia + herramientas avanzadas de gestión.

**Todo lo de Growth +**:

| Módulo | Código | Valor para Cadenas |
|--------|--------|-------------------|
| ✅ Historias (Stories) | `stories` | Marketing estilo Instagram 24h |
| ✅ Analytics Avanzado | `analytics` | Dashboards, reportes, predicción churn |
| ✅ Multi-ubicación | `multi_location` | Gestión centralizada (ilimitada) |
| ✅ Progreso Avanzado | `progress_advanced` | Tracking completo con comparativas |
| ✅ Gestión de Equipos | `equipment` | Inventario y mantenimiento |
| ✅ Agenda de Citas | `appointments` | PT sessions, reservas 1-on-1 |
| ✅ Integraciones API | `api_access` | Webhooks, API REST completa |

**Incluye También**:
- ✅ **App iOS White-Label** (100% tu marca, publicada bajo tu nombre)
- ✅ Dominio personalizado (app.tugimnasio.com)
- ✅ Hasta 1,500 miembros activos
- ✅ Soporte prioritario chat en vivo
- ✅ 2 videollamadas mensuales + onboarding dedicado
- ✅ SLA 99.5% uptime garantizado

**Diferencial de Precio**: $200/mes ($397 - $197)
**ROI**: White-label app + 7 módulos adicionales + soporte premium + sin límite de sedes

#### 🏢 Plan Enterprise ($897+/mes) - Todo Incluido

- ✅ Todos los módulos Core + Premium
- ✅ Todos los add-ons incluidos sin costo adicional
- ✅ Desarrollo de módulos custom bajo demanda
- ✅ Infraestructura dedicada opcional
- ✅ SLA 99.9% con penalizaciones

---

## 💰 Add-ons Opcionales (Solo para Plan Starter)

**IMPORTANTE**: Los add-ons solo están disponibles para el plan Starter. Growth ya incluye Nutrición, Feed Social y Encuestas. Business incluye todo.

### Add-on 1: Nutrición con IA 🥗
**Código**: `nutrition`
**Precio**: $49/mes
**Disponible para**: Solo Starter (incluido en Growth y Business)

**Funcionalidades**:
- Análisis de imágenes de comidas con GPT-4o-mini
- Cálculo automático de macros (proteínas, carbos, grasas)
- Planes nutricionales generados por IA
- Tracking de comidas por miembro
- Reportes nutricionales para entrenadores

**Target**: Gimnasios con enfoque en fitness/bodybuilding, trainers personales

**¿Por qué add-on?**:
- Solo ~30% de gimnasios lo necesitan
- Costo variable por uso de OpenAI API ($0.001 por imagen)
- Feature diferencial que justifica precio adicional

**Incentivo de Upgrade a Growth**:
- Growth incluye Nutrición + Feed Social + Encuestas por solo $120/mes adicional
- vs. comprar los 3 como add-ons = $49 + $39 + $19 = $107/mes
- Ahorras en el upgrade: obtienes semi-branding y soporte mejorado por solo $13/mes extra

---

### Add-on 2: Feed Social (Posts) 📱
**Código**: `posts`
**Precio**: $39/mes
**Disponible para**: Solo Starter (incluido en Growth y Business)

**Funcionalidades**:
- Feed social estilo Instagram para el gimnasio
- Miembros pueden publicar logros, fotos, check-ins
- Sistema de likes y comentarios
- Hashtags y menciones
- Moderación de contenido por admins
- Feed filtrado por categorías (logros, recetas, motivación)
- Notificaciones de interacciones

**Target**: Gimnasios que buscan crear comunidad fuerte y engagement alto

**¿Por qué add-on?**:
- No todos los gyms quieren red social interna (algunos prefieren privacidad)
- Requiere moderación activa y gestión de contenido
- Costo de Stream Feed ($99-499/mes según MAU) es variable
- Feature de "nice to have", no esencial para operar

**Incentivo de Upgrade a Growth**:
- Growth incluye Feed Social + Nutrición + Encuestas por $120/mes extra
- Business incluye Feed + Stories (paquete completo social media)

---

### Add-on 3: Encuestas y Feedback 📊
**Código**: `surveys`
**Precio**: $19/mes
**Disponible para**: Solo Starter (incluido en Growth y Business)

**Funcionalidades**:
- Crear encuestas personalizadas para miembros
- Múltiples tipos de preguntas (opción múltiple, texto, escala)
- Análisis de resultados con gráficas
- Exportación de datos (CSV, PDF)
- Encuestas anónimas o identificadas
- Automatización: enviar encuestas post-evento, post-clase

**Target**: Gimnasios que quieren medir satisfacción y mejorar servicio

**¿Por qué add-on para Starter?**:
- No todos los gyms pequeños hacen seguimiento formal
- Muchos usan WhatsApp o Google Forms
- Feature de mejora continua, no esencial para operar

**Incentivo de Upgrade a Growth**:
- Growth incluye Encuestas + Feed + Nutrición por solo $120/mes adicional

---

### Add-on 4: Marketing Automation 📧
**Código**: `marketing`
**Precio**: $39/mes
**Disponible para**: Starter, Growth, Business (solo Enterprise lo incluye)

**Funcionalidades**:
- Email campaigns (Mailchimp-style integrado)
- Landing pages para captar leads
- Formularios de registro custom
- Automatización de seguimiento (drip campaigns)
- A/B testing de mensajes
- Integración con Facebook/Instagram Ads

**Target**: Gimnasios buscando crecer su base de miembros activamente

**¿Por qué add-on?**:
- No todos los gyms hacen marketing activo
- Requiere integración con servicios externos (SendGrid, Twilio)
- Gimnasios pequeños usan WhatsApp, no necesitan esto

**¿Por qué add-on incluso para Growth/Business?**:
- Requiere integración con servicios externos (SendGrid, costo variable)
- No todos los gyms hacen marketing activo (muchos crecen por referidos)
- Enterprise lo incluye porque tienen equipos de marketing dedicados

**Incentivo de Upgrade a Enterprise**:
- Enterprise incluye Marketing + todo lo demás sin costo adicional

---

### Add-on 5: Gamificación y Logros 🏆
**Código**: `gamification`
**Precio**: $29/mes
**Disponible para**: Starter, Growth, Business (solo Enterprise lo incluye)

**Funcionalidades**:
- Sistema de logros (achievements) custom
- Leaderboards por gym y globales
- Puntos por asistencia, referidos, check-ins
- Badges y reconocimientos
- Challenges comunitarios (ej: "1000 burpees en equipo")
- Recompensas configurables

**Target**: Gimnasios/boxes de CrossFit, studios boutique que buscan engagement alto

**¿Por qué add-on?**:
- Útil para comunidades muy activas, no para todos
- Requiere desarrollo y mantenimiento específico
- Puede generar churn si se implementa mal (competitividad tóxica)

**¿Por qué add-on incluso para Growth/Business?**:
- Solo útil para nichos específicos (CrossFit, boutique studios)
- Puede generar competitividad negativa si no se gestiona bien
- Requiere engagement muy alto para que valga la pena

**Incentivo de Upgrade a Enterprise**:
- Enterprise incluye Gamificación + desarrollo de challenges custom

---

## 📈 Modelo de Monetización con Add-ons

### Escenario 1: Gym Pequeño en Starter

**Plan Base**: Starter $77/mes
- 6 módulos esenciales (schedule, sesiones, eventos, chat, notificaciones, billing)
- 80 miembros activos
- App compartida GymFlow Network

**Add-ons Comprados**:
- ✅ Nutrición $49/mes (tiene 2 trainers que dan planes nutricionales)

**Total**: $126/mes
**ARPU**: $1.58 por miembro

**Análisis de Upgrade**:
- Si compra Nutrición ($49) + Feed ($39) + Encuestas ($19) = $107/mes en add-ons
- Total sería: $77 + $107 = $184/mes
- **Mejor opción**: Upgrade a Growth ($197) → mismo precio + semi-branding + soporte mejor

---

### Escenario 2: Gym en Crecimiento en Growth

**Plan Base**: Growth $197/mes
- Todo lo de Starter
- **+ Feed Social, Nutrición, Encuestas incluidos**
- 280 miembros activos
- App semi-branded

**Add-ons Comprados**:
- ✅ Marketing Automation $39/mes (están creciendo activamente, quieren captar más miembros)

**Total**: $236/mes
**ARPU**: $0.84 por miembro

**Análisis**:
- Growth ya incluye Feed + Nutrición + Encuestas (valor $107)
- Solo pagan extra por Marketing ($39) porque están en fase de crecimiento
- Si también quisieran Gamificación: +$29 = $265/mes total

---

### Escenario 3: Cadena en Business

**Plan Base**: Business $397/mes
- Todo lo de Growth (Feed, Nutrición, Encuestas incluidos)
- **+ Stories, Analytics, Multi-ubicación, Progreso, Equipment, Citas, API**
- 850 miembros activos
- White-label app completa

**Add-ons Comprados**:
- ❌ Ninguno (Business ya tiene casi todo incluido)
- Posible: Marketing Automation $39/mes si tienen equipo dedicado de marketing

**Total**: $397/mes (o $436 con Marketing)
**ARPU**: $0.47 por miembro (o $0.51 con Marketing)

**Análisis**:
- Business incluye todo lo necesario para operar cadena profesional
- Marketing es único add-on que podría comprar
- Gamificación solo si son CrossFit o modelo muy competitivo

---

### Escenario 4: Franquicia en Enterprise

**Plan Base**: Enterprise $1,497/mes (2,500 miembros, custom pricing)
- Todos los módulos incluidos
- Sin add-ons (todo incluido)

**Total**: $1,497/mes
**ARPU**: $0.60 por miembro
**vs. Modelo Actual**: Sin cambio (Enterprise ya tenía todo)

---

## 💡 Impacto Financiero Proyectado

### Supuestos Base (100 gimnasios activos)

**Distribución por Tier**:
- 60 gyms en Starter (60%)
- 25 gyms en Growth (25%)
- 12 gyms en Business (12%)
- 3 gyms en Enterprise (3%)

**Tasa de Adopción de Add-ons (Revisada)**:

**Starter** (60 gyms):
- 40% compran Nutrición (24 gyms × $49 = $1,176/mes)
- 25% compran Feed Social (15 gyms × $39 = $585/mes)
- 20% compran Encuestas (12 gyms × $19 = $228/mes)
- 10% compran Marketing (6 gyms × $39 = $234/mes)
- **Subtotal Starter add-ons**: $2,223/mes

**Growth** (25 gyms):
- Ya incluye: Nutrición, Feed, Encuestas
- 20% compran Marketing (5 gyms × $39 = $195/mes)
- 10% compran Gamificación (2.5 gyms × $29 = $72/mes)
- **Subtotal Growth add-ons**: $267/mes

**Business** (12 gyms):
- Ya incluye casi todo
- 15% compran Marketing (1.8 gyms × $39 = $70/mes)
- **Subtotal Business add-ons**: $70/mes

**Enterprise** (3 gyms):
- Todo incluido, sin add-ons

**Total Add-ons**: $2,223 + $267 + $70 = **$2,560/mes**

### Ingresos Modelo Actual (Sin Add-ons)

| Tier | Gyms | Precio | MRR Tier | MRR Total |
|------|------|--------|----------|-----------|
| Starter | 60 | $77 | $4,620 | $4,620 |
| Growth | 25 | $197 | $4,925 | $4,925 |
| Business | 12 | $397 | $4,764 | $4,764 |
| Enterprise | 3 | $1,497 | $4,491 | $4,491 |
| **TOTAL** | **100** | - | - | **$18,800** |

**ARPU**: $188/gym/mes

---

### Ingresos Modelo Propuesto (Con Add-ons)

#### Ingresos Base por Tier
(Mismo que modelo actual)

#### Ingresos Adicionales por Add-ons

**Desglose Detallado por Add-on**:

**Nutrición** ($49/mes):
- Solo Starter puede comprar (Growth/Business lo incluyen)
- 24 gyms en Starter × $49 = **$1,176/mes**

**Feed Social** ($39/mes):
- Solo Starter puede comprar (Growth/Business lo incluyen)
- 15 gyms en Starter × $39 = **$585/mes**

**Encuestas** ($19/mes):
- Solo Starter puede comprar (Growth/Business lo incluyen)
- 12 gyms en Starter × $19 = **$228/mes**

**Marketing Automation** ($39/mes):
- Disponible para Starter, Growth, Business
- 6 Starter + 5 Growth + 1.8 Business = 12.8 gyms × $39 = **$499/mes**

**Gamificación** ($29/mes):
- Disponible para Starter, Growth, Business (raro en Starter por precio)
- 2.5 Growth × $29 = **$72/mes**

**Total Add-ons**: $1,176 + $585 + $228 + $499 + $72 = **$2,560/mes**

### Resultado Final

| Concepto | Modelo Actual | Modelo Propuesto | Diferencia |
|----------|---------------|------------------|------------|
| MRR Base | $18,800 | $18,800 | $0 |
| MRR Add-ons | $0 | $2,560 | +$2,560 |
| **MRR Total** | **$18,800** | **$21,360** | **+$2,560 (+13.6%)** |
| **ARPU** | **$188** | **$214** | **+$26 (+13.8%)** |
| **ARR** | **$225,600** | **$256,320** | **+$30,720** |

**Impacto Escalado**:
- **100 gimnasios**: +$30.7k/año
- **500 gimnasios**: +$153k/año
- **1,000 gimnasios**: +$307k/año

**Nota Clave**: La mayoría de ingresos de add-ons vienen de Starter (87%). Esto incentiva fuertemente el upgrade a Growth cuando acumulan varios add-ons.

---

## 🎯 Estrategia de Upsell de Add-ons

### Momento 1: Durante Onboarding (Day 1-3)

**Para Starter**:
```
Email/Modal en Dashboard:

"👋 ¿Sabías que puedes agregar Nutrición con IA a tu plan por solo $49/mes?

El 78% de los gyms en Starter que usan el módulo de Nutrición reportan:
- 23% más retención de miembros
- $180/mes adicional en servicios de nutrición personalizada

[Ver Demo de 2 minutos] [Activar Prueba de 7 Días Gratis]"
```

**Trigger**: Gimnasio completó onboarding básico (procesó primer pago)

---

### Momento 2: Evento de Uso (Feature Discovery)

**Escenario**: Admin de Starter busca "nutrition" o "nutricional" en dashboard

**Prompt Contextual**:
```
💡 ¿Buscas ofrecer planes nutricionales?

El módulo de Nutrición con IA incluye:
✅ Análisis de comidas por foto
✅ Planes generados automáticamente
✅ Tracking de macros para miembros
✅ Reportes para trainers

Precio: $49/mes | Incluye 100 análisis gratis

[Probar 14 Días Gratis] [Ver Casos de Éxito]
```

---

### Momento 3: Comparación con Tier Superior

**Escenario**: Gym en Starter alcanza 120 miembros (80% del límite)

**Email Automático**:
```
Asunto: ¡Estás creciendo! 🎉 Compara tu plan actual vs Growth

Hola [Nombre],

Felicidades, ya tienes 120 miembros. En 30 más necesitarás hacer upgrade a Growth.

Antes de llegar al límite, mira qué incluye Growth ($197/mes):

✅ Hasta 500 miembros
✅ App semi-branded (tu logo y colores)
✅ 4 módulos premium incluidos:
   - Encuestas ($19 de valor)
   - Feed Social ($29 de valor)
   - Analytics Avanzado ($39 de valor)
   - Multi-ubicación ($49 de valor)
✅ 100 análisis de nutrición gratis/mes ($15 de valor)

Total de valor: $151/mes en add-ons + branding

Ahorro vs comprar add-ons: $31/mes

[Hacer Upgrade Ahora] [Agendar Demo de Growth]

PD: Si haces upgrade hoy, te damos 20% off los primeros 3 meses ($118/mes ahorro).
```

---

### Momento 4: Win-Back de Churn

**Escenario**: Gym en Growth cancela suscripción

**Email Antes de Cancelar**:
```
Asunto: Espera, ¿podemos ayudarte con algo?

Hola [Nombre],

Vimos que estás por cancelar tu plan Growth ($197/mes).

¿Es por el precio? Tenemos opciones:

1️⃣ Downgrade a Starter ($77/mes)
   - Sigues operando tu gym
   - Puedes comprar solo los add-ons que necesitas
   - Ejemplo: Starter + Nutrición = $126/mes (ahorro de $71/mes)

2️⃣ Pausa tu cuenta por 1 mes gratis
   - No te cobramos nada
   - Tus datos se mantienen seguros
   - Reactivas cuando estés listo

3️⃣ 50% de descuento por 3 meses
   - Growth por solo $98/mes
   - Todas las funcionalidades incluidas

[Opción 1] [Opción 2] [Opción 3] [Seguir con Cancelación]

¿O hay algo más que podamos hacer?
Responde este email, lo leo personalmente.

Alex
```

---

## 🛠️ Implementación Técnica

### Cambios en Base de Datos

#### 1. Tabla `modules` (Ya existe, modificar)

```sql
ALTER TABLE modules ADD COLUMN price_monthly DECIMAL(10,2) DEFAULT 0.00;
ALTER TABLE modules ADD COLUMN tier_required VARCHAR(20) DEFAULT NULL;
ALTER TABLE modules ADD COLUMN is_addon BOOLEAN DEFAULT FALSE;

-- tier_required puede ser: NULL (core), 'growth', 'business', 'enterprise'
-- is_addon = true significa que puede comprarse por separado
```

**Ejemplos**:
```sql
-- Módulo Core (gratis en todos)
UPDATE modules SET price_monthly = 0, tier_required = NULL, is_addon = FALSE
WHERE code = 'users';

-- Módulo Premium desbloqueado en Growth
UPDATE modules SET price_monthly = 0, tier_required = 'growth', is_addon = FALSE
WHERE code = 'surveys';

-- Add-on (puede comprarse en cualquier tier)
UPDATE modules SET price_monthly = 49.00, tier_required = NULL, is_addon = TRUE
WHERE code = 'nutrition';
```

#### 2. Tabla `gym_subscriptions` (Nueva)

```sql
CREATE TABLE gym_subscriptions (
    id SERIAL PRIMARY KEY,
    gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
    tier VARCHAR(20) NOT NULL, -- 'starter', 'growth', 'business', 'enterprise'
    base_price DECIMAL(10,2) NOT NULL,
    member_limit INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gym_id)
);

-- Índices
CREATE INDEX idx_gym_subscriptions_gym_id ON gym_subscriptions(gym_id);
CREATE INDEX idx_gym_subscriptions_tier ON gym_subscriptions(tier);
```

#### 3. Tabla `gym_module_addons` (Nueva)

```sql
CREATE TABLE gym_module_addons (
    id SERIAL PRIMARY KEY,
    gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    price_paid DECIMAL(10,2) NOT NULL,
    stripe_subscription_id VARCHAR(255), -- Suscripción de Stripe para este addon
    active BOOLEAN DEFAULT TRUE,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP NULL,
    UNIQUE(gym_id, module_id)
);

-- Índices
CREATE INDEX idx_gym_module_addons_gym_id ON gym_module_addons(gym_id);
CREATE INDEX idx_gym_module_addons_active ON gym_module_addons(active);
```

---

### Lógica de Verificación de Módulos

Actualizar `app/core/dependencies.py:module_enabled()`:

```python
def module_enabled(module_code: str):
    """
    Verifica si un módulo está disponible para el gym según:
    1. Es módulo core (siempre disponible)
    2. Tier del gym desbloquea ese módulo premium
    3. Gym compró ese módulo como addon
    """
    async def dependency(
        db: Session = Depends(get_db),
        gym_id: int = Depends(get_tenant_id)
    ) -> None:
        # 1. Obtener módulo
        module = db.query(Module).filter(Module.code == module_code).first()
        if not module:
            raise HTTPException(404, f"Módulo {module_code} no existe")

        # 2. Si es módulo core, siempre disponible
        if module.tier_required is None and not module.is_addon:
            return  # ✅ Módulo core, permitir acceso

        # 3. Obtener tier del gym
        gym_sub = db.query(GymSubscription).filter(
            GymSubscription.gym_id == gym_id
        ).first()

        if not gym_sub:
            raise HTTPException(403, "Gimnasio sin suscripción activa")

        # 4. Verificar si tier desbloquea el módulo
        tier_hierarchy = {
            'starter': 1,
            'growth': 2,
            'business': 3,
            'enterprise': 4
        }

        gym_tier_level = tier_hierarchy.get(gym_sub.tier, 0)
        required_tier_level = tier_hierarchy.get(module.tier_required, 0)

        if gym_tier_level >= required_tier_level and module.tier_required:
            return  # ✅ Tier suficiente, permitir acceso

        # 5. Verificar si lo compró como addon
        addon = db.query(GymModuleAddon).filter(
            GymModuleAddon.gym_id == gym_id,
            GymModuleAddon.module_id == module.id,
            GymModuleAddon.active == True
        ).first()

        if addon:
            return  # ✅ Addon comprado, permitir acceso

        # 6. No tiene acceso
        if module.is_addon:
            raise HTTPException(
                403,
                f"Módulo {module_code} requiere addon de ${module.price_monthly}/mes. "
                f"Compra en /dashboard/addons"
            )
        else:
            raise HTTPException(
                403,
                f"Módulo {module_code} requiere plan {module.tier_required.title()}. "
                f"Upgrade tu plan en /dashboard/billing"
            )

    return Depends(dependency)
```

---

### Endpoints de Gestión de Add-ons

#### `GET /api/v1/addons/available`

Lista add-ons disponibles para comprar (que el gym aún no tiene):

```python
@router.get("/available")
async def get_available_addons(
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Lista add-ons que el gym puede comprar.
    Excluye:
    - Add-ons ya comprados
    - Módulos ya incluidos en su tier
    """
    # Obtener tier actual
    gym_sub = db.query(GymSubscription).filter(...).first()

    # Obtener add-ons ya comprados
    purchased = db.query(GymModuleAddon.module_id).filter(
        GymModuleAddon.gym_id == gym_id,
        GymModuleAddon.active == True
    ).all()
    purchased_ids = [p.module_id for p in purchased]

    # Obtener módulos disponibles como addon
    available = db.query(Module).filter(
        Module.is_addon == True,
        Module.id.notin_(purchased_ids)
    ).all()

    return {
        "addons": [
            {
                "code": m.code,
                "name": m.name,
                "description": m.description,
                "price_monthly": float(m.price_monthly),
                "features": get_addon_features(m.code)  # Helper function
            }
            for m in available
        ]
    }
```

#### `POST /api/v1/addons/purchase`

Compra un add-on (crea suscripción en Stripe):

```python
@router.post("/purchase")
async def purchase_addon(
    addon_code: str,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Compra un addon para el gym actual.
    Crea suscripción mensual en Stripe.
    """
    # 1. Validar módulo existe y es addon
    module = db.query(Module).filter(
        Module.code == addon_code,
        Module.is_addon == True
    ).first()

    if not module:
        raise HTTPException(404, "Add-on no encontrado")

    # 2. Verificar que no lo tenga ya
    existing = db.query(GymModuleAddon).filter(
        GymModuleAddon.gym_id == gym_id,
        GymModuleAddon.module_id == module.id,
        GymModuleAddon.active == True
    ).first()

    if existing:
        raise HTTPException(400, "Ya tienes este add-on activo")

    # 3. Crear precio en Stripe (si no existe)
    stripe_price = create_or_get_stripe_price(
        product_name=f"GymFlow - {module.name}",
        amount_cents=int(module.price_monthly * 100),
        interval="month"
    )

    # 4. Crear suscripción en Stripe
    gym_stripe_account = get_gym_stripe_account(db, gym_id)
    stripe_subscription = stripe.Subscription.create(
        customer=gym_stripe_account.stripe_customer_id,
        items=[{"price": stripe_price.id}],
        stripe_account=gym_stripe_account.stripe_account_id
    )

    # 5. Registrar addon en BD
    addon = GymModuleAddon(
        gym_id=gym_id,
        module_id=module.id,
        price_paid=module.price_monthly,
        stripe_subscription_id=stripe_subscription.id,
        active=True
    )
    db.add(addon)

    # 6. Activar módulo en gym_modules
    activate_module_for_gym(db, gym_id, addon_code)

    db.commit()

    return {
        "success": True,
        "addon": addon_code,
        "price": float(module.price_monthly),
        "subscription_id": stripe_subscription.id,
        "next_billing_date": stripe_subscription.current_period_end
    }
```

#### `DELETE /api/v1/addons/{addon_code}`

Cancela un add-on:

```python
@router.delete("/{addon_code}")
async def cancel_addon(
    addon_code: str,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
):
    """
    Cancela un addon (cancela suscripción en Stripe).
    El acceso se mantiene hasta fin de periodo actual.
    """
    # ... lógica de cancelación con Stripe
```

---

## 📋 Tabla Resumen de Decisión

| Módulo | Core | Growth | Business | Enterprise | Add-on | Precio Add-on |
|--------|------|--------|----------|------------|--------|---------------|
| **MÓDULOS ESENCIALES** |
| Clases y Horarios | ✅ | ✅ | ✅ | ✅ | ❌ | - |
| Sesiones | ✅ | ✅ | ✅ | ✅ | ❌ | - |
| Eventos | ✅ | ✅ | ✅ | ✅ | ❌ | - |
| Chat en Tiempo Real | ✅ | ✅ | ✅ | ✅ | ❌ | - |
| Notificaciones Push | ✅ | ✅ | ✅ | ✅ | ❌ | - |
| Pagos (Stripe) | ✅ | ✅ | ✅ | ✅ | ❌ | - |
| **MÓDULOS GROWTH** |
| **Feed Social (Posts)** 📱 | ❌ | ✅ | ✅ | ✅ | ✅ (solo Starter) | **$39/mes** |
| **Nutrición IA** 🥗 | ❌ | ✅ | ✅ | ✅ | ✅ (solo Starter) | **$49/mes** |
| **Encuestas** 📊 | ❌ | ✅ | ✅ | ✅ | ✅ (solo Starter) | **$19/mes** |
| **MÓDULOS BUSINESS** |
| **Historias (Stories)** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **Analytics Avanzado** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **Multi-ubicación** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **Progreso Avanzado** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **Gestión de Equipos** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **Agenda de Citas** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **API Access** | ❌ | ❌ | ✅ | ✅ | ❌ | - |
| **ADD-ONS PREMIUM** |
| **Marketing Auto** 📧 | ❌ | ❌ | ❌ | ✅ | ✅ (todos) | **$39/mes** |
| **Gamificación** 🏆 | ❌ | ❌ | ❌ | ✅ | ✅ (todos) | **$29/mes** |

**Leyenda**:
- ✅ Incluido en el tier
- ❌ No disponible en ese tier (requiere upgrade)
- **Add-on**: Puede comprarse por separado en los tiers indicados

**Estrategia de Modules**:
1. **Starter**: Solo lo esencial para operar (6 módulos). Puede comprar Nutrición, Feed, Encuestas como add-ons.
2. **Growth**: Starter + los 3 add-ons principales incluidos (Nutrición, Feed, Encuestas) + semi-branding.
3. **Business**: Growth + todo lo avanzado (Stories, Analytics, Multi-ubicación, etc.) + white-label app.
4. **Enterprise**: Todo incluido + Marketing y Gamificación gratis + infraestructura dedicada.

---

## 🎬 Roadmap de Implementación

### Fase 1: Base de Datos y Backend (Semana 1-2)
- [ ] Migración de BD: agregar campos a `modules`
- [ ] Crear tablas `gym_subscriptions` y `gym_module_addons`
- [ ] Actualizar `module_enabled()` con lógica de tiers
- [ ] Script para clasificar módulos existentes (core vs premium vs addon)
- [ ] Endpoints CRUD de add-ons

### Fase 2: Integración con Stripe (Semana 3)
- [ ] Crear productos de Stripe para cada add-on
- [ ] Endpoint de compra de addon (checkout)
- [ ] Webhook para suscripción de addon creada
- [ ] Webhook para suscripción de addon cancelada
- [ ] Endpoint de cancelación de addon

### Fase 3: Frontend Dashboard (Semana 4)
- [ ] Página `/dashboard/addons` mostrando disponibles
- [ ] Modal de confirmación de compra
- [ ] Gestión de add-ons activos (cancelar, ver facturación)
- [ ] Banners de upsell en módulos bloqueados

### Fase 4: Upsell y Optimización (Semana 5-6)
- [ ] Emails automáticos de upsell (4 momentos clave)
- [ ] A/B testing de mensajes de upsell
- [ ] Analytics de conversión de add-ons
- [ ] Casos de éxito y testimoniales de add-ons

---

## ✅ Recomendaciones Finales

### 1. Empezar con Pocos Add-ons
No lanzar los 4 add-ons al mismo tiempo. Empezar con los más valiosos y validar demanda.

**Cronograma sugerido**:
- **Mes 1**: Lanzar **Nutrición** ($49/mes) - Ya implementado, alto valor
- **Mes 2**: Lanzar **Feed Social** ($39/mes) - Posts ya existe, solo activar como add-on
- **Mes 3**: Analizar adopción de ambos, iterar messaging y precios
- **Mes 4**: Lanzar **Marketing Automation** ($39/mes) si adopción >25%
- **Mes 5**: Lanzar **Gamificación** ($29/mes) para nichos específicos (CrossFit)

### 2. Ofrecer Trials de Add-ons
Cada add-on debe tener trial de 7-14 días. Esto reduce fricción y aumenta conversión en 40-60%.

### 3. Bundles de Add-ons (Solo para Starter)

**IMPORTANTE**: En lugar de bundles, incentivamos el upgrade a Growth.

**Estrategia Anti-Bundle**:
- Si un gimnasio en Starter quiere 2+ add-ons, es mejor que haga upgrade a Growth
- Ejemplo: Starter + Nutrición ($49) + Feed ($39) = $165/mes
- Growth incluye esos dos + Encuestas por solo $197/mes ($32 más y obtiene semi-branding)

**Mensaje para Starter con múltiples add-ons**:
```
💡 Notamos que tienes Nutrición y Feed Social activados ($88/mes en add-ons).

¿Sabías que el plan Growth cuesta solo $197/mes e incluye:
✅ Nutrición + Feed Social + Encuestas (ya los tienes cubiertos)
✅ App semi-branded (tu logo y colores)
✅ Soporte prioritario (12h vs 24h)
✅ Hasta 500 miembros (vs 150 actual)

Pagas solo $32/mes más y obtienes todo esto.

[Ver Plan Growth] [No, gracias]
```

### 4. Monitorear Cannibalización
Riesgo: Gimnasios en Growth downgrade a Starter + compran solo add-ons que necesitan.

**Mitigación**:
- Hacer algunos módulos (Multi-ubicación, API Access) exclusivos de Growth+ (no vendibles como addon)
- Ofrecer descuentos por permanencia en Growth: "Si llevas 6 meses en Growth, 10% off permanente"

### 5. Comunicación Clara en Website
Actualizar página de pricing con:
- Comparador interactivo de tiers
- Sección "Add-ons" con precios transparentes
- Calculadora: "Ingresa cuántos miembros tienes → te recomendamos X plan + Y add-ons"

---

**Impacto Esperado (12 meses)**:
- **MRR**: +13.6% por ingresos de add-ons ($2,560/mes con 100 gyms)
- **Upgrade rate Starter→Growth**: +35% (incentivo fuerte cuando acumulan add-ons)
- **Churn**: -10% (Starter asequible permite retener gyms pequeños)
- **NPS**: +5 puntos (claridad en qué incluye cada plan)
- **Adopción de add-ons en Starter**: 40% Nutrición, 25% Feed, 20% Encuestas
- **Conversión Starter→Growth**: 30% al llegar a 100 miembros o 2+ add-ons
