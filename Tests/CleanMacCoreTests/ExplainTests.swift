import XCTest
@testable import CleanMacCore

final class ExplainTests: XCTestCase {
    func testFixedSchema() throws {
        let e = Explain.describe(kind: "cache", ownerApp: "Xcode", ageDays: 12)
        let data = try JSONEncoder().encode(e)
        let json = String(data: data, encoding: .utf8) ?? ""
        XCTAssertFalse(json.contains("safety"))
        XCTAssertFalse(Explain.isSafetyAssertion(json))
        XCTAssertEqual(try JSONDecoder().decode(FileExplanation.self, from: data), e)
    }

    func testAdversarialNeverSafety() {
        for input in ["a3f9c1d2e44b", "/Applications/Signed.app/Contents/MacOS/Signed", "com.apple.signed-bundle"] {
            let e = Explain.describe(kind: input, ownerApp: input, ageDays: 9999)
            XCTAssertFalse(Explain.isSafetyAssertion(Explain.summary(for: e)))
        }
    }
}
