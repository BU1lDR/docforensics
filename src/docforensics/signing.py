"""Signed checkpoints of the audit trail (scope D, package S).

The hash chain in audit.py shows that an event was edited or removed in the middle of the trail. It cannot show that someone with write access
changed an event and worked every later hash out again, or cut the end off. A checkpoint can: it is the case, the number of events and the
hash of the last one, signed with an Ed25519 key, and kept as one line of checkpoints.jsonl in the case folder. A trail that was changed or cut
no longer matches a checkpoint signed before the change.

What it does not show: who held the key, or when. The private key is made once per data folder, in <data>/signing/, so that a case folder can
be copied without it, but it is a plain file with no password, and no outside clock stamps a checkpoint. Whoever can read that folder can
sign a trail of their own, and a reader can tell only if they know the public key from somewhere else (`verify-audit --pubkey`).
"""
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (Encoding, NoEncryption, PrivateFormat, PublicFormat, load_pem_private_key,
                                                          load_pem_public_key)

from .audit import AuditLog, _lock_for
from .store import CaseDir

ALGORITHM = "Ed25519"
_SIGNED = ("v", "case", "events", "head", "ts")  # the fields a signature covers
_key_lock = threading.Lock()


def _message(cp: dict) -> bytes:
    return json.dumps({k: cp[k] for k in _SIGNED}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _raw(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def key_id(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def public_key_bytes(pem: bytes) -> bytes:
    """The 32 bytes of an Ed25519 public key given as a PEM file. ValueError if it is anything else."""
    try:
        key = load_pem_public_key(pem)
    except (ValueError, UnsupportedAlgorithm) as e:
        raise ValueError(f"not a public key in PEM form ({e})") from e
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("not an Ed25519 public key")
    return _raw(key)


def _private_key(cd: CaseDir) -> Ed25519PrivateKey:
    """The key of this data folder, made the first time one is needed. A key file that is there is read, never replaced: if it cannot be
    read that is an error, because a new key would sign over the old one's checkpoints."""
    folder = cd.root.parent.parent / "signing"
    path = folder / "private.pem"
    with _key_lock:  # ponytail: two processes making the first key at the same moment can read each other's half-written file; the loser reports checkpoint_failed and the next checkpoint works
        if not path.exists():
            folder.mkdir(parents=True, exist_ok=True)
            key = Ed25519PrivateKey.generate()
            with path.open("xb") as f:
                f.write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
            path.chmod(0o600)
            (folder / "public.pem").write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
            return key
    key = load_pem_private_key(path.read_bytes(), None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private.pem is not an Ed25519 private key")
    return key


def _why(e: Exception) -> str:
    """What went wrong, without the file name an OS error carries: the trail is shared in the dossier, and a name holds a user's folders."""
    return f"{type(e).__name__}: {e.strerror if isinstance(e, OSError) and e.strerror else e}"[:200]


def _last(cd: CaseDir) -> dict | None:
    """The last line of checkpoints.jsonl as it reads, or None. Read loosely: a damaged file is reported by signing_view, not here."""
    try:
        lines = [ln for ln in cd.checkpoints_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        last = json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None
    return last if isinstance(last, dict) else None


def checkpoint(cd: CaseDir) -> dict | None:
    """Sign the trail as it stands and add the checkpoint to checkpoints.jsonl, unless the last checkpoint already says the same. Returns
    that checkpoint, or None if there is nothing to sign (an empty trail) or signing failed. A trail that fails its own chain is not signed:
    a checkpoint says the trail was whole. Failing never stops the work: it is written to the trail as `checkpoint_failed` (if the trail
    can take an event), and verify-audit then shows the events as not covered."""
    log = AuditLog(cd.audit_path)
    try:
        with _lock_for(cd.checkpoints_path):
            ok, at = log.verify()
            if not ok:
                raise ValueError(f"the trail does not verify (event {at}), so it was not signed")
            count, head = log.head()
            if count == 0:
                return None
            last = _last(cd)
            if last and last.get("events") == count and last.get("head") == head:
                return last
            key = _private_key(cd)
            cp = {"v": 1, "case": cd.id, "events": count, "head": head, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
            cp |= {"key": _raw(key.public_key()).hex(), "sig": key.sign(_message(cp)).hex()}
            with cd.checkpoints_path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(cp, sort_keys=True) + "\n")
            return cp
    except (OSError, ValueError) as e:
        try:
            log.append("system", "checkpoint_failed", {"error": _why(e)})
        except (OSError, ValueError):
            pass  # a trail that cannot take an event cannot say why either
        return None


def _checkpoints(cd: CaseDir) -> list[dict]:
    """Every line of checkpoints.jsonl, each checked for its shape. ValueError, worded as the problem, if one is not a checkpoint."""
    if not cd.checkpoints_path.exists():
        return []
    out = []
    for n, ln in enumerate(cd.checkpoints_path.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            cp = json.loads(ln)
            ok = (isinstance(cp, dict) and cp.get("v") == 1 and isinstance(cp["case"], str) and type(cp["events"]) is int and cp["events"] > 0
                  and isinstance(cp["head"], str) and isinstance(cp["ts"], str) and len(bytes.fromhex(cp["key"])) == 32
                  and len(bytes.fromhex(cp["sig"])) == 64)
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            raise ValueError(f"UNREADABLE: line {n} of checkpoints.jsonl is not a checkpoint.")
        out.append(cp)
    return out


def _signed(cp: dict) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(cp["key"])).verify(bytes.fromhex(cp["sig"]), _message(cp))
        return True
    except (InvalidSignature, ValueError):
        return False


def _problem(cd: CaseDir, cps: list[dict], pinned: bytes | None) -> str | None:
    try:
        events = AuditLog(cd.audit_path).events()
    except ValueError:  # a line that is not an event: the chain check says where
        events = []
    for i, cp in enumerate(cps, 1):
        if not _signed(cp):
            return f"BAD SIGNATURE: checkpoint {i} (events 1-{cp['events']}) was not signed by the key it names."
        if cp["case"] != cd.id:
            return f"WRONG CASE: checkpoint {i} was made for {cp['case']}, not for {cd.id}."
        if len(events) < cp["events"]:
            return (f"TRUNCATED: checkpoint {i} covers {cp['events']} events and the trail has {len(events)}: "
                    "the end of the trail was cut off, or these checkpoints belong to a longer trail.")
        if events[cp["events"] - 1].hash != cp["head"]:
            return (f"REWRITTEN: checkpoint {i} signed event {cp['events']} as ending in {cp['head'][:16]}, and the trail has "
                    f"{events[cp['events'] - 1].hash[:16]} there: events up to {cp['events']} were changed and chained again.")
    keys = {cp["key"] for cp in cps}
    if len(keys) > 1:
        return f"MORE THAN ONE KEY: the checkpoints are signed by {len(keys)} different keys, and one data folder has one key."
    if pinned is not None and not cps:
        return "NOT SIGNED: you gave a public key, and this case has no signed checkpoint to check it against."
    if pinned is not None and bytes.fromhex(cps[0]["key"]) != pinned:
        return f"WRONG KEY: the checkpoints are signed by key {key_id(bytes.fromhex(cps[0]['key']))[:16]}, not by the key you gave ({key_id(pinned)[:16]})."
    return None


def signing_view(cd: CaseDir, pinned: bytes | None = None) -> dict:
    """What the checkpoints of a case say about its trail: status "signed" (every checkpoint holds), "unsigned" (there is none) or "broken"
    (one does not, and `problem` says which and how); the key; the last checkpoint; and how many events came after it. With `pinned`, the
    public key the reader already knew, a case that is unsigned or signed by another key is broken."""
    view = {"status": "unsigned", "algorithm": ALGORITHM, "key_id": None, "checkpoints": 0, "last": None, "uncovered": 0, "problem": None}
    try:
        cps = _checkpoints(cd)
        problem = _problem(cd, cps, pinned)
    except ValueError as e:
        cps, problem = [], str(e)
    if problem:
        return view | {"status": "broken", "problem": problem}
    try:
        count = len(AuditLog(cd.audit_path).events())
    except ValueError:
        count = 0
    if not cps:
        return view | {"uncovered": count}
    last = cps[-1]
    return view | {"status": "signed", "key_id": key_id(bytes.fromhex(last["key"])), "checkpoints": len(cps), "last": last,
                   "uncovered": max(count - last["events"], 0)}
