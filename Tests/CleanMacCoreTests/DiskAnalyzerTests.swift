import Foundation
import XCTest
@testable import CleanMacCore

final class DiskAnalyzerTests: XCTestCase {
    func testFixtureTotalsSaneAndNeverAboveNaive() throws {
        let dir = try makeTree()
        let result = try DiskAnalyzer.scan(at: dir)
        XCTAssertGreaterThan(result.totalPhysicalBytes, 0)
        let naive = try naiveSum(at: dir)
        XCTAssertLessThanOrEqual(result.totalPhysicalBytes, naive)
        XCTAssertFalse(result.topPaths.isEmpty)
    }

    func testSymlinkLoopTerminates() throws {
        let dir = try makeTree()
        let link = dir.appendingPathComponent("loop")
        try? FileManager.default.createSymbolicLink(at: link, withDestinationURL: dir)
        let result = try DiskAnalyzer.scan(at: dir)
        XCTAssertGreaterThan(result.totalPhysicalBytes, 0)
    }

    private func makeTree() throws -> URL {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let a = dir.appendingPathComponent("a.bin")
        try Data(repeating: 0x41, count: 1024 * 64).write(to: a)
        try FileManager.default.linkItem(at: a, to: dir.appendingPathComponent("a-hardlink.bin"))
        return dir
    }

    private func naiveSum(at url: URL) throws -> UInt64 {
        var sum: UInt64 = 0
        let e = FileManager.default.enumerator(at: url, includingPropertiesForKeys: [.fileSizeKey], options: [])!
        for case let u as URL in e {
            let v = try u.resourceValues(forKeys: [.fileSizeKey])
            sum += UInt64(max(0, v.fileSize ?? 0))
        }
        return sum
    }
}
