"""Decides where every file in a folder should go and what it should be called.

Pure logic: no file moves happen here. `build_plan` takes the list of files plus
the on-device analysis from the Swift helper and returns one plan item per file.
"""

import hashlib
import os
import re
import unicodedata
from datetime import datetime

# (folder, group) in display order. Folder paths are relative to the sorted folder.
CATEGORIES = [
    ("Photos/People & selfies", "Photos"),
    ("Photos/Food & drinks", "Photos"),
    ("Photos/Nature & outdoors", "Photos"),
    ("Photos/Travel & city", "Photos"),
    ("Photos/Interiors & spaces", "Photos"),
    ("Photos/Pets & animals", "Photos"),
    ("Photos/Events & celebrations", "Photos"),
    ("Photos/Sport & hobbies", "Photos"),
    ("Photos/Paper & receipts", "Photos"),
    ("Photos/Other photos", "Photos"),
    ("Screenshots", "Photos"),
    ("Graphics & logos", "Photos"),
    ("Videos/Talking head", "Videos & audio"),
    ("Videos/B-roll", "Videos & audio"),
    ("Videos/Screen recordings", "Videos & audio"),
    ("Audio/Music", "Videos & audio"),
    ("Audio/Sounds", "Videos & audio"),
    ("Audio/Voice notes", "Videos & audio"),
    ("Documents/Invoices & receipts", "Documents"),
    ("Documents/Bank statements", "Documents"),
    ("Documents/Contracts & legal", "Documents"),
    ("Documents/Tax & accounting", "Documents"),
    ("Documents/Travel & tickets", "Documents"),
    ("Documents/CVs", "Documents"),
    ("Documents/Scans", "Documents"),
    ("Documents/Other PDFs", "Documents"),
    ("Documents/Word & text", "Documents"),
    ("Documents/Presentations", "Documents"),
    ("Spreadsheets & data", "Documents"),
    ("eBooks", "Documents"),
    ("Emails, contacts & calendar", "Documents"),
    ("Archives", "Everything else"),
    ("Apps & installers", "Everything else"),
    ("Code & web", "Everything else"),
    ("Fonts", "Everything else"),
    ("Duplicates", "Everything else"),
    ("Empty files", "Everything else"),
    ("Other", "Everything else"),
]
CATEGORY_GROUP = dict(CATEGORIES)

IMAGE_EXTS = {"jpg", "jpeg", "png", "heic", "heif", "webp", "gif", "tif", "tiff", "bmp", "avif"}
VIDEO_EXTS = {"mov", "mp4", "m4v", "webm", "avi", "mkv", "3gp"}
AUDIO_EXTS = {"mp3", "m4a", "wav", "aac", "flac", "aiff", "aif", "opus", "ogg", "caf"}
ANALYZED_EXTS = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS | {"pdf"}

EXT_CATEGORY = {}
for _folder, _exts in {
    "Graphics & logos": "svg ico icns eps ai psd sketch fig xd",
    "Documents/Word & text": "doc docx odt rtf pages txt md",
    "Documents/Presentations": "ppt pptx key odp",
    "Spreadsheets & data": "csv xls xlsx ods numbers json xml sql tsv yaml yml",
    "eBooks": "epub mobi azw azw3",
    "Emails, contacts & calendar": "eml msg vcf ics mbox",
    "Archives": "zip gz tgz tar rar 7z bz2 xz",
    "Apps & installers": "dmg pkg app exe msi apk ipa",
    "Code & web": "php html htm css js ts jsx tsx py sh rb go java c cpp h swift sql patch diff",
    "Fonts": "ttf otf woff woff2",
}.items():
    for _e in _exts.split():
        EXT_CATEGORY.setdefault(_e, _folder)

PARTIAL_EXTS = {"crdownload", "download", "part", "partial", "tmp"}

# Vision label groups used to place photos. Weights favour specific labels.
PHOTO_LABELS = {
    "Photos/Food & drinks": "food drink dessert coffee baked_goods meal pizza pasta salad sushi cake bread fruit vegetable "
    "cocktail wine beer juice tea_drink restaurant tableware plate cup seafood meat burger sandwich ice_cream breakfast "
    "candy chocolate pastry cookie cheese soup snack sweets bowl utensil",
    "Photos/Nature & outdoors": "plant tree foliage flower blossom forest mountain hill beach ocean sea lake river waterfall "
    "sunset_sunrise sky blue_sky cloudy grass garden snow desert canyon cliff shore water_body vegetation land park",
    "Photos/Travel & city": "cityscape building skyscraper street monument bridge castle tower harbour airport airplane "
    "ruins church dome statue sidewalk storefront train_station road alley arch belltower palm_tree pool",
    "Photos/Interiors & spaces": "interior_room living_room bedroom kitchen kitchen_room dining_room bathroom bathroom_room "
    "furniture sofa chair table desk lamp interior_shop curtain bookshelf fireplace window",
    "Photos/Pets & animals": "animal canine feline dog cat puppy kitten bird horse mammal fish reptile insect",
    "Photos/Events & celebrations": "wedding celebration ceremony bride groom bridesmaid wedding_dress wedding_cake concert "
    "crowd fireworks birthday_cake party performance balloon christmas_tree graduation stage",
    "Photos/Sport & hobbies": "sport sports_equipment ball soccer football basketball baseball tennis golf golf_ball bowling "
    "hockey billiards ping_pong volleyball rugby cycling bicycle skiing surfing swimming workout yoga gymnastics "
    "health_club dumbbell musical_instrument music guitar piano violin drum cello string_instrument turntable record "
    "games board_game chess play_card videogame gamepad toy puzzles",
    "Photos/Paper & receipts": "document receipt printed_page handwriting paper envelope ticket calendar map passport "
    "credit_card magazine newspaper book",
}
PHOTO_LABELS = {k: set(v.split()) for k, v in PHOTO_LABELS.items()}
PEOPLE_LABELS = {"people", "adult", "child", "baby", "teen", "crowd"}

# Labels too vague to use in a file name.
GENERIC_LABELS = {
    "outdoor", "structure", "land", "conveyance", "material", "machine", "people", "adult", "consumer_electronics",
    "mammal", "animal", "plant", "sky", "blue_sky", "cloudy", "vegetation", "art", "decoration", "container",
    "housewares", "textile", "wood_processed", "wood_natural", "light", "portal", "dial", "compass", "liquid",
    "daytime", "water", "screenshot", "document", "printed_page", "illustrations", "foliage", "grass", "food",
    "drink", "furniture", "interior_room", "clothing", "footwear", "headgear", "vehicle", "rocks", "teen",
    "tableware", "utensil", "plate", "cup", "bowl", "drinking_glass", "wood_processed", "child", "crowd", "sign",
    "recreation", "sport", "sports_equipment", "ballgames", "games", "music", "musical_instrument",
    "string_instrument", "celestial_body", "celestial_body_other", "arthropods", "ungulates",
}
# Fallback word for a photo when Vision saw nothing specific enough to name it by.
CATEGORY_WORD = {
    "Photos/Food & drinks": "Food", "Photos/Nature & outdoors": "Nature", "Photos/Travel & city": "City",
    "Photos/Interiors & spaces": "Interior", "Photos/Pets & animals": "Animal", "Photos/Events & celebrations": "Event",
    "Photos/Sport & hobbies": "Hobby",
    "Photos/Paper & receipts": "Document", "Photos/Other photos": "Photo", "Videos/B-roll": "B-roll",
    "Graphics & logos": "Graphic",
}

PDF_RULES = [
    ("Documents/Tax & accounting", [
        "bilant", "balanta", "declaratia", "d112", "d300", "d301", "d390", "d394", "recipisa", "anaf", "spv",
        "impozit", "tax return", "vat return", "self assessment", "hmrc", "dividend", "balance sheet",
        "profit and loss", "registrul", "contabil", "accountant", "accounting",
    ]),
    ("Documents/Bank statements", [
        "extras de cont", "extrasul de cont", "account statement", "statement of account", "bank statement",
        "sold initial", "sold final", "opening balance", "closing balance", "sold precedent", "rulaj",
    ]),
    ("Documents/Invoices & receipts", [
        "factura", "invoice", "receipt", "chitanta", "bon fiscal", "proforma", "total de plata", "amount due",
        "total due", "ordin de plata", "payment confirmation", "dovada plata", "aviz de plata", "plati",
        "tax invoice", "billing", "abonament",
    ]),
    ("Documents/Travel & tickets", [
        "boarding pass", "e-ticket", "eticket", "booking confirmation", "itinerary", "reservation",
        "rezervare", "bilet", "flight", "check-in", "zbor", "hotel",
    ]),
    ("Documents/CVs", ["curriculum vitae", "resume", "work experience", "experienta profesionala"]),
    ("Documents/Contracts & legal", [
        "contract", "anexa", "act aditional", "agreement", "termeni si conditii", "terms and conditions",
        "imputernicire", "procura", "declaratie", "cerere", "hotarare", "certificat", "notarial",
        "proces verbal", "decizie", "statut", "power of attorney", "non-disclosure", "nda", "adeverinta",
        "mandat", "notificare", "somatie",
    ]),
]

SCREENSHOT_NAME = re.compile(r"(screen ?shot|screenshot|screen recording|captur|snip)", re.I)
VOICE_NAME = re.compile(r"(whatsapp audio|ptt|voice|recording|inregistrare|memo)", re.I)
DUP_SUFFIX = re.compile(r"(\s\(\d+\)|\s\d+|-\d|_\d|\scopy)+$", re.I)
MEANINGLESS_PREFIX = re.compile(
    r"^(?:whatsapp image|whatsapp video|img|image|dsc|dscn|dcim|pxl|vid|video|mvimg|photo|picture|pic|snapchat|"
    r"signal|downloads?|untitled|unnamed|file|media|frame|clip|movie|portrait|mov|insta|ig|fb|received)(?=[\s_\-.]|\d|$)",
    re.I,
)


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s):
    return strip_accents(s or "").lower()


def file_key(path, st):
    return hashlib.sha1(f"{path}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:20]


def ext_of(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def label_dict(a):
    return {l: c for l, c in (a.get("labels") or [])}


def is_screenshot(name, a, ext):
    labels = label_dict(a)
    if a.get("screenCapture") or SCREENSHOT_NAME.search(name):
        return True
    if a.get("camera"):
        return False
    if labels.get("screenshot", 0) >= 0.5:
        return True
    # Phone screenshots: tall PNGs full of text, no camera metadata.
    w, h = a.get("w") or 0, a.get("h") or 0
    return ext == "png" and h > w * 1.7 and a.get("textChars", 0) > 60


def photo_category(a):
    labels = label_dict(a)
    scores = {}
    for cat, wanted in PHOTO_LABELS.items():
        scores[cat] = sum(c for l, c in labels.items() if l in wanted)
    people = sum(c for l, c in labels.items() if l in PEOPLE_LABELS) * 0.6
    if a.get("faces", 0):
        people += 0.5 + min(a.get("faceArea", 0) * 20, 1.5)
    scores["Photos/People & selfies"] = people
    if a.get("textChars", 0) > 200 and not a.get("faces"):
        scores["Photos/Paper & receipts"] += 1.0
    best = max(scores, key=scores.get)
    return best if scores[best] >= 0.5 else "Photos/Other photos"


def image_category(name, ext, a):
    labels = label_dict(a)
    if is_screenshot(name, a, ext):
        return "Screenshots", "looks like a screen capture"
    if not a.get("camera"):
        if a.get("alpha") or ext in {"gif"}:
            return "Graphics & logos", "transparent / web graphic"
        if max(labels.get("illustrations", 0), labels.get("diagram", 0), labels.get("chart", 0)) >= 0.4:
            return "Graphics & logos", "illustration or diagram"
        if ext == "png" and a.get("textChars", 0) > 120 and not a.get("faces"):
            return "Screenshots", "image full of on-screen text"
    cat = photo_category(a)
    top = [l for l, _ in (a.get("labels") or [])[:3]]
    return cat, ("sees " + ", ".join(top)) if top else "photo"


def video_category(name, a):
    labels = label_dict(a)
    if a.get("screenCapture") or SCREENSHOT_NAME.search(name):
        return "Videos/Screen recordings", "screen recording"
    if a.get("faces", 0) and a.get("faceArea", 0) >= 0.02:
        return "Videos/Talking head", "a face fills the frame"
    if (labels.get("screenshot", 0) >= 0.4 or labels.get("document", 0) >= 0.5) and a.get("textChars", 0) > 40:
        return "Videos/Screen recordings", "mostly on-screen text"
    return "Videos/B-roll", "footage without a talking face"


def audio_category(name, ext, a):
    if ext == "opus" or VOICE_NAME.search(name):
        return "Audio/Voice notes", "voice message"
    if 0 < a.get("duration", 0) < 45:
        return "Audio/Sounds", f"short clip ({a['duration']:.0f}s)"
    return "Audio/Music", "long track"


def pdf_category(name, a):
    text = norm(name + " " + (a.get("title") or "") + " " + (a.get("text") or ""))
    best, best_hits = None, 0
    for cat, words in PDF_RULES:
        hits = sum(1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", text))
        if hits > best_hits:
            best, best_hits = cat, hits
    if best:
        return best, "mentions " + next(w for w in dict(PDF_RULES)[best] if re.search(r"\b" + re.escape(w) + r"\b", text))
    if not (a.get("text") or "").strip():
        return "Documents/Scans", "scanned pages, no text"
    return "Documents/Other PDFs", "PDF"


def custom_category(name, a, rules):
    hay = norm(" ".join([
        name,
        " ".join(l.replace("_", " ") for l, c in (a.get("labels") or []) if c >= 0.3),
        a.get("ocr") or "",
        a.get("title") or "",
        a.get("text") or "",
    ]))
    for rule in rules:
        for kw in rule.get("keywords", []):
            kw = norm(kw).strip()
            if kw and re.search(r"\b" + re.escape(kw) + r"\b", hay):
                return rule["folder"], f'matches "{kw}"'
    return None


def categorize(name, ext, a, rules, is_dir=False):
    if rules:
        hit = custom_category(name, a, rules)
        if hit:
            return hit
    if is_dir:
        return "Apps & installers", "app bundle"
    if ext in IMAGE_EXTS:
        return image_category(name, ext, a)
    if ext in VIDEO_EXTS:
        return video_category(name, a)
    if ext in AUDIO_EXTS:
        return audio_category(name, ext, a)
    if ext == "pdf":
        return pdf_category(name, a)
    if ext in EXT_CATEGORY:
        return EXT_CATEGORY[ext], f".{ext} file"
    return "Other", "unknown type"


def is_meaningless(stem):
    """True for camera / messenger / hash style names like IMG_4821, 1050677 or a UUID."""
    s = re.sub(r"(\s\(\d+\)|[\s_\-]copy|\s[ap]m\b)", "", stem.strip(), flags=re.I).strip()
    s = MEANINGLESS_PREFIX.sub("", s)
    s = re.sub(r"(\bat\b|_[nob]$)", " ", s)
    tokens = [t for t in re.split(r"[\s_\-.:@]+", s) if t]
    return all(
        t.isdigit() or re.fullmatch(r"\d+x", t) or (len(t) >= 4 and re.fullmatch(r"[0-9a-f]+", t, re.I) and re.search(r"\d", t))
        for t in tokens
    )


NICE_LABELS = {"sunset_sunrise": "sunset", "water_body": "water", "track_rail": "rail tracks", "health_club": "gym",
               "interior_room": "room", "tea_drink": "tea", "optical_equipment": "glasses", "timepiece": "watch"}


def nice(label):
    return NICE_LABELS.get(label, label.replace("_", " "))


def file_date(a, st):
    taken = a.get("taken")
    if taken:
        try:
            return datetime.strptime(taken[:10], "%Y:%m:%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.fromtimestamp(getattr(st, "st_birthtime", st.st_mtime)).strftime("%Y-%m-%d")


def content_name(category, a, st):
    """A short human name for a media file based on what Vision saw, or None."""
    labels = [l for l, c in (a.get("labels") or []) if c >= 0.3 and l not in GENERIC_LABELS]
    date = file_date(a, st)
    if category == "Videos/Talking head":
        head = "Talking head"
    elif category == "Videos/Screen recordings":
        head = "Screen recording"
    elif category == "Screenshots":
        head = "Screenshot"
    elif category == "Photos/People & selfies":
        big = a.get("faces") == 1 and a.get("faceArea", 0) > 0.05
        head = ("Selfie" if big else "People") + (f", {nice(labels[0])}" if labels else "")
    elif labels:
        first = nice(labels[0])
        second = next((nice(l) for l in labels[1:] if first not in nice(l) and nice(l) not in first), None)
        head = first.capitalize() + (f" & {second}" if second else "")
    elif category in CATEGORY_WORD:
        head = CATEGORY_WORD[category]
    else:
        return None
    head = re.sub(r'[/:\\"<>|?*\n\t]', " ", head).strip()[:60]
    return f"{head} {date}"


def build_plan(entries, analysis, rules, options, duplicates):
    """entries: [{path, name, st, is_dir}] → list of plan items (JSON-ready)."""
    plan = []
    for i, e in enumerate(entries):
        name, st = e["name"], e["st"]
        ext = "app" if e["is_dir"] else ext_of(name)
        a = analysis.get(e["path"], {})
        if not e["is_dir"] and st.st_size == 0:
            category, reason = "Empty files", "0 bytes, probably a failed download"
        elif e["path"] in duplicates and options.get("duplicates", True):
            category, reason = "Duplicates", "same content as " + os.path.basename(duplicates[e["path"]])
        else:
            category, reason = categorize(name, ext, a, rules, e["is_dir"])
        stem = name[: -(len(ext) + 1)] if ext and name.lower().endswith("." + ext) else name
        new_name = name
        if options.get("rename", True) and not e["is_dir"] and category != "Duplicates" and is_meaningless(stem):
            base = content_name(category, a, st)
            if base:
                new_name = f"{base}.{name.rsplit('.', 1)[-1]}" if "." in name else base
        plan.append({
            "id": i,
            "path": e["path"],
            "name": name,
            "newName": new_name,
            "ext": ext,
            "size": st.st_size if not e["is_dir"] else 0,
            "kind": a.get("kind") or ("app" if e["is_dir"] else "other"),
            "category": category,
            "reason": reason,
            "thumb": a.get("thumb"),
            "include": True,
        })
    return plan


def find_duplicates(entries, progress=None):
    """Returns {duplicate_path: original_path} for files with identical bytes."""
    by_size = {}
    for e in entries:
        if not e["is_dir"] and e["st"].st_size > 0:
            by_size.setdefault(e["st"].st_size, []).append(e)
    groups = [g for g in by_size.values() if len(g) > 1]
    dupes = {}
    for n, group in enumerate(groups):
        if progress:
            progress(n, len(groups))
        by_hash = {}
        for e in group:
            h = hashlib.sha1()
            try:
                with open(e["path"], "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                continue
            by_hash.setdefault(h.hexdigest(), []).append(e)
        for same in by_hash.values():
            if len(same) < 2:
                continue
            # Keep the copy with the cleanest name ("file.pdf" over "file (1).pdf"), then the oldest.
            same.sort(key=lambda e: (bool(DUP_SUFFIX.search(e["name"].rsplit(".", 1)[0])), len(e["name"]), e["st"].st_mtime))
            for e in same[1:]:
                dupes[e["path"]] = same[0]["path"]
    return dupes
