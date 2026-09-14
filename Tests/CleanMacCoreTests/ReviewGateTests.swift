import XCTest
@testable import CleanMacCore

final class ReviewGateTests: XCTestCase {
    func testListedPathsConfirmCommits() {
        var gate = ReviewGate(paths: ["/tmp/a", "/tmp/b"])
        XCTAssertTrue(gate.presentsGate)
        XCTAssertFalse(gate.committed)
        gate.confirm()
        XCTAssertTrue(gate.committed)
        XCTAssertEqual(gate.scope, ["/tmp/a", "/tmp/b"])
    }

    func testToggleChangesScopeWithoutCommitting() {
        var gate = ReviewGate(paths: ["/tmp/a", "/tmp/b"])
        gate.toggle("/tmp/a")
        XCTAssertFalse(gate.committed)
        XCTAssertEqual(gate.scope, ["/tmp/b"])
    }

    func testZeroEvidenceReturnsSummaryWithoutGate() {
        let gate = ReviewGate(paths: [])
        XCTAssertFalse(gate.presentsGate)
        let summary = ReviewGate.emptySummary(searched: ["/tmp"])
        XCTAssertTrue(summary.lowercased().contains("nothing found"))
        XCTAssertTrue(summary.contains("/tmp"))
    }
}
