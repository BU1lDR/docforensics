"""The sample data: five cases of the development split, written with the manifest that says what is true of them.

Four are the first case of their kind in the split, so their position picked them and not their result: a PDF edited in a later saved
revision (D1), a genuine case, a scan with a part of another scan spliced in (S1) and a name changed in one document (C2). The fifth was
picked because the development report lists it as a miss: a small logo changed (C5). They are not the best cases of the split."""
import json
from pathlib import Path

from .build import build_case, plan_cases

SPLIT = "dev"
CASES = ("dev-0000", "dev-0002", "dev-0006", "dev-0009", "dev-0043")


def build_sample(out: Path | str) -> Path:
    """The files of each case under `out/<case>/` and `out/manifest.json`, which is returned. A case depends only on its number."""
    out = Path(out)
    entries = []
    for name in CASES:
        (plan,) = plan_cases(SPLIT, 1, int(name.rpartition("-")[2]))
        assert plan["case"] == name, (plan["case"], name)
        files, entry = build_case(plan)
        (out / name).mkdir(parents=True, exist_ok=True)
        for filename, data in files.items():
            (out / name / filename).write_bytes(data)
        entries.append(entry)
    path = out / "manifest.json"
    path.write_text(json.dumps({"split": SPLIT, "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.sample", description="Write the five sample cases and their manifest.")
    ap.add_argument("out", help="the folder to write to (sample_data in the repository)")
    print(build_sample(ap.parse_args().out))
