import XCTest
@testable import CleanMacCore

final class SnapshotTests: XCTestCase {
    func testListNeverThrows() {
        let snaps = Snapshots.list()
        XCTAssertGreaterThanOrEqual(snaps.count, 0)
    }

    func testParseFallback() {
        XCTAssertEqual(Snapshots.parse(output: "garbage\nno snapshots\n"), [])
        let parsed = Snapshots.parse(output: "com.apple.TimeMachine.2026-09-01-120000.local\n")
        XCTAssertEqual(parsed.count, 1)
        XCTAssertFalse(parsed[0].name.isEmpty)
    }
}
