import XCTest
@testable import CleanMacCore

final class LargeOldTests: XCTestCase {
    func testNothingPreselected() {
        let item = LargeOldItem(path: "/x", size: 10, ageDays: 900, label: .normal)
        XCTAssertFalse(item.selectedByDefault)
    }

    func testForeignLabeled() {
        XCTAssertEqual(LargeOldItem(path: "/Volumes/Ext/x", size: 1, ageDays: 1, label: .foreign).label, .foreign)
        XCTAssertEqual(LargeOldItem(path: "/x", size: 1, ageDays: 1, label: .evicted).label, .evicted)
    }
}
