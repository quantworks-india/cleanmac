import Foundation

public struct UninstallPlan: Sendable, Equatable {
    public let appPath: String
    public let files: [String]
    public let evidence: [String: Int]

    public init(appPath: String, files: [String], evidence: [String: Int]) {
        self.appPath = appPath
        self.files = files
        self.evidence = evidence
    }
}

public enum Uninstall: Sendable {
    public static func plan(appPath: String, fingerprint: AppFingerprint, homeFiles: [String]) throws -> UninstallPlan {
        if ProtectedPaths.isRefused(appPath) {
            throw CocoaError(.fileWriteNoPermission, userInfo: [NSLocalizedDescriptionKey: "refused protected path: \(appPath)"])
        }
        if let bid = fingerprint.bundleID, bid.hasPrefix("com.apple.") {
            throw CocoaError(.fileWriteNoPermission, userInfo: [NSLocalizedDescriptionKey: "refused Apple bundle: \(bid)"])
        }
        var files: [String] = []
        var evidence: [String: Int] = [:]
        for file in homeFiles {
            if ProtectedPaths.isRefused(file) { continue }
            if isAppleSystemFile(file) { continue }
            let level = levelForFile(file, fingerprint: fingerprint)
            if level > 0 { files.append(file); evidence[file] = level }
        }
        guard !files.isEmpty else {
            throw CocoaError(.fileNoSuchFile, userInfo: [NSLocalizedDescriptionKey: "searched \(homeFiles.count) files, found no evidence for \(appPath)"])
        }
        return UninstallPlan(appPath: appPath, files: files, evidence: evidence)
    }

    private static func levelForFile(_ path: String, fingerprint: AppFingerprint) -> Int {
        if let bid = fingerprint.bundleID, !bid.isEmpty, path.contains(bid) { return 3 }
        if let tid = fingerprint.teamID, !tid.isEmpty, path.contains(tid) { return 2 }
        if nameMatches(path: path, target: fingerprint.name) { return 1 }
        return 0
    }

    private static func nameMatches(path: String, target: String) -> Bool {
        let components = path.split(separator: "/").map(String.init)
        for c in components {
            if Fingerprint.isSeparatorBoundaryMatch(candidate: c, target: target) { return true }
        }
        if target.lowercased().hasSuffix(".app") {
            // Bare-stem fallback matches exact components only: extending the
            // separator rule here would re-admit "Foo.app2.*" via the "." in
            // "foo" + ".app2" — the exact misattribution the rule prevents.
            let base = String(target.dropLast(4)).lowercased()
            for c in components {
                if c.lowercased() == base { return true }
            }
        }
        return false
    }

    private static func isAppleSystemFile(_ path: String) -> Bool {
        if path.hasPrefix("/System/") || path == "/System" { return true }
        return path.lowercased().contains("/com.apple.")
    }
}
