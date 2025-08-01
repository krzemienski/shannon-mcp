// swift-tools-version: 6.0
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "ShannonMCPTesterFeature",
    platforms: [
        .iOS(.v18),
        .macOS(.v13)
    ],
    products: [
        // Products define the executables and libraries a package produces, making them visible to other packages.
        .library(
            name: "ShannonMCPTesterFeature",
            targets: ["ShannonMCPTesterFeature"]
        ),
    ],
    dependencies: [
        // Add SwiftMCP for MCP protocol implementation
        .package(url: "https://github.com/Cocoanetics/SwiftMCP.git", branch: "main"),
    ],
    targets: [
        // Targets are the basic building blocks of a package, defining a module or a test suite.
        // Targets can depend on other targets in this package and products from dependencies.
        .target(
            name: "ShannonMCPTesterFeature",
            dependencies: [
                .product(name: "SwiftMCP", package: "SwiftMCP"),
            ],
            exclude: [
                "Infrastructure/Network/SSEClient.swift.bak",
                "Infrastructure/Network/WebSocketClient.swift.bak"
            ]
        ),
        .testTarget(
            name: "ShannonMCPTesterFeatureTests",
            dependencies: [
                "ShannonMCPTesterFeature"
            ]
        ),
    ]
)