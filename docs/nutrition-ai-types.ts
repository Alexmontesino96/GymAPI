/**
 * TypeScript Types para la API de Nutrición con IA
 *
 * Estos tipos pueden ser copiados directamente al proyecto frontend
 * para tener tipado fuerte al trabajar con la API de nutrición.
 */

// ============================================
// Enums y Tipos Base
// ============================================

export enum MealType {
  BREAKFAST = 'breakfast',
  LUNCH = 'lunch',
  DINNER = 'dinner',
  SNACK = 'snack',
  PRE_WORKOUT = 'pre_workout',
  POST_WORKOUT = 'post_workout'
}

export enum DietaryRestriction {
  VEGETARIAN = 'vegetarian',
  VEGAN = 'vegan',
  GLUTEN_FREE = 'gluten_free',
  DAIRY_FREE = 'dairy_free',
  NUT_FREE = 'nut_free',
  KETO = 'keto',
  PALEO = 'paleo',
  LOW_CARB = 'low_carb',
  HIGH_PROTEIN = 'high_protein',
  HALAL = 'halal',
  KOSHER = 'kosher'
}

export enum DifficultyLevel {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced'
}

export type NutritionUnit = 'gr' | 'ml' | 'cups' | 'tbsp' | 'tsp' | 'oz' | 'kg' | 'l';

export type Language = 'es' | 'en' | 'pt';

// ============================================
// Request Types
// ============================================

/**
 * Request para generar ingredientes con IA
 */
export interface GenerateIngredientsRequest {
  dietary_restrictions?: DietaryRestriction[];
  preferences?: string[];
  servings?: number;
  language?: Language;
}

/**
 * Request para agregar ingrediente manualmente
 */
export interface AddIngredientRequest {
  name: string;
  quantity: number;
  unit: NutritionUnit;
  calories_per_unit: number;
  protein_g_per_unit: number;
  carbs_g_per_unit: number;
  fat_g_per_unit: number;
  fiber_g_per_unit: number;
  notes?: string;
}

// ============================================
// Response Types
// ============================================

/**
 * Información nutricional
 */
export interface NutritionInfo {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
}

/**
 * Ingrediente individual
 */
export interface Ingredient {
  id: number;
  name: string;
  quantity: number;
  unit: NutritionUnit;
  calories_per_unit: number;
  protein_g_per_unit: number;
  carbs_g_per_unit: number;
  fat_g_per_unit: number;
  fiber_g_per_unit: number;
  notes?: string;
  order: number;
}

/**
 * Respuesta de generación con IA
 */
export interface GenerateIngredientsResponse {
  status: 'success' | 'error';
  message: string;
  data: {
    meal_id: number;
    ingredients: Ingredient[];
    recipe_instructions: string;
    total_nutrition: NutritionInfo;
    estimated_prep_time: number;
    difficulty_level: DifficultyLevel;
    ai_confidence_score: number;
    generated_at: string;
  };
}

/**
 * Comida (Meal)
 */
export interface Meal {
  id: number;
  name: string;
  meal_type: MealType;
  description?: string;
  target_calories: number;
  target_protein_g: number;
  target_carbs_g: number;
  target_fat_g: number;
  ingredients: Ingredient[];
  has_ingredients: boolean;
  can_generate_with_ai: boolean;
  daily_nutrition_plan_id: number;
  order: number;
}

/**
 * Plan diario
 */
export interface DailyNutritionPlan {
  id: number;
  day_number: number;
  day_name: string;
  description?: string;
  total_calories_goal: number;
  total_protein_g_goal: number;
  total_carbs_g_goal: number;
  total_fat_g_goal: number;
  meals: Meal[];
  is_published: boolean;
  nutrition_plan_id: number;
}

/**
 * Plan de nutrición
 */
export interface NutritionPlan {
  id: number;
  name: string;
  description?: string;
  plan_type: 'TEMPLATE' | 'LIVE' | 'ARCHIVED';
  duration_days: number;
  goal: string;
  difficulty_level: DifficultyLevel;
  calories_goal_per_day?: number;
  created_by_user_id: number;
  gym_id: number;
  is_active: boolean;
  is_public: boolean;
  is_live_active?: boolean;
  live_start_date?: string;
  live_participants_count?: number;
  daily_plans: DailyNutritionPlan[];
  created_at: string;
  updated_at: string;
}

// ============================================
// Error Response Types
// ============================================

export interface ErrorResponse {
  detail: string;
  status?: number;
  type?: string;
}

export interface ValidationError {
  detail: Array<{
    loc: string[];
    msg: string;
    type: string;
  }>;
}

// ============================================
// API Service Types
// ============================================

/**
 * Configuración para el cliente API
 */
export interface NutritionAPIConfig {
  baseURL: string;
  token: string;
  gymId: number;
  timeout?: number;
  retryAttempts?: number;
}

/**
 * Opciones para las llamadas API
 */
export interface APICallOptions {
  signal?: AbortSignal;
  onProgress?: (progress: number) => void;
  retryOnError?: boolean;
}

// ============================================
// State Management Types
// ============================================

/**
 * Estado de generación de IA
 */
export interface AIGenerationState {
  isGenerating: boolean;
  progress: number;
  message?: string;
  error?: ErrorResponse | null;
  lastGeneratedAt?: Date;
  generationCount: number;
}

/**
 * Estado de nutrición en el store
 */
export interface NutritionState {
  plans: NutritionPlan[];
  currentPlan: NutritionPlan | null;
  currentDay: DailyNutritionPlan | null;
  currentMeal: Meal | null;
  aiGeneration: AIGenerationState;
  isLoading: boolean;
  error: ErrorResponse | null;
}

// ============================================
// Utility Types
// ============================================

/**
 * Resultado de validación nutricional
 */
export interface NutritionValidation {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  adjustedValues?: Partial<NutritionInfo>;
}

/**
 * Estadísticas de uso de IA
 */
export interface AIUsageStats {
  dailyUsage: number;
  dailyLimit: number;
  monthlyUsage: number;
  monthlyLimit: number;
  lastResetDate: string;
}

// ============================================
// Hook Return Types
// ============================================

/**
 * Return type para useAIGeneration hook
 */
export interface UseAIGenerationReturn {
  generate: (mealId: number, options: GenerateIngredientsRequest) => Promise<GenerateIngredientsResponse>;
  isGenerating: boolean;
  progress: number;
  error: ErrorResponse | null;
  reset: () => void;
  canGenerate: boolean;
  usageStats: AIUsageStats;
}

/**
 * Return type para useNutritionPlan hook
 */
export interface UseNutritionPlanReturn {
  plan: NutritionPlan | null;
  currentDay: DailyNutritionPlan | null;
  isLoading: boolean;
  error: ErrorResponse | null;
  followPlan: (planId: number) => Promise<void>;
  unfollowPlan: () => Promise<void>;
  completeMeal: (mealId: number) => Promise<void>;
  getTodayMeals: () => Meal[];
  getProgress: () => number;
}

// ============================================
// Constants
// ============================================

export const NUTRITION_CONSTANTS = {
  CALORIES_PER_GRAM_PROTEIN: 4,
  CALORIES_PER_GRAM_CARBS: 4,
  CALORIES_PER_GRAM_FAT: 9,
  MAX_CALORIES_PER_UNIT: 9,
  MAX_MACROS_PER_UNIT: 1,
  TOLERANCE_PERCENTAGE: 0.1,
  DEFAULT_SERVINGS: 1,
  DEFAULT_LANGUAGE: 'es' as Language,
  AI_TIMEOUT_SECONDS: 30,
  RETRY_DELAY_MS: 1000,
  MAX_RETRY_ATTEMPTS: 3,
  CACHE_DURATION_MINUTES: 5,
  DAILY_GENERATION_LIMIT: 10,
  GYM_DAILY_LIMIT: 500
} as const;

// ============================================
// Validation Functions
// ============================================

/**
 * Valida que los macronutrientes sean coherentes con las calorías
 */
export function validateNutrition(nutrition: NutritionInfo): NutritionValidation {
  const errors: string[] = [];
  const warnings: string[] = [];

  const calculatedCalories =
    (nutrition.protein_g * NUTRITION_CONSTANTS.CALORIES_PER_GRAM_PROTEIN) +
    (nutrition.carbs_g * NUTRITION_CONSTANTS.CALORIES_PER_GRAM_CARBS) +
    (nutrition.fat_g * NUTRITION_CONSTANTS.CALORIES_PER_GRAM_FAT);

  const difference = Math.abs(calculatedCalories - nutrition.calories);
  const toleranceCalories = nutrition.calories * NUTRITION_CONSTANTS.TOLERANCE_PERCENTAGE;

  if (difference > toleranceCalories) {
    errors.push(`Las calorías (${nutrition.calories}) no coinciden con los macros calculados (${calculatedCalories.toFixed(1)})`);
  }

  if (nutrition.protein_g < 0 || nutrition.carbs_g < 0 || nutrition.fat_g < 0 || nutrition.fiber_g < 0) {
    errors.push('Los valores nutricionales no pueden ser negativos');
  }

  if (nutrition.fiber_g > nutrition.carbs_g) {
    warnings.push('La fibra no puede ser mayor que los carbohidratos totales');
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Calcula las calorías totales basándose en los macronutrientes
 */
export function calculateCalories(
  protein_g: number,
  carbs_g: number,
  fat_g: number
): number {
  return (
    protein_g * NUTRITION_CONSTANTS.CALORIES_PER_GRAM_PROTEIN +
    carbs_g * NUTRITION_CONSTANTS.CALORIES_PER_GRAM_CARBS +
    fat_g * NUTRITION_CONSTANTS.CALORIES_PER_GRAM_FAT
  );
}

/**
 * Formatea el tiempo de preparación en un string legible
 */
export function formatPrepTime(minutes: number): string {
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
}