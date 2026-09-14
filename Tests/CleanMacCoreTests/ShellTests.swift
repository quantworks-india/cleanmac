import XCTest
@testable import CleanMacCore

final class ShellTests: XCTestCase {
    func testRegisterAndRoute() {
        var shell = Shell()
        XCTAssertNil(shell.route(to: "scan"))
        shell.register(ShellScreen(id: "scan", title: "Scan"))
        shell.register(ShellScreen(id: "review", title: "Review"))
        XCTAssertEqual(shell.registeredScreens.count, 2)
        XCTAssertEqual(shell.route(to: "scan")?.title, "Scan")
        XCTAssertNil(shell.route(to: "missing"))
    }

    func testDuplicateRegistrationIgnored() {
        var shell = Shell()
        shell.register(ShellScreen(id: "scan", title: "Scan"))
        shell.register(ShellScreen(id: "scan", title: "Scan Again"))
        XCTAssertEqual(shell.registeredScreens.count, 1)
    }
}
