"""Append-only, hash-chained audit trail (design 7.9).

Each line is a JSON AuditEvent whose hash covers its own fields and the previous hash, so editing or
removing a line breaks the chain from that point on. Truncating the tail cannot be seen from the file
alone: the dossier records `head()` as an external anchor.
"""
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .model import AuditEvent

GENESIS = "0" * 64
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(path.resolve()), threading.Lock())


def _digest(seq: int, ts: str, actor: str, event: str, data: dict, prev_hash: str) -> str:
    body = {"seq": seq, "ts": ts, "actor": actor, "event": event, "data": data, "prev_hash": prev_hash}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = _lock_for(self.path)

    def _lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def append(self, actor: str, event: str, data: dict) -> AuditEvent:
        data = json.loads(json.dumps(data, default=str))  # what is hashed is what is stored
        with self._lock:  # ponytail: re-reads the file per append, fine below ~10k events
            lines = self._lines()
            last = AuditEvent.model_validate_json(lines[-1]) if lines else None
            seq, prev = (last.seq + 1, last.hash) if last else (1, GENESIS)
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            ev = AuditEvent(seq=seq, ts=ts, actor=actor, event=event, data=data, prev_hash=prev,
                            hash=_digest(seq, ts, actor, event, data, prev))
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(ev.model_dump_json() + "\n")
            return ev

    def events(self) -> list[AuditEvent]:
        return [AuditEvent.model_validate_json(ln) for ln in self._lines()]

    def head(self) -> tuple[int, str]:
        """(event count, hash of the last event): the anchor that makes truncation visible."""
        evs = self.events()
        return (len(evs), evs[-1].hash) if evs else (0, GENESIS)

    def verify(self) -> tuple[bool, int | None]:
        prev, expected = GENESIS, 1
        for lineno, ln in enumerate(self._lines(), 1):
            try:
                ev = AuditEvent.model_validate_json(ln)
            except ValueError:
                return False, lineno
            if ev.seq != expected or ev.prev_hash != prev or ev.hash != _digest(ev.seq, ev.ts, ev.actor, ev.event, ev.data, prev):
                return False, ev.seq
            prev, expected = ev.hash, expected + 1
        return True, None
