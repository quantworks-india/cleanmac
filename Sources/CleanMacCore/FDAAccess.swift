import Foundation

public enum FDAAccessStatus: Sendable, Equatable { case granted, denied, unknown }

public struct FDAAccess {
    public static func status(home: URL) -> FDAAccessStatus {
        let fm = FileManager.default
        for sub in ["Library/Mail", "Library/Messages"] {
            let u = home.appendingPathComponent(sub)
            var isDir: ObjCBool = false
            guard fm.fileExists(atPath: u.path, isDirectory: &isDir) else { continue }
            do {
                _ = try fm.contentsOfDirectory(atPath: u.path)
                return .granted
            } catch let e as NSError where e.domain == NSCocoaErrorDomain && (e.code == NSFileReadNoPermissionError || e.code == 257) {
                return .denied
            } catch { continue }
        }
        return .unknown
    }

    public static func degradedBanner(unscanned: [String]) -> String {
        if unscanned.isEmpty { return "Partial results: some locations were not scanned." }
        return "Partial results: \(unscanned.count) location(s) unscanned due to permissions: " + unscanned.joined(separator: ", ")
    }
}
