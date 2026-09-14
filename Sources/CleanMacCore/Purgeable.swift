import Foundation

public struct VolumeSpace: Sendable, Equatable {
    public let freeBytes: UInt64
    public let purgeableBytes: UInt64
    public let unavailableBytes: UInt64
    public init(freeBytes: UInt64, purgeableBytes: UInt64, unavailableBytes: UInt64) {
        self.freeBytes = freeBytes; self.purgeableBytes = purgeableBytes; self.unavailableBytes = unavailableBytes
    }
}

public enum Purgeable {
    public static func current(for url: URL = URL(fileURLWithPath: "/")) -> VolumeSpace {
        let keys: Set<URLResourceKey> = [.volumeTotalCapacityKey, .volumeAvailableCapacityKey, .volumeAvailableCapacityForImportantUsageKey, .volumeAvailableCapacityForOpportunisticUsageKey]
        guard let v = try? url.resourceValues(forKeys: keys) else {
            return VolumeSpace(freeBytes: 0, purgeableBytes: 0, unavailableBytes: 0)
        }
        let total = UInt64(max(0, v.volumeTotalCapacity ?? 0))
        let free = UInt64(max(0, v.volumeAvailableCapacity ?? 0))
        let important = UInt64(max(0, Int64(v.volumeAvailableCapacityForImportantUsage ?? Int64(free))))
        let purgeable: UInt64 = free > important ? free - important : 0
        let unavailable: UInt64 = total > free ? total - free : 0
        return VolumeSpace(freeBytes: free, purgeableBytes: purgeable, unavailableBytes: unavailable)
    }
}
