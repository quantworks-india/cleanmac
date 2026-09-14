import XCTest
@testable import CleanMacCore

final class SensitivityTests: XCTestCase {
    func testAllCasesExist() {
        XCTAssertEqual(Set(Sensitivity.allCases.map(\.rawValue)), ["strict", "enhanced", "deep"])
        XCTAssertEqual(Sensitivity.allCases.count, 3)
    }

    func testRequiredEvidence() {
        XCTAssertEqual(Sensitivity.strict.requiredEvidence, 3)
        XCTAssertEqual(Sensitivity.enhanced.requiredEvidence, 2)
        XCTAssertEqual(Sensitivity.deep.requiredEvidence, 1)
    }

    func testMaxFalsePositiveRate() {
        XCTAssertEqual(Sensitivity.strict.maxFalsePositiveRate, 0.001, accuracy: 1e-9)
        XCTAssertEqual(Sensitivity.enhanced.maxFalsePositiveRate, 0.01, accuracy: 1e-9)
        XCTAssertEqual(Sensitivity.deep.maxFalsePositiveRate, 0.05, accuracy: 1e-9)
    }
}
