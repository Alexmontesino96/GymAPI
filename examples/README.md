# 📦 Ejemplos de Código - Sistema de Entrenadores

Este directorio contiene ejemplos de código completos y funcionales para integrar el sistema de entrenadores personales en aplicaciones frontend.

## 📂 Estructura

```
examples/
├── README.md                           # Este archivo
├── services/                           # Servicios API reutilizables
│   ├── trainerService.ts              # Servicio de registro de trainers
│   ├── contextService.ts              # Servicio de contexto del workspace
│   ├── cacheService.ts                # Servicio de cache
│   └── errorHandler.ts                # Manejo de errores
├── hooks/                              # Custom hooks de React
│   ├── useWorkspace.ts                # Hook para cargar contexto
│   ├── useTerminology.ts              # Hook para terminología adaptativa
│   ├── useFeatures.ts                 # Hook para features condicionales
│   └── useBranding.ts                 # Hook para branding dinámico
├── components/                         # Componentes React reutilizables
│   ├── TrainerRegistrationForm.tsx    # Formulario completo de registro
│   ├── WorkspaceProvider.tsx          # Context Provider
│   ├── AdaptiveNavigation.tsx         # Navegación adaptativa
│   └── FeatureGuard.tsx               # Componente condicional
└── react-typescript/                   # App completa de ejemplo
    ├── package.json
    ├── tsconfig.json
    └── src/
        ├── App.tsx
        ├── pages/
        └── ...
```

## 🚀 Inicio Rápido

### 1. Copiar Servicios

Los servicios en `/services` son independientes del framework y pueden usarse en cualquier proyecto:

```typescript
// Copiar a tu proyecto
import { TrainerService } from './services/trainerService';

const service = new TrainerService('https://api.tu-app.com/api/v1');
const result = await service.registerTrainer({
  email: 'trainer@example.com',
  firstName: 'Juan',
  lastName: 'Pérez',
  specialties: ['CrossFit']
});
```

### 2. Usar Hooks (React)

Si usas React, copia los hooks de `/hooks`:

```typescript
import { useWorkspace } from './hooks/useWorkspace';
import { useTerminology } from './hooks/useTerminology';
import { useFeatures } from './hooks/useFeatures';

function MyComponent() {
  const { context, isLoading } = useWorkspace();
  const { t } = useTerminology();
  const { hasFeature } = useFeatures();

  return (
    <div>
      <h1>{t('members')}</h1> {/* "Clientes" o "Miembros" */}

      {hasFeature('show_appointments') && (
        <AppointmentsWidget />
      )}
    </div>
  );
}
```

### 3. Usar Componentes Completos

Los componentes en `/components` están listos para usar:

```typescript
import { TrainerRegistrationForm } from './components/TrainerRegistrationForm';
import { WorkspaceProvider } from './components/WorkspaceProvider';

function App() {
  return (
    <WorkspaceProvider>
      <TrainerRegistrationForm
        onSuccess={(result) => {
          console.log('Trainer registered:', result);
          navigate('/dashboard');
        }}
        onError={(error) => {
          console.error('Error:', error);
        }}
      />
    </WorkspaceProvider>
  );
}
```

## 📚 Ejemplos por Categoría

### Servicios API

#### TrainerService - Registro y validaciones

```typescript
import { TrainerService } from './services/trainerService';

const service = new TrainerService();

// Registrar entrenador
const result = await service.registerTrainer({
  email: 'maria@trainer.com',
  firstName: 'María',
  lastName: 'González',
  phone: '+525587654321',
  specialties: ['Yoga', 'Pilates'],
  maxClients: 20
});

// Verificar email disponible
const available = await service.checkEmailAvailability('test@trainer.com');

// Validar subdomain
const valid = await service.validateSubdomain('maria-gonzalez');
```

#### ContextService - Cargar contexto del workspace

```typescript
import { ContextService } from './services/contextService';

const service = new ContextService();
const token = localStorage.getItem('auth_token');
const gymId = parseInt(localStorage.getItem('gym_id')!);

// Cargar contexto con cache automático
const context = await service.loadWorkspaceContext(token, gymId);

console.log(context.workspace.type); // "personal_trainer" o "gym"
console.log(context.terminology.members); // "clientes" o "miembros"
console.log(context.features.show_appointments); // true/false
```

### Hooks Personalizados

#### useWorkspace - Gestión de estado del workspace

```typescript
import { useWorkspace } from './hooks/useWorkspace';

function Dashboard() {
  const { context, isLoading, error, reload } = useWorkspace();

  if (isLoading) return <Spinner />;
  if (error) return <Error message={error} />;

  return (
    <div>
      <h1>Bienvenido a {context.workspace.display_name}</h1>
      <p>Tipo: {context.workspace.entity_label}</p>
      <button onClick={reload}>Recargar</button>
    </div>
  );
}
```

#### useTerminology - Textos adaptativos

```typescript
import { useTerminology } from './hooks/useTerminology';

function MembersList() {
  const { t } = useTerminology();

  return (
    <div>
      <h1>Lista de {t('members', 'Miembros')}</h1>
      <button>Agregar {t('member', 'Miembro')}</button>
      <p>Total de {t('members')}: 15</p>
    </div>
  );
}
```

#### useFeatures - Features condicionales

```typescript
import { useFeatures } from './hooks/useFeatures';

function Dashboard() {
  const { hasFeature } = useFeatures();

  return (
    <div className="dashboard">
      {hasFeature('show_appointments') && <AppointmentsWidget />}
      {hasFeature('show_class_schedule') && <ClassScheduleWidget />}
      {hasFeature('show_client_progress') && <ProgressWidget />}
      {!hasFeature('show_equipment_management') && null}
    </div>
  );
}
```

### Componentes Completos

#### TrainerRegistrationForm - Formulario completo con validación

```typescript
import { TrainerRegistrationForm } from './components/TrainerRegistrationForm';

function RegistrationPage() {
  const navigate = useNavigate();

  return (
    <TrainerRegistrationForm
      onSuccess={(result) => {
        // Guardar datos
        localStorage.setItem('gym_id', result.workspace.id);
        localStorage.setItem('user_id', result.user.id);

        // Redirigir
        if (result.stripe_onboarding_url) {
          window.location.href = result.stripe_onboarding_url;
        } else {
          navigate('/dashboard');
        }
      }}
      onError={(error) => {
        alert(error.message);
      }}
    />
  );
}
```

#### FeatureGuard - Renderizado condicional

```typescript
import { FeatureGuard } from './components/FeatureGuard';

function App() {
  return (
    <div>
      <FeatureGuard feature="show_appointments">
        <AppointmentsSection />
      </FeatureGuard>

      <FeatureGuard feature="show_equipment_management">
        <EquipmentSection />
      </FeatureGuard>

      <FeatureGuard feature="show_client_progress" fallback={<div>No disponible</div>}>
        <ProgressSection />
      </FeatureGuard>
    </div>
  );
}
```

## 🎨 Patrones de Uso

### Patrón 1: App con UI Adaptativa

```typescript
import { WorkspaceProvider } from './components/WorkspaceProvider';
import { useTerminology } from './hooks/useTerminology';
import { useFeatures } from './hooks/useFeatures';

function App() {
  return (
    <WorkspaceProvider>
      <AdaptiveApp />
    </WorkspaceProvider>
  );
}

function AdaptiveApp() {
  const { t } = useTerminology();
  const { hasFeature } = useFeatures();

  return (
    <div>
      <nav>
        <Link to="/clients">{t('members')}</Link>

        {hasFeature('show_appointments') && (
          <Link to="/appointments">{t('schedule')}</Link>
        )}

        {hasFeature('show_class_schedule') && (
          <Link to="/classes">{t('classes')}</Link>
        )}
      </nav>

      <Routes>
        <Route path="/clients" element={<ClientsPage />} />
        {/* ... */}
      </Routes>
    </div>
  );
}
```

### Patrón 2: Registro con Validación en Tiempo Real

```typescript
import { useState, useEffect } from 'react';
import { TrainerService } from './services/trainerService';
import { debounce } from 'lodash';

function RegistrationForm() {
  const [email, setEmail] = useState('');
  const [emailValid, setEmailValid] = useState<boolean | null>(null);
  const service = new TrainerService();

  // Validación debounced
  const checkEmail = debounce(async (email: string) => {
    if (!email.includes('@')) return;

    const result = await service.checkEmailAvailability(email);
    setEmailValid(result.available);
  }, 500);

  useEffect(() => {
    checkEmail(email);
  }, [email]);

  return (
    <input
      type="email"
      value={email}
      onChange={(e) => setEmail(e.target.value)}
      className={emailValid ? 'valid' : emailValid === false ? 'invalid' : ''}
    />
  );
}
```

### Patrón 3: Dashboard con Estadísticas Adaptativas

```typescript
import { useWorkspace } from './hooks/useWorkspace';
import { ContextService } from './services/contextService';

function Dashboard() {
  const { context } = useWorkspace();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const loadStats = async () => {
      const service = new ContextService();
      const token = localStorage.getItem('auth_token')!;
      const gymId = context.workspace.id;

      const data = await service.getWorkspaceStats(token, gymId);
      setStats(data);
    };

    if (context) loadStats();
  }, [context]);

  if (!stats) return <Spinner />;

  return (
    <div>
      {context.workspace.is_personal_trainer ? (
        <TrainerDashboard
          activeClients={stats.metrics.active_clients}
          maxClients={stats.metrics.max_clients}
          capacity={stats.metrics.capacity_percentage}
          sessions={stats.metrics.sessions_this_week}
        />
      ) : (
        <GymDashboard
          members={stats.metrics.total_members}
          trainers={stats.metrics.active_trainers}
          classes={stats.metrics.active_classes}
        />
      )}
    </div>
  );
}
```

## 🔧 Instalación en Tu Proyecto

### React + TypeScript

```bash
# Instalar dependencias
npm install axios lodash
npm install -D @types/lodash

# Copiar archivos
cp -r examples/services src/
cp -r examples/hooks src/
cp -r examples/components src/

# Importar en tu App
import { WorkspaceProvider } from './components/WorkspaceProvider';
import { TrainerRegistrationForm } from './components/TrainerRegistrationForm';
```

### Vue 3 + TypeScript

```bash
# Instalar dependencias
npm install axios

# Copiar servicios (funcionan en cualquier framework)
cp -r examples/services src/

# Crear composables basados en los hooks
# Ver ejemplos/vue-composables/
```

## 📖 Documentación Relacionada

- [API Documentation](../docs/TRAINER_API_DOCUMENTATION.md) - Referencia completa de la API
- [Integration Guide](../docs/TRAINER_INTEGRATION_GUIDE.md) - Guía de integración detallada
- [Implementation Summary](../IMPLEMENTATION_SUMMARY.md) - Resumen de la implementación

## 💡 Tips y Trucos

### 1. Debugging del Contexto

```typescript
// Agregar en App.tsx para debugging
import { useWorkspace } from './hooks/useWorkspace';

function DebugPanel() {
  const { context } = useWorkspace();

  if (process.env.NODE_ENV !== 'development') return null;

  return (
    <div style={{ position: 'fixed', bottom: 0, right: 0, background: '#000', color: '#0f0', padding: '1rem' }}>
      <h4>Debug Info</h4>
      <pre>{JSON.stringify(context, null, 2)}</pre>
    </div>
  );
}
```

### 2. Mock Data para Testing

```typescript
// services/mockData.ts
export const mockTrainerContext = {
  workspace: {
    id: 1,
    name: 'Entrenamiento Personal Test',
    type: 'personal_trainer',
    is_personal_trainer: true,
    // ...
  },
  terminology: {
    members: 'clientes',
    member: 'cliente',
    // ...
  },
  features: {
    show_appointments: true,
    show_class_schedule: false,
    // ...
  }
};

// Usar en tests
const service = new ContextService();
service.setMockData(mockTrainerContext);
```

### 3. Manejo de Errores Global

```typescript
// App.tsx
import { ErrorBoundary } from 'react-error-boundary';

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <div role="alert">
      <p>Algo salió mal:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Reintentar</button>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <WorkspaceProvider>
        <Routes />
      </WorkspaceProvider>
    </ErrorBoundary>
  );
}
```

## 🤝 Contribuir

Si encuentras bugs o tienes mejoras para estos ejemplos:

1. Crea un issue describiendo el problema
2. Envía un PR con la solución
3. Actualiza la documentación si es necesario

---

**Última actualización**: 2024-01-24
**Versión**: 1.0.0
