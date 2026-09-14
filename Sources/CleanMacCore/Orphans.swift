import Foundation

public struct OrphanItem: Sendable, Equatable {
    public let path: String
    public let evidence: [String]

    public init(path: String, evidence: [String]) {
        self.path = path
        self.evidence = evidence
    }
}

public enum Orphans: Sendable {
    public static func isSharedLocation(_ path: String) -> Bool {
        let lower = path.lowercased()
        if lower.contains("electron") { return true }
        if lower.contains("sparkle") { return true }
        if lower.contains("/fonts/") || lower.hasSuffix("/fonts") { return true }
        if lower.contains("/containers/") || lower.hasSuffix("/containers") { return true }
        if lower.contains("group containers") { return true }
        return false
    }

    public static func flag(path: String, evidence: [String]) -> OrphanItem? {
        if evidence.isEmpty { return nil }
        if isSharedLocation(path) {
            guard Set(evidence).count >= 2 else { return nil }
        }
        return OrphanItem(path: path, evidence: evidence)
    }
}
