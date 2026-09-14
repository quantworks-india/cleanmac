import XCTest
@testable import CleanMacCore

final class UpdaterTests: XCTestCase {
    func testDryRunListsPerApp() {
        let items = [UpdateItem(app: "Foo", fromVersion: "1.0", toVersion: "1.1", isMajor: false)]
        XCTAssertEqual(Updater.dryRun(items), ["Foo: 1.0 -> 1.1"])
    }

    func testMajorGated() {
        XCTAssertTrue(Updater.requiresConfirm(UpdateItem(app: "A", fromVersion: "1.0", toVersion: "2.0", isMajor: true)))
        XCTAssertFalse(Updater.requiresConfirm(UpdateItem(app: "A", fromVersion: "1.0", toVersion: "1.1", isMajor: false)))
    }
}
