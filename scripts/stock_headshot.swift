// Turns a photo of one person into a game headshot in the same look as the NBA player headshots:
// the person cut out from the background (macOS Vision person segmentation), greyscale, framed head-and-shoulders
// like ESPN's 1040x760 player headshots, saved small (AVIF with transparency by default).
//
// Usage:
//   stock_headshot <input> <output> [width=260] [--measure]
// --measure prints the face box of <input> (top-left origin, fractions of the image) and writes nothing; it is how
// the framing below was matched to ESPN's player headshots.
//
// Prints one JSON line with what was found, so the caller can reject unsuitable photos:
//   faces, second_face_ratio (area of the 2nd largest face / largest), face_px (largest face width in the source),
//   yaw / roll (degrees), quality (Vision face capture quality, 0-1), outside (share of the output frame that falls
//   outside the source photo), body_bottom (share of the bottom row covered by the person), cover (share of the
//   output covered by the person), written (bool).
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

// ESPN framing, measured on ESPN's college and NBA player headshots with --measure: the face box is about 29% of the
// frame width, centred, with its top about 26% down the frame.
let FACE_WIDTH_SHARE: CGFloat = 0.29
let FACE_TOP_SHARE: CGFloat = 0.26
let FRAME_ASPECT: CGFloat = 760.0 / 1040.0

let args = CommandLine.arguments.filter { $0 != "--measure" }
let measure = CommandLine.arguments.contains("--measure")
guard args.count >= 2 else { print("{\"error\":\"usage\"}"); exit(2) }
let outWidth = args.count > 3 ? Int(args[3]) ?? 260 : 260
let outHeight = Int((CGFloat(outWidth) * FRAME_ASPECT).rounded())

// Oriented (EXIF), at most 1600 px on the long side.
guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, nil),
      let loaded = CGImageSourceCreateThumbnailAtIndex(source, 0, [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: 1600,
      ] as CFDictionary) else { print("{\"error\":\"read\"}"); exit(1) }
let W = CGFloat(loaded.width), H = CGFloat(loaded.height)
// Photos that already have a transparent background (some roster headshots) go onto white first.
guard let flat = CGContext(data: nil, width: loaded.width, height: loaded.height, bitsPerComponent: 8, bytesPerRow: 0,
                           space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)
else { print("{\"error\":\"read\"}"); exit(1) }
flat.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
flat.fill(CGRect(x: 0, y: 0, width: W, height: H))
flat.draw(loaded, in: CGRect(x: 0, y: 0, width: W, height: H))
guard let image = flat.makeImage() else { print("{\"error\":\"read\"}"); exit(1) }

let faceRequest = VNDetectFaceRectanglesRequest()
let qualityRequest = VNDetectFaceCaptureQualityRequest()
let handler = VNImageRequestHandler(cgImage: image, options: [:])
try? handler.perform([faceRequest])
let faces = (faceRequest.results ?? []).sorted { $0.boundingBox.width * $0.boundingBox.height > $1.boundingBox.width * $1.boundingBox.height }
guard let face = faces.first else { print("{\"faces\":0,\"written\":false}"); exit(0) }
qualityRequest.inputFaceObservations = [face]
try? handler.perform([qualityRequest])
let quality = (qualityRequest.results?.first?.faceCaptureQuality).map { Double($0) } ?? -1
let area0 = face.boundingBox.width * face.boundingBox.height
let second = faces.count > 1 ? Double(faces[1].boundingBox.width * faces[1].boundingBox.height / area0) : 0
let yaw = (face.yaw?.doubleValue ?? 0) * 180 / .pi
let roll = (face.roll?.doubleValue ?? 0) * 180 / .pi

// Face box in top-left pixel coordinates.
let fw = face.boundingBox.width * W, fh = face.boundingBox.height * H
let fx = face.boundingBox.minX * W, fy = (1 - face.boundingBox.maxY) * H

if measure {
  print(String(format: "{\"faces\":%d,\"face_left\":%.4f,\"face_top\":%.4f,\"face_width\":%.4f,\"face_height\":%.4f,\"width\":%d,\"height\":%d}",
               faces.count, fx / W, fy / H, fw / W, fh / H, image.width, image.height))
  exit(0)
}

// Output frame in source pixels: face width = FACE_WIDTH_SHARE of the frame, face centred, face top at FACE_TOP_SHARE.
// A tightly cropped photo (shoulders running off the bottom or sides) is framed a little closer instead, so the
// shoulders still reach the bottom edge: the face may then fill up to MAX_FACE_SHARE of the width.
let MAX_FACE_SHARE: CGFloat = 0.40
var frameW = fw / FACE_WIDTH_SHARE
let bottomRoom = (H - fy) / (1 - FACE_TOP_SHARE)            // tallest frame whose bottom stays inside the photo
let sideRoom = 2 * min(fx + fw / 2, W - fx - fw / 2)        // widest frame centred on the face inside the photo
frameW = min(frameW, max(fw / MAX_FACE_SHARE, min(bottomRoom / FRAME_ASPECT, sideRoom)))
let frameH = frameW * FRAME_ASPECT
let frameX = fx + fw / 2 - frameW / 2
let frameY = fy - FACE_TOP_SHARE * frameH
let frame = CGRect(x: frameX, y: frameY, width: frameW, height: frameH)
let inside = frame.intersection(CGRect(x: 0, y: 0, width: W, height: H))
let outside = inside.isNull ? 1.0 : Double(1 - (inside.width * inside.height) / (frameW * frameH))

// Person mask (white = person), scaled to the photo.
let segment = VNGeneratePersonSegmentationRequest()
segment.qualityLevel = .accurate
segment.outputPixelFormat = kCVPixelFormatType_OneComponent8
try? handler.perform([segment])
guard let maskBuffer = segment.results?.first?.pixelBuffer else { print("{\"error\":\"segment\"}"); exit(1) }
var mask = CIImage(cvPixelBuffer: maskBuffer)
mask = mask.transformed(by: CGAffineTransform(scaleX: W / mask.extent.width, y: H / mask.extent.height))

let photo = CIImage(cgImage: image)
let grey = photo.applyingFilter("CIColorControls", parameters: [kCIInputSaturationKey: 0.0, kCIInputContrastKey: 1.06])
let cut = grey.applyingFilter("CIBlendWithMask", parameters: [
  kCIInputBackgroundImageKey: CIImage(color: .clear).cropped(to: photo.extent),
  kCIInputMaskImageKey: mask,
])
// CoreImage has a bottom-left origin: move the frame to the origin and scale it to the output size.
let scale = CGFloat(outWidth) / frameW
let ciFrameY = H - frameY - frameH
let placed = cut.transformed(by: CGAffineTransform(translationX: -frameX, y: -ciFrameY).concatenating(CGAffineTransform(scaleX: scale, y: scale)))
let outRect = CGRect(x: 0, y: 0, width: outWidth, height: outHeight)
let context = CIContext(options: [.workingColorSpace: CGColorSpace(name: CGColorSpace.sRGB)!])
guard let rendered = context.createCGImage(placed.cropped(to: outRect), from: outRect, format: .RGBA8,
                                           colorSpace: CGColorSpace(name: CGColorSpace.sRGB)) else { print("{\"error\":\"render\"}"); exit(1) }

// Coverage of the cut-out person in the frame, and along its bottom row (shoulders should reach the bottom edge).
let data = CFDataGetBytePtr(rendered.dataProvider!.data)!
let bpr = rendered.bytesPerRow
var covered = 0, bottom = 0
for y in 0..<outHeight {
  for x in 0..<outWidth where data[y * bpr + x * 4 + 3] > 127 {
    covered += 1
    if y == outHeight - 1 { bottom += 1 }
  }
}
let cover = Double(covered) / Double(outWidth * outHeight)
let bodyBottom = Double(bottom) / Double(outWidth)

let ext = (args[2] as NSString).pathExtension.lowercased()
let type = ext == "png" ? UTType.png : ext == "heic" ? UTType.heic : UTType(filenameExtension: "avif") ?? UTType.png
guard let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL, type.identifier as CFString, 1, nil) else {
  print("{\"error\":\"write\"}"); exit(1)
}
CGImageDestinationAddImage(dest, rendered, [kCGImageDestinationLossyCompressionQuality: 0.62] as CFDictionary)
let written = CGImageDestinationFinalize(dest)
print(String(format: "{\"faces\":%d,\"second_face_ratio\":%.3f,\"face_px\":%.0f,\"yaw\":%.1f,\"roll\":%.1f,\"quality\":%.3f,\"outside\":%.3f,\"body_bottom\":%.3f,\"cover\":%.3f,\"written\":%@}",
             faces.count, second, fw, yaw, roll, quality, outside, bodyBottom, cover, written ? "true" : "false"))
