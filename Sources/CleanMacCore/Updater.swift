import Foundation

public struct UpdateItem: Sendable, Equatable {
    public let app: String
    public let fromVersion: String
    public let toVersion: String
    public let isMajor: Bool
    public init(app: String, fromVersion: String, toVersion: String, isMajor: Bool) {
        self.app = app; self.fromVersion = fromVersion; self.toVersion = toVersion; self.isMajor = isMajor
    }
}

public enum Updater {
    public static func dryRun(_ items: [UpdateItem]) -> [String] {
        items.map { "\($0.app): \($0.fromVersion) -> \($0.toVersion)" }
    }

    public static func requiresConfirm(_ item: UpdateItem) -> Bool {
        item.isMajor
    }
}
