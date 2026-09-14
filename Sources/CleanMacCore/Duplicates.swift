import Darwin
import Foundation

public enum Duplicates {
    public static func fnv1a(_ data: Data) -> UInt64 {
        var h: UInt64 = 14_695_959_275_955_611
        for b in data { h ^= UInt64(b); h &*= 1_099_511_628_211 }
        return h
    }

    public static func hashOfFile(at url: URL) throws -> UInt64 {
        let fh = try FileHandle(forReadingFrom: url)
        defer { try? fh.close() }
        var h: UInt64 = 14_695_959_275_955_611
        while let chunk = try fh.read(upToCount: 1 << 20), !chunk.isEmpty {
            for b in chunk { h ^= UInt64(b); h &*= 1_099_511_628_211 }
        }
        return h
    }

    public static func group(paths: [String]) throws -> [[String]] {
        var bySize: [UInt64: [String]] = [:]
        var idsSeen = Set<String>()
        for p in paths {
            let url = URL(fileURLWithPath: p)
            let v = try url.resourceValues(forKeys: [.fileSizeKey])
            var st = stat()
            if stat(p, &st) == 0 {
                let k = "\(st.st_dev)-\(st.st_ino)"
                if !idsSeen.insert(k).inserted { continue }
            }
            bySize[UInt64(max(0, v.fileSize ?? 0)), default: []].append(p)
        }
        var out: [[String]] = []
        for (_, group) in bySize where group.count > 1 {
            var byHash: [UInt64: [String]] = [:]
            for p in group { byHash[try hashOfFile(at: URL(fileURLWithPath: p)), default: []].append(p) }
            for (_, g) in byHash where g.count > 1 { out.append(g.sorted()) }
        }
        return out
    }
}
