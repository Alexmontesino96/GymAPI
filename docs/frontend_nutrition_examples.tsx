// 🍎 Ejemplos de Hooks y Componentes React para Sistema Híbrido
// Ejemplos prácticos para implementar en el frontend

import React, { useState, useEffect, useCallback } from 'react';
import { 
  NutritionPlan, 
  PlanType, 
  PlanStatus, 
  TodayMealPlan, 
  NutritionDashboardHybrid,
  PlanStatusInfo,
  NutritionPlanFilters,
  LivePlanStatusUpdate,
  ArchivePlanRequest,
  PLAN_TYPE_CONFIG,
  PLAN_STATUS_CONFIG,
  NUTRITION_ENDPOINTS,
  formatDate,
  formatDateShort,
  getDaysUntilStart,
  isPlanActive,
  isPlanStartingSoon,
  buildPlanFilters
} from './frontend_nutrition_types';

// ===== HOOKS =====

/**
 * Hook para manejar la lista de planes nutricionales
 */
export const useNutritionPlans = () => {
  const [plans, setPlans] = useState<NutritionPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPlans = useCallback(async (filters?: NutritionPlanFilters) => {
    setLoading(true);
    setError(null);

    try {
      const params = filters ? buildPlanFilters(filters) : '';
      const url = `${NUTRITION_ENDPOINTS.PLANS}?${params}`;
      
      const response = await fetch(url);
      if (!response.ok) throw new Error('Error al cargar planes');
      
      const data = await response.json();
      setPlans(data.plans || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  }, []);

  const followPlan = useCallback(async (planId: number) => {
    try {
      const response = await fetch(NUTRITION_ENDPOINTS.FOLLOW(planId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) throw new Error('Error al seguir plan');
      
      // Actualizar el plan en la lista
      setPlans(prev => prev.map(plan => 
        plan.id === planId 
          ? { ...plan, is_following: true }
          : plan
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al seguir plan');
    }
  }, []);

  const unfollowPlan = useCallback(async (planId: number) => {
    try {
      const response = await fetch(NUTRITION_ENDPOINTS.UNFOLLOW(planId), {
        method: 'DELETE'
      });
      
      if (!response.ok) throw new Error('Error al dejar de seguir plan');
      
      setPlans(prev => prev.map(plan => 
        plan.id === planId 
          ? { ...plan, is_following: false }
          : plan
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al dejar de seguir plan');
    }
  }, []);

  return {
    plans,
    loading,
    error,
    fetchPlans,
    followPlan,
    unfollowPlan
  };
};

/**
 * Hook para manejar el plan de hoy
 */
export const useTodayPlan = () => {
  const [todayPlan, setTodayPlan] = useState<TodayMealPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTodayPlan = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(NUTRITION_ENDPOINTS.TODAY);
      if (!response.ok) throw new Error('Error al cargar plan de hoy');
      
      const data = await response.json();
      setTodayPlan(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  }, []);

  const completeMeal = useCallback(async (mealId: number) => {
    try {
      const response = await fetch(`/api/v1/nutrition/meals/${mealId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) throw new Error('Error al completar comida');
      
      // Refrescar el plan de hoy
      await fetchTodayPlan();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al completar comida');
    }
  }, [fetchTodayPlan]);

  const uncompleteMeal = useCallback(async (mealId: number) => {
    try {
      const response = await fetch(`/api/v1/nutrition/meals/${mealId}/uncomplete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) throw new Error('Error al desmarcar comida');
      
      await fetchTodayPlan();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al desmarcar comida');
    }
  }, [fetchTodayPlan]);

  useEffect(() => {
    fetchTodayPlan();
  }, [fetchTodayPlan]);

  return {
    todayPlan,
    loading,
    error,
    completeMeal,
    uncompleteMeal,
    refresh: fetchTodayPlan
  };
};

/**
 * Hook para manejar el dashboard híbrido
 */
export const useNutritionDashboard = () => {
  const [dashboard, setDashboard] = useState<NutritionDashboardHybrid | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(NUTRITION_ENDPOINTS.DASHBOARD);
      if (!response.ok) throw new Error('Error al cargar dashboard');
      
      const data = await response.json();
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  return {
    dashboard,
    loading,
    error,
    refresh: fetchDashboard
  };
};

/**
 * Hook para manejar el estado de un plan específico
 */
export const usePlanStatus = (planId: number) => {
  const [status, setStatus] = useState<PlanStatusInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(NUTRITION_ENDPOINTS.PLAN_STATUS(planId));
      if (!response.ok) throw new Error('Error al cargar estado del plan');
      
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  }, [planId]);

  const updateStatus = useCallback(async (update: LivePlanStatusUpdate) => {
    try {
      const response = await fetch(NUTRITION_ENDPOINTS.LIVE_STATUS(planId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update)
      });
      
      if (!response.ok) throw new Error('Error al actualizar estado');
      
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al actualizar estado');
    }
  }, [planId, fetchStatus]);

  const archivePlan = useCallback(async (request: ArchivePlanRequest) => {
    try {
      const response = await fetch(NUTRITION_ENDPOINTS.ARCHIVE(planId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });
      
      if (!response.ok) throw new Error('Error al archivar plan');
      
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al archivar plan');
    }
  }, [planId, fetchStatus]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return {
    status,
    loading,
    error,
    updateStatus,
    archivePlan
  };
};

// ===== COMPONENTES =====

/**
 * Componente para mostrar el tipo de plan
 */
interface PlanTypeIndicatorProps {
  plan: NutritionPlan;
  size?: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}

export const PlanTypeIndicator: React.FC<PlanTypeIndicatorProps> = ({
  plan,
  size = 'medium',
  showLabel = true
}) => {
  const config = PLAN_TYPE_CONFIG[plan.plan_type];
  
  const sizeClasses = {
    small: 'px-2 py-1 text-xs',
    medium: 'px-3 py-1 text-sm',
    large: 'px-4 py-2 text-base'
  };

  return (
    <span 
      className={`inline-flex items-center rounded-full font-medium ${sizeClasses[size]} bg-${config.color}-100 text-${config.color}-800`}
    >
      <span className="mr-1">{config.icon}</span>
      {showLabel && config.label}
    </span>
  );
};

/**
 * Componente para mostrar el estado de un plan live
 */
interface LivePlanStatusProps {
  plan: NutritionPlan;
  showParticipants?: boolean;
  showCountdown?: boolean;
}

export const LivePlanStatus: React.FC<LivePlanStatusProps> = ({
  plan,
  showParticipants = true,
  showCountdown = true
}) => {
  if (plan.plan_type !== PlanType.LIVE) return null;

  const renderStatus = () => {
    if (plan.status === PlanStatus.NOT_STARTED && showCountdown) {
      return (
        <div className="flex items-center space-x-2 text-gray-600">
          <span>⏰</span>
          <span>Empieza en {plan.days_until_start} días</span>
          <span className="text-sm">({formatDateShort(plan.live_start_date!)})</span>
        </div>
      );
    }
    
    if (plan.status === PlanStatus.RUNNING) {
      return (
        <div className="flex items-center space-x-2 text-green-600">
          <span>🔴</span>
          <span className="font-medium">LIVE - Día {plan.current_day}</span>
          {showParticipants && (
            <span className="text-sm">
              👥 {plan.live_participants_count} participantes
            </span>
          )}
        </div>
      );
    }
    
    return (
      <div className="flex items-center space-x-2 text-blue-600">
        <span>✅</span>
        <span>Plan terminado</span>
      </div>
    );
  };

  return <div className="mt-2">{renderStatus()}</div>;
};

/**
 * Tarjeta de plan universal que se adapta al tipo
 */
interface PlanCardProps {
  plan: NutritionPlan;
  onFollow?: (planId: number) => void;
  onUnfollow?: (planId: number) => void;
  onSelect?: (planId: number) => void;
  className?: string;
}

export const PlanCard: React.FC<PlanCardProps> = ({
  plan,
  onFollow,
  onUnfollow,
  onSelect,
  className = ''
}) => {
  const handleAction = () => {
    if (onSelect) {
      onSelect(plan.id);
      return;
    }

    if (plan.is_following && onUnfollow) {
      onUnfollow(plan.id);
    } else if (!plan.is_following && onFollow) {
      onFollow(plan.id);
    }
  };

  const getActionText = () => {
    if (plan.plan_type === PlanType.LIVE) {
      if (plan.status === PlanStatus.FINISHED) return 'Plan Terminado';
      if (plan.status === PlanStatus.NOT_STARTED) return 'Reservar Lugar';
      return plan.is_following ? 'Siguiendo' : 'Unirse';
    }
    
    return plan.is_following ? 'Siguiendo' : 'Empezar Plan';
  };

  const isActionDisabled = () => {
    return plan.plan_type === PlanType.LIVE && plan.status === PlanStatus.FINISHED;
  };

  return (
    <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
      <div className="flex justify-between items-start mb-3">
        <PlanTypeIndicator plan={plan} />
        {isPlanStartingSoon(plan) && (
          <span className="bg-orange-100 text-orange-800 px-2 py-1 rounded-full text-xs">
            🔥 Empieza pronto
          </span>
        )}
      </div>

      <h3 className="text-xl font-semibold mb-2">{plan.title}</h3>
      
      {plan.description && (
        <p className="text-gray-600 mb-3">{plan.description}</p>
      )}

      <div className="flex items-center space-x-4 mb-3 text-sm text-gray-500">
        <span>📊 {plan.duration_days} días</span>
        <span>🎯 {plan.goal.replace('_', ' ')}</span>
        <span>⭐ {plan.difficulty_level}</span>
      </div>

      {plan.plan_type === PlanType.LIVE && (
        <LivePlanStatus plan={plan} />
      )}

      {plan.plan_type === PlanType.ARCHIVED && (
        <div className="mt-2 text-sm text-purple-600">
          <span>📊 Probado por {plan.original_participants_count} usuarios</span>
        </div>
      )}

      <div className="flex items-center justify-between mt-4">
        <div className="text-sm text-gray-500">
          por {plan.created_by_name}
        </div>
        
        <button
          onClick={handleAction}
          disabled={isActionDisabled()}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            isActionDisabled()
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : plan.is_following
              ? 'bg-green-100 text-green-800 hover:bg-green-200'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {getActionText()}
        </button>
      </div>
    </div>
  );
};

/**
 * Sección del plan de hoy
 */
interface TodaySectionProps {
  plan?: TodayMealPlan;
  onMealComplete?: (mealId: number) => void;
  onMealUncomplete?: (mealId: number) => void;
  onExplorePlans?: () => void;
}

export const TodaySection: React.FC<TodaySectionProps> = ({
  plan,
  onMealComplete,
  onMealUncomplete,
  onExplorePlans
}) => {
  if (!plan?.plan) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-2xl font-bold mb-4">📅 Hoy</h2>
        <p className="text-gray-600 mb-4">No tienes planes activos para hoy</p>
        <button
          onClick={onExplorePlans}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Explorar Planes
        </button>
      </div>
    );
  }

  const renderMessage = () => {
    if (plan.status === PlanStatus.NOT_STARTED) {
      return (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-4">
          <p className="text-orange-800">
            ⏰ Tu plan "{plan.plan.title}" empieza en {plan.days_until_start} días
          </p>
        </div>
      );
    }
    
    if (plan.status === PlanStatus.RUNNING) {
      return (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold">
              🍽️ Día {plan.current_day} - {plan.plan.title}
            </h3>
            <PlanTypeIndicator plan={plan.plan} size="small" />
          </div>
          <p className="text-gray-600 mb-2">{plan.meals.length} comidas programadas</p>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-green-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${plan.completion_percentage}%` }}
            />
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {plan.completion_percentage.toFixed(0)}% completado
          </p>
        </div>
      );
    }
    
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
        <p className="text-green-800">✅ Plan completado</p>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-2xl font-bold mb-4">📅 Hoy</h2>
      {renderMessage()}
      
      {plan.meals.length > 0 && (
        <div className="space-y-3">
          {plan.meals.map((meal) => (
            <div 
              key={meal.id}
              className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">{meal.meal_name}</h4>
                  <p className="text-sm text-gray-600">{meal.meal_type}</p>
                  <p className="text-sm text-gray-500">{meal.calories} cal</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => onMealComplete?.(meal.id)}
                    className="text-green-600 hover:text-green-800"
                  >
                    ✅
                  </button>
                  <button
                    onClick={() => onMealUncomplete?.(meal.id)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    ❌
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Dashboard híbrido completo
 */
export const NutritionDashboard: React.FC = () => {
  const { dashboard, loading, error } = useNutritionDashboard();
  const { followPlan, unfollowPlan } = useNutritionPlans();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Cargando dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    );
  }

  if (!dashboard) return null;

  return (
    <div className="space-y-8">
      {/* Plan de Hoy */}
      <TodaySection plan={dashboard.today_plan} />
      
      {/* Planes Live */}
      {dashboard.live_plans.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold mb-4">🔴 Planes Live</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {dashboard.live_plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onFollow={followPlan}
                onUnfollow={unfollowPlan}
              />
            ))}
          </div>
        </section>
      )}
      
      {/* Mis Planes Template */}
      {dashboard.template_plans.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold mb-4">📋 Mis Planes</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {dashboard.template_plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onFollow={followPlan}
                onUnfollow={unfollowPlan}
              />
            ))}
          </div>
        </section>
      )}
      
      {/* Planes Disponibles */}
      {dashboard.available_plans.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold mb-4">📚 Descubrir</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {dashboard.available_plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onFollow={followPlan}
                onUnfollow={unfollowPlan}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

// ===== EJEMPLO DE USO =====

/**
 * Ejemplo de página principal de nutrición
 */
export const NutritionPage: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          🍎 Sistema de Nutrición
        </h1>
        <p className="text-gray-600">
          Gestiona tus planes nutricionales con nuestro sistema híbrido
        </p>
      </div>
      
      <NutritionDashboard />
    </div>
  );
}; 