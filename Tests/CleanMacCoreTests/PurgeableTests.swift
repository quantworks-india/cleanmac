import Foundation
import XCTest
@testable import CleanMacCore

final class PurgeableTests: XCTestCase {
    func testThreeDistinctNumbers() {
        let s = Purgeable.current()
        XCTAssertGreaterThanOrEqual(s.freeBytes, 0)
        XCTAssertGreaterThanOrEqual(s.purgeableBytes, 0)
        XCTAssertGreaterThanOrEqual(s.unavailableBytes, 0)
    }

    func testFallbackNeverThrows() {
        let s = Purgeable.current(for: URL(fileURLWithPath: "/nonexistent-\(UUID().uuidString)"))
        XCTAssertEqual(s.freeBytes, 0)
        XCTAssertEqual(s.purgeableBytes, 0)
    }
}
