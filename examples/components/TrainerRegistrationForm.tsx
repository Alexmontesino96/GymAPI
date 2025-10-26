/**
 * TrainerRegistrationForm - Formulario completo de registro de entrenadores
 *
 * Este componente incluye:
 * - Validación en tiempo real de email
 * - Validación de campos
 * - Manejo de errores
 * - Estados de loading
 * - Feedback visual
 *
 * Uso:
 * ```typescript
 * <TrainerRegistrationForm
 *   onSuccess={(result) => {
 *     console.log('Registrado:', result);
 *     navigate('/dashboard');
 *   }}
 *   onError={(error) => {
 *     console.error('Error:', error);
 *   }}
 * />
 * ```
 */

import React, { useState, useEffect } from 'react';
import { TrainerService, TrainerRegistrationResponse, APIError } from '../services/trainerService';

interface TrainerRegistrationFormProps {
  /**
   * Callback cuando el registro es exitoso
   */
  onSuccess: (result: TrainerRegistrationResponse) => void;

  /**
   * Callback cuando ocurre un error
   */
  onError?: (error: APIError) => void;

  /**
   * Servicio personalizado (opcional, para testing)
   */
  service?: TrainerService;
}

interface FormData {
  email: string;
  firstName: string;
  lastName: string;
  phone: string;
  specialties: string;
  bio: string;
  maxClients: number;
}

interface FormErrors {
  email?: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
  specialties?: string;
}

export function TrainerRegistrationForm({
  onSuccess,
  onError,
  service
}: TrainerRegistrationFormProps) {
  const trainerService = service || new TrainerService();

  // Form state
  const [formData, setFormData] = useState<FormData>({
    email: '',
    firstName: '',
    lastName: '',
    phone: '',
    specialties: '',
    bio: '',
    maxClients: 30
  });

  // Validation state
  const [errors, setErrors] = useState<FormErrors>({});
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);
  const [isCheckingEmail, setIsCheckingEmail] = useState(false);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Validar email en tiempo real (debounced)
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (formData.email && formData.email.includes('@')) {
        setIsCheckingEmail(true);
        try {
          const result = await trainerService.checkEmailAvailability(formData.email);
          setEmailAvailable(result.available);

          if (!result.available) {
            setErrors(prev => ({
              ...prev,
              email: 'Email ya registrado'
            }));
          } else {
            setErrors(prev => {
              const { email, ...rest } = prev;
              return rest;
            });
          }
        } catch (err) {
          console.error('Error checking email:', err);
        } finally {
          setIsCheckingEmail(false);
        }
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [formData.email]);

  // Validar campos
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.email) {
      newErrors.email = 'Email es requerido';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Email inválido';
    } else if (emailAvailable === false) {
      newErrors.email = 'Email ya registrado';
    }

    if (!formData.firstName || formData.firstName.length < 2) {
      newErrors.firstName = 'Nombre debe tener al menos 2 caracteres';
    }

    if (!formData.lastName || formData.lastName.length < 2) {
      newErrors.lastName = 'Apellido debe tener al menos 2 caracteres';
    }

    if (formData.phone && !/^\+?[1-9]\d{1,14}$/.test(formData.phone.replace(/[\s-]/g, ''))) {
      newErrors.phone = 'Formato de teléfono inválido (ej: +525512345678)';
    }

    if (!formData.specialties) {
      newErrors.specialties = 'Agrega al menos una especialidad';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Manejar envío del formulario
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const result = await trainerService.registerTrainer({
        email: formData.email,
        firstName: formData.firstName,
        lastName: formData.lastName,
        phone: formData.phone || undefined,
        specialties: formData.specialties.split(',').map(s => s.trim()).filter(Boolean),
        maxClients: formData.maxClients,
        bio: formData.bio || undefined
      });

      onSuccess(result);

    } catch (err: any) {
      const apiError = err as APIError;
      setSubmitError(apiError.message);

      if (onError) {
        onError(apiError);
      }

    } finally {
      setIsSubmitting(false);
    }
  };

  // Actualizar campo del formulario
  const updateField = (field: keyof FormData, value: string | number) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="trainer-registration-form">
      <h2>Registro de Entrenador Personal</h2>

      {/* Error general */}
      {submitError && (
        <div className="alert alert-danger">
          {submitError}
        </div>
      )}

      {/* Email */}
      <div className="form-group">
        <label htmlFor="email">
          Email *
          {isCheckingEmail && <span className="spinner-small">Verificando...</span>}
        </label>
        <input
          type="email"
          id="email"
          value={formData.email}
          onChange={(e) => updateField('email', e.target.value)}
          className={
            errors.email ? 'is-invalid' :
            emailAvailable === true ? 'is-valid' : ''
          }
          required
        />
        {errors.email && <div className="invalid-feedback">{errors.email}</div>}
        {emailAvailable === true && (
          <div className="valid-feedback">✓ Email disponible</div>
        )}
      </div>

      {/* Nombre */}
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="firstName">Nombre *</label>
          <input
            type="text"
            id="firstName"
            value={formData.firstName}
            onChange={(e) => updateField('firstName', e.target.value)}
            className={errors.firstName ? 'is-invalid' : ''}
            required
          />
          {errors.firstName && <div className="invalid-feedback">{errors.firstName}</div>}
        </div>

        <div className="form-group">
          <label htmlFor="lastName">Apellido *</label>
          <input
            type="text"
            id="lastName"
            value={formData.lastName}
            onChange={(e) => updateField('lastName', e.target.value)}
            className={errors.lastName ? 'is-invalid' : ''}
            required
          />
          {errors.lastName && <div className="invalid-feedback">{errors.lastName}</div>}
        </div>
      </div>

      {/* Teléfono */}
      <div className="form-group">
        <label htmlFor="phone">
          Teléfono
          <small>(Formato internacional: +525512345678)</small>
        </label>
        <input
          type="tel"
          id="phone"
          value={formData.phone}
          onChange={(e) => updateField('phone', e.target.value)}
          className={errors.phone ? 'is-invalid' : ''}
          placeholder="+525512345678"
        />
        {errors.phone && <div className="invalid-feedback">{errors.phone}</div>}
      </div>

      {/* Especialidades */}
      <div className="form-group">
        <label htmlFor="specialties">
          Especialidades *
          <small>(Separadas por comas)</small>
        </label>
        <input
          type="text"
          id="specialties"
          value={formData.specialties}
          onChange={(e) => updateField('specialties', e.target.value)}
          className={errors.specialties ? 'is-invalid' : ''}
          placeholder="CrossFit, Nutrición, Yoga"
          required
        />
        {errors.specialties && <div className="invalid-feedback">{errors.specialties}</div>}
      </div>

      {/* Máximo de clientes */}
      <div className="form-group">
        <label htmlFor="maxClients">
          Máximo de clientes simultáneos
        </label>
        <input
          type="number"
          id="maxClients"
          value={formData.maxClients}
          onChange={(e) => updateField('maxClients', parseInt(e.target.value))}
          min="1"
          max="200"
        />
      </div>

      {/* Biografía */}
      <div className="form-group">
        <label htmlFor="bio">
          Biografía
          <small>(Opcional, máx 500 caracteres)</small>
        </label>
        <textarea
          id="bio"
          value={formData.bio}
          onChange={(e) => updateField('bio', e.target.value)}
          maxLength={500}
          rows={4}
          placeholder="Cuéntanos sobre tu experiencia y enfoque como entrenador..."
        />
        <small>{formData.bio.length}/500</small>
      </div>

      {/* Botón de envío */}
      <button
        type="submit"
        disabled={isSubmitting || emailAvailable === false}
        className="btn btn-primary"
      >
        {isSubmitting ? 'Registrando...' : 'Crear Cuenta'}
      </button>
    </form>
  );
}

/**
 * Estilos CSS recomendados (copiar a tu archivo CSS)
 */
export const RECOMMENDED_STYLES = `
.trainer-registration-form {
  max-width: 600px;
  margin: 2rem auto;
  padding: 2rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.form-group small {
  display: block;
  margin-top: 0.25rem;
  color: #6c757d;
  font-size: 0.875rem;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 1rem;
}

.form-group input.is-valid {
  border-color: #28a745;
}

.form-group input.is-invalid {
  border-color: #dc3545;
}

.valid-feedback {
  color: #28a745;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.invalid-feedback {
  color: #dc3545;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.alert {
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 4px;
}

.alert-danger {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.btn {
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background-color: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #0056b3;
}
`;
