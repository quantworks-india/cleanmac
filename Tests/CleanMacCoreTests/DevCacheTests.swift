import XCTest
@testable import CleanMacCore

final class DevCacheTests: XCTestCase {
    func testDetectorTableIsData() {
        XCTAssertGreaterThanOrEqual(DevCaches.detectors.count, 9)
        XCTAssertTrue(DevCaches.detectors.contains(where: { $0.tool == "brew" }))
    }

    func testRunningToolSkipped() {
        XCTAssertNotNil(DevCaches.skipReasonIfRunning("brew", runningTools: ["brew"]))
        XCTAssertNil(DevCaches.skipReasonIfRunning("brew", runningTools: []))
    }

    func testSimulatorRequiresOptIn() {
        XCTAssertTrue(DevCaches.detectors.first(where: { $0.tool == "simulator" })?.requiresOptIn == true)
    }
}
