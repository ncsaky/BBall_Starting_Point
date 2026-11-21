// Crops a photo to a head-and-shoulders headshot around the largest detected face (macOS Vision framework).
// Usage: swift scripts/crop_headshot.swift <input> <output.jpg> [width=260]
// Prints a JSON line: {"faces": n, "crop": [x, y, w, h]} or {"faces": 0} (output not written when no face).
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else { print("{\"error\":\"usage\"}"); exit(2) }
let width = args.count > 3 ? Int(args[3]) ?? 260 : 260
guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { print("{\"error\":\"read\"}"); exit(1) }

let request = VNDetectFaceRectanglesRequest()
try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
let faces = (request.results ?? []).sorted { $0.boundingBox.width * $0.boundingBox.height > $1.boundingBox.width * $1.boundingBox.height }
guard let face = faces.first else { print("{\"faces\":0}"); exit(0) }

let W = CGFloat(image.width), H = CGFloat(image.height)
// Vision boxes are normalised with the origin at the bottom left.
let fw = face.boundingBox.width * W, fh = face.boundingBox.height * H
let fx = face.boundingBox.minX * W, fy = (1 - face.boundingBox.maxY) * H
// Head-and-shoulders: 2.8 face widths wide, 3:4 portrait, the face in the upper part of the frame.
var cw = min(W, fw * 2.8)
var ch = min(H, cw * 4 / 3)
cw = min(cw, ch * 3 / 4)
var cx = fx + fw / 2 - cw / 2
var cy = fy - fh * 0.75
cx = max(0, min(W - cw, cx))
cy = max(0, min(H - ch, cy))
let rect = CGRect(x: cx.rounded(), y: cy.rounded(), width: cw.rounded(), height: ch.rounded())
guard let cropped = image.cropping(to: rect) else { print("{\"error\":\"crop\"}"); exit(1) }

let outW = min(width, cropped.width)
let outH = Int((CGFloat(outW) * CGFloat(cropped.height) / CGFloat(cropped.width)).rounded())
guard let context = CGContext(data: nil, width: outW, height: outH, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { exit(1) }
context.interpolationQuality = .high
context.draw(cropped, in: CGRect(x: 0, y: 0, width: outW, height: outH))
guard let scaled = context.makeImage(),
      let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { exit(1) }
CGImageDestinationAddImage(dest, scaled, [kCGImageDestinationLossyCompressionQuality: 0.72] as CFDictionary)
CGImageDestinationFinalize(dest)
print("{\"faces\":\(faces.count),\"crop\":[\(Int(rect.minX)),\(Int(rect.minY)),\(Int(rect.width)),\(Int(rect.height))]}")
