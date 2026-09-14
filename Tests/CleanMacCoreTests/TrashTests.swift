import Foundation
import XCTest
@testable import CleanMacCore

final class TrashTests: XCTestCase {
    func testTrashRecordsResultingURL() throws {
        let fixture = try makeFixture(contents: "trash-me")
        let item = try Trash.trashItem(at: fixture)
        XCTAssertEqual(item.originalPath, fixture.path)
        XCTAssertTrue(FileManager.default.fileExists(atPath: item.trashURL.path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.path))
    }

    func testTrashDoesNotClaimFreed() throws {
        let fixture = try makeFixture(contents: "payload")
        let attrs = try FileManager.default.attributesOfItem(atPath: fixture.path)
        let size: Int64
        if let n = attrs[.size] as? NSNumber { size = n.int64Value } else { size = 0 }
        let item = try Trash.trashItem(at: fixture)
        XCTAssertTrue(FileManager.default.fileExists(atPath: item.trashURL.path))
        var accounting = Accounting()
        accounting.addPending(size)
        XCTAssertEqual(accounting.pendingBytes, size)
        XCTAssertEqual(accounting.freedBytes, 0)
    }

    func testEmptyTrashIsExplicit() {
        var accounting = Accounting()
        accounting.addPending(100)
        XCTAssertEqual(accounting.pendingBytes, 100)
        XCTAssertEqual(accounting.freedBytes, 0)
        accounting.emptyTrash()
        XCTAssertEqual(accounting.pendingBytes, 0)
        XCTAssertEqual(accounting.freedBytes, 100)
    }

    private func makeFixture(contents: String) throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("txt")
        try contents.write(to: url, atomically: true, encoding: .utf8)
        return url
    }
}
