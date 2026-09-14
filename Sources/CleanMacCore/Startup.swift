import Foundation

public enum StartupItemState: String, Sendable, Equatable {
    case enabled
    case disabled
    case requiresApproval
}

public struct StartupItem: Sendable, Equatable {
    public let label: String
    public let state: StartupItemState

    public init(label: String, state: StartupItemState) {
        self.label = label
        self.state = state
    }
}

public enum Startup: Sendable {
    public static func disable(_ item: StartupItem) -> StartupItem {
        StartupItem(label: item.label, state: .disabled)
    }

    public static func approvalDeniedExplanation() -> String {
        "Approval required in System Settings > General > Login Items. Open x-apple.systempreferences:com.apple.LoginItems-Settings.extension to allow the change."
    }
}
