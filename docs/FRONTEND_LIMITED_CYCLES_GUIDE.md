# 🔄 Sistema de Ciclos Limitados de Facturación - Guía Frontend

## 📋 Resumen de Cambios

Se ha implementado un sistema de **ciclos limitados de facturación** que permite crear planes de membresía que se cancelan automáticamente después de un número específico de pagos. Esta funcionalidad es especialmente útil para:

- ✅ Programas de entrenamiento de duración fija (ej: 3 meses)
- ✅ Desafíos temporales
- ✅ Membresías estudiantiles con períodos específicos
- ✅ Promociones de duración limitada

---

## 🆕 Nuevos Campos en la API

### **MembershipPlan Model**

```typescript
interface MembershipPlan {
  // ... campos existentes
  
  // 🆕 NUEVO CAMPO
  max_billing_cycles: number | null;  // Máximo número de ciclos (null = ilimitado)
  
  // 🆕 CAMPOS CALCULADOS
  is_limited_duration: boolean;        // Si tiene duración limitada
  total_duration_days: number;        // Duración total estimada
  subscription_description: string;   // Descripción legible del plan
}
```

### **Ejemplo de Respuesta de API**

```json
{
  "id": 123,
  "name": "Programa 3 Meses",
  "price_cents": 3999,
  "price_amount": 39.99,
  "currency": "EUR",
  "billing_interval": "month",
  "duration_days": 30,
  "max_billing_cycles": 3,
  "is_active": true,
  "is_recurring": true,
  "is_limited_duration": true,
  "total_duration_days": 90,
  "subscription_description": "Pago mesal por 3 meses",
  "created_at": "2025-01-08T23:59:00Z"
}
```

---

## 🎯 Casos de Uso por Tipo de Plan

### **1. Plan Mensual Ilimitado (Comportamiento Actual)**
```json
{
  "name": "Mensual Premium",
  "billing_interval": "month",
  "max_billing_cycles": null,
  "is_limited_duration": false,
  "subscription_description": "Suscripción mensual ilimitada"
}
```

### **2. Plan Mensual por 3 Meses (Nuevo)**
```json
{
  "name": "Programa 3 Meses",
  "billing_interval": "month",
  "max_billing_cycles": 3,
  "is_limited_duration": true,
  "total_duration_days": 90,
  "subscription_description": "Pago mesal por 3 meses"
}
```

### **3. Plan Anual por 2 Años (Nuevo)**
```json
{
  "name": "Estudiante 2 Años",
  "billing_interval": "year",
  "max_billing_cycles": 2,
  "is_limited_duration": true,
  "total_duration_days": 730,
  "subscription_description": "Pago añoal por 2 añoes"
}
```

### **4. Plan de Pago Único (Sin Cambios)**
```json
{
  "name": "Pase Diario",
  "billing_interval": "one_time",
  "max_billing_cycles": null,
  "is_limited_duration": false,
  "subscription_description": "Pago único - 1 días"
}
```

---

## 🛠️ Implementación Frontend

### **1. Formulario de Creación de Planes**

```tsx
interface PlanFormData {
  name: string;
  price_cents: number;
  billing_interval: 'month' | 'year' | 'one_time';
  duration_days: number;
  max_billing_cycles?: number | null;  // 🆕 NUEVO CAMPO
}

const PlanForm: React.FC = () => {
  const [formData, setFormData] = useState<PlanFormData>({
    name: '',
    price_cents: 0,
    billing_interval: 'month',
    duration_days: 30,
    max_billing_cycles: null
  });

  const [isLimitedDuration, setIsLimitedDuration] = useState(false);

  return (
    <form>
      {/* Campos existentes */}
      <input 
        type="text" 
        value={formData.name}
        onChange={(e) => setFormData({...formData, name: e.target.value})}
        placeholder="Nombre del plan"
      />
      
      <select 
        value={formData.billing_interval}
        onChange={(e) => setFormData({...formData, billing_interval: e.target.value})}
      >
        <option value="month">Mensual</option>
        <option value="year">Anual</option>
        <option value="one_time">Pago único</option>
      </select>

      {/* 🆕 NUEVA SECCIÓN: Duración Limitada */}
      {formData.billing_interval !== 'one_time' && (
        <div className="limited-duration-section">
          <label>
            <input
              type="checkbox"
              checked={isLimitedDuration}
              onChange={(e) => {
                setIsLimitedDuration(e.target.checked);
                setFormData({
                  ...formData,
                  max_billing_cycles: e.target.checked ? 1 : null
                });
              }}
            />
            Limitar duración del plan
          </label>

          {isLimitedDuration && (
            <div className="billing-cycles-input">
              <label>
                Número de {formData.billing_interval === 'month' ? 'meses' : 'años'}:
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={formData.max_billing_cycles || 1}
                  onChange={(e) => setFormData({
                    ...formData,
                    max_billing_cycles: parseInt(e.target.value)
                  })}
                />
              </label>
            </div>
          )}
        </div>
      )}

      {/* Vista previa del plan */}
      <PlanPreview formData={formData} />
    </form>
  );
};
```

### **2. Componente de Vista Previa**

```tsx
interface PlanPreviewProps {
  formData: PlanFormData;
}

const PlanPreview: React.FC<PlanPreviewProps> = ({ formData }) => {
  const calculateTotalDuration = () => {
    if (!formData.max_billing_cycles) return null;
    
    if (formData.billing_interval === 'month') {
      return formData.max_billing_cycles * 30;
    } else if (formData.billing_interval === 'year') {
      return formData.max_billing_cycles * 365;
    }
    return formData.duration_days;
  };

  const calculateTotalCost = () => {
    if (!formData.max_billing_cycles) return null;
    return (formData.price_cents / 100) * formData.max_billing_cycles;
  };

  const getSubscriptionDescription = () => {
    if (formData.billing_interval === 'one_time') {
      return `Pago único - ${formData.duration_days} días`;
    }
    
    if (formData.max_billing_cycles) {
      const interval = formData.billing_interval === 'month' ? 'mes' : 'año';
      const intervalPlural = formData.max_billing_cycles > 1 ? 
        (formData.billing_interval === 'month' ? 'meses' : 'años') : interval;
      return `Pago ${interval}al por ${formData.max_billing_cycles} ${intervalPlural}`;
    }
    
    const interval = formData.billing_interval === 'month' ? 'mensual' : 'anual';
    return `Suscripción ${interval} ilimitada`;
  };

  return (
    <div className="plan-preview">
      <h3>Vista Previa del Plan</h3>
      
      <div className="preview-item">
        <span>Tipo:</span>
        <span>{getSubscriptionDescription()}</span>
      </div>
      
      <div className="preview-item">
        <span>Precio:</span>
        <span>
          €{(formData.price_cents / 100).toFixed(2)}
          {formData.billing_interval !== 'one_time' && `/${formData.billing_interval === 'month' ? 'mes' : 'año'}`}
        </span>
      </div>
      
      {formData.max_billing_cycles && (
        <>
          <div className="preview-item">
            <span>Duración total:</span>
            <span>{calculateTotalDuration()} días</span>
          </div>
          
          <div className="preview-item">
            <span>Costo total:</span>
            <span>€{calculateTotalCost()?.toFixed(2)}</span>
          </div>
          
          <div className="preview-item">
            <span>Se cancela automáticamente:</span>
            <span className="auto-cancel">✅ Sí</span>
          </div>
        </>
      )}
    </div>
  );
};
```

### **3. Tarjeta de Plan para Usuarios**

```tsx
interface PlanCardProps {
  plan: MembershipPlan;
  onSelect: (planId: number) => void;
}

const PlanCard: React.FC<PlanCardProps> = ({ plan, onSelect }) => {
  const getBadgeColor = () => {
    if (plan.billing_interval === 'one_time') return 'blue';
    if (plan.is_limited_duration) return 'orange';
    return 'green';
  };

  const getBadgeText = () => {
    if (plan.billing_interval === 'one_time') return 'Pago Único';
    if (plan.is_limited_duration) return 'Duración Limitada';
    return 'Ilimitado';
  };

  return (
    <div className="plan-card">
      <div className="plan-header">
        <h3>{plan.name}</h3>
        <span className={`badge badge-${getBadgeColor()}`}>
          {getBadgeText()}
        </span>
      </div>

      <div className="plan-price">
        <span className="amount">€{plan.price_amount}</span>
        {plan.billing_interval !== 'one_time' && (
          <span className="interval">
            /{plan.billing_interval === 'month' ? 'mes' : 'año'}
          </span>
        )}
      </div>

      <div className="plan-description">
        {plan.subscription_description}
      </div>

      {/* 🆕 INFORMACIÓN ADICIONAL PARA PLANES LIMITADOS */}
      {plan.is_limited_duration && (
        <div className="limited-info">
          <div className="info-item">
            <span>📅 Duración total:</span>
            <span>{plan.total_duration_days} días</span>
          </div>
          
          <div className="info-item">
            <span>🔄 Número de pagos:</span>
            <span>{plan.max_billing_cycles}</span>
          </div>
          
          <div className="info-item">
            <span>💰 Costo total:</span>
            <span>€{(plan.price_amount * plan.max_billing_cycles).toFixed(2)}</span>
          </div>
          
          <div className="auto-cancel-notice">
            ⚡ Se cancela automáticamente después de {plan.max_billing_cycles} pagos
          </div>
        </div>
      )}

      <button 
        className="select-plan-btn"
        onClick={() => onSelect(plan.id)}
      >
        Seleccionar Plan
      </button>
    </div>
  );
};
```

### **4. Validación del Frontend**

```typescript
// Validación para el formulario de creación
const validatePlanForm = (formData: PlanFormData): string[] => {
  const errors: string[] = [];

  // Validaciones existentes...
  
  // 🆕 NUEVAS VALIDACIONES
  if (formData.billing_interval === 'one_time' && formData.max_billing_cycles) {
    errors.push('Los planes de pago único no pueden tener ciclos limitados');
  }

  if (formData.max_billing_cycles && formData.max_billing_cycles < 1) {
    errors.push('El número de ciclos debe ser mayor a 0');
  }

  if (formData.max_billing_cycles && formData.max_billing_cycles > 60) {
    errors.push('El número de ciclos no puede exceder 60');
  }

  return errors;
};
```

---

## 🔧 Respuesta del Checkout de Stripe

### **Checkout Session Response (Actualizada)**

```json
{
  "checkout_session_id": "cs_test_...",
  "checkout_url": "https://checkout.stripe.com/...",
  "plan_name": "Programa 3 Meses",
  "price": 39.99,
  "currency": "EUR",
  "is_limited_duration": true,
  "subscription_description": "Pago mesal por 3 meses",
  "max_billing_cycles": 3,
  "total_duration_days": 90,
  "auto_cancel_date": "2025-04-08T23:59:00Z"
}
```

### **Manejo en Frontend**

```typescript
const handleCheckoutResponse = (response: CheckoutResponse) => {
  if (response.is_limited_duration) {
    // Mostrar información específica para planes limitados
    showLimitedDurationInfo({
      cycles: response.max_billing_cycles,
      totalDays: response.total_duration_days,
      autoCancel: response.auto_cancel_date,
      totalCost: response.price * response.max_billing_cycles
    });
  }
  
  // Redirigir al checkout
  window.location.href = response.checkout_url;
};
```

---

## 🎨 Sugerencias de UX/UI

### **1. Indicadores Visuales**

```css
.plan-card.limited-duration {
  border: 2px solid #f59e0b;
  position: relative;
}

.plan-card.limited-duration::before {
  content: "⏰ Duración Limitada";
  position: absolute;
  top: -10px;
  right: 10px;
  background: #f59e0b;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.auto-cancel-notice {
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 4px;
  padding: 8px;
  margin-top: 12px;
  font-size: 14px;
  color: #92400e;
}
```

### **2. Iconografía Recomendada**

- 🔄 Para planes recurrentes ilimitados
- ⏰ Para planes de duración limitada
- ⚡ Para pago único
- 📅 Para fechas de cancelación
- 💰 Para costos totales

### **3. Mensajes de Confirmación**

```typescript
const getConfirmationMessage = (plan: MembershipPlan) => {
  if (plan.is_limited_duration) {
    return `¿Confirmas la compra del plan "${plan.name}"? Se cobrará €${plan.price_amount} cada ${plan.billing_interval === 'month' ? 'mes' : 'año'} por ${plan.max_billing_cycles} ${plan.billing_interval === 'month' ? 'meses' : 'años'} (total: €${(plan.price_amount * plan.max_billing_cycles).toFixed(2)}) y se cancelará automáticamente.`;
  }
  
  return `¿Confirmas la suscripción al plan "${plan.name}"? Se cobrará €${plan.price_amount} cada ${plan.billing_interval === 'month' ? 'mes' : 'año'} hasta que canceles.`;
};
```

---

## 🚀 Casos de Uso Recomendados

### **1. Programas de Fitness**
```json
{
  "name": "Desafío 90 Días",
  "billing_interval": "month",
  "max_billing_cycles": 3,
  "price_cents": 4999
}
```

### **2. Membresías Estudiantiles**
```json
{
  "name": "Plan Estudiante",
  "billing_interval": "year",
  "max_billing_cycles": 2,
  "price_cents": 19999
}
```

### **3. Promociones Temporales**
```json
{
  "name": "Oferta Verano",
  "billing_interval": "month",
  "max_billing_cycles": 4,
  "price_cents": 2999
}
```

---

## ✅ Checklist de Implementación

- [ ] Actualizar interfaces TypeScript
- [ ] Implementar formulario de creación con ciclos limitados
- [ ] Crear componente de vista previa
- [ ] Actualizar tarjetas de planes
- [ ] Agregar validaciones del frontend
- [ ] Implementar indicadores visuales
- [ ] Testear flujo completo de checkout
- [ ] Documentar en Storybook (si aplica)

---

## 🐛 Debugging y Testing

### **Plan de Pruebas**

1. **Crear plan limitado**: max_billing_cycles = 2
2. **Verificar respuesta**: Campos calculados correctos
3. **Checkout**: Verificar auto_cancel_date en respuesta
4. **Stripe**: Confirmar suscripción con cancel_at configurado

### **Logs Útiles**

```typescript
console.log('Plan data:', {
  name: plan.name,
  isLimited: plan.is_limited_duration,
  cycles: plan.max_billing_cycles,
  totalDays: plan.total_duration_days,
  description: plan.subscription_description
});
```

---

## 📞 Contacto

Para dudas sobre la implementación, contactar al equipo backend o revisar el código en:
- `app/models/membership.py`
- `app/schemas/membership.py`
- `app/services/stripe_service.py`

¡Éxito con la implementación! 🚀 