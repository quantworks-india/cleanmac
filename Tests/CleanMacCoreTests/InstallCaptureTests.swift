import XCTest
@testable import CleanMacCore

final class InstallCaptureTests: XCTestCase {
    func testDiffFindsAddedWithConfidence() {
        let result = InstallCapture.diff(before: ["/Applications/Foo.app"], after: ["/Applications/Foo.app", "/Library/Preferences/com.example.Foo.plist"])
        XCTAssertEqual(result.added, ["/Library/Preferences/com.example.Foo.plist"])
        XCTAssertEqual(result.confidence["/Library/Preferences/com.example.Foo.plist"], 0.9)
        XCTAssertTrue(result.unknowns.isEmpty)
    }

    func testDaemonAndSIPFlaggedUnknown() {
        let result = InstallCapture.diff(before: [], after: ["/Library/LaunchDaemons/com.example.Foo.plist", "/System/Library/Extensions/Foo.kext", "/Applications/Foo.app/Contents/MacOS/Foo"])
        XCTAssertTrue(result.unknowns.contains("/Library/LaunchDaemons/com.example.Foo.plist"))
        XCTAssertTrue(result.unknowns.contains("/System/Library/Extensions/Foo.kext"))
        XCTAssertFalse(result.unknowns.contains("/Applications/Foo.app/Contents/MacOS/Foo"))
    }
}
