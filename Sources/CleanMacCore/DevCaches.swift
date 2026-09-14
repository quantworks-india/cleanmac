import Foundation

public struct DevCacheDetector: Sendable {
    public let tool: String
    public let paths: [String]
    public let requiresOptIn: Bool
    public init(tool: String, paths: [String], requiresOptIn: Bool = false) {
        self.tool = tool; self.paths = paths; self.requiresOptIn = requiresOptIn
    }
}

public enum DevCaches {
    public static let detectors: [DevCacheDetector] = [
        DevCacheDetector(tool: "brew", paths: ["~/Library/Caches/Homebrew"]),
        DevCacheDetector(tool: "npm", paths: ["~/.npm"]),
        DevCacheDetector(tool: "pip", paths: ["~/Library/Caches/pip"]),
        DevCacheDetector(tool: "cargo", paths: ["~/.cargo/registry/cache"]),
        DevCacheDetector(tool: "go", paths: ["~/Library/Caches/go-build"]),
        DevCacheDetector(tool: "docker", paths: ["~/Library/Containers/com.docker.docker/Data"]),
        DevCacheDetector(tool: "xcode", paths: ["~/Library/Developer/Xcode/DerivedData"], requiresOptIn: true),
        DevCacheDetector(tool: "jetbrains", paths: ["~/Library/Caches/JetBrains"]),
        DevCacheDetector(tool: "vscode", paths: ["~/Library/Application Support/Code/Cache"]),
        DevCacheDetector(tool: "simulator", paths: ["~/Library/Developer/CoreSimulator"], requiresOptIn: true),
        DevCacheDetector(tool: "toolchain", paths: ["~/Library/Developer/Toolchains"], requiresOptIn: true),
    ]

    public static func skipReasonIfRunning(_ tool: String, runningTools: Set<String>) -> String? {
        runningTools.contains(tool) ? "\(tool) is running; skipped, never killed" : nil
    }
}
