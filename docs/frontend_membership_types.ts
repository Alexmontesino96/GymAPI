// 🔄 Tipos TypeScript actualizados para el Sistema de Ciclos Limitados
// Archivo: types/membership.ts

/**
 * 🆕 NUEVOS TIPOS PARA CICLOS LIMITADOS
 */

export type BillingInterval = 'month' | 'year' | 'one_time';

export interface MembershipPlan {
  // Campos existentes
  id: number;
  gym_id: number;
  name: string;
  description?: string;
  price_cents: number;
  price_amount: number;
  currency: string;
  billing_interval: BillingInterval;
  duration_days: number;
  is_active: boolean;
  features?: string;
  max_bookings_per_month?: number;
  stripe_price_id?: string;
  stripe_product_id?: string;
  created_at: string;
  updated_at?: string;
  
  // 🆕 NUEVOS CAMPOS
  max_billing_cycles?: number | null;  // Máximo número de ciclos (null = ilimitado)
  
  // 🆕 CAMPOS CALCULADOS
  is_recurring: boolean;               // Si es recurrente (month/year)
  is_limited_duration: boolean;        // Si tiene duración limitada
  total_duration_days: number;         // Duración total estimada
  subscription_description: string;    // Descripción legible del plan
}

export interface MembershipPlanCreate {
  name: string;
  description?: string;
  price_cents: number;
  currency: string;
  billing_interval: BillingInterval;
  duration_days: number;
  max_billing_cycles?: number | null;  // 🆕 NUEVO CAMPO
  is_active?: boolean;
  features?: string;
  max_bookings_per_month?: number;
}

export interface MembershipPlanUpdate {
  name?: string;
  description?: string;
  price_cents?: number;
  currency?: string;
  billing_interval?: BillingInterval;
  duration_days?: number;
  max_billing_cycles?: number | null;  // 🆕 NUEVO CAMPO
  is_active?: boolean;
  features?: string;
  max_bookings_per_month?: number;
}

/**
 * 🆕 RESPUESTA DEL CHECKOUT ACTUALIZADA
 */
export interface CheckoutResponse {
  checkout_session_id: string;
  checkout_url: string;
  plan_name: string;
  price: number;
  currency: string;
  
  // 🆕 NUEVOS CAMPOS
  is_limited_duration: boolean;
  subscription_description: string;
  max_billing_cycles?: number;
  total_duration_days?: number;
  auto_cancel_date?: string;  // ISO string
}

/**
 * 🆕 TIPOS PARA FORMULARIOS
 */
export interface PlanFormData {
  name: string;
  description?: string;
  price_cents: number;
  currency: string;
  billing_interval: BillingInterval;
  duration_days: number;
  max_billing_cycles?: number | null;
  is_active: boolean;
  features?: string;
  max_bookings_per_month?: number;
}

export interface PlanFormState {
  formData: PlanFormData;
  isLimitedDuration: boolean;
  errors: string[];
  isSubmitting: boolean;
}

/**
 * 🆕 TIPOS PARA COMPONENTES
 */
export interface PlanCardProps {
  plan: MembershipPlan;
  onSelect: (planId: number) => void;
  isSelected?: boolean;
  showLimitedInfo?: boolean;
}

export interface PlanPreviewProps {
  formData: PlanFormData;
  showCalculations?: boolean;
}

/**
 * 🆕 TIPOS PARA VALIDACIÓN
 */
export interface PlanValidationResult {
  isValid: boolean;
  errors: string[];
  warnings?: string[];
}

export interface PlanCalculations {
  totalCost: number;
  totalDuration: number;
  costPerDay: number;
  cyclesRemaining?: number;
  nextPaymentDate?: string;
}

/**
 * 🆕 ENUMS PARA BADGES Y ESTADOS
 */
export enum PlanBadgeType {
  UNLIMITED = 'unlimited',
  LIMITED = 'limited',
  ONE_TIME = 'one_time'
}

export enum PlanBadgeColor {
  GREEN = 'green',
  ORANGE = 'orange',
  BLUE = 'blue'
}

/**
 * 🆕 FUNCIONES HELPER
 */
export const PlanHelpers = {
  /**
   * Determina el tipo de badge para un plan
   */
  getBadgeType: (plan: MembershipPlan): PlanBadgeType => {
    if (plan.billing_interval === 'one_time') return PlanBadgeType.ONE_TIME;
    if (plan.is_limited_duration) return PlanBadgeType.LIMITED;
    return PlanBadgeType.UNLIMITED;
  },

  /**
   * Determina el color del badge
   */
  getBadgeColor: (plan: MembershipPlan): PlanBadgeColor => {
    if (plan.billing_interval === 'one_time') return PlanBadgeColor.BLUE;
    if (plan.is_limited_duration) return PlanBadgeColor.ORANGE;
    return PlanBadgeColor.GREEN;
  },

  /**
   * Obtiene el texto del badge
   */
  getBadgeText: (plan: MembershipPlan): string => {
    if (plan.billing_interval === 'one_time') return 'Pago Único';
    if (plan.is_limited_duration) return 'Duración Limitada';
    return 'Ilimitado';
  },

  /**
   * Calcula el costo total de un plan limitado
   */
  calculateTotalCost: (plan: MembershipPlan): number | null => {
    if (!plan.max_billing_cycles) return null;
    return plan.price_amount * plan.max_billing_cycles;
  },

  /**
   * Obtiene la descripción del intervalo de facturación
   */
  getIntervalText: (interval: BillingInterval, isPlural: boolean = false): string => {
    switch (interval) {
      case 'month':
        return isPlural ? 'meses' : 'mes';
      case 'year':
        return isPlural ? 'años' : 'año';
      case 'one_time':
        return 'único';
      default:
        return '';
    }
  },

  /**
   * Genera mensaje de confirmación para checkout
   */
  getConfirmationMessage: (plan: MembershipPlan): string => {
    if (plan.is_limited_duration) {
      const interval = PlanHelpers.getIntervalText(plan.billing_interval);
      const intervalPlural = PlanHelpers.getIntervalText(plan.billing_interval, true);
      const total = PlanHelpers.calculateTotalCost(plan);
      
      return `¿Confirmas la compra del plan "${plan.name}"? Se cobrará €${plan.price_amount} cada ${interval} por ${plan.max_billing_cycles} ${intervalPlural} (total: €${total?.toFixed(2)}) y se cancelará automáticamente.`;
    }
    
    const interval = PlanHelpers.getIntervalText(plan.billing_interval);
    return `¿Confirmas la suscripción al plan "${plan.name}"? Se cobrará €${plan.price_amount} cada ${interval} hasta que canceles.`;
  },

  /**
   * Valida datos del formulario de plan
   */
  validatePlanForm: (formData: PlanFormData): PlanValidationResult => {
    const errors: string[] = [];
    
    // Validaciones básicas
    if (!formData.name.trim()) {
      errors.push('El nombre del plan es requerido');
    }
    
    if (formData.price_cents <= 0) {
      errors.push('El precio debe ser mayor a 0');
    }
    
    if (formData.duration_days <= 0) {
      errors.push('La duración debe ser mayor a 0');
    }
    
    // 🆕 VALIDACIONES PARA CICLOS LIMITADOS
    if (formData.billing_interval === 'one_time' && formData.max_billing_cycles) {
      errors.push('Los planes de pago único no pueden tener ciclos limitados');
    }
    
    if (formData.max_billing_cycles && formData.max_billing_cycles < 1) {
      errors.push('El número de ciclos debe ser mayor a 0');
    }
    
    if (formData.max_billing_cycles && formData.max_billing_cycles > 60) {
      errors.push('El número de ciclos no puede exceder 60');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }
};

/**
 * 🆕 CONSTANTES ÚTILES
 */
export const PLAN_CONSTANTS = {
  MAX_CYCLES: 60,
  MIN_CYCLES: 1,
  DEFAULT_DURATION_DAYS: 30,
  DAYS_PER_MONTH: 30,
  DAYS_PER_YEAR: 365
};

/**
 * 🆕 TIPOS PARA HOOKS PERSONALIZADOS
 */
export interface UsePlanFormReturn {
  formData: PlanFormData;
  setFormData: (data: PlanFormData) => void;
  isLimitedDuration: boolean;
  setIsLimitedDuration: (limited: boolean) => void;
  errors: string[];
  isValid: boolean;
  calculations: PlanCalculations;
  reset: () => void;
}

export interface UsePlanListReturn {
  plans: MembershipPlan[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createPlan: (data: PlanFormData) => Promise<MembershipPlan>;
  updatePlan: (id: number, data: PlanFormData) => Promise<MembershipPlan>;
  deletePlan: (id: number) => Promise<void>;
}

/**
 * 🆕 EJEMPLO DE USO
 */
export const EXAMPLE_LIMITED_PLAN: MembershipPlan = {
  id: 123,
  gym_id: 1,
  name: "Programa 3 Meses",
  description: "Plan mensual que se paga 3 veces y se cancela automáticamente",
  price_cents: 3999,
  price_amount: 39.99,
  currency: "EUR",
  billing_interval: "month",
  duration_days: 30,
  max_billing_cycles: 3,
  is_active: true,
  is_recurring: true,
  is_limited_duration: true,
  total_duration_days: 90,
  subscription_description: "Pago mesal por 3 meses",
  created_at: "2025-01-08T23:59:00Z"
};

export const EXAMPLE_UNLIMITED_PLAN: MembershipPlan = {
  id: 124,
  gym_id: 1,
  name: "Mensual Premium",
  description: "Plan mensual que se renueva automáticamente",
  price_cents: 2999,
  price_amount: 29.99,
  currency: "EUR",
  billing_interval: "month",
  duration_days: 30,
  max_billing_cycles: null,
  is_active: true,
  is_recurring: true,
  is_limited_duration: false,
  total_duration_days: 30,
  subscription_description: "Suscripción mensual ilimitada",
  created_at: "2025-01-08T23:59:00Z"
};

/**
 * 🆕 TIPOS PARA RESPUESTAS DE API
 */
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
  error?: string;
}

export interface PlanListResponse extends ApiResponse<MembershipPlan[]> {
  total: number;
  gym_id: number;
  gym_name: string;
}

export interface CheckoutSessionResponse extends ApiResponse<CheckoutResponse> {
  // Hereda de ApiResponse
} 