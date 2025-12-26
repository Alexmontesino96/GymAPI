# Stripe Connect - Quick Start para Frontend

## 🚀 Guía Rápida de 5 Minutos

Esta guía te permite integrar Stripe Connect en tu frontend en minutos.

---

## 📋 Checklist Rápido

```
1. ✅ Verificar estado actual
2. ✅ Crear cuenta (si no existe)
3. ✅ Generar link de onboarding
4. ✅ Abrir ventana de Stripe
5. ✅ Detectar cuando complete (polling)
```

---

## 🎯 Código Listo para Usar

### TypeScript / JavaScript

```typescript
const API_URL = 'https://gymapi-eh6m.onrender.com/api/v1/stripe-connect';

// ========================================
// 1. FUNCIÓN: Verificar Estado
// ========================================
async function checkStripeStatus(token: string, gymId: number) {
  const response = await fetch(`${API_URL}/accounts/connection-status`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-ID': String(gymId),
    }
  });

  return await response.json();
}

// ========================================
// 2. FUNCIÓN: Crear Cuenta
// ========================================
async function createAccount(token: string, gymId: number, country = 'US') {
  const response = await fetch(
    `${API_URL}/accounts?country=${country}&account_type=standard`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': String(gymId),
        'Content-Type': 'application/json',
      }
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return await response.json();
}

// ========================================
// 3. FUNCIÓN: Generar Link de Onboarding
// ========================================
async function getOnboardingLink(token: string, gymId: number) {
  const response = await fetch(`${API_URL}/accounts/onboarding-link`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-ID': String(gymId),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      return_url: `${window.location.origin}/admin/stripe/success`,
      refresh_url: `${window.location.origin}/admin/stripe/reauth`
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return await response.json();
}

// ========================================
// 4. FUNCIÓN PRINCIPAL: Setup Completo
// ========================================
async function setupStripeConnect(token: string, gymId: number) {
  try {
    // PASO 1: Verificar estado
    const status = await checkStripeStatus(token, gymId);

    if (status.connected && status.charges_enabled) {
      console.log('✅ Stripe ya está configurado');
      return { success: true, message: 'Ya configurado' };
    }

    // PASO 2: Crear cuenta (si no existe)
    if (!status.connected || status.action_required === "Crear cuenta de Stripe Connect") {
      console.log('📝 Creando cuenta...');
      await createAccount(token, gymId);
    }

    // PASO 3: Generar link de onboarding
    console.log('🔗 Generando link de onboarding...');
    const link = await getOnboardingLink(token, gymId);

    // PASO 4: Abrir ventana de Stripe
    console.log('🌐 Abriendo ventana de Stripe...');
    window.open(link.onboarding_url, '_blank');

    // PASO 5: Polling para detectar cuando termine
    return await pollOnboardingCompletion(token, gymId);

  } catch (error) {
    console.error('❌ Error:', error);
    throw error;
  }
}

// ========================================
// 5. FUNCIÓN: Polling de Completación
// ========================================
async function pollOnboardingCompletion(
  token: string,
  gymId: number,
  maxAttempts = 120 // 10 minutos (cada 5 seg)
): Promise<{ success: boolean; message: string }> {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const interval = setInterval(async () => {
      attempts++;

      try {
        const status = await checkStripeStatus(token, gymId);

        if (status.onboarding_completed && status.charges_enabled) {
          clearInterval(interval);
          console.log('✅ Onboarding completado!');
          resolve({
            success: true,
            message: 'Stripe configurado correctamente'
          });
        }

        if (attempts >= maxAttempts) {
          clearInterval(interval);
          console.log('⏱️ Timeout esperando onboarding');
          resolve({
            success: false,
            message: 'Timeout - verifica manualmente'
          });
        }
      } catch (error) {
        console.error('Error en polling:', error);
      }
    }, 5000); // Cada 5 segundos
  });
}

// ========================================
// USO
// ========================================
const token = 'tu-token-aqui';
const gymId = 4;

setupStripeConnect(token, gymId)
  .then(result => {
    if (result.success) {
      alert('✅ Stripe configurado correctamente!');
      // Recargar página o actualizar UI
      window.location.reload();
    } else {
      alert('⏱️ Por favor verifica el estado manualmente');
    }
  })
  .catch(error => {
    alert(`❌ Error: ${error.message}`);
  });
```

---

## 🎨 React Hook Completo

```typescript
import { useState, useEffect } from 'react';

interface UseStripeConnectProps {
  token: string;
  gymId: number;
}

interface StripeState {
  status: 'loading' | 'not_configured' | 'configuring' | 'connected';
  accountInfo: any;
  error: string | null;
}

export function useStripeConnect({ token, gymId }: UseStripeConnectProps) {
  const [state, setState] = useState<StripeState>({
    status: 'loading',
    accountInfo: null,
    error: null
  });

  const API_URL = 'https://gymapi-eh6m.onrender.com/api/v1/stripe-connect';

  // Verificar estado al montar
  useEffect(() => {
    checkStatus();
  }, []);

  async function checkStatus() {
    try {
      const response = await fetch(`${API_URL}/accounts/connection-status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Gym-ID': String(gymId),
        }
      });

      const data = await response.json();

      setState({
        status: data.connected && data.charges_enabled
          ? 'connected'
          : 'not_configured',
        accountInfo: data,
        error: null
      });
    } catch (error) {
      setState(prev => ({
        ...prev,
        status: 'not_configured',
        error: 'Error verificando estado'
      }));
    }
  }

  async function setupStripe() {
    setState(prev => ({ ...prev, status: 'configuring', error: null }));

    try {
      // Crear cuenta
      await fetch(
        `${API_URL}/accounts?country=US&account_type=standard`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Gym-ID': String(gymId),
            'Content-Type': 'application/json',
          }
        }
      );

      // Obtener link
      const linkResponse = await fetch(`${API_URL}/accounts/onboarding-link`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Gym-ID': String(gymId),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          return_url: `${window.location.origin}/admin/stripe/success`,
          refresh_url: `${window.location.origin}/admin/stripe/reauth`
        })
      });

      const linkData = await linkResponse.json();

      // Abrir ventana
      window.open(linkData.onboarding_url, '_blank');

      // Polling
      const interval = setInterval(async () => {
        const statusResponse = await fetch(
          `${API_URL}/accounts/connection-status`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'X-Gym-ID': String(gymId),
            }
          }
        );

        const statusData = await statusResponse.json();

        if (statusData.onboarding_completed && statusData.charges_enabled) {
          clearInterval(interval);
          setState({
            status: 'connected',
            accountInfo: statusData,
            error: null
          });
        }
      }, 5000);

      // Timeout después de 10 minutos
      setTimeout(() => {
        clearInterval(interval);
        if (state.status === 'configuring') {
          setState(prev => ({
            ...prev,
            status: 'not_configured',
            error: 'Timeout - verifica manualmente'
          }));
        }
      }, 600000);

    } catch (error) {
      setState(prev => ({
        ...prev,
        status: 'not_configured',
        error: error instanceof Error ? error.message : 'Error desconocido'
      }));
    }
  }

  return {
    ...state,
    setupStripe,
    checkStatus,
    isConfiguring: state.status === 'configuring',
    isConnected: state.status === 'connected',
  };
}

// ========================================
// COMPONENTE DE EJEMPLO
// ========================================
function StripeSetupButton() {
  const { status, accountInfo, error, setupStripe, isConfiguring } =
    useStripeConnect({
      token: 'tu-token',
      gymId: 4
    });

  if (status === 'loading') {
    return <div>Verificando Stripe...</div>;
  }

  if (status === 'connected') {
    return (
      <div className="stripe-connected">
        <h3>✅ Stripe Configurado</h3>
        <p>Account: {accountInfo.account_id}</p>
        <a href="https://dashboard.stripe.com" target="_blank">
          Ver Dashboard
        </a>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={setupStripe}
        disabled={isConfiguring}
      >
        {isConfiguring ? 'Configurando...' : 'Configurar Stripe'}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
```

---

## 🍎 Swift / iOS

```swift
import Foundation

struct StripeConnectAPI {
    let baseURL = "https://gymapi-eh6m.onrender.com/api/v1/stripe-connect"
    let token: String
    let gymId: Int

    // MARK: - Check Status
    func checkStatus(completion: @escaping (Result<ConnectionStatus, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/accounts/connection-status") else {
            return
        }

        var request = URLRequest(url: url)
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.addValue("\(gymId)", forHTTPHeaderField: "X-Gym-ID")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: 0)))
                return
            }

            do {
                let status = try JSONDecoder().decode(ConnectionStatus.self, from: data)
                completion(.success(status))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    // MARK: - Create Account
    func createAccount(country: String = "US",
                      completion: @escaping (Result<AccountResponse, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/accounts?country=\(country)&account_type=standard") else {
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.addValue("\(gymId)", forHTTPHeaderField: "X-Gym-ID")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: 0)))
                return
            }

            do {
                let account = try JSONDecoder().decode(AccountResponse.self, from: data)
                completion(.success(account))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    // MARK: - Get Onboarding Link
    func getOnboardingLink(completion: @escaping (Result<OnboardingLink, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/accounts/onboarding-link") else {
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.addValue("\(gymId)", forHTTPHeaderField: "X-Gym-ID")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: String] = [
            "return_url": "gymapp://stripe/success",
            "refresh_url": "gymapp://stripe/reauth"
        ]

        request.httpBody = try? JSONEncoder().encode(body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: 0)))
                return
            }

            do {
                let link = try JSONDecoder().decode(OnboardingLink.self, from: data)
                completion(.success(link))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    // MARK: - Setup Complete Flow
    func setupStripe(completion: @escaping (Result<Bool, Error>) -> Void) {
        // Step 1: Create account
        createAccount { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success:
                // Step 2: Get onboarding link
                self.getOnboardingLink { linkResult in
                    switch linkResult {
                    case .success(let link):
                        // Step 3: Open in Safari
                        if let url = URL(string: link.onboarding_url) {
                            DispatchQueue.main.async {
                                UIApplication.shared.open(url)
                            }
                        }
                        completion(.success(true))

                    case .failure(let error):
                        completion(.failure(error))
                    }
                }

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
}

// MARK: - Models
struct ConnectionStatus: Codable {
    let connected: Bool
    let accountId: String?
    let accountType: String?
    let chargesEnabled: Bool?
    let payoutsEnabled: Bool?
    let message: String

    enum CodingKeys: String, CodingKey {
        case connected
        case accountId = "account_id"
        case accountType = "account_type"
        case chargesEnabled = "charges_enabled"
        case payoutsEnabled = "payouts_enabled"
        case message
    }
}

struct AccountResponse: Codable {
    let message: String
    let accountId: String
    let accountType: String

    enum CodingKeys: String, CodingKey {
        case message
        case accountId = "account_id"
        case accountType = "account_type"
    }
}

struct OnboardingLink: Codable {
    let message: String
    let onboardingUrl: String
    let expiresInMinutes: Int

    enum CodingKeys: String, CodingKey {
        case message
        case onboardingUrl = "onboarding_url"
        case expiresInMinutes = "expires_in_minutes"
    }
}

// MARK: - Usage
let api = StripeConnectAPI(token: "tu-token", gymId: 4)

api.setupStripe { result in
    switch result {
    case .success:
        print("✅ Setup initiated")
    case .failure(let error):
        print("❌ Error: \(error)")
    }
}
```

---

## 📱 Flutter / Dart

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class StripeConnectAPI {
  final String baseUrl = 'https://gymapi-eh6m.onrender.com/api/v1/stripe-connect';
  final String token;
  final int gymId;

  StripeConnectAPI({required this.token, required this.gymId});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'X-Gym-ID': '$gymId',
    'Content-Type': 'application/json',
  };

  // Check Status
  Future<Map<String, dynamic>> checkStatus() async {
    final response = await http.get(
      Uri.parse('$baseUrl/accounts/connection-status'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Error checking status: ${response.body}');
    }
  }

  // Create Account
  Future<Map<String, dynamic>> createAccount({String country = 'US'}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/accounts?country=$country&account_type=standard'),
      headers: _headers,
    );

    if (response.statusCode == 201 || response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Error creating account: ${response.body}');
    }
  }

  // Get Onboarding Link
  Future<Map<String, dynamic>> getOnboardingLink() async {
    final response = await http.post(
      Uri.parse('$baseUrl/accounts/onboarding-link'),
      headers: _headers,
      body: json.encode({
        'return_url': 'gymapp://stripe/success',
        'refresh_url': 'gymapp://stripe/reauth',
      }),
    );

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Error getting link: ${response.body}');
    }
  }

  // Complete Setup Flow
  Future<bool> setupStripe() async {
    try {
      // Create account
      await createAccount();

      // Get link
      final link = await getOnboardingLink();

      // Open URL (requires url_launcher package)
      // await launch(link['onboarding_url']);

      return true;
    } catch (e) {
      print('Error: $e');
      return false;
    }
  }
}

// Usage
void main() async {
  final api = StripeConnectAPI(token: 'tu-token', gymId: 4);

  final status = await api.checkStatus();
  print('Status: $status');

  if (!status['connected']) {
    await api.setupStripe();
  }
}
```

---

## ⚡ Resumen de URLs

```
Base: https://gymapi-eh6m.onrender.com/api/v1/stripe-connect

GET  /accounts/connection-status  → Verificar estado
GET  /accounts/status              → Detalles completos
POST /accounts                     → Crear cuenta
POST /accounts/onboarding-link     → Generar link
```

---

## 🎯 Headers Requeridos

```http
Authorization: Bearer <tu-token-jwt>
X-Gym-ID: <id-del-gimnasio>
Content-Type: application/json
```

---

## 📚 Links Útiles

- **Documentación completa:** `docs/STRIPE_CONNECT_FRONTEND_API.md`
- **Stripe Dashboard:** https://dashboard.stripe.com
- **Stripe Connect Docs:** https://stripe.com/docs/connect

---

**¿Necesitas ayuda?** Revisa la documentación completa o contacta al equipo de desarrollo.
