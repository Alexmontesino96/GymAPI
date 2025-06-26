# 🏗️ Guía de Arquitectura Multi-Tenant con Stripe

## 📋 Resumen Ejecutivo

**Decisión Recomendada**: Una cuenta de Stripe + Sistema de distribución propio

### ✅ **Beneficios de la Arquitectura Elegida**

1. **💰 Costos Optimizados**: Una sola cuenta reduce tarifas y comisiones
2. **🔧 Simplicidad Técnica**: Menor complejidad de integración y mantenimiento
3. **📊 Centralización**: Dashboard unificado y reportes consolidados
4. **🚀 Escalabilidad**: Fácil agregar nuevos gimnasios sin setup adicional
5. **⚡ Time-to-Market**: Implementación más rápida

---

## 🛠️ Implementación Técnica

### **1. Identificación de Gimnasio en Stripe**

Cada transacción incluye metadatos completos para identificar el gimnasio:

```javascript
metadata: {
    'user_id': user_id,
    'gym_id': str(gym_id),           // 🔑 CLAVE PRINCIPAL
    'gym_name': gym.name,            // Para reportes
    'plan_id': str(plan_id),
    'plan_name': plan.name,
    'plan_price': str(plan.price_cents),
    'currency': plan.currency,
    'billing_interval': plan.billing_interval,
    'platform': 'gymapi'             // Identificador de plataforma
}
```

### **2. Tracking de Ingresos por Gimnasio**

#### **Servicio de Ingresos** (`app/services/gym_revenue.py`)
- ✅ `get_gym_revenue_summary()`: Resumen de ingresos por gimnasio
- ✅ `get_platform_revenue_summary()`: Resumen total de la plataforma
- ✅ `calculate_gym_payout()`: Cálculo de pagos a gimnasios
- ✅ `_get_stripe_payments_for_gym()`: Extrae pagos de Stripe por gym_id

#### **Endpoints de Gestión**
- `GET /api/v1/memberships/revenue/gym-summary` - Ingresos del gimnasio
- `GET /api/v1/memberships/revenue/platform-summary` - Ingresos de plataforma
- `GET /api/v1/memberships/revenue/payout-calculation` - Cálculo de pagos

---

## 💰 Modelo de Distribución de Ingresos

### **Estructura de Comisiones**
```
Pago del Cliente: €100
├── Comisión Stripe: €2.90 (2.9%)
├── Comisión Plataforma: €4.86 (5% del neto)
└── Pago al Gimnasio: €92.24 (95% del neto)
```

### **Ejemplo de Cálculo**
```python
# Para un pago de €100
gross_amount = 100.00
stripe_fee = 2.90  # 2.9% + €0.30
net_after_stripe = 97.10

platform_fee_rate = 0.05  # 5%
platform_fee = net_after_stripe * platform_fee_rate  # €4.86
gym_payout = net_after_stripe - platform_fee  # €92.24
```

---

## 🔍 Consultas de Ingresos

### **Por Gimnasio Específico**
```python
# Obtener ingresos del último mes
revenue_summary = await gym_revenue_service.get_gym_revenue_summary(
    db, gym_id=1, 
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Resultado:
{
    "gym_id": 1,
    "gym_name": "FitZone Madrid",
    "revenue": {
        "total_gross": 2450.00,
        "platform_fee": 119.03,
        "gym_net": 2330.97,
        "currency": "EUR"
    },
    "transactions": {
        "total_count": 25,
        "by_plan": {
            "Plan Mensual": {"count": 20, "revenue": 1800.00},
            "Plan Anual": {"count": 5, "revenue": 650.00}
        }
    }
}
```

### **Búsqueda en Stripe por Gimnasio**
```python
# Buscar todos los pagos de un gimnasio
charges = stripe.Charge.list(
    created={'gte': start_timestamp, 'lte': end_timestamp},
    limit=100
)

gym_payments = [
    charge for charge in charges.data 
    if charge.metadata.get('gym_id') == str(gym_id)
]
```

---

## 📊 Dashboard y Reportes

### **Para Administradores de Gimnasio**
- 📈 Ingresos mensuales/anuales
- 💳 Transacciones por plan
- 📊 Métricas de conversión
- 💰 Cálculo de pagos pendientes

### **Para Super-Administradores**
- 🏢 Resumen de todos los gimnasios
- 💰 Comisiones de plataforma
- 📊 Top gimnasios por ingresos
- 📈 Crecimiento de la plataforma

---

## 🔒 Seguridad Multi-Tenant

### **Validación de Pertenencia**
```python
# Verificar que el recurso pertenece al gimnasio
customer_membership = db.query(UserGym).filter(
    UserGym.stripe_customer_id == customer_id,
    UserGym.gym_id == current_gym.id
).first()

if not customer_membership:
    raise HTTPException(403, "Cliente no pertenece a este gimnasio")
```

### **Metadatos Obligatorios**
- ✅ `gym_id`: Siempre presente en transacciones
- ✅ `gym_name`: Para verificación cruzada
- ✅ `platform`: Identificador de origen

---

## 🚀 Escalabilidad

### **Agregar Nuevo Gimnasio**
1. ✅ Crear registro en base de datos
2. ✅ Los pagos automáticamente incluyen `gym_id`
3. ✅ Reportes disponibles inmediatamente
4. ✅ Sin configuración adicional en Stripe

### **Límites y Consideraciones**
- **Stripe API**: 100 requests/segundo (más que suficiente)
- **Metadatos**: Máximo 500 caracteres por campo
- **Búsquedas**: Eficientes por metadata indexado

---

## 💡 Alternativas Consideradas

### **❌ Stripe Connect (Descartada)**
- **Pros**: Separación automática de fondos
- **Contras**: 
  - Complejidad técnica alta
  - Costos 2-3x más altos
  - Onboarding complejo para gimnasios
  - Múltiples cuentas que gestionar

### **❌ Múltiples Cuentas Stripe (Descartada)**
- **Pros**: Separación total
- **Contras**:
  - Gestión operativa compleja
  - Costos multiplicados
  - Integración técnica compleja

---

## 🎯 Próximos Pasos

### **Fase 1: Implementación Actual** ✅
- [x] Metadatos completos en transacciones
- [x] Servicio de tracking de ingresos
- [x] Endpoints de consulta
- [x] Validación multi-tenant

### **Fase 2: Automatización** (Próxima)
- [ ] Cálculo automático de payouts
- [ ] Notificaciones a gimnasios
- [ ] Dashboard visual
- [ ] Exportación de reportes

### **Fase 3: Optimización** (Futura)
- [ ] Cache de métricas frecuentes
- [ ] Análisis predictivo
- [ ] Alertas automáticas
- [ ] Integración bancaria

---

## 📞 Soporte y Mantenimiento

### **Monitoreo**
- 📊 Logs detallados de transacciones
- 🚨 Alertas de fallos en webhooks
- 📈 Métricas de rendimiento

### **Troubleshooting**
- 🔍 Búsqueda por `gym_id` en Stripe Dashboard
- 📋 Logs estructurados con contexto completo
- 🛠️ Herramientas de debug integradas

---

**✨ Con esta arquitectura, tienes un sistema robusto, escalable y cost-effective para manejar pagos multi-tenant con una excelente experiencia tanto para gimnasios como para usuarios finales.** 