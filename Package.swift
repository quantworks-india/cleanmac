// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CleanMac",
    platforms: [.macOS(.v15)],
    products: [
        .library(name: "CleanMacCore", targets: ["CleanMacCore"]),
        .executable(name: "CleanMac", targets: ["CleanMac"]),
    ],
    targets: [
        .target(name: "CleanMacCore"),
        .executableTarget(name: "CleanMac", dependencies: ["CleanMacCore"]),
        .testTarget(name: "CleanMacCoreTests", dependencies: ["CleanMacCore"]),
    ]
)
