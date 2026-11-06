"""The sample data: the cases of sample_data/, written with the manifests that say what is true of them.

Five cases of the development split. Four are the first case of their kind in the split, so their position picked them and not their
result: a PDF edited in a later saved revision (D1), a genuine case, a scan with a part of another scan spliced in (S1) and a name changed
in one document (C2). The fifth was picked because the development report lists it as a miss: a small logo changed (C5). They are not the
best cases of the split.

Then cases of the ext-dev split of the two packs made for the two newer checks, the split on which those checks were set up: a signature
that is the same image on two documents (datagen/reuse_pack.py, the three documents of a case as in the splits) and the compression history
of a scanned picture (datagen/ela_pack.py, one payslip scan a case). Each is the first of its kind by case number, or a miss that the
pack's own report lists (sample_data/README.md says which and why). A pack case is drawn by the pack's own code, which is not touched here:
this module only picks cases by number and writes what the packs return, with a manifest of each pack's own shape."""
import json
from pathlib import Path

from . import ela_pack, reuse_pack
from .build import build_case, plan_cases

SPLIT = "dev"
CASES = ("dev-0000", "dev-0002", "dev-0006", "dev-0009", "dev-0043")

PACK_SPLIT = "ext-dev"
PACKS = {"h": ("ext-dev-h-0000", "ext-dev-h-0001", "ext-dev-h-0046"), "e": ("ext-dev-e-0000", "ext-dev-e-0002", "ext-dev-e-0012")}
MANIFESTS = {"h": "manifest-ext-dev-h.json", "e": "manifest-ext-dev-e.json"}  # beside manifest.json, which holds the five dev cases
PACK_NAME = {"h": "reuse", "e": "e"}  # the "pack" key of a pack's own manifest


def _number(name: str) -> int:
    return int(name.rpartition("-")[2])


def _pack_case(kind: str, name: str) -> tuple[dict[str, bytes], dict]:
    """The files of one case of a pack, by name, and its manifest entry. A case depends only on its number."""
    if kind == "h":
        (plan,) = reuse_pack.plan_pack(PACK_SPLIT, 1, _number(name))
        files, entry = reuse_pack.build_pack_case(plan)
    else:
        (plan,) = ela_pack.plan_cases(PACK_SPLIT, 1, _number(name))
        scan, entry = ela_pack.build_case(plan)
        files = {ela_pack.FILE: scan}
    assert plan["case"] == name, (plan["case"], name)
    return files, entry


def _write(folder: Path, files: dict[str, bytes]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for filename, data in files.items():
        (folder / filename).write_bytes(data)


def _manifest(path: Path, head: dict, entries: list[dict]) -> None:
    path.write_text(json.dumps({**head, "cases": entries}, indent=1), encoding="utf-8", newline="\n")


def build_sample(out: Path | str) -> Path:
    """The files of each case under `out/<case>/` and the manifests (`manifest.json` for the development cases, which is returned, and one for
    each pack's cases). A case depends only on its number."""
    out = Path(out)
    entries = []
    for name in CASES:
        (plan,) = plan_cases(SPLIT, 1, _number(name))
        assert plan["case"] == name, (plan["case"], name)
        files, entry = build_case(plan)
        _write(out / name, files)
        entries.append(entry)
    path = out / "manifest.json"
    _manifest(path, {"split": SPLIT}, entries)
    for kind, names in PACKS.items():
        entries = []
        for name in names:
            files, entry = _pack_case(kind, name)
            _write(out / name, files)
            entries.append(entry)
        _manifest(out / MANIFESTS[kind], {"split": PACK_SPLIT, "pack": PACK_NAME[kind]}, entries)
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.sample", description="Write the sample cases and their manifests.")
    ap.add_argument("out", help="the folder to write to (sample_data in the repository)")
    print(build_sample(ap.parse_args().out))
