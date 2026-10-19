"""
Saves readings the Pi could not deliver, and hands them back to be resent once
the website is reachable again.

Safe by design: every public method swallows its own errors (a full disk or a
damaged file must never stop the sender), and the storage is capped three ways:
  * age        - nothing older than max_days is kept (default 60)
  * file size  - never grows past max_bytes
  * disk space - if the SD card is nearly full, the oldest half is dropped first
"""
import json
import os
import shutil
import time

DEFAULT_MAX_DAYS = 60
DEFAULT_MAX_BYTES = 20 * 1024 * 1024        # about 80,000 readings; 60 days is about 17,000
DEFAULT_MIN_FREE_BYTES = 200 * 1024 * 1024  # keep this much of the SD card free


class ReadingQueue:
    def __init__(self, path, max_days=DEFAULT_MAX_DAYS, max_bytes=DEFAULT_MAX_BYTES,
                 min_free_bytes=DEFAULT_MIN_FREE_BYTES, clock=time.time, disk_usage=shutil.disk_usage,
                 log=None):
        self.path = path
        self.max_days = max_days
        self.max_bytes = max_bytes
        self.min_free_bytes = min_free_bytes
        self.clock = clock
        self.disk_usage = disk_usage
        self.log = log or (lambda message: None)

    # ---- reading and writing the file
    def _load(self):
        """All saved entries, oldest first. Damaged lines are skipped."""
        entries = []
        try:
            with open(self.path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        if isinstance(item, dict) and isinstance(item.get('payload'), dict):
                            entries.append(item)
                    except ValueError:
                        continue
        except OSError:
            pass
        return entries

    def _write_all(self, entries):
        """Replace the file in one step, so a power cut never leaves half a file."""
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            for item in entries:
                f.write(json.dumps(item, separators=(',', ':')) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    # ---- limits
    def _trim(self, entries):
        cutoff = self.clock() - self.max_days * 86400
        kept = [e for e in entries if e.get('queued_at', 0) >= cutoff]
        dropped = len(entries) - len(kept)
        size = sum(len(json.dumps(e, separators=(',', ':'))) + 1 for e in kept)
        while kept and size > self.max_bytes:
            size -= len(json.dumps(kept[0], separators=(',', ':'))) + 1
            kept.pop(0)
            dropped += 1
        try:
            folder = os.path.dirname(os.path.abspath(self.path))
            if kept and self.disk_usage(folder).free < self.min_free_bytes:
                half = len(kept) // 2          # always keep the newest reading
                dropped += half
                kept = kept[half:]
        except Exception:
            pass
        if dropped:
            self.log('[QUEUE] dropped %d oldest saved readings (age, size or disk limit)' % dropped)
        return kept

    # ---- public
    def add(self, payload):
        """Save one reading for later. Returns True if it was saved."""
        try:
            entries = self._load()
            entries.append({'queued_at': self.clock(), 'payload': payload})
            self._write_all(self._trim(entries))
            return True
        except Exception as e:
            self.log('[QUEUE] could not save reading: %s' % str(e))
            return False

    def count(self):
        try:
            return len(self._load())
        except Exception:
            return 0

    def flush(self, send, max_seconds=120, save_every=25):
        """Resend saved readings, oldest first, until one fails or time is up.
        send(payload) must return True when the website has taken it.
        Returns (sent, left_waiting). Progress is saved as it goes, so a power
        cut mid-way at worst resends a few (the website ignores duplicates)."""
        sent = 0
        try:
            entries = self._load()
            if not entries:
                return 0, 0
            started = self.clock()
            while entries and self.clock() - started < max_seconds:
                if not send(entries[0]['payload']):
                    break
                entries.pop(0)
                sent += 1
                if sent % save_every == 0:
                    self._write_all(entries)
            if sent:
                self._write_all(entries)
            return sent, len(entries)
        except Exception as e:
            self.log('[QUEUE] resend problem: %s' % str(e))
            return sent, self.count()
