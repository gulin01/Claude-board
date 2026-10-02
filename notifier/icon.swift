// Renders the Agent Board app icon PNGs into the iconset folder given as the first argument.
import Cocoa

let out = CommandLine.arguments[1]
for (name, px) in [("16x16", 16), ("16x16@2x", 32), ("32x32", 32), ("32x32@2x", 64), ("128x128", 128),
                   ("128x128@2x", 256), ("256x256", 256), ("256x256@2x", 512), ("512x512", 512), ("512x512@2x", 1024)] {
    let s = CGFloat(px)
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                               bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let inset = s * 0.1
    let rect = NSRect(x: inset, y: inset, width: s - 2 * inset, height: s - 2 * inset)
    NSColor(red: 0.12, green: 0.11, blue: 0.10, alpha: 1).setFill()
    NSBezierPath(roundedRect: rect, xRadius: rect.width * 0.22, yRadius: rect.width * 0.22).fill()
    // Three "agent" rows: two done, one live.
    let colors = [NSColor(red: 0.76, green: 0.34, blue: 0.18, alpha: 1),
                  NSColor(white: 0.55, alpha: 1), NSColor(red: 0.44, green: 0.83, blue: 0.63, alpha: 1)]
    for i in 0..<3 {
        let h = rect.height * 0.12, gap = rect.height * 0.08
        let y = rect.midY + (CGFloat(1 - i) * (h + gap)) - h / 2
        colors[i].setFill()
        NSBezierPath(ovalIn: NSRect(x: rect.minX + rect.width * 0.18, y: y, width: h, height: h)).fill()
        NSColor(white: 0.92, alpha: i == 2 ? 1 : 0.55).setFill()
        NSBezierPath(roundedRect: NSRect(x: rect.minX + rect.width * 0.18 + h * 1.6, y: y + h * 0.2,
                                         width: rect.width * (i == 1 ? 0.38 : 0.5), height: h * 0.6),
                     xRadius: h * 0.3, yRadius: h * 0.3).fill()
    }
    NSGraphicsContext.restoreGraphicsState()
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(out)/icon_\(name).png"))
}
