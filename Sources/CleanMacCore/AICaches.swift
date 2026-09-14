public struct AICacheDetector: Sendable {
    public let tool: String
    public let versionedLayout: Int
    public let cachePaths: [String]
    public init(tool: String, versionedLayout: Int, cachePaths: [String]) {
        self.tool = tool; self.versionedLayout = versionedLayout; self.cachePaths = cachePaths
    }
}

public enum AICaches {
    public static let currentLayoutVersion: Int = 1

    public static let detectors: [AICacheDetector] = [
        AICacheDetector(tool: "Claude", versionedLayout: currentLayoutVersion, cachePaths: ["~/Library/Caches/claude-code", "~/Library/Logs/Claude"]),
        AICacheDetector(tool: "Cursor", versionedLayout: currentLayoutVersion, cachePaths: ["~/Library/Caches/Cursor", "~/Library/Logs/Cursor"]),
        AICacheDetector(tool: "Ollama", versionedLayout: currentLayoutVersion, cachePaths: ["~/.ollama/logs", "~/Library/Logs/Ollama", "~/Library/Caches/Ollama"]),
        AICacheDetector(tool: "Copilot", versionedLayout: currentLayoutVersion, cachePaths: ["~/Library/Caches/github-copilot", "~/Library/Logs/github-copilot"]),
    ]

    public static func isModelDirExcluded(_ path: String) -> Bool {
        let lower = path.lowercased()
        for m in ["/models", ".ollama/models", "huggingface/hub", "/weights", "/checkpoints", ".gguf", ".safetensors"] {
            if lower.contains(m) { return true }
        }
        return false
    }

    public static func status(for detector: AICacheDetector) -> String {
        guard detector.versionedLayout == currentLayoutVersion else { return "unknown" }
        return "known"
    }
}
