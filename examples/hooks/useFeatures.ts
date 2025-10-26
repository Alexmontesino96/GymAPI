/**
 * useFeatures - Hook para verificar features habilitadas del workspace
 *
 * Este hook permite mostrar/ocultar funcionalidades según el tipo
 * de workspace y configuración.
 *
 * Features comunes:
 * - show_appointments: Mostrar agenda de citas
 * - show_class_schedule: Mostrar horario de clases
 * - show_equipment_management: Gestión de equipos
 * - show_client_progress: Progreso de clientes
 * - show_multiple_trainers: Múltiples entrenadores
 *
 * Uso:
 * ```typescript
 * function Dashboard() {
 *   const { hasFeature } = useFeatures();
 *
 *   return (
 *     <div>
 *       {hasFeature('show_appointments') && <AppointmentsWidget />}
 *       {hasFeature('show_class_schedule') && <ClassScheduleWidget />}
 *     </div>
 *   );
 * }
 * ```
 */

import { useWorkspace } from './useWorkspace';

interface UseFeaturesReturn {
  /**
   * Verificar si una feature está habilitada
   *
   * @param feature - Nombre de la feature
   * @returns true si está habilitada, false en caso contrario
   */
  hasFeature: (feature: string) => boolean;

  /**
   * Verificar múltiples features (AND lógico)
   *
   * @param features - Array de features a verificar
   * @returns true si TODAS están habilitadas
   */
  hasAllFeatures: (features: string[]) => boolean;

  /**
   * Verificar múltiples features (OR lógico)
   *
   * @param features - Array de features a verificar
   * @returns true si AL MENOS UNA está habilitada
   */
  hasAnyFeature: (features: string[]) => boolean;

  /**
   * Obtener todas las features
   */
  features: Record<string, boolean> | null;
}

export function useFeatures(): UseFeaturesReturn {
  const { context } = useWorkspace();

  const hasFeature = (feature: string): boolean => {
    if (!context?.features) {
      return false;
    }

    return context.features[feature] === true;
  };

  const hasAllFeatures = (features: string[]): boolean => {
    return features.every(feature => hasFeature(feature));
  };

  const hasAnyFeature = (features: string[]): boolean => {
    return features.some(feature => hasFeature(feature));
  };

  return {
    hasFeature,
    hasAllFeatures,
    hasAnyFeature,
    features: context?.features || null
  };
}

/**
 * Hook para features específicas de entrenadores personales
 */
export function useTrainerFeatures() {
  const { hasFeature, features } = useFeatures();

  return {
    // Features específicas de trainers
    canManageClients: hasFeature('show_client_progress'),
    canScheduleAppointments: hasFeature('show_appointments'),
    hasClientLimit: hasFeature('max_clients_limit'),
    hasPersonalBranding: hasFeature('personal_branding'),
    hasSimplifiedBilling: hasFeature('simplified_billing'),

    // Todas las features
    features
  };
}

/**
 * Hook para features específicas de gimnasios
 */
export function useGymFeatures() {
  const { hasFeature, features } = useFeatures();

  return {
    // Features específicas de gyms
    canManageEquipment: hasFeature('show_equipment_management'),
    canManageClasses: hasFeature('show_class_schedule'),
    hasMultipleTrainers: hasFeature('show_multiple_trainers'),

    // Todas las features
    features
  };
}
