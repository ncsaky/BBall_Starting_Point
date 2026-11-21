// Contact sheet: images in a grid, each with a short label underneath (used to review the stock face library).
// Usage: contact_sheet <output.jpg> <columns> <cell width> <cell height> <list file>
// The list file has one "path<TAB>label" per line. Transparent images are shown on light grey.
import AppKit
import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count == 6, let columns = Int(args[2]), let cellW = Int(args[3]), let cellH = Int(args[4]),
      let list = try? String(contentsOfFile: args[5], encoding: .utf8) else { print("usage"); exit(2) }
let rows = list.split(separator: "\n").map { $0.split(separator: "\t", maxSplits: 1).map(String.init) }
let labelH = 16, gap = 4
let rowCount = (rows.count + columns - 1) / columns
let width = columns * (cellW + gap) + gap, height = rowCount * (cellH + labelH + gap) + gap
guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                          space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { exit(1) }
ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 11), .foregroundColor: NSColor.black]
for (i, row) in rows.enumerated() {
  let col = i % columns, r = i / columns
  let x = gap + col * (cellW + gap)
  let yTop = height - (gap + r * (cellH + labelH + gap))
  let cell = CGRect(x: x, y: yTop - cellH, width: cellW, height: cellH)
  ctx.setFillColor(CGColor(red: 0.86, green: 0.87, blue: 0.88, alpha: 1))
  ctx.fill(cell)
  if let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: row[0]) as CFURL, nil),
     let img = CGImageSourceCreateThumbnailAtIndex(src, 0, [kCGImageSourceCreateThumbnailFromImageAlways: true,
       kCGImageSourceCreateThumbnailWithTransform: true, kCGImageSourceThumbnailMaxPixelSize: max(cellW, cellH) * 2] as CFDictionary) {
    let s = min(CGFloat(cellW) / CGFloat(img.width), CGFloat(cellH) / CGFloat(img.height))
    let w = CGFloat(img.width) * s, h = CGFloat(img.height) * s
    ctx.draw(img, in: CGRect(x: cell.midX - w / 2, y: cell.minY, width: w, height: h))
  }
  if row.count > 1 {
    NSAttributedString(string: row[1], attributes: attrs).draw(at: NSPoint(x: x + 2, y: yTop - cellH - labelH + 2))
  }
}
guard let image = ctx.makeImage(),
      let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { exit(1) }
CGImageDestinationAddImage(dest, image, [kCGImageDestinationLossyCompressionQuality: 0.8] as CFDictionary)
CGImageDestinationFinalize(dest)
print("ok \(rows.count)")
