import Darwin
import Foundation

public struct TopPath: Sendable, Equatable {
    public let path: String
    public let size: UInt64
    public init(path: String, size: UInt64) { self.path = path; self.size = size }
}

public struct DiskScanResult: Sendable {
    public let totalPhysicalBytes: UInt64
    public let topPaths: [TopPath]
    public let unknownPaths: [String]
    public var unknownCount: Int { unknownPaths.count }
    public init(totalPhysicalBytes: UInt64, topPaths: [TopPath], unknownPaths: [String]) {
        self.totalPhysicalBytes = totalPhysicalBytes
        self.topPaths = topPaths
        self.unknownPaths = unknownPaths
    }
}

public enum DiskAnalyzer {
    public static func scan(at url: URL) throws -> DiskScanResult {
        let fm = FileManager.default
        guard fm.fileExists(atPath: url.path) else { throw CocoaError(.fileNoSuchFile) }
        var total: UInt64 = 0
        var unknowns: [String] = []
        var seenIDs = Set<String>()
        var seenRealPaths = Set<String>()
        var files: [TopPath] = []
        var stack: [URL] = [url]
        let keys: Set<URLResourceKey> = [.isDirectoryKey, .isSymbolicLinkKey, .totalFileAllocatedSizeKey, .fileAllocatedSizeKey, .fileSizeKey]

        func fileKey(_ path: String) -> String? {
            var st = stat()
            guard stat(path, &st) == 0 else { return nil }
            return "\(st.st_dev)-\(st.st_ino)"
        }

        while let cur = stack.popLast() {
            let real = cur.resolvingSymlinksInPath().path
            let vals: URLResourceValues
            do { vals = try cur.resourceValues(forKeys: keys) } catch { unknowns.append(cur.path); continue }
            if vals.isSymbolicLink == true {
                if seenRealPaths.contains(real) { continue }
                seenRealPaths.insert(real)
                if !fm.fileExists(atPath: real) { unknowns.append(cur.path); continue }
            }
            if let k = fileKey(cur.path), !seenIDs.insert(k).inserted { continue }
            if vals.isDirectory == true {
                if seenRealPaths.contains(real + "/d") { continue }
                seenRealPaths.insert(real + "/d")
                do {
                    let kids = try fm.contentsOfDirectory(at: cur, includingPropertiesForKeys: Array(keys), options: [])
                    stack.append(contentsOf: kids)
                } catch { unknowns.append(cur.path) }
                continue
            }
            let size: UInt64
            if let a = vals.totalFileAllocatedSize { size = UInt64(max(0, a)) }
            else if let a = vals.fileAllocatedSize { size = UInt64(max(0, a)) }
            else { size = UInt64(max(0, vals.fileSize ?? 0)) }
            total &+= size
            files.append(TopPath(path: cur.path, size: size))
        }
        files.sort { $0.size > $1.size }
        return DiskScanResult(totalPhysicalBytes: total, topPaths: Array(files.prefix(10)), unknownPaths: unknowns)
    }
}
