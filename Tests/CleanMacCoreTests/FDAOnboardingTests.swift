import Foundation
import XCTest
@testable import CleanMacCore

final class FDAOnboardingTests: XCTestCase {
    func testDeniedShowsUnscanned() {
        let banner = FDAAccess.degradedBanner(unscanned: ["/Users/x/Library/Mail"])
        XCTAssertTrue(banner.lowercased().contains("partial"))
        XCTAssertTrue(banner.contains("/Users/x/Library/Mail"))
    }

    func testEmptyStillPartial() {
        XCTAssertTrue(FDAAccess.degradedBanner(unscanned: []).lowercased().contains("partial"))
    }

    func testStatusNeverThrows() {
        let s = FDAAccess.status(home: FileManager.default.temporaryDirectory)
        XCTAssertTrue([FDAAccessStatus.granted, .denied, .unknown].contains(s))
    }
}
