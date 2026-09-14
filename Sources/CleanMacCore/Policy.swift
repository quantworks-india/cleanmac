public enum NetworkCallKind: Sendable, Equatable {
    case userInitiatedUpdateCheck
    case userInvokedCLITool
    case backgroundAnalytics
}

public enum Policy {
    public static let isFreeForever = true
    public static let allowsTelemetry = false

    public static var carveOuts: [NetworkCallKind] {
        [.userInitiatedUpdateCheck, .userInvokedCLITool]
    }

    public static func isNetworkCallAllowed(_ kind: NetworkCallKind) -> Bool {
        carveOuts.contains(kind)
    }
}
