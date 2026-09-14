import XCTest
@testable import CleanMacCore

final class MaintenanceTests: XCTestCase {
    func testNoHealthOpReportsBytes() {
        for op in MaintenanceHealth.ops { XCTAssertFalse(op.claimsBytes) }
    }

    func testSpaceOpsFree() {
        for op in MaintenanceSpace.ops { XCTAssertTrue(op.freesBytes) }
    }

    func testPrivilegeDocumented() {
        for op in MaintenanceHealth.ops { XCTAssertFalse(op.privilege.isEmpty) }
    }
}
