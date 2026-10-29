<p align="center">
  <img src="docs/banner.png" alt="Downloads Sorter — every file in its folder, named by what's in it." />
</p>

<h1 align="center">Downloads Sorter</h1>

<p align="center">
  <strong>Every file in its folder. Named by what's in it. Undo in one click.</strong>
</p>

<p align="center">
  A free, local Mac app for anyone whose Downloads folder has quietly become a landfill.<br />
  It looks inside every photo, video and PDF with Apple's on-device Vision, renames <code>IMG_4821.heic</code> by what's in the frame,<br />
  and files everything into tidy folders. You see the whole plan before anything moves, and Undo puts it all back.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/macOS-Apple%20silicon%20%26%20Intel-0e1726?logo=apple&logoColor=white" alt="macOS" />
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776ab?logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/Swift-Vision-f05138?logo=swift&logoColor=white" alt="Swift + Vision" />
  <img src="https://img.shields.io/badge/Version-1.0.0-2456e0" alt="Version 1.0.0" />
  <img src="https://img.shields.io/badge/Privacy-100%25%20on--device-0f766e" alt="100% on-device" />
  <img src="https://img.shields.io/badge/License-MIT-5b6779" alt="License MIT" />
</p>

<p align="center">
  <a href="#-quick-start-under-2-minutes">Quick start</a> ·
  <a href="#what-it-does">Features</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="#development">Development</a>
</p>

<p align="center">
  Author: <a href="https://www.nomad-developer.co.uk/">Costin Botez</a> (<a href="https://www.instagram.com/costinbotez/">@costinbotez</a>) ·
  <a href="https://www.nomad-developer.co.uk/">Portfolio</a> ·
  <a href="https://www.instagram.com/costinbotez/">Instagram</a> ·
  <a href="https://github.com/costibotez">GitHub</a>
</p>

---

## Why Downloads Sorter exists

Every Downloads folder ends up the same: 3,000 files called `IMG_4821.heic`, `10228315888.pdf`, `WhatsApp Image … at 6.51.15 PM (1).jpeg` and `invoice (3) (1).pdf`. Sorting by file type doesn't help, because a folder of 800 PDFs is still a mess. What you want is *invoices here, bank statements there, the wedding photos together*.

Downloads Sorter does that on your Mac, with no cloud and no API key:

- It **reads what's in the file**: what's in the picture, whether there's a face, how much text is on screen, the text inside a PDF.
- It **shows a plan first**: every folder with a count and thumbnails. Change anything before a single file moves.
- It **only moves**. Nothing is deleted, duplicates get their own folder, and every sort can be undone.

## What it does

### 🔍 Looks inside every file
- **Photos** are classified with Apple's on-device Vision (1,300+ scene labels, face detection, on-screen text) into People & selfies, Food & drinks, Nature & outdoors, Travel & city, Interiors & spaces, Pets & animals, Events & celebrations, Sport & hobbies and Paper & receipts
- **Screenshots** are recognised from macOS screenshot metadata, phone-screenshot shapes and text density. **Logos and graphics** are recognised by transparency and illustration labels
- **Videos** become *Talking head* (a face fills the frame), *B-roll* or *Screen recordings*. Three frames per clip are analysed
- **PDFs** are sorted by the text inside them, in English and Romanian: Invoices & receipts (*factură*, *invoice*), Bank statements (*extras de cont*, *opening balance*), Contracts & legal, Tax & accounting (*bilanț*, *ANAF*, *HMRC*), Travel & tickets, CVs and Scans
- **Audio** goes into Music, Sounds or Voice notes. **Everything else** is filed by type: Word & text, Spreadsheets & data, Presentations, eBooks, Emails & calendar, Archives, Apps & installers, Code & web, Fonts

### ✏️ Names files by what's in them
- Only meaningless names are renamed: camera rolls (`IMG_`, `DSC_`, `PXL_`), WhatsApp and Facebook exports, UUIDs, hashes and digit strings
- `IMG_5020.heic` → `Guitar 2026-08-08.heic`, `20230808_103547.jpg` → `Selfie 2023-08-08.jpg`. The date comes from the photo's EXIF data when it has one
- Files that already have a real name keep it. Name clashes get ` 2`, ` 3` instead of overwriting

### 🗂️ Your folders, in your own words
- Add a folder plus keywords in Settings, e.g. **Wedding**: `wedding, bride, nunta`
- A file goes there when its name, what Vision sees in it, the text on screen or the text inside the PDF matches a keyword
- Your folders take priority over the built-in ones

### 👀 Preview, then sort, then undo
- Every scan is a **preview**: folder cards with counts and thumbnails, plus a review drawer per folder to untick files or send them elsewhere
- **Sort** moves everything at once, with files flying from the pile into their folders
- **Undo** restores every file to its original place and name and removes the folders it created. History keeps your last 10 sorts

### 🧹 Catches the clutter
- **Duplicates**: byte-identical copies (`file (1).pdf`) are found by hash and moved to a *Duplicates* folder. The copy with the cleanest name stays in place
- **Empty files**: 0-byte failed downloads go to *Empty files*
- Skips partial downloads (`.crdownload`, `.part`, …), hidden files and anything modified in the last 2 minutes

### 🔒 Private by design
- **Nothing leaves your Mac.** Analysis runs in a small Swift helper using Apple's Vision, PDFKit and AVFoundation frameworks. There's no network call, account or API key
- The server listens on `127.0.0.1` only, and each launch requires a random token, so other web pages can't trigger a sort
- Cache, thumbnails, settings and undo history live in `~/Library/Application Support/Downloads Sorter/`

## ⚡ Quick start (under 2 minutes)

1. Clone the repo:
   ```bash
   git clone https://github.com/costibotez/downloads-cleanup.git && cd downloads-cleanup
   ```
2. Double-click **`Sort Downloads.command`**, or build a proper app with `./make-app.sh` and drag **Downloads Sorter.app** to your Dock.
3. When macOS asks whether it may access your Downloads folder, click **Allow**.
4. Press **Look at my files**, check the preview, then press **Sort**.

The first scan of ~3,000 files takes a minute or two. After that, results are cached and rescans are near-instant. Click the folder chip at the top to sort any other folder.

## Roadmap

- **Move to Trash** for the Duplicates and Empty files folders (recoverable via the macOS Trash)
- **Watch mode**: file new downloads automatically as they land
- **Smarter document names**: e.g. `10228315888.pdf` → `Invoice – Engie – 2023-05-22.pdf`
- Sort into subfolders by year and month as an option

## Screenshots

| Preview | Review a folder |
|---|---|
| ![Preview: folder cards with counts and thumbnails next to the pile of unsorted files](docs/screenshot-1.png) | ![Review drawer: each file with its new name, what Vision saw, and a folder picker](docs/screenshot-2.png) |

| Your folders & settings | Sorted |
|---|---|
| ![Settings: rename, duplicates, custom folders with keywords and undo history](docs/screenshot-3.png) | ![Sorted: 76 files sorted in seconds, with Undo one click away](docs/screenshot-4.png) |

<sub>Screenshots use a demo folder made from macOS stock pictures and generated documents (`docs/src/demo-files.sh`), so no personal files are shown.</sub>

## Development

- macOS with Python 3.9+ (standard library only) and the Xcode Command Line Tools for `swiftc`. No pip installs, no Node, no build step for the UI.
- The Swift helper is compiled on first launch, and again whenever `native/SorterVision.swift` changes. It reads `key<TAB>path` lines on stdin and writes one JSON object per file, using all but two CPU cores.
- Results are cached per file (path + size + modification time), so a rescan only analyses new files.

```
Sort Downloads.command   Double-click launcher (opens Terminal + browser)
make-app.sh              Builds "Downloads Sorter.app" with its icon
native/
  SorterVision.swift     On-device analysis: Vision labels, faces, OCR, PDF text, video frames, thumbnails
app/
  server.py              Local web server: scan → plan → move → undo, token-protected API
  sorter.py              Rules: which folder each file goes to and what it's called
  static/                Interface (vanilla HTML/CSS/JS)
docs/
  banner.png, icon.png, screenshot-*.png
  src/                   Banner HTML, demo-folder generator and render script for the images above
```

Useful knobs:

| Where | What | Purpose |
|---|---|---|
| `sorter.py` → `CATEGORIES` | list | Folder names, order and grouping |
| `sorter.py` → `PHOTO_LABELS` | dict | Which Vision labels send a photo to which folder |
| `sorter.py` → `PDF_RULES` | list | Keywords that classify a PDF (first-match by most hits) |
| `sorter.py` → `GENERIC_LABELS` | set | Labels too vague to use in a file name |
| `server.py` → `RECENT_SECONDS` | int | Files newer than this are treated as still downloading (default 120) |
| `DOWNLOADS_SORTER_DATA` | env var | Use a different data directory (handy for testing on a copy) |

QA shortcut: test on a fake folder without touching your real Downloads:

```bash
bash docs/src/demo-files.sh /tmp/demo/Downloads
mkdir -p /tmp/demo/data && echo '{"folder": "/tmp/demo/Downloads"}' > /tmp/demo/data/config.json
DOWNLOADS_SORTER_DATA=/tmp/demo/data python3 app/server.py
```

To refresh the README images, run `./make-app.sh`, then `bash docs/src/render.sh` for the banner and icon. Retake the screenshots from the app at 1280×760.

## License

MIT.

---

<p align="center">
  <img src="docs/icon.png" alt="Downloads Sorter icon" width="80" height="80">
</p>

<p align="center">
  Built and maintained by <a href="https://www.nomad-developer.co.uk/">Costin Botez</a> — <a href="https://www.nomad-developer.co.uk/">Nomad Developer</a> · <a href="https://www.instagram.com/costinbotez/">@costinbotez</a><br />
  WordPress development, care plans and performance work for agencies and small businesses.
</p>
