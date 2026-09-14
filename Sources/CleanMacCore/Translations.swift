import Foundation

public enum Translations {
    public static func prunePlan(app: String, lprojDirs: [String], keep: Set<String>) -> [String] {
        lprojDirs.filter { !keep.contains($0) }
    }
}
