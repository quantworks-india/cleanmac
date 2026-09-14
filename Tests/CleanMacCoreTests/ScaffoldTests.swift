import Testing

@testable import CleanMacCore

@Test("Engine version is set")
func engineVersionIsSet() {
    #expect(!CleanMacCore.version.isEmpty)
}
