import Foundation

public struct TrashedItem: Sendable {
    public let originalPath: String
    public let trashURL: URL

    public init(originalPath: String, trashURL: URL) {
        self.originalPath = originalPath
        self.trashURL = trashURL
    }
}

public enum Trash {
    public static func trashItem(at url: URL) throws -> TrashedItem {
        var resultingURL: NSURL?
        try FileManager.default.trashItem(at: url, resultingItemURL: &resultingURL)
        guard let trashURL = resultingURL as URL? else {
            throw CocoaError(.fileNoSuchFile)
        }
        return TrashedItem(originalPath: url.path, trashURL: trashURL)
    }
}
