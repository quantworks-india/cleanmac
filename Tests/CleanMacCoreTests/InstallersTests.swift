import XCTest
@testable import CleanMacCore

final class InstallersTests: XCTestCase {
    func testOnlyDmgPkgXip() {
        XCTAssertTrue(Installers.isInstaller("/Users/x/Downloads/foo.dmg"))
        XCTAssertTrue(Installers.isInstaller("/Users/x/Downloads/foo.pkg"))
        XCTAssertTrue(Installers.isInstaller("/Users/x/Downloads/foo.xip"))
        XCTAssertFalse(Installers.isInstaller("/Users/x/Downloads/foo.zip"))
    }
}
