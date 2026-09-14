import XCTest

@testable import CleanMacCore

final class PolicyTests: XCTestCase {
    func testFreeForeverNoTelemetry() {
        XCTAssertTrue(Policy.isFreeForever)
        XCTAssertFalse(Policy.allowsTelemetry)
    }
}
