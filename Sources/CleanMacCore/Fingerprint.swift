import Foundation

public struct AppFingerprint: Sendable, Equatable {
    public let bundleID: String?
    public let teamID: String?
    public let name: String

    public init(bundleID: String?, teamID: String?, name: String) {
        self.bundleID = bundleID
        self.teamID = teamID
        self.name = name
    }
}

public enum Fingerprint: Sendable {
    public static func evidenceLevel(app: AppFingerprint, bundleID: String?, teamID: String?, name: String?) -> Int {
        if let observed = bundleID, !observed.isEmpty,
           let expected = app.bundleID, !expected.isEmpty, observed == expected { return 3 }
        if let observed = teamID, !observed.isEmpty,
           let expected = app.teamID, !expected.isEmpty, observed == expected { return 2 }
        if let observed = name, !observed.isEmpty,
           isSeparatorBoundaryMatch(candidate: observed, target: app.name) { return 1 }
        return 0
    }

    public static func isSeparatorBoundaryMatch(candidate: String, target: String) -> Bool {
        if candidate.isEmpty || target.isEmpty { return false }
        if candidate == target { return true }
        let lc = candidate.lowercased()
        let lt = target.lowercased()
        guard lc.hasPrefix(lt) else { return false }
        let idx = lc.index(lc.startIndex, offsetBy: lt.count)
        let next = lc[idx]
        return next == "." || next == "-" || next == "_" || next == " " || next == "/" || next == "(" || next == "["
    }
}
