import Foundation

public enum Rollback {
    public static func restore(_ item: TrashedItem) throws -> URL {
        let fm = FileManager.default
        guard fm.fileExists(atPath: item.trashURL.path) else {
            throw CocoaError(.fileNoSuchFile)
        }
        let destination = URL(fileURLWithPath: item.originalPath)
        let finalDestination: URL
        if fm.fileExists(atPath: destination.path) {
            finalDestination = firstAvailableURL(near: destination)
            warn("destination exists, restoring with suffix: \(finalDestination.path)")
        } else {
            finalDestination = destination
        }
        try fm.moveItem(at: item.trashURL, to: finalDestination)
        return finalDestination
    }

    private static func firstAvailableURL(near url: URL) -> URL {
        let fm = FileManager.default
        var attempt = 1
        while true {
            let candidate = suffixedURL(for: url, attempt: attempt)
            if !fm.fileExists(atPath: candidate.path) { return candidate }
            attempt += 1
        }
    }

    private static func suffixedURL(for url: URL, attempt: Int) -> URL {
        let stem = url.deletingPathExtension().lastPathComponent
        let ext = url.pathExtension
        let name = "\(stem) (restored \(attempt))"
        let dir = url.deletingLastPathComponent()
        if ext.isEmpty { return dir.appendingPathComponent(name, isDirectory: false) }
        return dir.appendingPathComponent(name).appendingPathExtension(ext)
    }

    private static func warn(_ message: String) {
        if let data = ("warning: \(message)\n").data(using: .utf8) {
            FileHandle.standardError.write(data)
        }
    }
}
