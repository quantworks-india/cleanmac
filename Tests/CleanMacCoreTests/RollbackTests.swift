import Foundation
import XCTest
@testable import CleanMacCore

final class RollbackTests: XCTestCase {
    func testRestoreReturnsItem() throws {
        let fixture = try makeFixture(contents: "restore-me")
        let item = try Trash.trashItem(at: fixture)
        let restored = try Rollback.restore(item)
        XCTAssertEqual(restored.path, fixture.path)
        XCTAssertTrue(FileManager.default.fileExists(atPath: restored.path))
        XCTAssertEqual(try String(contentsOf: restored), "restore-me")
    }

    func testRebuiltOverPathGetsSuffixNotOverwrite() throws {
        let fixture = try makeFixture(contents: "original")
        let item = try Trash.trashItem(at: fixture)
        try "rebuilt".write(to: fixture, atomically: true, encoding: .utf8)
        let restored = try Rollback.restore(item)
        XCTAssertNotEqual(restored.path, fixture.path)
        XCTAssertTrue(restored.lastPathComponent.contains("(restored "))
        XCTAssertEqual(try String(contentsOf: fixture), "rebuilt")
        XCTAssertEqual(try String(contentsOf: restored), "original")
    }

    func testPerItemFailureReportedViaThrows() {
        let missing = TrashedItem(
            originalPath: FileManager.default.temporaryDirectory.appendingPathComponent("nope").path,
            trashURL: FileManager.default.temporaryDirectory.appendingPathComponent("nope-missing")
        )
        XCTAssertThrowsError(try Rollback.restore(missing))
    }

    private func makeFixture(contents: String) throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("txt")
        try contents.write(to: url, atomically: true, encoding: .utf8)
        return url
    }
}
