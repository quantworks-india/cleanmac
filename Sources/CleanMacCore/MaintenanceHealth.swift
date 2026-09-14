import Foundation

public struct HealthOp: Sendable {
    public let name: String
    public let claimsBytes: Bool
    public let reversible: Bool
    public let privilege: String
    public init(name: String, reversible: Bool, privilege: String) {
        self.name = name; self.claimsBytes = false; self.reversible = reversible; self.privilege = privilege
    }
}

public enum MaintenanceHealth {
    public static let ops: [HealthOp] = [
        HealthOp(name: "dns-flush", reversible: true, privilege: "admin auth prompt"),
        HealthOp(name: "spotlight-reindex", reversible: true, privilege: "admin auth prompt"),
        HealthOp(name: "periodic-scripts", reversible: true, privilege: "admin auth prompt"),
    ]
}
