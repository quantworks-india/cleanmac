import XCTest
@testable import CleanMacCore

final class UninstallTests: XCTestCase {
    private func fingerprint() -> AppFingerprint {
        AppFingerprint(bundleID: "com.example.Foo", teamID: "TEAM123", name: "Foo")
    }

    func testEvidenceLevels() {
        let app = fingerprint()
        XCTAssertEqual(Fingerprint.evidenceLevel(app: app, bundleID: "com.example.Foo", teamID: nil, name: nil), 3)
        XCTAssertEqual(Fingerprint.evidenceLevel(app: app, bundleID: "other", teamID: "TEAM123", name: nil), 2)
        XCTAssertEqual(Fingerprint.evidenceLevel(app: app, bundleID: nil, teamID: nil, name: "Foo Helper"), 1)
        XCTAssertEqual(Fingerprint.evidenceLevel(app: app, bundleID: nil, teamID: nil, name: "FooBar"), 0)
    }

    func testSeparatorBoundaryRejectsSubstring() {
        XCTAssertTrue(Fingerprint.isSeparatorBoundaryMatch(candidate: "Foo", target: "Foo"))
        XCTAssertTrue(Fingerprint.isSeparatorBoundaryMatch(candidate: "Foo Helper.plist", target: "Foo"))
        XCTAssertFalse(Fingerprint.isSeparatorBoundaryMatch(candidate: "Foo.app2", target: "Foo.app"))
        XCTAssertFalse(Fingerprint.isSeparatorBoundaryMatch(candidate: "FooBar.plist", target: "Foo"))
    }

    func testPlanAttributesBundleIDEvidence() throws {
        let plan = try Uninstall.plan(
            appPath: "/Applications/Foo.app",
            fingerprint: fingerprint(),
            homeFiles: ["/Users/test/Library/Preferences/com.example.Foo.plist", "/Users/test/Library/Caches/Unrelated.plist"]
        )
        XCTAssertEqual(plan.files, ["/Users/test/Library/Preferences/com.example.Foo.plist"])
        XCTAssertEqual(plan.evidence["/Users/test/Library/Preferences/com.example.Foo.plist"], 3)
    }

    func testPlanNeverAttributesFooApp2ToFooApp() {
        XCTAssertThrowsError(try Uninstall.plan(
            appPath: "/Applications/Foo.app",
            fingerprint: AppFingerprint(bundleID: nil, teamID: nil, name: "Foo.app"),
            homeFiles: ["/Users/test/Library/Caches/Foo.app2.cache"]
        ))
    }

    func testPlanZeroEvidenceThrows() {
        XCTAssertThrowsError(try Uninstall.plan(
            appPath: "/Applications/Foo.app",
            fingerprint: fingerprint(),
            homeFiles: ["/Users/test/Library/Caches/Other.plist"]
        )) { error in
            XCTAssertTrue((error as NSError).localizedDescription.contains("searched"))
        }
    }

    func testPlanRefusesSystemAndApple() {
        XCTAssertThrowsError(try Uninstall.plan(appPath: "/System/Library/Foo.app", fingerprint: fingerprint(), homeFiles: ["/Users/test/Library/Preferences/com.example.Foo.plist"]))
        XCTAssertThrowsError(try Uninstall.plan(appPath: "/Applications/Safari.app", fingerprint: AppFingerprint(bundleID: "com.apple.Safari", teamID: nil, name: "Safari"), homeFiles: ["/Users/test/Library/Preferences/com.apple.Safari.plist"]))
    }
}
