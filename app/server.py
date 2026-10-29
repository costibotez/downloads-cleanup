"""Downloads Sorter: a small local web app that files a messy folder by content.

Run:  python3 app/server.py [--port 8765] [--no-open]
Everything stays on this Mac: analysis is done by the bundled Swift helper using
Apple's on-device Vision framework, and the server only listens on 127.0.0.1.
"""

import argparse
import json
import mimetypes
import os
import re
import secrets
import stat
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import sorter
from watcher import Watcher

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
HELPER_SRC = ROOT / "native" / "SorterVision.swift"
HELPER = ROOT / "build" / "sorter-vision"
DATA = Path(os.environ.get("DOWNLOADS_SORTER_DATA") or Path.home() / "Library" / "Application Support" / "Downloads Sorter")
THUMBS = DATA / "thumbs"
HISTORY = DATA / "history"
CACHE_FILE = DATA / "cache.json"
CONFIG_FILE = DATA / "config.json"

DEFAULT_CONFIG = {
    "folder": str(Path.home() / "Downloads"),
    "rename": True,
    "duplicates": True,
    "apps": True,
    "rules": [],
    "watch": False,
    "dateFolders": False,
}
TOKEN = secrets.token_urlsafe(24)
RECENT_SECONDS = 120  # leave files alone that are probably still downloading
IDLE_EXIT_SECONDS = 2 * 3600
last_activity = time.time()

operation_lock = threading.Lock()
lock = threading.Lock()
watcher = Watcher()
state = {"phase": "idle", "done": 0, "total": 0, "message": "", "plan": None, "folder": None, "error": None}


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


def config():
    return {**DEFAULT_CONFIG, **load_json(CONFIG_FILE, {})}


def ensure_helper():
    if HELPER.exists() and HELPER.stat().st_mtime >= HELPER_SRC.stat().st_mtime:
        return
    HELPER.parent.mkdir(parents=True, exist_ok=True)
    print("Building the on-device vision helper (one time)…", flush=True)
    subprocess.run(["swiftc", "-O", "-o", str(HELPER), str(HELPER_SRC)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def set_state(**kw):
    with lock:
        state.update(kw)


def list_entries(folder, include_apps, min_age=RECENT_SECONDS):
    entries = []
    now = time.time()
    with os.scandir(folder) as it:
        for d in it:
            if d.name.startswith("."):
                continue
            try:
                st = d.stat(follow_symlinks=False)
            except OSError:
                continue
            is_app = d.is_dir(follow_symlinks=False) and d.name.lower().endswith(".app")
            if d.is_dir(follow_symlinks=False) and not (is_app and include_apps):
                continue
            if not is_app and not d.is_file(follow_symlinks=False):
                continue
            if sorter.ext_of(d.name) in sorter.PARTIAL_EXTS or now - st.st_mtime < min_age:
                continue
            entries.append({"path": d.path, "name": d.name, "st": st, "is_dir": is_app})
    entries.sort(key=lambda e: e["name"].lower())
    return entries


def analyze(entries):
    cache = load_json(CACHE_FILE, {})
    keyed = {e["path"]: sorter.file_key(e["path"], e["st"]) for e in entries}
    todo = [e for e in entries
            if not e["is_dir"] and sorter.ext_of(e["name"]) in sorter.ANALYZED_EXTS
            and keyed[e["path"]] not in cache and "\n" not in e["path"] and "\t" not in e["path"]]
    total = len(todo)
    set_state(phase="analyzing", done=0, total=total, message=f"Looking inside {total} photos, videos and PDFs")
    if todo:
        ensure_helper()
        proc = subprocess.Popen([str(HELPER), "analyze", str(THUMBS)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        proc.stdin.write("".join(f"{keyed[e['path']]}\t{e['path']}\n" for e in todo))
        proc.stdin.close()
        done = 0
        for line in proc.stdout:
            try:
                a = json.loads(line)
            except ValueError:
                continue
            a["faceArea"] = round(a.get("faceArea", 0), 3)
            a["labels"] = [[l, round(c, 2)] for l, c in a.get("labels", [])]
            cache[keyed[a["path"]]] = a
            done += 1
            if done % 10 == 0 or done == total:
                set_state(done=done)
            if done % 200 == 0:
                save_json(CACHE_FILE, cache)
        proc.wait()
        save_json(CACHE_FILE, cache)
    return {e["path"]: cache.get(keyed[e["path"]], {}) for e in entries}


def scan(folder, entries=None):
    try:
        cfg = config()
        set_state(phase="listing", done=0, total=0, message="Listing files", plan=None, folder=folder, error=None)
        entries = list_entries(folder, cfg["apps"]) if entries is None else entries
        analysis = analyze(entries)
        dupes = {}
        if cfg["duplicates"]:
            set_state(phase="duplicates", message="Checking for duplicates")
            dupes = sorter.find_duplicates(entries, lambda n, t: set_state(done=n, total=t))
        plan = sorter.build_plan(entries, analysis, cfg["rules"], cfg, dupes)
        for item, entry in zip(plan, entries):
            item["snapshot"] = file_snapshot(entry["st"])
            item["trashable"] = (not entry["is_dir"] and
                                 (entry["st"].st_size == 0 or entry["path"] in dupes))
        set_state(phase="ready", plan=plan, message=f"{len(plan)} files ready to sort")
    except Exception as exc:  # surfaced in the UI
        set_state(phase="error", error=str(exc), message="Scan failed")


def valid_relative(value):
    return (isinstance(value, str) and bool(value) and "\x00" not in value
            and all(part not in ("", ".", "..") for part in value.split("/")))


def watch_tick():
    with operation_lock:
        cfg = config()
        if not cfg["watch"]:
            watcher.folder = None
            watcher.message = "Watch mode is off"
            return
        if state["phase"] not in ("idle", "done"):
            watcher.message = "Watch paused during preview or scan"
            return
        entries = list_entries(cfg["folder"], cfg["apps"], min_age=0)
        if watcher.folder != cfg["folder"]:
            watcher.reset(cfg["folder"], entries)
            return
        candidates = watcher.candidates(entries)
        if not candidates:
            watcher.message = "Watching for new files (waits 2 minutes for files to settle)"
            return
        scan(cfg["folder"], candidates)
        if state["phase"] != "ready":
            raise RuntimeError(state["error"] or "Automatic scan failed")
        result = apply_moves(cfg["folder"], [{"id": p["id"]} for p in state["plan"]], automatic=True)
        watcher.acknowledge(candidates)
        watcher.message = f"Automatically sorted {result['moved']} files"
        if result["errors"]:
            raise RuntimeError("; ".join(result["errors"][:3]))


def watch_loop():
    while True:
        try:
            watch_tick()
        except Exception as exc:
            with operation_lock:
                cfg = config()
                cfg["watch"] = False
                save_json(CONFIG_FILE, cfg)
                watcher.message = f"Watch stopped: {exc}"
                set_state(phase="error", error=str(exc))
        time.sleep(10)


def unique_dest(directory, name):
    stem, ext = (name[:-4], name[-4:]) if name.lower().endswith(".app") else os.path.splitext(name)
    dest, n = directory / name, 2
    while dest.exists():
        dest = directory / f"{stem} {n}{ext}"
        n += 1
    return dest


def apply_moves(folder, items, automatic=False):
    base = Path(folder)
    plan = {p["id"]: p for p in (state["plan"] or [])}
    moves, errors = [], []
    log = HISTORY / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    record = {"folder": folder, "time": datetime.now().isoformat(timespec="seconds"), "moves": moves, "automatic": automatic}
    for it in items:
        p = plan.get(it.get("id"))
        if not p or not it.get("include", True):
            continue
        category = it.get("category") or p["category"]
        name = it.get("newName") or p["newName"]
        if not valid_relative(category) or not valid_relative(name) or "/" in name:
            errors.append(f"{p['name']}: invalid destination")
            continue
        src = Path(p["path"])
        if src.parent != base or not src.exists():
            errors.append(f"{p['name']}: no longer there")
            continue
        date_folder = p.get("dateFolder", "") if category not in ("Duplicates", "Empty files") else ""
        dest_dir = base / category / date_folder
        try:
            if src.is_symlink() or (p.get("snapshot") and file_snapshot(src.lstat()) != p["snapshot"]):
                raise OSError("File changed since scan; scan again")
            if base.resolve() not in dest_dir.resolve().parents:
                raise OSError("Destination is outside the selected folder")
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = unique_dest(dest_dir, name)
            os.rename(src, dest)
            moves.append([str(src), str(dest)])
        except OSError as exc:
            errors.append(f"{p['name']}: {exc.strerror or exc}")
        if len(moves) % 200 == 0:
            save_json(log, record)
    if moves:
        save_json(log, record)
    set_state(plan=None, phase="done", message=f"Sorted {len(moves)} files")
    return {"moved": len(moves), "errors": errors[:50], "errorCount": len(errors)}


def file_snapshot(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def trash_file(item_id):
    """Trash only an unchanged, eligible file from the current preview."""
    if state["phase"] != "ready":
        raise ValueError("Scan first before moving a file to Trash.")
    item = next((p for p in state["plan"] or [] if p["id"] == item_id), None)
    if not item or not item.get("trashable"):
        raise ValueError("Only scanned duplicates and empty files can be moved to Trash.")
    src = Path(item["path"])
    base = Path(state["folder"])
    st = src.lstat()
    if (src.parent != base or src.parent.resolve() != base.resolve()
            or not stat.S_ISREG(st.st_mode) or file_snapshot(st) != item["snapshot"]):
        raise ValueError("This file has changed since the scan. Scan again before moving it to Trash.")
    # Pass the path as an argument, never interpolate filenames into AppleScript.
    script = '''on run argv
        tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)
    end run'''
    result = subprocess.run(["osascript", "-e", script, str(src)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Could not move the file to Trash.")
    set_state(plan=[p for p in state["plan"] if p["id"] != item_id])
    return {"trashed": 1}


def history():
    out = []
    for f in sorted(HISTORY.glob("*.json"), reverse=True)[:10]:
        h = load_json(f, {})
        out.append({"id": f.stem, "time": h.get("time"), "folder": h.get("folder"),
                    "automatic": h.get("automatic", False), "count": len(h.get("moves", [])), "undone": h.get("undone", False)})
    return out


def undo(log_id):
    f = HISTORY / f"{log_id}.json"
    if not re.fullmatch(r"[\d-]+", log_id) or not f.exists():
        return {"restored": 0, "errors": ["Nothing to undo"]}
    cfg = config()
    cfg["watch"] = False
    save_json(CONFIG_FILE, cfg)
    watcher.folder = None
    h = load_json(f, {})
    restored, errors, touched = 0, [], set()
    for src, dest in reversed(h.get("moves", [])):
        src, dest = Path(src), Path(dest)
        if not dest.exists():
            errors.append(f"{dest.name}: missing")
            continue
        target = src if not src.exists() else unique_dest(src.parent, src.name)
        try:
            os.rename(dest, target)
            restored += 1
            touched.add(dest.parent)
        except OSError as exc:
            errors.append(f"{dest.name}: {exc.strerror}")
    base = Path(h.get("folder", "/nonexistent"))
    parents = {ancestor for p in touched for ancestor in (p, *p.parents) if base in ancestor.parents}
    for d in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            if d != base and base in d.parents and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    h["undone"] = True
    save_json(f, h)
    set_state(phase="idle", plan=None, message=f"Put back {restored} files")
    return {"restored": restored, "errors": errors[:50]}


def pick_folder():
    script = 'POSIX path of (choose folder with prompt "Choose a folder to sort")'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip().rstrip("/") or None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        global last_activity
        last_activity = time.time()
        return secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            html = (STATIC / "index.html").read_text().replace("__TOKEN__", TOKEN)
            return self.send(200, html.encode(), "text/html; charset=utf-8")
        if path.startswith("/static/"):
            f = (STATIC / unquote(path[8:])).resolve()
            if STATIC in f.parents and f.is_file():
                return self.send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            return self.send(404, {"error": "not found"})
        if path.startswith("/thumb/"):
            name = path[7:]
            f = THUMBS / name
            if re.fullmatch(r"[0-9a-f]{20}\.jpg", name) and f.is_file():
                return self.send(200, f.read_bytes(), "image/jpeg")
            return self.send(404, {"error": "not found"})
        if path == "/api/state":
            if not self.authorized():
                return self.send(403, {"error": "forbidden"})
            with lock:
                snap = dict(state)
            snap["config"] = config()
            snap["watchMessage"] = watcher.message
            snap["categories"] = sorter.CATEGORIES
            snap["history"] = history()
            return self.send(200, snap)
        self.send(404, {"error": "not found"})

    def do_POST(self):
        with operation_lock:
            self.handle_post()

    def handle_post(self):
        if not self.authorized():
            return self.send(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad json"})
        path = urlparse(self.path).path
        if path == "/api/scan":
            if state["phase"] in ("listing", "analyzing", "duplicates"):
                return self.send(409, {"error": "already scanning"})
            folder = config()["folder"]
            if not os.path.isdir(folder):
                return self.send(400, {"error": f"Folder not found: {folder}"})
            set_state(phase="listing", plan=None)
            threading.Thread(target=scan, args=(folder,), daemon=True).start()
            return self.send(200, {"ok": True})
        if path == "/api/trash":
            try:
                return self.send(200, trash_file(body.get("id")))
            except (OSError, ValueError) as exc:
                return self.send(400, {"error": str(exc)})
        if path == "/api/apply":
            if state["phase"] != "ready" or not state["plan"]:
                return self.send(409, {"error": "scan first"})
            return self.send(200, apply_moves(state["folder"], body.get("items", [])))
        if path == "/api/undo":
            return self.send(200, undo(str(body.get("id", ""))))
        if path == "/api/config":
            cfg = config()
            for k in ("rename", "duplicates", "apps", "dateFolders", "watch"):
                if k in body:
                    cfg[k] = bool(body[k])
            if "rules" in body:
                rules = []
                for r in body["rules"]:
                    folder = re.sub(r"[/:\x00]", " ", str(r.get("folder", ""))).strip()[:60]
                    kws = [str(k).strip() for k in r.get("keywords", []) if str(k).strip()][:30]
                    if folder and kws and folder not in ("..", "."):
                        rules.append({"folder": folder, "keywords": kws})
                cfg["rules"] = rules
            if cfg["watch"] and (not config()["watch"] or watcher.folder != cfg["folder"]):
                try:
                    watcher.reset(cfg["folder"], list_entries(cfg["folder"], cfg["apps"], min_age=0))
                except OSError as exc:
                    return self.send(400, {"error": str(exc)})
            if not cfg["watch"]:
                watcher.folder = None
                watcher.message = "Watch mode is off"
            save_json(CONFIG_FILE, cfg)
            if cfg["watch"]:
                set_state(phase="idle", plan=None, message="Watching for new files")
            return self.send(200, cfg)
        if path == "/api/pick-folder":
            folder = pick_folder()
            if folder:
                cfg = config()
                cfg["folder"] = folder
                cfg["watch"] = False
                watcher.folder = None
                save_json(CONFIG_FILE, cfg)
                set_state(phase="idle", plan=None, message="")
            return self.send(200, {"folder": folder})
        if path == "/api/quit":
            self.send(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path == "/api/reveal":
            target = Path(str(body.get("path", "")))
            base = Path(config()["folder"])
            if target == base or base in target.parents:
                if target.is_dir() and not target.name.endswith(".app"):
                    subprocess.run(["open", str(target)])
                elif target.exists():
                    subprocess.run(["open", "-R", str(target)])
            return self.send(200, {"ok": True})
        self.send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    for d in (THUMBS, HISTORY):
        d.mkdir(parents=True, exist_ok=True)
    ensure_helper()
    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if not server:
        sys.exit("No free port found")
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Downloads Sorter is running at {url}  (Ctrl+C to quit)", flush=True)
    def exit_when_idle():
        while True:
            time.sleep(60)
            if not config()["watch"] and time.time() - last_activity > IDLE_EXIT_SECONDS and state["phase"] not in ("listing", "analyzing", "duplicates"):
                server.shutdown()
                return

    threading.Thread(target=exit_when_idle, daemon=True).start()
    threading.Thread(target=watch_loop, daemon=True).start()
    (DATA / "server.url").write_text(url)
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        (DATA / "server.url").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
