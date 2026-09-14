import Foundation

public enum Installers {
    public static func isInstaller(_ path: String) -> Bool {
        let lower = path.lowercased()
        guard lower.hasSuffix(".dmg") || lower.hasSuffix(".pkg") || lower.hasSuffix(".xip") else { return false }
        return lower.contains("/downloads/") || lower.hasPrefix("/users/") || lower.hasPrefix("/private/tmp/")
    }
}
