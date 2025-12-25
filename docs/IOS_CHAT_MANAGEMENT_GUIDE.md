# Guía de Implementación iOS - Chat Management

Guía completa para implementar la funcionalidad de gestión de chats estilo WhatsApp en la app iOS del gimnasio.

## 📋 Tabla de Contenidos

- [¿Qué es esto?](#qué-es-esto)
- [Arquitectura de la Solución](#arquitectura-de-la-solución)
- [Setup Inicial](#setup-inicial)
- [Implementación por Funcionalidad](#implementación-por-funcionalidad)
  - [1. Ocultar Chat 1-to-1](#1-ocultar-chat-1-to-1)
  - [2. Salir de Grupo](#2-salir-de-grupo)
  - [3. Eliminar Grupo (Admin)](#3-eliminar-grupo-admin)
- [Actualizar Lista de Chats](#actualizar-lista-de-chats)
- [UI/UX Patterns](#uiux-patterns)
- [Manejo de Errores](#manejo-de-errores)
- [Testing](#testing)
- [Checklist de Implementación](#checklist-de-implementación)

---

## ¿Qué es esto?

Esta funcionalidad permite a los usuarios gestionar sus chats de manera similar a WhatsApp:

### 🎯 Funcionalidades

| Funcionalidad | Descripción | Similar a WhatsApp |
|---------------|-------------|-------------------|
| **Ocultar Chat** | Usuario oculta un chat 1-to-1 de su lista | ✅ "Archivar chat" |
| **Salir de Grupo** | Usuario abandona un grupo | ✅ "Salir del grupo" |
| **Eliminar Grupo** | Admin elimina un grupo vacío | ✅ "Eliminar grupo" (solo admin) |

### 🔑 Casos de Uso

**Miembro regular:**
- Ocultar conversaciones 1-to-1 molestas o no importantes
- Salir de grupos que ya no le interesan

**Trainer:**
- Todo lo anterior
- Eliminar grupos temporales que creó (después de que todos salieron)

**Admin:**
- Todo lo anterior
- Eliminar cualquier grupo vacío del gimnasio

---

## Arquitectura de la Solución

```
┌─────────────────┐
│   iOS App       │
│                 │
│  ┌───────────┐  │
│  │ SwiftUI   │  │
│  │   View    │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ViewModel  │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │  Service  │◄─┼──── Auth Token (JWT)
│  │  Layer    │  │
│  └─────┬─────┘  │
│        │        │
└────────┼────────┘
         │
    ┌────▼──────────────┐
    │  HTTP Request     │
    │  /api/v1/chat/    │
    └────┬──────────────┘
         │
    ┌────▼──────────────┐
    │  Backend API      │
    │  (FastAPI)        │
    └────┬──────────────┘
         │
    ┌────▼──────────────┐
    │  Stream Chat      │
    │  Sync             │
    └───────────────────┘
```

### Flujo de Datos

1. **Usuario acción** → SwiftUI View
2. **View** → ViewModel (call async function)
3. **ViewModel** → Service Layer (API call)
4. **Service** → Backend API (con Auth token)
5. **Backend** → Stream Chat (sincronización)
6. **Backend** → Response
7. **Service** → ViewModel (update state)
8. **ViewModel** → View (UI update)

---

## Setup Inicial

### 1. Crear el Service Layer

```swift
// ChatManagementService.swift

import Foundation

enum ChatManagementError: LocalizedError {
    case notDirectChat
    case notGroupChat
    case notAMember
    case groupNotEmpty(membersCount: Int)
    case noPermission
    case notFound
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .notDirectChat:
            return "Solo puedes ocultar chats directos 1-to-1. Para grupos, debes salir primero."
        case .notGroupChat:
            return "No puedes salir de un chat directo 1-to-1. Usa la opción 'ocultar'."
        case .notAMember:
            return "No eres miembro de este chat."
        case .groupNotEmpty(let count):
            return "Debes remover a todos los miembros (\(count) restantes) antes de eliminar el grupo."
        case .noPermission:
            return "No tienes permisos para realizar esta acción."
        case .notFound:
            return "Chat no encontrado."
        case .serverError(let message):
            return message
        }
    }
}

struct ChatHideResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let isHidden: Bool

    enum CodingKeys: String, CodingKey {
        case success, message
        case roomId = "room_id"
        case isHidden = "is_hidden"
    }
}

struct ChatLeaveResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let remainingMembers: Int
    let groupDeleted: Bool
    let autoHidden: Bool

    enum CodingKeys: String, CodingKey {
        case success, message
        case roomId = "room_id"
        case remainingMembers = "remaining_members"
        case groupDeleted = "group_deleted"
        case autoHidden = "auto_hidden"
    }
}

struct ChatDeleteResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let deletedFromStream: Bool

    enum CodingKeys: String, CodingKey {
        case success, message
        case roomId = "room_id"
        case deletedFromStream = "deleted_from_stream"
    }
}

class ChatManagementService {
    static let shared = ChatManagementService()

    private let baseURL = "https://api.tugym.com/api/v1/chat"
    private let session: URLSession

    // Inyecta el AuthManager o como manejes la autenticación
    private var authToken: String {
        // TODO: Obtener token de tu AuthManager
        AuthManager.shared.accessToken ?? ""
    }

    private var gymId: String {
        // TODO: Obtener gym ID actual
        UserDefaults.standard.string(forKey: "current_gym_id") ?? "1"
    }

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - Private Helper Methods

    private func createRequest(
        url: URL,
        method: String,
        body: [String: Any]? = nil
    ) throws -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue(gymId, forHTTPHeaderField: "X-Gym-ID")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let body = body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }

        return request
    }

    private func handleResponse<T: Codable>(
        data: Data,
        response: URLResponse
    ) throws -> T {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw ChatManagementError.serverError("Invalid response")
        }

        switch httpResponse.statusCode {
        case 200...299:
            return try JSONDecoder().decode(T.self, from: data)

        case 400:
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                if errorResponse.detail.contains("Solo puedes ocultar chats directos") {
                    throw ChatManagementError.notDirectChat
                } else if errorResponse.detail.contains("No puedes salir de un chat directo") {
                    throw ChatManagementError.notGroupChat
                } else if errorResponse.detail.contains("Debes remover a todos los miembros") {
                    // Extraer número de miembros del mensaje
                    let pattern = #"(\d+) restantes"#
                    if let regex = try? NSRegularExpression(pattern: pattern),
                       let match = regex.firstMatch(in: errorResponse.detail, range: NSRange(errorResponse.detail.startIndex..., in: errorResponse.detail)),
                       let range = Range(match.range(at: 1), in: errorResponse.detail),
                       let count = Int(errorResponse.detail[range]) {
                        throw ChatManagementError.groupNotEmpty(membersCount: count)
                    }
                }
                throw ChatManagementError.serverError(errorResponse.detail)
            }
            throw ChatManagementError.serverError("Bad request")

        case 403:
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                if errorResponse.detail.contains("No eres miembro") {
                    throw ChatManagementError.notAMember
                }
                throw ChatManagementError.noPermission
            }
            throw ChatManagementError.noPermission

        case 404:
            throw ChatManagementError.notFound

        default:
            throw ChatManagementError.serverError("Server error \(httpResponse.statusCode)")
        }
    }

    // MARK: - Public API Methods

    /// Oculta un chat 1-to-1 para el usuario actual
    /// - Parameter roomId: ID de la sala de chat
    /// - Returns: Respuesta con el resultado
    func hideChat(roomId: Int) async throws -> ChatHideResponse {
        let url = URL(string: "\(baseURL)/rooms/\(roomId)/hide")!
        let request = try createRequest(url: url, method: "POST")

        let (data, response) = try await session.data(for: request)
        return try handleResponse(data: data, response: response)
    }

    /// Muestra un chat previamente ocultado
    /// - Parameter roomId: ID de la sala de chat
    /// - Returns: Respuesta con el resultado
    func showChat(roomId: Int) async throws -> ChatHideResponse {
        let url = URL(string: "\(baseURL)/rooms/\(roomId)/show")!
        let request = try createRequest(url: url, method: "POST")

        let (data, response) = try await session.data(for: request)
        return try handleResponse(data: data, response: response)
    }

    /// Permite al usuario salir de un grupo
    /// - Parameters:
    ///   - roomId: ID del grupo
    ///   - autoHide: Si debe ocultarse automáticamente (default: true)
    /// - Returns: Respuesta con información de miembros restantes
    func leaveGroup(roomId: Int, autoHide: Bool = true) async throws -> ChatLeaveResponse {
        let url = URL(string: "\(baseURL)/rooms/\(roomId)/leave?auto_hide=\(autoHide)")!
        let request = try createRequest(url: url, method: "POST")

        let (data, response) = try await session.data(for: request)
        return try handleResponse(data: data, response: response)
    }

    /// Elimina un grupo completamente (solo admin/creador)
    /// - Parameters:
    ///   - roomId: ID del grupo a eliminar
    ///   - hardDelete: Si debe eliminarse de Stream Chat (default: false)
    /// - Returns: Respuesta con el resultado
    func deleteGroup(roomId: Int, hardDelete: Bool = false) async throws -> ChatDeleteResponse {
        let url = URL(string: "\(baseURL)/rooms/\(roomId)?hard_delete=\(hardDelete)")!
        let request = try createRequest(url: url, method: "DELETE")

        let (data, response) = try await session.data(for: request)
        return try handleResponse(data: data, response: response)
    }
}

// MARK: - Supporting Types

struct ErrorResponse: Codable {
    let detail: String
}
```

---

## Implementación por Funcionalidad

### 1. Ocultar Chat 1-to-1

#### Cuándo Usar
- Usuario quiere archivar una conversación 1-to-1
- Chat no es importante pero quiere mantenerlo accesible
- **NO** usar para grupos (usar "Salir de Grupo")

#### ViewModel

```swift
// ChatListViewModel.swift

import SwiftUI
import StreamChat

@MainActor
class ChatListViewModel: ObservableObject {
    @Published var chats: [ChatChannel] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showingError = false

    private let service = ChatManagementService.shared

    // MARK: - Hide Chat

    func hideChat(_ channel: ChatChannel) async {
        guard channel.isDirect else {
            showError("Solo puedes ocultar chats directos. Para grupos, usa 'Salir del grupo'.")
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await service.hideChat(roomId: channel.roomId)

            // Remover de la lista local
            chats.removeAll { $0.id == channel.id }

            // Opcional: Mostrar confirmación
            showSuccess(response.message)

            // Sincronizar con Stream Chat si es necesario
            await syncWithStreamChat(channel)

        } catch let error as ChatManagementError {
            showError(error.localizedDescription)
        } catch {
            showError("Error al ocultar el chat: \(error.localizedDescription)")
        }
    }

    private func syncWithStreamChat(_ channel: ChatChannel) async {
        // Si usas Stream Chat SDK, el backend ya sincronizó
        // Pero puedes forzar un refresh si es necesario
        // await streamChatClient.hideChannel(channel.streamChannelId)
    }

    private func showError(_ message: String) {
        errorMessage = message
        showingError = true
    }

    private func showSuccess(_ message: String) {
        // Implementar toast o mensaje de éxito
        print("✅ \(message)")
    }
}
```

#### SwiftUI View

```swift
// ChatListView.swift

import SwiftUI

struct ChatListView: View {
    @StateObject private var viewModel = ChatListViewModel()
    @State private var chatToHide: ChatChannel?
    @State private var showingHideConfirmation = false

    var body: some View {
        List {
            ForEach(viewModel.chats) { chat in
                ChatRow(chat: chat)
                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                        // Botón de ocultar (solo para chats 1-to-1)
                        if chat.isDirect {
                            Button {
                                chatToHide = chat
                                showingHideConfirmation = true
                            } label: {
                                Label("Ocultar", systemImage: "archivebox")
                            }
                            .tint(.orange)
                        }
                    }
                    .contextMenu {
                        if chat.isDirect {
                            Button {
                                chatToHide = chat
                                showingHideConfirmation = true
                            } label: {
                                Label("Ocultar Chat", systemImage: "archivebox")
                            }
                        }
                    }
            }
        }
        .overlay {
            if viewModel.isLoading {
                ProgressView()
            }
        }
        .alert("Ocultar Chat", isPresented: $showingHideConfirmation) {
            Button("Cancelar", role: .cancel) { }
            Button("Ocultar", role: .destructive) {
                if let chat = chatToHide {
                    Task {
                        await viewModel.hideChat(chat)
                    }
                }
            }
        } message: {
            Text("Este chat se ocultará de tu lista. Puedes mostrarlo nuevamente desde la sección de chats ocultos.")
        }
        .alert("Error", isPresented: $viewModel.showingError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(viewModel.errorMessage ?? "Error desconocido")
        }
    }
}
```

#### Mostrar Chats Ocultos

```swift
// HiddenChatsView.swift

struct HiddenChatsView: View {
    @StateObject private var viewModel = HiddenChatsViewModel()

    var body: some View {
        List {
            ForEach(viewModel.hiddenChats) { chat in
                ChatRow(chat: chat)
                    .swipeActions(edge: .trailing) {
                        Button {
                            Task {
                                await viewModel.unhideChat(chat)
                            }
                        } label: {
                            Label("Mostrar", systemImage: "arrow.up.bin")
                        }
                        .tint(.blue)
                    }
            }
        }
        .navigationTitle("Chats Ocultos")
        .task {
            await viewModel.loadHiddenChats()
        }
    }
}

@MainActor
class HiddenChatsViewModel: ObservableObject {
    @Published var hiddenChats: [ChatChannel] = []

    private let service = ChatManagementService.shared

    func loadHiddenChats() async {
        // Llamar al endpoint /my-rooms?include_hidden=true
        // Filtrar los que están ocultos
    }

    func unhideChat(_ chat: ChatChannel) async {
        do {
            let response = try await service.showChat(roomId: chat.roomId)
            hiddenChats.removeAll { $0.id == chat.id }
        } catch {
            print("Error: \(error)")
        }
    }
}
```

---

### 2. Salir de Grupo

#### Cuándo Usar
- Usuario quiere abandonar un grupo
- **NO** funciona en chats 1-to-1 (usar "Ocultar")
- **NO** funciona en chats de eventos (se cierran automáticamente)

#### ViewModel

```swift
// GroupChatViewModel.swift

import SwiftUI

@MainActor
class GroupChatViewModel: ObservableObject {
    @Published var isLoading = false
    @Published var showingLeaveAlert = false
    @Published var showingSuccessAlert = false
    @Published var alertMessage = ""

    private let service = ChatManagementService.shared
    let channel: ChatChannel

    init(channel: ChatChannel) {
        self.channel = channel
    }

    func leaveGroup() async {
        guard !channel.isDirect else {
            showError("No puedes salir de un chat directo. Usa 'Ocultar' en su lugar.")
            return
        }

        guard !channel.isEventChat else {
            showError("Los chats de eventos se cierran automáticamente al finalizar.")
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await service.leaveGroup(
                roomId: channel.roomId,
                autoHide: true // Ocultar automáticamente
            )

            if response.groupDeleted {
                // Eras el último miembro
                alertMessage = "Has salido del grupo. El grupo ha sido eliminado porque no quedan miembros."
            } else {
                // Aún hay miembros
                alertMessage = "Has salido del grupo '\(channel.name)'. Quedan \(response.remainingMembers) miembros."
            }

            showingSuccessAlert = true

            // Navegar de vuelta a la lista
            // O hacer dismiss si estás en un modal

        } catch let error as ChatManagementError {
            showError(error.localizedDescription)
        } catch {
            showError("Error al salir del grupo: \(error.localizedDescription)")
        }
    }

    private func showError(_ message: String) {
        alertMessage = message
        showingLeaveAlert = true
    }
}
```

#### SwiftUI View

```swift
// GroupChatView.swift

struct GroupChatView: View {
    @StateObject private var viewModel: GroupChatViewModel
    @Environment(\.dismiss) private var dismiss

    init(channel: ChatChannel) {
        _viewModel = StateObject(wrappedValue: GroupChatViewModel(channel: channel))
    }

    var body: some View {
        VStack {
            // Tu UI de chat aquí

            // Botón de opciones
            Menu {
                // Otras opciones...

                Divider()

                // Opción de salir del grupo
                Button(role: .destructive) {
                    viewModel.showingLeaveAlert = true
                } label: {
                    Label("Salir del Grupo", systemImage: "rectangle.portrait.and.arrow.right")
                }
            } label: {
                Image(systemName: "ellipsis.circle")
            }
        }
        .overlay {
            if viewModel.isLoading {
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.2))
            }
        }
        .alert("Salir del Grupo", isPresented: $viewModel.showingLeaveAlert) {
            Button("Cancelar", role: .cancel) { }
            Button("Salir", role: .destructive) {
                Task {
                    await viewModel.leaveGroup()
                }
            }
        } message: {
            Text("¿Estás seguro que quieres salir de '\(viewModel.channel.name)'?")
        }
        .alert("Confirmación", isPresented: $viewModel.showingSuccessAlert) {
            Button("OK") {
                dismiss()
            }
        } message: {
            Text(viewModel.alertMessage)
        }
    }
}
```

---

### 3. Eliminar Grupo (Admin)

#### Cuándo Usar
- **Solo Admin/Owner**: Puede eliminar cualquier grupo del gimnasio
- **Trainer**: Solo puede eliminar grupos que él creó
- **Requisito**: El grupo DEBE estar vacío (0 miembros)

#### ViewModel

```swift
// GroupManagementViewModel.swift

@MainActor
class GroupManagementViewModel: ObservableObject {
    @Published var isLoading = false
    @Published var showingDeleteAlert = false
    @Published var showingMembersWarning = false
    @Published var alertMessage = ""
    @Published var membersCount = 0

    private let service = ChatManagementService.shared
    let channel: ChatChannel
    let userRole: UserRole // ADMIN, TRAINER, MEMBER

    init(channel: ChatChannel, userRole: UserRole) {
        self.channel = channel
        self.userRole = userRole
    }

    var canDeleteGroup: Bool {
        // Admin puede eliminar cualquier grupo
        if userRole == .admin || userRole == .owner {
            return true
        }

        // Trainer solo puede eliminar grupos que creó
        if userRole == .trainer && channel.isCreatedByCurrentUser {
            return true
        }

        return false
    }

    func checkAndDeleteGroup() async {
        // Verificar que el grupo esté vacío
        membersCount = await fetchMembersCount()

        if membersCount > 0 {
            alertMessage = "Debes remover a todos los miembros (\(membersCount)) antes de eliminar el grupo."
            showingMembersWarning = true
            return
        }

        // Si está vacío, proceder
        showingDeleteAlert = true
    }

    func deleteGroup(hardDelete: Bool = true) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await service.deleteGroup(
                roomId: channel.roomId,
                hardDelete: hardDelete
            )

            alertMessage = response.message

            if response.deletedFromStream {
                print("✅ Grupo eliminado permanentemente de Stream")
            }

            // Navegar de vuelta
            // dismiss o pop

        } catch let error as ChatManagementError {
            alertMessage = error.localizedDescription
            showingMembersWarning = true
        } catch {
            alertMessage = "Error al eliminar el grupo: \(error.localizedDescription)"
            showingMembersWarning = true
        }
    }

    private func fetchMembersCount() async -> Int {
        // Obtener info del grupo desde tu API
        // return channel.memberCount
        return 0 // Placeholder
    }
}
```

#### SwiftUI View

```swift
// GroupSettingsView.swift

struct GroupSettingsView: View {
    @StateObject private var viewModel: GroupManagementViewModel
    @Environment(\.dismiss) private var dismiss

    init(channel: ChatChannel, userRole: UserRole) {
        _viewModel = StateObject(
            wrappedValue: GroupManagementViewModel(channel: channel, userRole: userRole)
        )
    }

    var body: some View {
        List {
            // Otras configuraciones...

            Section {
                // Opción de salir (todos)
                Button(role: .destructive) {
                    // Lógica de leave
                } label: {
                    Label("Salir del Grupo", systemImage: "rectangle.portrait.and.arrow.right")
                }

                // Opción de eliminar (solo admin/creador)
                if viewModel.canDeleteGroup {
                    Button(role: .destructive) {
                        Task {
                            await viewModel.checkAndDeleteGroup()
                        }
                    } label: {
                        Label("Eliminar Grupo", systemImage: "trash")
                    }
                }
            } header: {
                Text("Acciones")
            } footer: {
                if viewModel.canDeleteGroup {
                    Text("Eliminar el grupo lo borrará permanentemente para todos los miembros.")
                }
            }
        }
        .navigationTitle("Configuración del Grupo")
        .overlay {
            if viewModel.isLoading {
                ProgressView()
            }
        }
        .alert("Eliminar Grupo", isPresented: $viewModel.showingDeleteAlert) {
            Button("Cancelar", role: .cancel) { }
            Button("Eliminar Permanentemente", role: .destructive) {
                Task {
                    await viewModel.deleteGroup(hardDelete: true)
                    dismiss()
                }
            }
        } message: {
            Text("Esta acción eliminará el grupo '\(viewModel.channel.name)' permanentemente. Esta acción no se puede deshacer.")
        }
        .alert("Atención", isPresented: $viewModel.showingMembersWarning) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(viewModel.alertMessage)
        }
    }
}
```

---

## Actualizar Lista de Chats

### Filtrar Chats Ocultos

Por defecto, el endpoint `/my-rooms` excluye chats ocultos.

```swift
// ChatService.swift

class ChatService {
    func fetchChats(includeHidden: Bool = false) async throws -> [ChatChannel] {
        let url = URL(string: "\(baseURL)/my-rooms?include_hidden=\(includeHidden)")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue(gymId, forHTTPHeaderField: "X-Gym-ID")

        let (data, _) = try await URLSession.shared.data(for: request)
        let channels = try JSONDecoder().decode([ChatChannel].self, from: data)

        return channels
    }
}
```

### Refresh después de Acciones

```swift
// En tu ChatListViewModel

func refreshChats() async {
    do {
        // Obtener chats visibles (sin ocultos)
        chats = try await ChatService.shared.fetchChats(includeHidden: false)
    } catch {
        showError("Error al actualizar: \(error)")
    }
}

// Llamar después de hide/leave/delete
func hideChat(_ channel: ChatChannel) async {
    // ... código anterior ...

    // Refresh al final
    await refreshChats()
}
```

---

## UI/UX Patterns

### 1. Swipe Actions (Estilo WhatsApp)

```swift
List {
    ForEach(chats) { chat in
        ChatRow(chat: chat)
            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                // Para chats 1-to-1
                if chat.isDirect {
                    Button {
                        hideChat(chat)
                    } label: {
                        Label("Ocultar", systemImage: "archivebox")
                    }
                    .tint(.orange)
                }

                // Para grupos
                if !chat.isDirect && !chat.isEventChat {
                    Button {
                        leaveGroup(chat)
                    } label: {
                        Label("Salir", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                    .tint(.red)
                }
            }
    }
}
```

### 2. Context Menu (Long Press)

```swift
.contextMenu {
    if chat.isDirect {
        Button {
            hideChat(chat)
        } label: {
            Label("Ocultar Chat", systemImage: "archivebox")
        }
    } else if !chat.isEventChat {
        Button {
            leaveGroup(chat)
        } label: {
            Label("Salir del Grupo", systemImage: "rectangle.portrait.and.arrow.right")
        }

        if canDeleteGroup(chat) {
            Divider()
            Button(role: .destructive) {
                deleteGroup(chat)
            } label: {
                Label("Eliminar Grupo", systemImage: "trash")
            }
        }
    }
}
```

### 3. Confirmación con Alert

```swift
.alert("Ocultar Chat", isPresented: $showingHideConfirmation) {
    Button("Cancelar", role: .cancel) { }
    Button("Ocultar", role: .destructive) {
        Task {
            await hideChat(selectedChat)
        }
    }
} message: {
    Text("Este chat se ocultará de tu lista. Puedes mostrarlo desde 'Chats Ocultos'.")
}
```

### 4. Loading State

```swift
.overlay {
    if viewModel.isLoading {
        ZStack {
            Color.black.opacity(0.3)
                .ignoresSafeArea()

            VStack(spacing: 12) {
                ProgressView()
                    .scaleEffect(1.2)
                    .tint(.white)

                Text("Procesando...")
                    .foregroundColor(.white)
                    .font(.caption)
            }
            .padding(24)
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
}
```

---

## Manejo de Errores

### Tipos de Errores

```swift
// Mostrar errores específicos con mensajes claros

switch error {
case ChatManagementError.notDirectChat:
    // "Solo puedes ocultar chats directos..."
    showAlert("Para salir de un grupo, usa la opción 'Salir del grupo'")

case ChatManagementError.notGroupChat:
    // "No puedes salir de un chat 1-to-1..."
    showAlert("Para ocultar este chat, usa la opción 'Ocultar'")

case ChatManagementError.groupNotEmpty(let count):
    // Grupo tiene miembros
    showAlert("Primero debes remover a los \(count) miembros del grupo")

case ChatManagementError.noPermission:
    // Sin permisos
    showAlert("No tienes permisos para realizar esta acción")

case ChatManagementError.notFound:
    // Chat no encontrado
    showAlert("Este chat ya no existe")

default:
    showAlert("Error: \(error.localizedDescription)")
}
```

### Retry Logic

```swift
func hideChat(_ channel: ChatChannel, retryCount: Int = 0) async {
    do {
        let response = try await service.hideChat(roomId: channel.roomId)
        // Success
    } catch {
        if retryCount < 2 {
            // Retry después de 1 segundo
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            await hideChat(channel, retryCount: retryCount + 1)
        } else {
            showError(error.localizedDescription)
        }
    }
}
```

---

## Testing

### Unit Tests

```swift
// ChatManagementServiceTests.swift

import XCTest
@testable import GymApp

final class ChatManagementServiceTests: XCTestCase {
    var service: ChatManagementService!

    override func setUp() {
        super.setUp()
        service = ChatManagementService.shared
    }

    func testHideChatSuccess() async throws {
        // Arrange
        let roomId = 123

        // Act
        let response = try await service.hideChat(roomId: roomId)

        // Assert
        XCTAssertTrue(response.success)
        XCTAssertTrue(response.isHidden)
        XCTAssertEqual(response.roomId, roomId)
    }

    func testLeaveGroupAsLastMember() async throws {
        // Arrange
        let roomId = 456

        // Act
        let response = try await service.leaveGroup(roomId: roomId)

        // Assert
        XCTAssertTrue(response.groupDeleted)
        XCTAssertEqual(response.remainingMembers, 0)
    }

    func testDeleteGroupNotEmpty() async {
        // Arrange
        let roomId = 789

        // Act & Assert
        do {
            _ = try await service.deleteGroup(roomId: roomId)
            XCTFail("Should throw groupNotEmpty error")
        } catch ChatManagementError.groupNotEmpty(let count) {
            XCTAssertGreaterThan(count, 0)
        } catch {
            XCTFail("Wrong error type: \(error)")
        }
    }
}
```

### UI Tests

```swift
// ChatManagementUITests.swift

func testHideChatFlow() throws {
    let app = XCUIApplication()
    app.launch()

    // Navigate to chat list
    app.tabBars.buttons["Chats"].tap()

    // Swipe on a chat
    let chatCell = app.cells.firstMatch
    chatCell.swipeLeft()

    // Tap hide button
    app.buttons["Ocultar"].tap()

    // Confirm
    app.alerts.buttons["Ocultar"].tap()

    // Verify chat is removed
    XCTAssertFalse(chatCell.exists)
}
```

---

## Checklist de Implementación

### ✅ Backend Integration

- [ ] Configurar `ChatManagementService` con URLs correctas
- [ ] Implementar manejo de Auth tokens
- [ ] Implementar manejo de Gym ID
- [ ] Manejar todos los códigos de error HTTP
- [ ] Agregar retry logic para errores de red

### ✅ UI Components

- [ ] Implementar swipe actions en lista de chats
- [ ] Agregar context menu para opciones
- [ ] Crear pantalla de "Chats Ocultos"
- [ ] Implementar confirmaciones con Alert
- [ ] Agregar loading states
- [ ] Implementar feedback de éxito (toast/alert)

### ✅ ViewModels

- [ ] `ChatListViewModel` - Ocultar chats
- [ ] `HiddenChatsViewModel` - Mostrar chats ocultos
- [ ] `GroupChatViewModel` - Salir de grupo
- [ ] `GroupManagementViewModel` - Eliminar grupo (admin)

### ✅ Business Logic

- [ ] Validar tipo de chat antes de cada acción
- [ ] Verificar permisos de usuario (role)
- [ ] Manejar caso de "último miembro sale"
- [ ] Sincronizar con Stream Chat SDK
- [ ] Refresh de lista después de acciones

### ✅ Error Handling

- [ ] Mostrar mensajes específicos por tipo de error
- [ ] Implementar retry logic
- [ ] Manejar pérdida de conexión
- [ ] Validar estados antes de acciones

### ✅ Testing

- [ ] Unit tests para `ChatManagementService`
- [ ] Unit tests para ViewModels
- [ ] UI tests para flujos principales
- [ ] Tests de integración con backend

### ✅ UX/Polish

- [ ] Animaciones de transición
- [ ] Feedback háptico en acciones
- [ ] Accessibility labels
- [ ] Localización de strings
- [ ] Dark mode support

---

## Recursos Adicionales

- 📖 [Documentación API Completa](./CHAT_MANAGEMENT_API.md)
- 📖 [Guía Rápida API](./CHAT_MANAGEMENT_QUICK_START.md)
- 🔗 [Stream Chat iOS SDK](https://getstream.io/chat/docs/sdk/ios/)
- 🔗 [Swift Concurrency Guide](https://docs.swift.org/swift-book/LanguageGuide/Concurrency.html)

---

## Soporte

Para dudas o problemas:
1. Revisar logs del backend en `/api/v1/chat/`
2. Verificar tokens de autenticación
3. Confirmar que Stream Chat está sincronizado
4. Contactar al equipo de backend

---

**Versión:** 1.0.0
**Última actualización:** 2025-12-13
**Compatibilidad:** iOS 15.0+
