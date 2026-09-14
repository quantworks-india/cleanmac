public enum ProtectedPaths: Sendable {
    public static func isRefused(_ path: String) -> Bool {
        let normalized = normalize(path)
        if normalized.isEmpty { return true }
        if normalized == "/" { return true }
        if isAllowedApplicationBundle(normalized) { return false }
        if containsAppleBundleSegment(normalized) { return true }
        return isUnderRefusedRoot(normalized)
    }

    private static func normalize(_ path: String) -> String {
        if path.isEmpty { return path }
        var result = path
        while result.count > 1 && result.hasSuffix("/") { result.removeLast() }
        return result
    }

    private static func isAllowedApplicationBundle(_ normalized: String) -> Bool {
        if normalized == "/Applications" { return true }
        guard normalized.hasPrefix("/Applications/") else { return false }
        let remainder = String(normalized.dropFirst("/Applications/".count))
        if remainder.isEmpty { return true }
        if remainder.contains(".app/") { return true }
        if remainder.hasSuffix(".app") { return true }
        return false
    }

    private static func containsAppleBundleSegment(_ normalized: String) -> Bool {
        let components = normalized.lowercased().split(separator: "/")
        for component in components {
            if component.contains("com.apple.") { return true }
        }
        return false
    }

    private static let refusedRoots: [String] = [
        "/System",
        "/bin",
        "/sbin",
        "/etc",
        "/private/etc",
        "/private/var/db",
        "/var/db",
        "/Library/Apple",
        "/dev",
    ]

    private static func isUnderRefusedRoot(_ normalized: String) -> Bool {
        for root in refusedRoots {
            if normalized == root || normalized.hasPrefix(root + "/") { return true }
        }
        if normalized == "/usr" { return true }
        if normalized.hasPrefix("/usr/") {
            if normalized == "/usr/local" || normalized.hasPrefix("/usr/local/") { return false }
            return true
        }
        return false
    }
}
