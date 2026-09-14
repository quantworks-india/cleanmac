import Foundation

public enum LargeOldLabel: String, Sendable { case normal, evicted, backup, foreign }

public struct LargeOldItem: Sendable, Equatable {
    public let path: String
    public let size: UInt64
    public let ageDays: Int
    public let label: LargeOldLabel
    public let selectedByDefault: Bool
    public init(path: String, size: UInt64, ageDays: Int, label: LargeOldLabel) {
        self.path = path; self.size = size; self.ageDays = ageDays; self.label = label
        self.selectedByDefault = false
    }
}
