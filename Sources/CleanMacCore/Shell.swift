import Foundation

public struct ShellScreen: Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String

    public init(id: String, title: String) {
        self.id = id
        self.title = title
    }
}

public struct Shell: Sendable {
    public private(set) var registeredScreens: [ShellScreen]

    public init(registeredScreens: [ShellScreen] = []) {
        self.registeredScreens = registeredScreens
    }

    public mutating func register(_ screen: ShellScreen) {
        guard !registeredScreens.contains(where: { $0.id == screen.id }) else { return }
        registeredScreens.append(screen)
    }

    public func route(to id: String) -> ShellScreen? {
        registeredScreens.first(where: { $0.id == id })
    }
}
