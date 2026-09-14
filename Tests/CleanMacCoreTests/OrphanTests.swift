import XCTest
@testable import CleanMacCore

final class OrphanTests: XCTestCase {
    func testSharedLocationsNeverAutoFlagged() {
        XCTAssertTrue(Orphans.isSharedLocation("/Users/test/Library/Application Support/Electron/cache"))
        XCTAssertTrue(Orphans.isSharedLocation("/Users/test/Library/Application Support/Sparkle/state"))
        XCTAssertTrue(Orphans.isSharedLocation("/Library/Fonts/Custom.ttf"))
        XCTAssertTrue(Orphans.isSharedLocation("/Users/test/Library/Containers/com.example.Foo/Data"))
        XCTAssertFalse(Orphans.isSharedLocation("/Users/test/Library/Application Support/com.example.Foo/data"))
    }

    func testSharedLocationRequiresTwoIndependentHits() {
        XCTAssertNil(Orphans.flag(path: "/Library/Fonts/Custom.ttf", evidence: []))
        XCTAssertNil(Orphans.flag(path: "/Users/test/Library/Containers/com.example.Foo/Data", evidence: ["a"]))
        XCTAssertNil(Orphans.flag(path: "/Users/test/Library/Containers/com.example.Foo/Data", evidence: ["a", "a"]))
        XCTAssertNotNil(Orphans.flag(path: "/Users/test/Library/Containers/com.example.Foo/Data", evidence: ["a", "b"]))
    }

    func testNonSharedSingleHit() {
        XCTAssertNotNil(Orphans.flag(path: "/Users/test/Library/Caches/com.example.Dead/cache", evidence: ["bundle-missing"]))
        XCTAssertNil(Orphans.flag(path: "/Users/test/Library/Caches/com.example.Dead/cache", evidence: []))
    }
}
