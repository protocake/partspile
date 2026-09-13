// Transparent part cut-out via Apple's on-device subject lifting (Vision framework).
// Usage: cutout <in-photo> <out.png> [x y w h]   (optional normalized crop region,
// top-left origin, applied before segmentation so the subject is unambiguous)
// Exit codes: 0 ok · 2 no subject found · 64 usage · 66 unreadable input
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count == 3 || args.count == 7 else {
    FileHandle.standardError.write("usage: cutout <in> <out.png> [x y w h]\n".data(using: .utf8)!)
    exit(64)
}
let inURL = URL(fileURLWithPath: args[1])
let outURL = URL(fileURLWithPath: args[2])

// Load with EXIF orientation applied so coordinates match what browsers/sips see.
guard var ci = CIImage(contentsOf: inURL, options: [.applyOrientationProperty: true]) else {
    exit(66)
}
ci = ci.transformed(by: CGAffineTransform(translationX: -ci.extent.origin.x,
                                          y: -ci.extent.origin.y))
let ctx = CIContext()

if args.count == 7 {
    guard let x = Double(args[3]), let y = Double(args[4]),
          let w = Double(args[5]), let h = Double(args[6]) else { exit(64) }
    let W = ci.extent.width, H = ci.extent.height
    // normalized top-left rect -> CoreImage bottom-left rect
    let rect = CGRect(x: x * W, y: H - (y + h) * H, width: w * W, height: h * H)
        .intersection(ci.extent)
    if rect.width > 4, rect.height > 4 {
        ci = ci.cropped(to: rect)
        ci = ci.transformed(by: CGAffineTransform(translationX: -rect.origin.x,
                                                  y: -rect.origin.y))
    }
}

guard let cg = ctx.createCGImage(ci, from: ci.extent) else { exit(66) }

let request = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(cgImage: cg)
do { try handler.perform([request]) } catch { exit(2) }
guard let result = request.results?.first, !result.allInstances.isEmpty else { exit(2) }

do {
    let buffer = try result.generateMaskedImage(
        ofInstances: result.allInstances, from: handler,
        croppedToInstancesExtent: true)
    let out = CIImage(cvPixelBuffer: buffer)
    try ctx.writePNGRepresentation(
        of: out, to: outURL, format: .RGBA8,
        colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!)
    exit(0)
} catch {
    exit(2)
}
