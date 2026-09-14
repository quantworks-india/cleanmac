import Foundation

public struct SpaceOp: Sendable {
    public let name: String
    public let freesBytes: Bool
    public init(name: String) { self.name = name; self.freesBytes = true }
}

public enum MaintenanceSpace {
    public static let ops: [SpaceOp] = [SpaceOp(name: "purgeable-release"), SpaceOp(name: "snapshot-thinning")]
}
