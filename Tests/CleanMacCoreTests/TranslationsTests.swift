import XCTest
@testable import CleanMacCore

final class TranslationsTests: XCTestCase {
    func testPruneKeepsSafelist() {
        let plan = Translations.prunePlan(app: "Foo", lprojDirs: ["en.lproj", "fr.lproj"], keep: ["en.lproj"])
        XCTAssertEqual(plan, ["fr.lproj"])
    }
}
