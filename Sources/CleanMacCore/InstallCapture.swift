import Foundation

public struct InstallDiff: Sendable, Equatable {
    public let added: [String]
    public let confidence: [String: Double]
    public let unknowns: [String]

    public init(added: [String], confidence: [String: Double], unknowns: [String]) {
        self.added = added
        self.confidence = confidence
        self.unknowns = unknowns
    }
}

public enum InstallCapture: Sendable {
    public static func diff(before: Set<String>, after: Set<String>) -> InstallDiff {
        let added = after.subtracting(before).sorted()
        var confidence: [String: Double] = [:]
        var unknowns: [String] = []
        for path in added {
            if isUnknownPath(path) { confidence[path] = 0.3; unknowns.append(path) } else { confidence[path] = 0.9 }
        }
        return InstallDiff(added: added, confidence: confidence, unknowns: unknowns.sorted())
    }

    private static func isUnknownPath(_ path: String) -> Bool {
        let lower = path.lowercased()
        if lower.hasPrefix("/system") { return true }
        if lower.hasPrefix("/bin") { return true }
        if lower.hasPrefix("/sbin") { return true }
        if lower.hasPrefix("/usr/bin") { return true }
        if lower.hasPrefix("/usr/sbin") { return true }
        if lower.contains("launchdaemon") { return true }
        if lower.contains("launchagent") { return true }
        if lower.contains("/var/db/") { return true }
        if lower.contains("reboot") { return true }
        return false
    }
}
