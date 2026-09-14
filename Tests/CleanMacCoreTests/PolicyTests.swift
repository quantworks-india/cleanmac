import XCTest

@testable import CleanMacCore

final class PolicyTests: XCTestCase {
    func testFreeForeverNoTelemetry() {
        XCTAssertTrue(Policy.isFreeForever)
        XCTAssertFalse(Policy.allowsTelemetry)
    }

    func testNonGoalsContainsExactlySix() {
        XCTAssertEqual(Policy.nonGoals, [
            "Photos bodies",
            "Mail bodies",
            "iCloud bodies",
            "boot-volume operations",
            "deleting running apps",
            "MDM-managed machines",
        ])
    }

    func testAssumptions() {
        XCTAssertEqual(Policy.assumptions, [
            "single-user Mac",
            "APFS boot volume",
            "Spotlight on",
        ])
    }
}
