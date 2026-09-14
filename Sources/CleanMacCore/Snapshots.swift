import Foundation

public struct Snapshot: Sendable, Equatable {
    public let name: String
    public let sizeBytes: UInt64
    public let ageDays: Int
    public init(name: String, sizeBytes: UInt64, ageDays: Int) {
        self.name = name; self.sizeBytes = sizeBytes; self.ageDays = ageDays
    }
}

public enum Snapshots {
    public static func list() -> [Snapshot] {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/tmutil")
        proc.arguments = ["listlocalsnapshots", "/"]
        let pipe = Pipe()
        proc.standardOutput = pipe; proc.standardError = Pipe()
        do { try proc.run(); proc.waitUntilExit() } catch { return [] }
        guard proc.terminationStatus == 0 else { return [] }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let text = String(data: data, encoding: .utf8) else { return [] }
        return parse(output: text)
    }

    public static func parse(output: String) -> [Snapshot] {
        var out: [Snapshot] = []
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        fmt.locale = Locale(identifier: "en_US_POSIX")
        for raw in output.components(separatedBy: .newlines) {
            let line = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard line.contains("com.apple.TimeMachine") else { continue }
            let name = line.components(separatedBy: .whitespaces).first(where: { $0.contains("com.apple.") }) ?? line
            var age = 0
            if let r = line.range(of: #"\d{4}-\d{2}-\d{2}"#, options: .regularExpression),
               let d = fmt.date(from: String(line[r])) {
                age = max(0, Calendar.current.dateComponents([.day], from: d, to: Date()).day ?? 0)
            }
            out.append(Snapshot(name: name, sizeBytes: 0, ageDays: age))
        }
        return out
    }
}
