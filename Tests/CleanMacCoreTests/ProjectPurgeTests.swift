import XCTest
@testable import CleanMacCore

final class ProjectPurgeTests: XCTestCase {
    func testNonReproducibleExcluded() {
        XCTAssertFalse(ProjectPurge.isPreselected(ProjectArtifact(path: "/proj/.venv", projectRoot: "/proj", reproducible: true)))
        XCTAssertFalse(ProjectPurge.isPreselected(ProjectArtifact(path: "/proj/env", projectRoot: "/proj", reproducible: false)))
    }

    func testProjectRootShown() {
        let a = ProjectArtifact(path: "/proj/node_modules", projectRoot: "/proj", reproducible: true)
        XCTAssertEqual(a.projectRoot, "/proj")
        XCTAssertTrue(ProjectPurge.isPreselected(a))
    }
}
