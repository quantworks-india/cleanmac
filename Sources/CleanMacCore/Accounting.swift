import Foundation

public struct Accounting: Sendable {
    public private(set) var pendingBytes: Int64
    public private(set) var freedBytes: Int64

    public init(pendingBytes: Int64 = 0, freedBytes: Int64 = 0) {
        self.pendingBytes = pendingBytes
        self.freedBytes = freedBytes
    }

    public mutating func addPending(_ bytes: Int64) {
        pendingBytes += bytes
    }

    public mutating func addFreed(_ bytes: Int64) {
        freedBytes += bytes
    }

    public mutating func emptyTrash() {
        freedBytes += pendingBytes
        pendingBytes = 0
    }
}
