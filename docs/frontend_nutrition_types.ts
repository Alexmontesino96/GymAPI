// 🍎 TypeScript Types para Sistema Híbrido de Planes Nutricionales
// Este archivo contiene todas las definiciones de tipos necesarias para el frontend

// ===== ENUMS =====
export enum PlanType {
  TEMPLATE = 'template',
  LIVE = 'live',
  ARCHIVED = 'archived'
}

export enum PlanStatus {
  NOT_STARTED = 'not_started',
  RUNNING = 'running',
  FINISHED = 'finished',
  ARCHIVED = 'archived'
}

export enum NutritionGoal {
  WEIGHT_LOSS = 'weight_loss',
  MUSCLE_GAIN = 'muscle_gain',
  MAINTENANCE = 'maintenance',
  HEALTHY_EATING = 'healthy_eating'
}

export enum DifficultyLevel {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced'
}

export enum Budget {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high'
}

// ===== INTERFACES BASE =====
export interface BaseModel {
  id: number;
  created_at: string;
  updated_at: string;
}

export interface EnumOption {
  value: string;
  label: string;
}

// ===== NUTRITION PLAN INTERFACES =====
export interface NutritionPlan extends BaseModel {
  // Campos originales
  title: string;
  description?: string;
  goal: NutritionGoal;
  difficulty_level: DifficultyLevel;
  duration_days: number;
  estimated_budget: Budget;
  dietary_restrictions?: string[];
  created_by: number;
  created_by_name: string;
  
  // Campos híbridos nuevos
  plan_type: PlanType;
  live_start_date?: string; // ISO datetime
  live_end_date?: string;
  is_live_active: boolean;
  live_participants_count: number;
  original_live_plan_id?: number;
  archived_at?: string;
  original_participants_count?: number;
  
  // Campos calculados dinámicamente
  current_day?: number;
  status?: PlanStatus;
  days_until_start?: number;
  is_following?: boolean;
}

export interface DailyNutritionPlan extends BaseModel {
  nutrition_plan_id: number;
  day_number: number;
  daily_calories: number;
  daily_protein: number;
  daily_carbs: number;
  daily_fat: number;
  notes?: string;
}

export interface Meal extends BaseModel {
  daily_nutrition_plan_id: number;
  meal_type: string;
  meal_name: string;
  description?: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  preparation_time: number;
  ingredients: MealIngredient[];
}

export interface MealIngredient extends BaseModel {
  meal_id: number;
  ingredient_name: string;
  quantity: number;
  unit: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

// ===== SEGUIMIENTO =====
export interface NutritionPlanFollower extends BaseModel {
  user_id: number;
  nutrition_plan_id: number;
  start_date: string;
  is_active: boolean;
  progress_percentage: number;
  current_day: number;
  notes?: string;
}

export interface UserMealCompletion extends BaseModel {
  user_id: number;
  meal_id: number;
  completion_date: string;
  completed: boolean;
  notes?: string;
}

export interface UserDailyProgress extends BaseModel {
  user_id: number;
  date: string;
  nutrition_plan_id: number;
  completed_meals: number;
  total_meals: number;
  completion_percentage: number;
  calories_consumed: number;
  protein_consumed: number;
  carbs_consumed: number;
  fat_consumed: number;
}

// ===== RESPUESTAS API =====
export interface NutritionPlanListResponse {
  plans: NutritionPlan[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface NutritionPlanListResponseHybrid {
  live_plans: NutritionPlan[];
  template_plans: NutritionPlan[];
  archived_plans: NutritionPlan[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface TodayMealPlan {
  date: string;
  meals: Meal[];
  completion_percentage: number;
  
  // Campos híbridos nuevos
  plan?: NutritionPlan;
  current_day: number;
  status: PlanStatus;
  days_until_start?: number;
}

export interface NutritionDashboardHybrid {
  // Planes categorizados por tipo
  template_plans: NutritionPlan[];
  live_plans: NutritionPlan[];
  available_plans: NutritionPlan[];
  
  // Plan actual del usuario
  today_plan?: TodayMealPlan;
  
  // Estadísticas
  completion_streak: number;
  weekly_progress: UserDailyProgress[];
}

export interface PlanStatusInfo {
  plan_id: number;
  plan_type: PlanType;
  current_day: number;
  status: PlanStatus;
  days_until_start?: number;
  is_live_active: boolean;
  live_participants_count: number;
  is_following: boolean;
}

// ===== REQUESTS =====
export interface NutritionPlanFilters {
  // Filtros existentes
  goal?: NutritionGoal;
  difficulty_level?: DifficultyLevel;
  search_query?: string;
  page?: number;
  per_page?: number;
  
  // Filtros híbridos nuevos
  plan_type?: PlanType;
  status?: PlanStatus;
  is_live_active?: boolean;
}

export interface CreateNutritionPlanRequest {
  title: string;
  description?: string;
  goal: NutritionGoal;
  difficulty_level: DifficultyLevel;
  duration_days: number;
  estimated_budget: Budget;
  dietary_restrictions?: string[];
  
  // Campos híbridos opcionales
  plan_type?: PlanType;
  live_start_date?: string; // requerido si plan_type es 'live'
}

export interface LivePlanStatusUpdate {
  is_live_active: boolean;
  live_participants_count?: number;
}

export interface ArchivePlanRequest {
  create_template_version: boolean;
  template_title?: string;
}

// ===== COMPONENTES PROPS =====
export interface PlanCardProps {
  plan: NutritionPlan;
  onFollow?: (planId: number) => void;
  onUnfollow?: (planId: number) => void;
  className?: string;
}

export interface PlanTypeIndicatorProps {
  plan: NutritionPlan;
  size?: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}

export interface LivePlanStatusProps {
  plan: NutritionPlan;
  showParticipants?: boolean;
  showCountdown?: boolean;
}

export interface NutritionDashboardProps {
  initialData?: NutritionDashboardHybrid;
  onPlanSelect?: (planId: number) => void;
  onPlanFollow?: (planId: number) => void;
}

export interface TodaySectionProps {
  plan?: TodayMealPlan;
  onMealComplete?: (mealId: number) => void;
  onMealUncomplete?: (mealId: number) => void;
}

// ===== HOOKS =====
export interface UseNutritionPlansReturn {
  plans: NutritionPlan[];
  loading: boolean;
  error: string | null;
  fetchPlans: (filters?: NutritionPlanFilters) => Promise<void>;
  followPlan: (planId: number) => Promise<void>;
  unfollowPlan: (planId: number) => Promise<void>;
}

export interface UseTodayPlanReturn {
  todayPlan: TodayMealPlan | null;
  loading: boolean;
  error: string | null;
  completeMeal: (mealId: number) => Promise<void>;
  uncompleteMeal: (mealId: number) => Promise<void>;
  refresh: () => Promise<void>;
}

export interface UseNutritionDashboardReturn {
  dashboard: NutritionDashboardHybrid | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export interface UsePlanStatusReturn {
  status: PlanStatusInfo | null;
  loading: boolean;
  error: string | null;
  updateStatus: (update: LivePlanStatusUpdate) => Promise<void>;
  archivePlan: (request: ArchivePlanRequest) => Promise<void>;
}

// ===== UTILITIES =====
export interface PlanTypeConfig {
  icon: string;
  color: string;
  label: string;
  description: string;
}

export interface PlanStatusConfig {
  icon: string;
  color: string;
  label: string;
  description: string;
}

export const PLAN_TYPE_CONFIG: Record<PlanType, PlanTypeConfig> = {
  'template': {
    icon: '📋',
    color: 'blue',
    label: 'Template',
    description: 'Empieza cuando quieras'
  },
  'live': {
    icon: '🔴',
    color: 'red',
    label: 'Live',
    description: 'Sincronizado con otros usuarios'
  },
  'archived': {
    icon: '📦',
    color: 'purple',
    label: 'Archived',
    description: 'Plan exitoso archivado'
  }
};

export const PLAN_STATUS_CONFIG: Record<PlanStatus, PlanStatusConfig> = {
  'not_started': {
    icon: '⏰',
    color: 'gray',
    label: 'Próximamente',
    description: 'Aún no ha comenzado'
  },
  'running': {
    icon: '▶️',
    color: 'green',
    label: 'Activo',
    description: 'En progreso'
  },
  'finished': {
    icon: '✅',
    color: 'blue',
    label: 'Terminado',
    description: 'Completado'
  },
  'archived': {
    icon: '📦',
    color: 'purple',
    label: 'Archivado',
    description: 'Guardado como template'
  }
};

// ===== API ENDPOINTS =====
export const NUTRITION_ENDPOINTS = {
  // Endpoints existentes
  PLANS: '/api/v1/nutrition/plans',
  PLAN_DETAIL: (id: number) => `/api/v1/nutrition/plans/${id}`,
  TODAY: '/api/v1/nutrition/today',
  DASHBOARD: '/api/v1/nutrition/dashboard',
  FOLLOW: (id: number) => `/api/v1/nutrition/plans/${id}/follow`,
  UNFOLLOW: (id: number) => `/api/v1/nutrition/plans/${id}/unfollow`,
  
  // Nuevos endpoints híbridos
  PLANS_HYBRID: '/api/v1/nutrition/plans/hybrid',
  PLAN_STATUS: (id: number) => `/api/v1/nutrition/plans/${id}/status`,
  LIVE_STATUS: (id: number) => `/api/v1/nutrition/plans/${id}/live-status`,
  ARCHIVE: (id: number) => `/api/v1/nutrition/plans/${id}/archive`,
  
  // Enums
  PLAN_TYPES: '/api/v1/nutrition/enums/plan-types',
  PLAN_STATUSES: '/api/v1/nutrition/enums/plan-statuses',
  GOALS: '/api/v1/nutrition/enums/goals',
  DIFFICULTIES: '/api/v1/nutrition/enums/difficulties',
  BUDGETS: '/api/v1/nutrition/enums/budgets'
} as const;

// ===== HELPER FUNCTIONS =====
export const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('es-ES', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
};

export const formatDateShort = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
};

export const getDaysUntilStart = (startDate: string): number => {
  const today = new Date();
  const start = new Date(startDate);
  const diffTime = start.getTime() - today.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

export const isPlanActive = (plan: NutritionPlan): boolean => {
  return plan.status === PlanStatus.RUNNING;
};

export const isPlanStartingSoon = (plan: NutritionPlan): boolean => {
  return plan.status === PlanStatus.NOT_STARTED && 
         plan.days_until_start !== undefined && 
         plan.days_until_start <= 3;
};

export const getPlanTypeConfig = (planType: PlanType): PlanTypeConfig => {
  return PLAN_TYPE_CONFIG[planType];
};

export const getPlanStatusConfig = (status: PlanStatus): PlanStatusConfig => {
  return PLAN_STATUS_CONFIG[status];
};

export const buildPlanFilters = (filters: Partial<NutritionPlanFilters>): URLSearchParams => {
  const params = new URLSearchParams();
  
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, value.toString());
    }
  });
  
  return params;
}; 