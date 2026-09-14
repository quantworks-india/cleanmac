import Foundation

public struct ProjectArtifact: Sendable, Equatable {
    public let path: String
    public let projectRoot: String
    public let reproducible: Bool
    public init(path: String, projectRoot: String, reproducible: Bool) {
        self.path = path; self.projectRoot = projectRoot; self.reproducible = reproducible
    }
}

public enum ProjectPurge {
    public static func isPreselected(_ artifact: ProjectArtifact) -> Bool {
        if !artifact.reproducible { return false }
        let lower = artifact.path.lowercased()
        if lower.hasSuffix("/.venv") || lower.contains("/.venv/") { return false }
        if lower.contains("conda") { return false }
        return true
    }
}
