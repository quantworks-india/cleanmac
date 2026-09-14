import XCTest
@testable import CleanMacCore

final class StartupTests: XCTestCase {
    func testDisableIsReversible() {
        let item = StartupItem(label: "com.example.Foo.helper", state: .enabled)
        let disabled = Startup.disable(item)
        XCTAssertEqual(disabled.label, "com.example.Foo.helper")
        XCTAssertEqual(disabled.state, .disabled)
        XCTAssertEqual(item.state, .enabled)
    }

    func testApprovalDeniedLinksLoginItems() {
        let text = Startup.approvalDeniedExplanation()
        XCTAssertTrue(text.contains("x-apple.systempreferences:com.apple.LoginItems-Settings.extension"))
        XCTAssertTrue(text.contains("Login Items"))
    }
}
