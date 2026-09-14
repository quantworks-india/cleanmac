import Foundation

public struct IgnoreList: Sendable {
    public var paths: Set<String>

    public init(paths: Set<String> = []) {
        self.paths = paths
    }

    public mutating func add(_ path: String) {
        paths.insert(path)
    }

    public mutating func remove(_ path: String) {
        paths.remove(path)
    }

    public func contains(_ path: String) -> Bool {
        paths.contains(path)
    }

    public func save(to url: URL) throws {
        let sorted = paths.sorted()
        let data = try JSONEncoder().encode(sorted)
        try data.write(to: url, options: .atomic)
    }

    public static func load(from url: URL) throws -> IgnoreList {
        let data = try Data(contentsOf: url)
        let array = try JSONDecoder().decode([String].self, from: data)
        return IgnoreList(paths: Set(array))
    }
}
