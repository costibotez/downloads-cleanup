"""Track new arrivals without moving pre-existing or still-changing files."""
import time


class Watcher:
    def __init__(self):
        self.folder = None
        self.seen = set()
        self.baseline = set()
        self.pending = {}
        self.message = 'Watch mode is off'

    @staticmethod
    def signature(entry):
        st = entry['st']
        return (entry['path'], st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)

    def reset(self, folder, entries):
        self.folder = folder
        self.seen = {self.signature(e) for e in entries}
        self.baseline = {e["path"] for e in entries}
        self.pending = {}
        self.message = 'Watching for new files'

    def candidates(self, entries, settle=120, now=None):
        now = time.time() if now is None else now
        live = {self.signature(e) for e in entries}
        self.seen.intersection_update(live)
        self.baseline.intersection_update({e["path"] for e in entries})
        self.pending = {s: t for s, t in self.pending.items() if s in live}
        ready = []
        for e in entries:
            signature = self.signature(e)
            if signature in self.seen or e["path"] in self.baseline:
                continue
            first = self.pending.setdefault(signature, now)
            if now - first >= settle and now - e['st'].st_mtime >= settle:
                ready.append(e)
        return ready

    def acknowledge(self, entries):
        for e in entries:
            signature = self.signature(e)
            self.seen.add(signature)
            self.pending.pop(signature, None)
