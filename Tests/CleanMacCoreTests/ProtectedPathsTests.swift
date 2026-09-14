import Foundation
import XCTest
@testable import CleanMacCore

final class ProtectedPathsTests: XCTestCase {
    func testRefusesSystemLibrary() {
        XCTAssertTrue(ProtectedPaths.isRefused("/System/Library/Extensions/foo.kext"))
        XCTAssertTrue(ProtectedPaths.isRefused("/System"))
        XCTAssertTrue(ProtectedPaths.isRefused("/bin/ls"))
        XCTAssertTrue(ProtectedPaths.isRefused("/sbin/reboot"))
        XCTAssertTrue(ProtectedPaths.isRefused("/usr/bin/ruby"))
        XCTAssertTrue(ProtectedPaths.isRefused("/private/var/db/receipts/foo.plist"))
        XCTAssertFalse(ProtectedPaths.isRefused("/usr/local/bin/foo"))
    }

    func testRefusesLibraryAppleAndComApplePaths() {
        XCTAssertTrue(ProtectedPaths.isRefused("/Library/Apple/System/foo"))
        XCTAssertTrue(ProtectedPaths.isRefused("/Library/LaunchAgents/com.apple.Safari.plist"))
        XCTAssertTrue(ProtectedPaths.isRefused("/Users/test/Library/Preferences/com.apple.finder.plist"))
    }

    func testAllowsApplicationsApp() {
        XCTAssertFalse(ProtectedPaths.isRefused("/Applications/Foo.app"))
        XCTAssertFalse(ProtectedPaths.isRefused("/Applications/Foo.app/Contents/MacOS/foo"))
        XCTAssertFalse(ProtectedPaths.isRefused("/Applications"))
    }

    func testIgnoreListAddRemove() {
        var list = IgnoreList()
        XCTAssertFalse(list.contains("/tmp/foo"))
        list.add("/tmp/foo")
        XCTAssertTrue(list.contains("/tmp/foo"))
        list.remove("/tmp/foo")
        XCTAssertFalse(list.contains("/tmp/foo"))
    }

    func testIgnoreListPersistRoundTrip() throws {
        var list = IgnoreList()
        list.add("/tmp/foo")
        list.add("/Applications/Foo.app")
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("IgnoreList-\(UUID().uuidString).json")
        try list.save(to: url)
        let loaded = try IgnoreList.load(from: url)
        XCTAssertTrue(loaded.contains("/tmp/foo"))
        XCTAssertTrue(loaded.contains("/Applications/Foo.app"))
        XCTAssertEqual(loaded.paths, list.paths)
        try? FileManager.default.removeItem(at: url)
    }
}
