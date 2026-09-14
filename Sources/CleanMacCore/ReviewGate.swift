/// Per-path review contract gate.
///
/// Rendering checklist:
/// - light appearance check
/// - dark appearance check
/// - monochrome appearance check
/// - 80-col table layout check
public struct ReviewGate: Sendable {
    public static let checklist: [String] = [
        "light: gate list renders in light appearance",
        "dark: gate list renders in dark appearance",
        "monochrome: gate list remains legible in monochrome",
        "80-col table: gate list fits an 80-col table",
    ]

    public let paths: [String]
    public private(set) var selected: Set<String>
    public private(set) var committed: Bool = false

    public var presentsGate: Bool { !paths.isEmpty }
    public var scope: [String] { selected.sorted() }

    public init(paths: [String]) {
        self.paths = paths
        self.selected = Set(paths)
    }

    public mutating func toggle(_ path: String) {
        guard paths.contains(path) else { return }
        if selected.contains(path) { selected.remove(path) } else { selected.insert(path) }
    }

    public mutating func confirm() {
        guard presentsGate, !committed else { return }
        committed = true
    }

    public static func emptySummary(searched: [String]) -> String {
        if searched.isEmpty { return "nothing found; nothing was searched" }
        return "nothing found; searched: " + searched.sorted().joined(separator: ", ")
    }
}
