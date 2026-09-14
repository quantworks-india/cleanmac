import XCTest
@testable import CleanMacCore

final class AICacheTests: XCTestCase {
    func testDetectorsCachesLogsOnly() {
        XCTAssertEqual(AICaches.detectors.count, 4)
        for d in AICaches.detectors {
            for p in d.cachePaths {
                let l = p.lowercased()
                XCTAssertTrue(l.contains("cach") || l.contains("log"))
            }
        }
    }

    func testModelDirsExcluded() {
        for m in ["~/.ollama/models/llama3", "~/Library/Caches/huggingface/hub/model.safetensors", "/models/llama-3.gguf"] {
            XCTAssertTrue(AICaches.isModelDirExcluded(m))
        }
    }

    func testStaleUnknown() {
        let stale = AICacheDetector(tool: "Claude", versionedLayout: -999, cachePaths: ["~/Library/Caches/claude-code"])
        XCTAssertEqual(AICaches.status(for: stale), "unknown")
    }
}
