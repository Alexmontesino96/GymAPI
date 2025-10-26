/**
 * FeatureGuard - Componente para renderizado condicional basado en features
 *
 * Este componente muestra u oculta su contenido según si una feature
 * está habilitada en el workspace actual.
 *
 * Uso:
 * ```typescript
 * <FeatureGuard feature="show_appointments">
 *   <AppointmentsWidget />
 * </FeatureGuard>
 *
 * <FeatureGuard
 *   feature="show_equipment_management"
 *   fallback={<div>No disponible</div>}
 * >
 *   <EquipmentWidget />
 * </FeatureGuard>
 * ```
 */

import React from 'react';
import { useFeatures } from '../hooks/useFeatures';

interface FeatureGuardProps {
  /**
   * Nombre de la feature a verificar
   */
  feature: string;

  /**
   * Contenido a mostrar si la feature está habilitada
   */
  children: React.ReactNode;

  /**
   * Contenido a mostrar si la feature NO está habilitada (opcional)
   */
  fallback?: React.ReactNode;

  /**
   * Callback cuando la feature no está habilitada
   */
  onFeatureDisabled?: () => void;
}

export function FeatureGuard({
  feature,
  children,
  fallback,
  onFeatureDisabled
}: FeatureGuardProps) {
  const { hasFeature } = useFeatures();

  const isEnabled = hasFeature(feature);

  // Ejecutar callback si la feature no está habilitada
  React.useEffect(() => {
    if (!isEnabled && onFeatureDisabled) {
      onFeatureDisabled();
    }
  }, [isEnabled, onFeatureDisabled]);

  if (!isEnabled) {
    return <>{fallback || null}</>;
  }

  return <>{children}</>;
}

/**
 * MultiFeatureGuard - Verifica múltiples features
 *
 * Uso:
 * ```typescript
 * <MultiFeatureGuard
 *   features={['show_appointments', 'show_client_progress']}
 *   requireAll={true}
 * >
 *   <ComplexWidget />
 * </MultiFeatureGuard>
 * ```
 */
interface MultiFeatureGuardProps {
  /**
   * Lista de features a verificar
   */
  features: string[];

  /**
   * Si es true, requiere que TODAS las features estén habilitadas (AND)
   * Si es false, requiere que AL MENOS UNA esté habilitada (OR)
   */
  requireAll?: boolean;

  /**
   * Contenido a mostrar si las features están habilitadas
   */
  children: React.ReactNode;

  /**
   * Contenido alternativo
   */
  fallback?: React.ReactNode;
}

export function MultiFeatureGuard({
  features,
  requireAll = true,
  children,
  fallback
}: MultiFeatureGuardProps) {
  const { hasAllFeatures, hasAnyFeature } = useFeatures();

  const isEnabled = requireAll
    ? hasAllFeatures(features)
    : hasAnyFeature(features);

  if (!isEnabled) {
    return <>{fallback || null}</>;
  }

  return <>{children}</>;
}

/**
 * WorkspaceTypeGuard - Muestra contenido según el tipo de workspace
 *
 * Uso:
 * ```typescript
 * <WorkspaceTypeGuard type="personal_trainer">
 *   <TrainerDashboard />
 * </WorkspaceTypeGuard>
 *
 * <WorkspaceTypeGuard type="gym">
 *   <GymDashboard />
 * </WorkspaceTypeGuard>
 * ```
 */
interface WorkspaceTypeGuardProps {
  /**
   * Tipo de workspace requerido
   */
  type: 'gym' | 'personal_trainer';

  /**
   * Contenido a mostrar si coincide el tipo
   */
  children: React.ReactNode;

  /**
   * Contenido alternativo
   */
  fallback?: React.ReactNode;
}

export function WorkspaceTypeGuard({
  type,
  children,
  fallback
}: WorkspaceTypeGuardProps) {
  const { context } = useFeatures() as any; // Usamos useWorkspace indirectamente

  // Necesitamos importar useWorkspace aquí
  const { context: workspaceContext } = require('../hooks/useWorkspace').useWorkspace();

  if (!workspaceContext) {
    return null;
  }

  const matches = workspaceContext.workspace.type === type;

  if (!matches) {
    return <>{fallback || null}</>;
  }

  return <>{children}</>;
}
