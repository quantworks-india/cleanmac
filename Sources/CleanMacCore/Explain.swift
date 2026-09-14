public struct FileExplanation: Sendable, Codable, Equatable {
    public let kind: String
    public let ownerApp: String
    public let ageDays: Int
    public init(kind: String, ownerApp: String, ageDays: Int) {
        self.kind = kind; self.ownerApp = ownerApp; self.ageDays = ageDays
    }
}

public enum Explain {
    public static func describe(kind: String, ownerApp: String, ageDays: Int) -> FileExplanation {
        FileExplanation(kind: kind, ownerApp: ownerApp, ageDays: ageDays)
    }

    public static func isSafetyAssertion(_ text: String) -> Bool {
        let lower = text.lowercased()
        for b in ["safe to delete", "safety", "safe for removal", "risk-free", "risk free", "guaranteed safe", "safe to remove"] {
            if lower.contains(b) { return true }
        }
        return false
    }

    public static func summary(for explanation: FileExplanation) -> String {
        if #available(macOS 26, *) {
            return "\(explanation.kind) from \(explanation.ownerApp), \(explanation.ageDays) days old."
        } else {
            return "Explanation unavailable on this macOS version."
        }
    }
}
