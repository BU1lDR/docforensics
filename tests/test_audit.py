import hashlib
import json
import threading

from docforensics.audit import AuditLog


def fill(path, n=5):
    log = AuditLog(path)
    for i in range(n):
        log.append("system", "stage_end", {"i": i})
    return log


def rewrite(path, fn):
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(fn(lines)) + "\n", encoding="utf-8")


def test_chain_verifies(tmp_path):
    log = fill(tmp_path / "audit.jsonl")
    assert log.verify() == (True, None)
    assert [e.seq for e in log.events()] == [1, 2, 3, 4, 5]
    assert log.events()[0].prev_hash == "0" * 64
    assert log.head() == (5, log.events()[-1].hash)


def test_hash_recipe_is_reproducible_outside_the_tool(tmp_path):
    log = fill(tmp_path / "audit.jsonl", 2)
    e = log.events()[1]
    body = {"seq": e.seq, "ts": e.ts, "actor": e.actor, "event": e.event, "data": e.data, "prev_hash": e.prev_hash}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert e.hash == hashlib.sha256(canon.encode("utf-8")).hexdigest()


def test_edit_in_the_middle_is_detected(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = fill(p)

    def edit(lines):
        d = json.loads(lines[2])
        d["data"]["i"] = 99
        lines[2] = json.dumps(d)
        return lines

    rewrite(p, edit)
    assert log.verify() == (False, 3)


def test_edit_with_recomputed_hash_breaks_the_next_link(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = fill(p)

    def edit(lines):
        d = json.loads(lines[2])
        d["data"]["i"] = 99
        body = {k: d[k] for k in ("seq", "ts", "actor", "event", "data", "prev_hash")}
        d["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        lines[2] = json.dumps(d)
        return lines

    rewrite(p, edit)
    assert log.verify() == (False, 4)


def test_deleted_line_is_detected(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = fill(p)
    rewrite(p, lambda lines: lines[:1] + lines[2:])
    assert log.verify() == (False, 3)


def test_garbage_line_is_detected(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = fill(p)
    rewrite(p, lambda lines: lines[:2] + ["not json"] + lines[3:])
    ok, bad = log.verify()
    assert not ok and bad == 3


def test_concurrent_appends_keep_chain_valid(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    def work(t):
        for i in range(25):
            log.append("system", "tick", {"t": t, "i": i})

    threads = [threading.Thread(target=work, args=(t,)) for t in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert log.verify() == (True, None)
    assert sorted(e.seq for e in log.events()) == list(range(1, 201))


def test_reopen_continues_chain(tmp_path):
    p = tmp_path / "audit.jsonl"
    fill(p, 2)
    again = AuditLog(p)
    assert again.append("reviewer", "review", {"finding": "F-001"}).seq == 3
    assert again.verify() == (True, None)


def test_two_instances_on_one_file_stay_consistent(tmp_path):
    p = tmp_path / "audit.jsonl"
    a, b = AuditLog(p), AuditLog(p)
    a.append("system", "x", {})
    b.append("system", "y", {})
    a.append("system", "z", {})
    assert a.verify() == (True, None)


def test_non_json_values_are_stored_as_text(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    ev = log.append("system", "file", {"path": tmp_path})
    assert ev.data["path"] == str(tmp_path)
    assert log.verify() == (True, None)
