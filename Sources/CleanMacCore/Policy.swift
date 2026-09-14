public enum NetworkCallKind: Sendable, Equatable {
    case userInitiatedUpdateCheck
    case userInvokedCLITool
    case backgroundAnalytics
}

public enum Policy {
    public static let isFreeForever = true
    public static let allowsTelemetry = false

    /// Exactly six exclusions the engine enforces (Task 2).
    /// Photos / Mail / iCloud count separately — total is six, reconciled.
    public static let nonGoals: [String] = [
        "Photos bodies",
        "Mail bodies",
        "iCloud bodies",
        "boot-volume operations",
        "deleting running apps",
        "MDM-managed machines",
    ]

    /// Stated assumptions the engine operates under (Task 2).
    public static let assumptions: [String] = [
        "single-user Mac",
        "APFS boot volume",
        "Spotlight on",
    ]

    public static var carveOuts: [NetworkCallKind] {
        [.userInitiatedUpdateCheck, .userInvokedCLITool]
    }

    public static func isNetworkCallAllowed(_ kind: NetworkCallKind) -> Bool {
        carveOuts.contains(kind)
    }
}
