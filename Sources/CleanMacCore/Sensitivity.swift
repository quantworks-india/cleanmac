public enum Sensitivity: String, Sendable, CaseIterable {
    case strict
    case enhanced
    case deep

    public var requiredEvidence: Int {
        switch self {
        case .strict: 3
        case .enhanced: 2
        case .deep: 1
        }
    }

    public var maxFalsePositiveRate: Double {
        switch self {
        case .strict: 0.001
        case .enhanced: 0.01
        case .deep: 0.05
        }
    }
}
