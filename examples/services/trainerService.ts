/**
 * TrainerService - Servicio para gestión de entrenadores personales
 *
 * Este servicio proporciona métodos para:
 * - Registrar nuevos entrenadores
 * - Verificar disponibilidad de email
 * - Validar subdomains
 *
 * Uso:
 * ```typescript
 * const service = new TrainerService('https://api.tu-app.com/api/v1');
 * const result = await service.registerTrainer({
 *   email: 'trainer@example.com',
 *   firstName: 'Juan',
 *   lastName: 'Pérez',
 *   specialties: ['CrossFit']
 * });
 * ```
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

export interface TrainerRegistrationData {
  email: string;
  firstName: string;
  lastName: string;
  phone?: string;
  specialties?: string[];
  certifications?: {
    name: string;
    year?: number;
    institution?: string;
    credential_id?: string;
  }[];
  timezone?: string;
  maxClients?: number;
  bio?: string;
}

export interface TrainerRegistrationResponse {
  success: boolean;
  message: string;
  workspace: {
    id: number;
    name: string;
    subdomain: string;
    type: string;
    email: string;
    timezone: string;
    specialties: string[];
    max_clients: number;
  };
  user: {
    id: number;
    email: string;
    name: string;
    role: string;
  };
  modules_activated: string[];
  payment_plans: string[];
  stripe_onboarding_url?: string;
  next_steps: string[];
}

export interface EmailCheckResponse {
  available: boolean;
  message: string;
  has_workspace?: boolean;
  details?: {
    user_id?: number;
    is_trainer?: boolean;
  };
}

export interface SubdomainValidationResponse {
  valid: boolean;
  available: boolean;
  message: string;
  subdomain?: string;
}

export class APIError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public errorCode?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export class TrainerService {
  private client: AxiosInstance;

  constructor(baseURL: string = 'http://localhost:8000/api/v1') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 30000 // 30 segundos
    });

    // Interceptor para manejar errores
    this.client.interceptors.response.use(
      response => response,
      this.handleError
    );
  }

  /**
   * Registrar un nuevo entrenador personal
   *
   * @param data - Datos del entrenador
   * @returns Respuesta con información del workspace creado
   * @throws APIError si hay un error en el registro
   */
  async registerTrainer(data: TrainerRegistrationData): Promise<TrainerRegistrationResponse> {
    try {
      const response = await this.client.post<TrainerRegistrationResponse>(
        '/auth/register-trainer',
        {
          email: data.email,
          first_name: data.firstName,
          last_name: data.lastName,
          phone: data.phone,
          specialties: data.specialties || ['Fitness General'],
          certifications: data.certifications || [],
          timezone: data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
          max_clients: data.maxClients || 30,
          bio: data.bio
        }
      );

      return response.data;

    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Verificar si un email está disponible para registro
   *
   * @param email - Email a verificar
   * @returns Información sobre disponibilidad del email
   */
  async checkEmailAvailability(email: string): Promise<EmailCheckResponse> {
    try {
      const response = await this.client.get<EmailCheckResponse>(
        `/auth/trainer/check-email/${encodeURIComponent(email)}`
      );

      return response.data;

    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Validar si un subdomain está disponible
   *
   * @param subdomain - Subdomain a validar
   * @returns Información sobre validez y disponibilidad del subdomain
   */
  async validateSubdomain(subdomain: string): Promise<SubdomainValidationResponse> {
    try {
      const response = await this.client.get<SubdomainValidationResponse>(
        `/auth/trainer/validate-subdomain/${subdomain}`
      );

      return response.data;

    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Manejo centralizado de errores
   *
   * @param error - Error de axios
   * @returns APIError estructurado
   */
  private handleError(error: any): never {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;

      if (axiosError.response) {
        const status = axiosError.response.status;
        const data: any = axiosError.response.data;

        // Rate limiting
        if (status === 429) {
          throw new APIError(
            'Demasiados intentos. Por favor espera antes de reintentar.',
            429,
            'RATE_LIMIT_EXCEEDED'
          );
        }

        // Email duplicado
        if (status === 400 && data.detail?.error_code === 'WORKSPACE_EXISTS') {
          throw new APIError(
            'Ya existe una cuenta con este email',
            400,
            'WORKSPACE_EXISTS',
            data.detail.details
          );
        }

        // Validación fallida
        if (status === 422) {
          const validationErrors = data.detail.map((err: any) => err.msg).join(', ');
          throw new APIError(
            `Error de validación: ${validationErrors}`,
            422,
            'VALIDATION_ERROR',
            data.detail
          );
        }

        // Error genérico del servidor
        throw new APIError(
          data.detail?.message || 'Error en la petición',
          status,
          data.detail?.error_code,
          data.detail?.details
        );
      }

      // Error de red
      if (axiosError.request) {
        throw new APIError(
          'No se pudo conectar con el servidor. Verifica tu conexión a internet.',
          0,
          'NETWORK_ERROR'
        );
      }
    }

    // Error desconocido
    throw new APIError(
      error.message || 'Error desconocido',
      0,
      'UNKNOWN_ERROR'
    );
  }
}

// Exportar instancia singleton si se desea
export const trainerService = new TrainerService();
