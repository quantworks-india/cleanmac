import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
let outDir = args.count > 1 ? args[1] : "build/iconset"
try FileManager.default.createDirectory(
    atPath: outDir, withIntermediateDirectories: true)

let srgb = CGColorSpace(name: CGColorSpace.sRGB)!

func col(_ r: Double, _ g: Double, _ b: Double, _ a: Double = 1) -> CGColor {
    CGColor(srgbRed: r, green: g, blue: b, alpha: a)
}

func pt(_ x: Double, _ y: Double, _ n: CGFloat) -> CGPoint {
    CGPoint(x: x * n, y: (1 - y) * n)
}

func drawIcon(_ n: CGFloat, reduced: Bool) -> CGImage {
    let ctx = CGContext(
        data: nil, width: Int(n), height: Int(n),
        bitsPerComponent: 8, bytesPerRow: 0, space: srgb,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

    let inset = 0.0
    let side = n
    let radius = 232.0 / 1024 * n
    let frame = CGRect(x: inset, y: inset, width: side, height: side)
    let squircle = CGPath(
        roundedRect: frame, cornerWidth: radius, cornerHeight: radius,
        transform: nil)

    ctx.saveGState()
    ctx.addPath(squircle)
    ctx.clip()

    let gradient = CGGradient(
        colorsSpace: srgb,
        colors: [col(0.247, 0.663, 0.961) as CFTypeRef,
                 col(0.114, 0.306, 0.847)] as CFArray,
        locations: [0, 1])!
    ctx.drawRadialGradient(
        gradient, startCenter: pt(0.28, 0.15, n), startRadius: 0,
        endCenter: pt(0.62, 0.95, n), endRadius: 1.25 * n,
        options: [])

    let isHero = n >= 256
    let isFull = n >= 128

    if isHero {
        let strays: [(Double, Double, Double)] = [
            (0.216, 0.216, 0.0205), (0.808, 0.239, 0.017),
            (0.789, 0.781, 0.0195), (0.231, 0.797, 0.0166),
            (0.191, 0.475, 0.0146), (0.845, 0.506, 0.012),
        ]
        ctx.setFillColor(col(1, 1, 1, 0.22))
        for (x, y, r) in strays {
            ctx.fillEllipse(in: CGRect(
                x: pt(x, y, n).x - r * n, y: pt(x, y, n).y - r * n,
                width: 2 * r * n, height: 2 * r * n))
        }
        ctx.setFillColor(col(1, 1, 1, 0.10 + 0.06 * (n / 1024)))
        ctx.move(to: CGPoint(x: n, y: n))
        ctx.addLine(to: CGPoint(x: n, y: 0))
        ctx.addLine(to: CGPoint(x: 0, y: 0))
        ctx.closePath()
        ctx.fillPath()
        ctx.move(to: pt(0, 0.96, n))
        ctx.addLine(to: pt(0.96, 0, n))
        ctx.setStrokeColor(col(1, 1, 1, 0.45))
        ctx.setLineWidth(14.0 / 1024 * n)
        ctx.strokePath()
    } else if isFull {
        ctx.setFillColor(col(1, 1, 1, 0.08))
        ctx.move(to: CGPoint(x: n, y: n))
        ctx.addLine(to: CGPoint(x: n, y: 0))
        ctx.addLine(to: CGPoint(x: 0, y: 0))
        ctx.closePath()
        ctx.fillPath()
    }

    let angles: [Double] = isFull
        ? [40, 80, 120, 160, 200, 240, 280, 320]
        : [45, 105, 180, 255, 315]
    let ringRadius = (isFull ? 0.295 : 0.35) * n
    let dotRadius = (isHero ? 0.062 : (isFull ? 0.075 : 0.15)) * n
    ctx.setFillColor(col(1, 1, 1))
    for deg in angles {
        let a = CGFloat(deg) * .pi / 180
        let c = CGPoint(
            x: 0.5 * n + ringRadius * cos(a),
            y: 0.5 * n - ringRadius * sin(a))
        ctx.fillEllipse(in: CGRect(
            x: c.x - dotRadius, y: c.y - dotRadius,
            width: 2 * dotRadius, height: 2 * dotRadius))
    }

    let gloss = CGGradient(
        colorsSpace: srgb,
        colors: [col(1, 1, 1, 0.5) as CFTypeRef,
                 col(1, 1, 1, 0)] as CFArray,
        locations: [0, 1])!
    ctx.drawRadialGradient(
        gloss, startCenter: pt(0.28, 0.12, n), startRadius: 0,
        endCenter: pt(0.5, 0.6, n), endRadius: 0.95 * n,
        options: [.drawsAfterEndLocation])
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(squircle)
    ctx.setStrokeColor(col(1, 1, 1, 0.22))
    ctx.setLineWidth(6.0 / 1024 * n)
    ctx.strokePath()
    ctx.restoreGState()

    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, to path: String) throws {
    let url = URL(fileURLWithPath: path) as CFURL
    guard let dest = CGImageDestinationCreateWithURL(
        url, UTType.png.identifier as CFString, 1, nil)
    else { throw NSError(domain: "icon", code: 1) }
    CGImageDestinationAddImage(dest, image, nil)
    guard CGImageDestinationFinalize(dest) else {
        throw NSError(domain: "icon", code: 2)
    }
}

let spec: [(Int, String)] = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]
var last: CGImage?
for (size, name) in spec {
    let image = drawIcon(CGFloat(size), reduced: size < 128)
    last = image
    try writePNG(image, to: "\(outDir)/\(name)")
    print("\(name) \(size)x\(size)")
}
_ = last
