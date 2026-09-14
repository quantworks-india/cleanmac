import Foundation
import XCTest
@testable import CleanMacCore

final class DuplicatesTests: XCTestCase {
    func testIdenticalGroupedByteExact() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let a = dir.appendingPathComponent("a.bin"); let b = dir.appendingPathComponent("b.bin"); let c = dir.appendingPathComponent("c.bin")
        try Data(repeating: 7, count: 4096).write(to: a)
        try Data(repeating: 7, count: 4096).write(to: b)
        try Data(repeating: 8, count: 4096).write(to: c)
        let groups = try Duplicates.group(paths: [a.path, b.path, c.path])
        XCTAssertEqual(groups.count, 1)
        XCTAssertEqual(Set(groups[0]), Set([a.path, b.path]))
    }

    func testHardlinkReportedOnce() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let a = dir.appendingPathComponent("a.bin")
        try Data(repeating: 9, count: 1024).write(to: a)
        let link = dir.appendingPathComponent("link.bin")
        try FileManager.default.linkItem(at: a, to: link)
        let groups = try Duplicates.group(paths: [a.path, link.path])
        XCTAssertEqual(groups.count, 0)
    }
}
