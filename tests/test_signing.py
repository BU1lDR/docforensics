"""Signed checkpoints of the audit trail (scope D, package S). A checkpoint is the case, the number of events and the hash of the last one,
signed with an Ed25519 key that is made once per data folder and kept outside the case folders. It lets a reader see that a trail was
changed and chained again, or cut short, which the hash chain alone cannot show. It proves nothing about who held the key or when."""
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (BestAvailableEncryption, Encoding, NoEncryption, PrivateFormat, PublicFormat,
                                                          load_pem_private_key)

from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.dossier import build_dossier, dossier_dict, dossier_stage
from docforensics.findings import add_findings
from docforensics.ingest import create_case
from docforensics.model import Evidence, Finding
from docforensics.pipeline import Ctx, run_case
from docforensics.review import apply_review
from docforensics.signing import _message, checkpoint, public_key_bytes, signing_view
from docforensics.store import CaseDir, save_case
from tests.helpers import pdf_bytes, rechain


def trail(tmp_path, n=3):
    cd = CaseDir.create(tmp_path)
    log = AuditLog(cd.audit_path)
    for i in range(n):
        log.append("system", "step", {"i": i})
    return cd, log


def started(cd):
    """The first checkpoint of a case, as the end of a run makes it."""
    return checkpoint(cd, start=True)


def lines(cd):
    return cd.checkpoints_path.read_text(encoding="utf-8").splitlines()


def edit_line(cd, n, **changes):
    ls = lines(cd)
    ls[n] = json.dumps({**json.loads(ls[n]), **changes})
    cd.checkpoints_path.write_text("\n".join(ls) + "\n", encoding="utf-8")


def public_pem(cd):
    return (cd.root.parent.parent / "signing" / "public.pem").read_bytes()


def test_a_checkpoint_names_the_case_the_count_and_the_last_hash_and_verifies(tmp_path):
    cd, log = trail(tmp_path)
    cp = started(cd)
    count, head = log.head()
    assert (cp["case"], cp["events"], cp["head"]) == (cd.id, count, head) and count == 3
    view = signing_view(cd)
    assert view["status"] == "signed" and view["problem"] is None and view["checkpoints"] == 1 and view["uncovered"] == 0
    assert view["algorithm"] == "Ed25519" and view["last"] == cp
    assert view["key_id"] == hashlib.sha256(bytes.fromhex(cp["key"])).hexdigest()
    assert log.verify() == (True, None)  # the checkpoint is in a file of its own: the trail has no new event


def test_the_key_is_made_once_per_data_folder_and_kept_outside_the_case_folder(tmp_path):
    a, _ = trail(tmp_path)
    b, _ = trail(tmp_path)
    ka, kb = started(a)["key"], started(b)["key"]
    assert ka == kb
    assert (tmp_path / "signing" / "private.pem").is_file() and (tmp_path / "signing" / "public.pem").is_file()
    assert not list(a.root.rglob("*.pem")) and not list(b.root.rglob("*.pem"))
    assert public_key_bytes(public_pem(a)) == bytes.fromhex(ka)


def test_a_second_checkpoint_at_the_same_head_adds_nothing_and_a_new_event_adds_one(tmp_path):
    cd, log = trail(tmp_path)
    first = started(cd)
    assert checkpoint(cd) == first and len(lines(cd)) == 1
    log.append("system", "step", {"i": 3})
    second = checkpoint(cd)
    assert second["events"] == 4 and len(lines(cd)) == 2
    assert signing_view(cd)["checkpoints"] == 2


def test_an_empty_trail_is_not_signed(tmp_path):
    cd = CaseDir.create(tmp_path)
    assert checkpoint(cd) is None and not cd.checkpoints_path.exists()
    assert signing_view(cd)["status"] == "unsigned"


def test_events_after_the_last_checkpoint_are_counted_and_do_not_fail(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    log.append("system", "step", {"i": 3})
    log.append("system", "step", {"i": 4})
    view = signing_view(cd)
    assert view["status"] == "signed" and view["problem"] is None and view["uncovered"] == 2 and view["last"]["events"] == 3


def test_an_event_changed_and_the_chain_worked_out_again_is_seen_by_the_signature(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    rechain(cd, 2)
    assert log.verify() == (True, None)  # the chain alone is fooled
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("REWRITTEN")


def test_a_trail_cut_short_is_seen_by_the_signature(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    cd.audit_path.write_text("".join(ln + "\n" for ln in cd.audit_path.read_text(encoding="utf-8").splitlines()[:2]), encoding="utf-8")
    assert log.verify() == (True, None)
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("TRUNCATED")


@pytest.mark.parametrize("field, value", [("head", "0" * 64), ("events", 2), ("ts", "2020-01-01T00:00:00.000+00:00"), ("sig", "00" * 64),
                                          ("case", "C-20200101-000000-abcd")])
def test_a_checkpoint_that_was_edited_does_not_verify(tmp_path, field, value):
    cd, _ = trail(tmp_path)
    started(cd)
    edit_line(cd, 0, **{field: value})
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("BAD SIGNATURE")


def test_the_checkpoints_of_another_case_are_refused(tmp_path):
    a, _ = trail(tmp_path)
    b, _ = trail(tmp_path)
    started(a)
    b.checkpoints_path.write_text(a.checkpoints_path.read_text(encoding="utf-8"), encoding="utf-8")
    view = signing_view(b)
    assert view["status"] == "broken" and view["problem"].startswith("WRONG CASE")


@pytest.mark.parametrize("junk", ["not json", "{}", '{"v": 1, "case": 5}', '{"v": 1, "case": "x", "events": 1, "head": "h", "ts": "t", "key": "zz", "sig": "zz"}'])
def test_a_line_that_cannot_be_read_is_reported_not_skipped(tmp_path, junk):
    cd, _ = trail(tmp_path)
    started(cd)
    cd.checkpoints_path.write_text(lines(cd)[0] + "\n" + junk + "\n", encoding="utf-8")
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("UNREADABLE")


def test_a_case_with_no_checkpoints_is_unsigned_and_is_not_a_failure(tmp_path):
    cd, _ = trail(tmp_path)
    view = signing_view(cd)
    assert view["status"] == "unsigned" and view["problem"] is None and view["checkpoints"] == 0 and view["last"] is None and view["uncovered"] == 3


def test_a_trail_changed_and_signed_again_with_another_key_passes_unless_the_key_is_pinned(tmp_path):
    """The limit, as a test: whoever holds the data folder can rewrite the trail and sign it with a key of their own. Only a key the reader
    knew beforehand, from outside the folder, tells that apart."""
    cd, _ = trail(tmp_path)
    started(cd)
    original = public_key_bytes(public_pem(cd))
    rechain(cd, 2)
    cd.checkpoints_path.unlink()
    for f in (tmp_path / "signing").iterdir():
        f.unlink()
    checkpoint(cd, start=True)  # a run again, and a new key, because there is none
    assert public_key_bytes(public_pem(cd)) != original
    assert signing_view(cd)["status"] == "signed"
    pinned = signing_view(cd, pinned=original)
    assert pinned["status"] == "broken" and pinned["problem"].startswith("WRONG KEY")


def signed_by(key, cd, count, head, case=None):
    """A checkpoint line made by hand with `key`, for a file that checkpoint() itself would refuse to write."""
    cp = {"v": 1, "case": case or cd.id, "events": count, "head": head, "ts": "2026-01-01T00:00:00.000+00:00"}
    cp |= {"key": key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(), "sig": key.sign(_message(cp)).hex()}
    return json.dumps(cp, sort_keys=True) + "\n"


def test_checkpoints_of_two_keys_in_one_file_are_refused(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    log.append("system", "step", {"i": 3})
    count, head = log.head()
    with cd.checkpoints_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(signed_by(Ed25519PrivateKey.generate(), cd, count, head))
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("MORE THAN ONE KEY")


def test_a_pinned_key_is_checked_against_the_signer_and_a_missing_signature_fails_it(tmp_path):
    cd, _ = trail(tmp_path)
    assert signing_view(cd, pinned=b"\x00" * 32)["problem"].startswith("NOT SIGNED")
    started(cd)
    right = public_key_bytes(public_pem(cd))
    assert signing_view(cd, pinned=right)["status"] == "signed"
    assert signing_view(cd, pinned=b"\x01" * 32)["problem"].startswith("WRONG KEY")


@pytest.mark.parametrize("pem", [b"", b"not a key", b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n"])
def test_a_public_key_file_that_is_not_one_is_refused(pem):
    with pytest.raises(ValueError):
        public_key_bytes(pem)


def test_a_data_folder_that_cannot_hold_a_key_does_not_stop_the_work_and_the_trail_says_so(tmp_path):
    (tmp_path / "signing").write_text("a file where the folder should be", encoding="utf-8")
    cd, log = trail(tmp_path)
    assert checkpoint(cd, start=True) is None and not cd.checkpoints_path.exists()
    failed = [e for e in log.events() if e.event == "checkpoint_failed"]
    assert len(failed) == 1 and failed[0].data["error"] and log.verify() == (True, None)
    assert tmp_path.name not in failed[0].data["error"]  # the trail is shared in the dossier: no path of this machine in it (a path is written with doubled backslashes in an error, so look for a folder name)


def test_a_key_file_that_is_not_a_key_does_not_stop_the_work_and_is_not_replaced(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    (tmp_path / "signing" / "private.pem").write_text("damaged", encoding="utf-8")
    log.append("system", "step", {"i": 3})
    assert checkpoint(cd) is None
    assert (tmp_path / "signing" / "private.pem").read_text(encoding="utf-8") == "damaged"  # a key is never made over a key that was there
    assert [e.event for e in log.events()][-1] == "checkpoint_failed"


def test_a_trail_whose_chain_does_not_verify_is_not_signed_and_the_refusal_is_recorded(tmp_path):
    """A checkpoint says the trail was whole when it was signed. A trail that already fails its chain gets no new one, and the events that
    came after the last good checkpoint stay counted as not covered."""
    cd, log = trail(tmp_path)
    first = started(cd)
    ls = cd.audit_path.read_bytes().splitlines()
    ls[0] = ls[0].replace(b'"event":"step"', b'"event":"stop"')  # an event edited, the chain not worked out again
    cd.audit_path.write_bytes(b"\n".join(ls) + b"\n")
    assert log.verify()[0] is False
    log.append("system", "step", {"i": 3})
    assert checkpoint(cd) is None and [json.loads(x) for x in lines(cd)] == [first]
    assert log.events()[-1].event == "checkpoint_failed" and "does not verify" in log.events()[-1].data["error"]
    view = signing_view(cd)  # a trail whose own chain fails is not shown as signed at all
    assert view["status"] == "broken" and view["problem"].startswith("CHAIN BROKEN")


def test_a_trail_with_a_line_that_is_not_an_event_is_not_signed_and_does_not_raise(tmp_path):
    cd, log = trail(tmp_path)
    with cd.audit_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write("not an event\n")
    assert checkpoint(cd, start=True) is None and not cd.checkpoints_path.exists()  # and no exception: the work goes on


def test_a_run_ends_with_a_checkpoint_over_the_whole_trail(tmp_path):
    th = Thresholds()
    case, cd, audit = create_case(tmp_path / "data", [("a.pdf", pdf_bytes())], th)
    run_case(cd, th, stages={})
    view = signing_view(cd)
    count, head = audit.head()
    assert view["status"] == "signed" and view["uncovered"] == 0 and (view["last"]["events"], view["last"]["head"]) == (count, head)


@pytest.fixture
def made(tmp_path):
    th = Thresholds()
    case, cd, audit = create_case(tmp_path / "data", [("a.pdf", pdf_bytes())], th)
    ctx = Ctx(cd, audit, th)
    add_findings(case, ctx, [Finding(fclass="observation", detector="pdf_fonts", family="visual", title="Font differs",
                                     evidence=[Evidence(doc="D1", page=1, box=(10.0, 10.0, 50.0, 20.0))])])
    save_case(case, cd)
    return case, ctx


@pytest.fixture
def ran(made):
    """A case at the end of its run: the trail is signed, as run_case leaves it."""
    case, ctx = made
    started(ctx.cd)
    return case, ctx


def test_a_reviewer_action_is_signed_when_it_is_made(ran):
    case, ctx = ran
    apply_review(case, ctx, "F-001", "needs_verification", "ask the branch")
    view = signing_view(ctx.cd)
    count, head = ctx.audit.head()
    assert view["status"] == "signed" and view["uncovered"] == 0 and (view["last"]["events"], view["last"]["head"]) == (count, head)
    assert ctx.audit.events()[-1].event == "reviewer_action"


def test_a_rejected_review_signs_nothing_and_adds_nothing(ran):
    case, ctx = ran
    before = ctx.cd.checkpoints_path.read_bytes()
    with pytest.raises(ValueError):
        apply_review(case, ctx, "F-001", "no such status")
    assert ctx.cd.checkpoints_path.read_bytes() == before


def test_the_dossier_carries_the_signed_anchor_and_the_event_it_writes_is_signed_too(made):
    case, ctx = made
    d = dossier_dict(case, ctx)  # a dict alone signs nothing
    assert d["appendices"]["audit_trail"]["signing"]["status"] == "unsigned"
    dossier_stage(case, ctx)  # the stage of a run, which starts the chain
    written = json.loads(ctx.cd.dossier_json.read_text(encoding="utf-8"))["appendices"]["audit_trail"]
    sig = written["signing"]
    assert sig["status"] == "signed" and sig["uncovered"] == 0
    assert (sig["last"]["events"], sig["last"]["head"]) == (written["anchor"]["events"], written["anchor"]["head"])  # the anchor, signed
    after = signing_view(ctx.cd)  # dossier_generated came after the anchor, and is covered by the checkpoint that follows it
    assert after["uncovered"] == 0 and after["last"]["events"] == written["anchor"]["events"] + 1
    assert ctx.audit.events()[-1].event == "dossier_generated"


# --- what a later action may sign, and what it may not (reviewer 62, part 1 and 2)

def test_a_trail_changed_chained_again_and_stripped_of_its_checkpoints_is_not_signed_afresh_by_a_later_action(tmp_path):
    """The hole a reviewer found: only the hash chain was checked before signing, so a trail that was changed, chained again and then
    stripped of checkpoints.jsonl was signed by the next reviewer action as if it had always been whole."""
    cd, log = trail(tmp_path)
    started(cd)
    rechain(cd, 2)
    cd.checkpoints_path.unlink()
    assert log.verify() == (True, None)
    assert checkpoint(cd) is None and not cd.checkpoints_path.exists()
    view = signing_view(cd)
    assert view["status"] == "unsigned" and view["uncovered"] == 3


def test_a_reviewer_action_on_a_case_that_was_never_signed_does_not_start_a_chain(made):
    case, ctx = made
    apply_review(case, ctx, "F-001", "needs_verification", "ask the branch")
    assert not ctx.cd.checkpoints_path.exists()
    assert signing_view(ctx.cd)["status"] == "unsigned"


def test_a_dossier_asked_for_later_does_not_start_a_chain_and_says_unsigned(made):
    case, ctx = made
    build_dossier(case, ctx)
    written = json.loads(ctx.cd.dossier_json.read_text(encoding="utf-8"))["appendices"]["audit_trail"]
    assert written["signing"]["status"] == "unsigned" and not ctx.cd.checkpoints_path.exists()


def test_only_a_run_starts_the_chain(tmp_path):
    cd, _ = trail(tmp_path)
    assert checkpoint(cd) is None and not cd.checkpoints_path.exists() and not (tmp_path / "signing").exists()  # no key is made for nothing
    assert checkpoint(cd, start=True)["events"] == 3


def rewritten(cd):
    rechain(cd, 2)


def cut(cd):
    cd.audit_path.write_text("".join(ln + "\n" for ln in cd.audit_path.read_text(encoding="utf-8").splitlines()[:2]), encoding="utf-8")


def bad_signature(cd):
    edit_line(cd, 0, sig="00" * 64)


def not_a_checkpoint(cd):
    cd.checkpoints_path.write_text(lines(cd)[0] + "\nnot json\n", encoding="utf-8")


@pytest.mark.parametrize("damage, word", [(rewritten, "REWRITTEN"), (cut, "TRUNCATED"), (bad_signature, "BAD SIGNATURE"),
                                          (not_a_checkpoint, "UNREADABLE")])
def test_a_trail_is_not_signed_on_top_of_checkpoints_that_no_longer_hold(tmp_path, damage, word):
    cd, log = trail(tmp_path)
    started(cd)
    damage(cd)
    before = cd.checkpoints_path.read_bytes()
    assert checkpoint(cd) is None
    last = log.events()[-1]
    assert last.event == "checkpoint_failed" and word in last.data["error"]
    assert checkpoint(cd, start=True) is None  # not even by a run
    assert cd.checkpoints_path.read_bytes() == before


def test_a_new_key_does_not_sign_over_the_checkpoints_of_an_old_one(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    log.append("system", "step", {"i": 3})
    for f in (tmp_path / "signing").iterdir():
        f.unlink()
    assert checkpoint(cd) is None
    assert len(lines(cd)) == 1 and not (tmp_path / "signing" / "private.pem").exists()
    assert log.events()[-1].event == "checkpoint_failed"


def test_a_key_that_did_not_sign_the_earlier_checkpoints_is_not_used(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    other = Ed25519PrivateKey.generate().private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    (tmp_path / "signing" / "private.pem").write_bytes(other)
    log.append("system", "step", {"i": 3})
    assert checkpoint(cd) is None and len(lines(cd)) == 1
    assert log.events()[-1].event == "checkpoint_failed"


def test_a_key_file_with_a_password_does_not_stop_the_work_and_is_not_replaced(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    path = tmp_path / "signing" / "private.pem"
    locked = load_pem_private_key(path.read_bytes(), None).private_bytes(Encoding.PEM, PrivateFormat.PKCS8, BestAvailableEncryption(b"pw"))
    path.write_bytes(locked)
    log.append("system", "step", {"i": 3})
    assert checkpoint(cd) is None  # and no TypeError out of the library
    assert path.read_bytes() == locked
    assert log.events()[-1].event == "checkpoint_failed"


def test_a_public_key_file_that_was_lost_is_written_again(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    original = public_pem(cd)
    (tmp_path / "signing" / "public.pem").unlink()
    log.append("system", "step", {"i": 3})
    assert checkpoint(cd) is not None
    assert public_pem(cd) == original


def test_a_trail_with_a_line_that_is_not_an_event_is_reported_as_a_broken_chain_and_not_as_cut_short(tmp_path):
    cd, _ = trail(tmp_path)
    started(cd)
    with cd.audit_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write("not an event\n")
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("CHAIN BROKEN")


def test_a_checkpoint_file_that_cannot_be_opened_is_reported_and_does_not_raise(tmp_path):
    cd, _ = trail(tmp_path)
    cd.checkpoints_path.mkdir()  # a folder where the file should be
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("UNREADABLE")
    assert checkpoint(cd, start=True) is None


def test_text_that_came_from_the_file_cannot_reach_a_terminal_as_an_escape_sequence(tmp_path):
    """A checkpoint is read from a file anyone with write access can edit, and `problem` is printed by verify-audit."""
    cd, log = trail(tmp_path)
    count, head = log.head()
    cd.checkpoints_path.write_text(signed_by(Ed25519PrivateKey.generate(), cd, count, head, case="\x1b[2Jother\x07"), encoding="utf-8")
    view = signing_view(cd)
    assert view["problem"].startswith("WRONG CASE") and "\x1b" not in view["problem"] and "\x07" not in view["problem"]


# --- second review of the hardening (6 Nov): a view that said "signed" over a failing chain, a parser that recursed, a stale public key

def test_a_trail_whose_own_chain_fails_is_not_shown_as_signed(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    ls = cd.audit_path.read_text(encoding="utf-8").split("\n")
    ev = json.loads(ls[0])
    ev["data"] = {"i": "changed"}  # the stored hash is left alone, so the chain fails at event 1
    ls[0] = json.dumps(ev)
    cd.audit_path.write_text("\n".join(ls), encoding="utf-8")
    assert log.verify() == (False, 1)
    view = signing_view(cd)
    assert view["status"] == "broken" and "chain" in view["problem"].lower() and view["last"] is None


def test_a_checkpoint_line_nested_deeper_than_the_parser_goes_is_reported_as_unreadable_and_does_not_raise(tmp_path):
    cd, log = trail(tmp_path)
    started(cd)
    cd.checkpoints_path.write_text("[" * 100_000 + "\n", encoding="utf-8")
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("UNREADABLE")
    assert checkpoint(cd) is None and checkpoint(cd, start=True) is None  # neither raises
    assert log.events()[-1].event == "checkpoint_failed"


def test_a_public_key_file_left_behind_by_an_earlier_key_is_replaced_by_the_half_of_the_key_in_use(tmp_path):
    a, _ = trail(tmp_path)
    first = started(a)
    (tmp_path / "signing" / "private.pem").unlink()  # the private key is lost; a case without checkpoints gets a new one
    b, _ = trail(tmp_path)
    second = started(b)
    assert second["key"] != first["key"]
    assert public_key_bytes(public_pem(b)) == bytes.fromhex(second["key"])


def test_a_trail_that_cannot_be_read_at_all_is_reported_as_unreadable_without_the_path_and_does_not_raise(tmp_path):
    cd, _ = trail(tmp_path)
    started(cd)
    cd.audit_path.unlink()
    cd.audit_path.mkdir()  # a folder where the trail should be
    view = signing_view(cd)
    assert view["status"] == "broken" and view["problem"].startswith("UNREADABLE") and str(tmp_path) not in view["problem"] and view["last"] is None
