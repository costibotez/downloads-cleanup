// SorterVision: on-device analysis helper for Downloads Sorter.
//
// Reads one "<thumb-key>\t<absolute path>" pair per line on stdin and writes one JSON object per
// line on stdout describing what is in the file (Vision labels, faces, amount of
// text, screenshot / camera metadata, PDF text, media duration) plus a small
// JPEG thumbnail written into the thumbnail directory.
//
//   sorter-vision analyze <thumb-dir>
//   sorter-vision labels            # print every Vision classification label

import AVFoundation
import CoreServices
import Foundation
import ImageIO
import PDFKit
import UniformTypeIdentifiers
import Vision

let imageExts: Set<String> = ["jpg", "jpeg", "png", "heic", "heif", "webp", "gif", "tif", "tiff", "bmp", "avif"]
let videoExts: Set<String> = ["mov", "mp4", "m4v", "webm", "avi", "mkv", "3gp"]
let audioExts: Set<String> = ["mp3", "m4a", "wav", "aac", "flac", "aiff", "aif", "opus", "ogg", "caf"]

let analysisSize = 768
let thumbSize = 256

struct Vis {
    var labels: [[Any]] = []
    var faces = 0
    var faceArea = 0.0
    var textChars = 0
    var text = ""
}

func analyze(_ image: CGImage) -> Vis {
    let classify = VNClassifyImageRequest()
    let faces = VNDetectFaceRectanglesRequest()
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .fast
    text.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try? handler.perform([classify, faces, text])

    var v = Vis()
    let obs = (classify.results ?? []).filter { $0.confidence > 0.1 }.prefix(10)
    v.labels = obs.map { [$0.identifier, (Double($0.confidence) * 100).rounded() / 100] }
    let rects = faces.results ?? []
    v.faces = rects.count
    v.faceArea = rects.map { Double($0.boundingBox.width * $0.boundingBox.height) }.max() ?? 0
    let lines = (text.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    v.textChars = lines.reduce(0) { $0 + $1.count }
    v.text = String(lines.joined(separator: " ").prefix(300))
    return v
}

func writeJPEG(_ image: CGImage, to url: URL) -> Bool {
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { return false }
    CGImageDestinationAddImage(dest, image, [kCGImageDestinationLossyCompressionQuality: 0.7] as CFDictionary)
    return CGImageDestinationFinalize(dest)
}

func scaled(_ image: CGImage, maxSide: Int) -> CGImage {
    let w = image.width, h = image.height
    let s = min(1.0, Double(maxSide) / Double(max(w, h)))
    if s >= 1.0 { return image }
    let nw = max(1, Int(Double(w) * s)), nh = max(1, Int(Double(h) * s))
    guard let ctx = CGContext(data: nil, width: nw, height: nh, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return image }
    ctx.interpolationQuality = .medium
    ctx.draw(image, in: CGRect(x: 0, y: 0, width: nw, height: nh))
    return ctx.makeImage() ?? image
}

func isScreenCapture(_ url: URL) -> Bool {
    guard let item = MDItemCreateWithURL(nil, url as CFURL) else { return false }
    let v = MDItemCopyAttribute(item, "kMDItemIsScreenCapture" as CFString)
    return (v as? Bool) ?? ((v as? NSNumber)?.boolValue ?? false)
}

func thumbURL(_ dir: URL, _ key: String) -> URL {
    dir.appendingPathComponent(key + ".jpg")
}

func analyzeImage(_ url: URL, _ out: inout [String: Any], _ thumb: URL) {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return }
    if let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [String: Any] {
        out["w"] = props[kCGImagePropertyPixelWidth as String] as? Int ?? 0
        out["h"] = props[kCGImagePropertyPixelHeight as String] as? Int ?? 0
        out["alpha"] = props[kCGImagePropertyHasAlpha as String] as? Bool ?? false
        let tiff = props[kCGImagePropertyTIFFDictionary as String] as? [String: Any] ?? [:]
        let exif = props[kCGImagePropertyExifDictionary as String] as? [String: Any] ?? [:]
        out["camera"] = tiff[kCGImagePropertyTIFFMake as String] != nil || exif[kCGImagePropertyExifLensModel as String] != nil
        if let d = exif[kCGImagePropertyExifDateTimeOriginal as String] as? String { out["taken"] = d }
    }
    let opts: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: analysisSize,
    ]
    guard let img = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) else { return }
    apply(analyze(img), &out)
    if writeJPEG(scaled(img, maxSide: thumbSize), to: thumb) { out["thumb"] = thumb.lastPathComponent }
}

func apply(_ v: Vis, _ out: inout [String: Any]) {
    out["labels"] = v.labels
    out["faces"] = v.faces
    out["faceArea"] = (v.faceArea * 1000).rounded() / 1000
    out["textChars"] = v.textChars
    out["ocr"] = v.text
}

func analyzeVideo(_ url: URL, _ out: inout [String: Any], _ thumb: URL) {
    let asset = AVURLAsset(url: url)
    let secs = CMTimeGetSeconds(asset.duration)
    out["duration"] = secs.isFinite ? (secs * 10).rounded() / 10 : 0
    let gen = AVAssetImageGenerator(asset: asset)
    gen.appliesPreferredTrackTransform = true
    gen.maximumSize = CGSize(width: analysisSize, height: analysisSize)
    var merged = Vis()
    var labelScore: [String: Double] = [:]
    var frames = 0
    for frac in [0.2, 0.5, 0.8] {
        let t = CMTime(seconds: max(0.1, (secs.isFinite ? secs : 1) * frac), preferredTimescale: 600)
        guard let img = try? gen.copyCGImage(at: t, actualTime: nil) else { continue }
        if frames == 0 {
            out["w"] = img.width
            out["h"] = img.height
            if writeJPEG(scaled(img, maxSide: thumbSize), to: thumb) { out["thumb"] = thumb.lastPathComponent }
        }
        frames += 1
        let v = analyze(img)
        for l in v.labels { labelScore[l[0] as! String, default: 0] += l[1] as! Double }
        merged.faces = max(merged.faces, v.faces)
        merged.faceArea = max(merged.faceArea, v.faceArea)
        merged.textChars = max(merged.textChars, v.textChars)
        if merged.text.isEmpty { merged.text = v.text }
    }
    out["frames"] = frames
    let n = Double(max(frames, 1))
    merged.labels = labelScore.sorted { $0.value > $1.value }.prefix(10).map { [$0.key, ($0.value / n * 100).rounded() / 100] }
    apply(merged, &out)
}

func analyzeAudio(_ url: URL, _ out: inout [String: Any]) {
    let secs = CMTimeGetSeconds(AVURLAsset(url: url).duration)
    out["duration"] = secs.isFinite ? (secs * 10).rounded() / 10 : 0
}

func analyzePDF(_ url: URL, _ out: inout [String: Any], _ thumb: URL) {
    guard let doc = PDFDocument(url: url) else { return }
    out["pages"] = doc.pageCount
    var text = ""
    for i in 0..<min(doc.pageCount, 2) {
        text += (doc.page(at: i)?.string ?? "") + "\n"
    }
    out["text"] = String(text.replacingOccurrences(of: "[ \t]+", with: " ", options: .regularExpression).prefix(2500))
    if let title = doc.documentAttributes?[PDFDocumentAttribute.titleAttribute] as? String { out["title"] = title }
    if let page = doc.page(at: 0) {
        let img = page.thumbnail(of: CGSize(width: thumbSize, height: thumbSize), for: .mediaBox)
        var rect = CGRect(origin: .zero, size: img.size)
        if let cg = img.cgImage(forProposedRect: &rect, context: nil, hints: nil), writeJPEG(cg, to: thumb) {
            out["thumb"] = thumb.lastPathComponent
        }
    }
}

func analyzeFile(_ path: String, key: String, thumbDir: URL) -> [String: Any] {
    let url = URL(fileURLWithPath: path)
    let ext = url.pathExtension.lowercased()
    var out: [String: Any] = ["path": path]
    let thumb = thumbURL(thumbDir, key)
    out["screenCapture"] = isScreenCapture(url)
    if imageExts.contains(ext) {
        out["kind"] = "image"
        analyzeImage(url, &out, thumb)
    } else if videoExts.contains(ext) {
        out["kind"] = "video"
        analyzeVideo(url, &out, thumb)
    } else if audioExts.contains(ext) {
        out["kind"] = "audio"
        analyzeAudio(url, &out)
    } else if ext == "pdf" {
        out["kind"] = "pdf"
        analyzePDF(url, &out, thumb)
    } else {
        out["kind"] = "other"
    }
    return out
}

let args = CommandLine.arguments
if args.count >= 2 && args[1] == "labels" {
    let ids = (try? VNClassifyImageRequest().supportedIdentifiers()) ?? []
    print(ids.joined(separator: "\n"))
    exit(0)
}
guard args.count >= 3 && args[1] == "analyze" else {
    FileHandle.standardError.write("usage: sorter-vision analyze <thumb-dir> | labels\n".data(using: .utf8)!)
    exit(2)
}

let thumbDir = URL(fileURLWithPath: args[2])
try? FileManager.default.createDirectory(at: thumbDir, withIntermediateDirectories: true)
var jobs: [(key: String, path: String)] = []
while let line = readLine() {
    let parts = line.split(separator: "\t", maxSplits: 1).map(String.init)
    if parts.count == 2 { jobs.append((parts[0], parts[1])) }
}

let lock = NSLock()
let workers = max(2, ProcessInfo.processInfo.activeProcessorCount - 2)
let queue = OperationQueue()
queue.maxConcurrentOperationCount = workers
for job in jobs {
    queue.addOperation {
        let result = autoreleasepool { analyzeFile(job.path, key: job.key, thumbDir: thumbDir) }
        guard let data = try? JSONSerialization.data(withJSONObject: result),
              let s = String(data: data, encoding: .utf8) else { return }
        lock.lock()
        print(s)
        fflush(stdout)
        lock.unlock()
    }
}
queue.waitUntilAllOperationsAreFinished()
