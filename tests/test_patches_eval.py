"""The model and the judging of the learned patch detector (evaluation/train_patches.py): small, deterministic, no scans."""
import numpy as np
import pytest

from evaluation import patches_data as pdta
from evaluation import train_patches as tp


def test_the_regression_separates_a_toy_set_and_gives_the_same_weights_twice():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 1, (300, 3)), rng.normal(3, 1, (15, 3))])
    y = np.r_[np.zeros(300), np.ones(15)]
    a, b = tp.fit(X, y, 1.0, 10.0), tp.fit(X, y, 1.0, 10.0)
    assert (a == b).all()
    s = tp.decision(X, a)
    assert s[y == 1].mean() > s[y == 0].mean() + 2


def test_the_threshold_lets_through_exactly_the_false_pages_it_is_allowed():
    best = [0.5, 0.9, 0.1, 0.7]
    assert sum(b >= tp.threshold(best, 0) for b in best) == 0
    assert sum(b >= tp.threshold(best, 1) for b in best) == 1  # the page with 0.9
    assert tp.threshold(best, 4) == float("-inf")


def test_a_case_stays_in_one_fold_and_cases_spread_over_all_folds():
    assert tp.fold_of("dev-0006") == tp.fold_of("dev-0006")
    assert {tp.fold_of(f"dev-{i:04d}") for i in range(60)} == set(range(tp.FOLDS))


def test_words_are_labelled_by_how_much_of_them_lies_in_the_edit_box_and_the_between_ones_are_left_out():
    edit = [100.0, 100.0, 200.0, 120.0]
    inside, half, overlap, away = [110.0, 100.0, 190.0, 120.0], [150.0, 100.0, 250.0, 120.0], [190.0, 100.0, 290.0, 120.0], [300.0, 100.0, 400.0, 120.0]
    share = np.array([pdta.share_inside(b, edit) for b in (inside, half, overlap, away)])
    assert share.tolist() == [1.0, 0.5, 0.1, 0.0]
    assert tp.labels({"share": share}).tolist() == [1, 1, -1, 0]


def test_a_measure_that_does_not_exist_counts_as_the_average_one():
    X = np.array([[1.0, np.nan], [3.0, np.nan], [2.0, 5.0]])
    mu, sd = tp.standardiser(X)
    z = tp.prep(X, mu, sd)
    assert np.isfinite(z).all() and (z[:2, 1] == 0).all()


def fake_slice(name, root, cases, rng, signal=True):
    """Pages of invented words: half the cases carry one changed word whose first measurement stands out; the checks flag nothing."""
    import pickle
    rows = []
    for c in range(cases):
        changed = c % 2 == 0
        X = rng.normal(0, 1, (12, len(tp.FEATURES)))
        boxes = np.array([[10.0 + 60 * j, 10.0, 60.0 + 60 * j, 40.0] for j in range(12)])
        share = np.zeros(12)
        if changed:
            X[0, 0] += 6 if signal else 0
            share[0] = 1.0
        rows.append({"slice": name, "case": f"{name}-{c:03d}", "kind": "S1" if changed else "genuine", "level": "mild", "layout": "A",
                     "file": "scan.jpg", "page": 1, "quality": "good", "edit": boxes[0].tolist() if changed else None, "n_words": 12,
                     "text": [f"w{j}" for j in range(12)], "boxes": boxes, "share": share, "X": X, "flags": {k: [] for k in tp.CHECKS}})
    (root / "features").mkdir(parents=True, exist_ok=True)
    with (root / "features" / f"{name}.pkl").open("wb") as f:
        pickle.dump(rows, f)


def slices(root, rng, signal=True):
    for name, cases in (("dev-design", 40), ("xdev-design", 40), ("dev-confirm", 30), ("xdev-confirm", 30)):
        fake_slice(name, root, cases, rng, signal)


def test_the_bar_is_read_off_the_tallies_as_written_and_a_baseline_with_nothing_wrong_leaves_the_learned_detector_no_room():
    def tl(found, false=0, regions=0, changed=40, unedited=40):
        return {"changed": changed, "found": list(range(found)), "unedited": unedited, "false": list(range(false)), "false_regions": regions}

    def rows(learned_found, learned_false=0, learned_regions=0, base_found=10):
        return {n: (tl(base_found), tl(learned_found, learned_false, learned_regions)) for n in ("dev-design", "dev-confirm", "xdev-confirm")}

    assert tp.verdict(rows(14)) == {"a": True, "b": True, "c": True, "b_with_one_page_allowed": True}  # 4 more, the margin for 40 pages
    assert not tp.verdict(rows(13))["a"] and not tp.verdict(rows(13))["c"]  # 3 more is under it
    v = tp.verdict(rows(20, learned_false=1, learned_regions=1))
    assert v["a"] and v["c"] and not v["b"] and v["b_with_one_page_allowed"]  # one false page: out, unless one is allowed
    assert not tp.verdict(rows(20, learned_false=0, learned_regions=3))["b"]  # no false page but false regions: out


def test_the_confirm_run_scores_once_and_writes_the_report_and_the_weights_only_if_the_bar_is_met(tmp_path):
    slices(tmp_path, np.random.default_rng(1))
    out, weights = tmp_path / "eval", tmp_path / "w.json"
    summary = tp.confirm(tmp_path, 1.0, 10.0, 0.5, out, weights)
    ok = summary["verdict"]
    assert summary["go"] == (ok["a"] and ok["b"] and ok["c"]) and weights.exists() == summary["go"]
    assert "## Verdict" in (out / "acceptance.md").read_text(encoding="utf-8") and (out / "acceptance.json").exists()
    try:
        tp.confirm(tmp_path, 1.0, 10.0, 0.5, out, weights)
        raise AssertionError("a second scoring of the confirm slices got through")
    except SystemExit:
        pass
    assert tp.report(tmp_path, out, weights)["verdict"] == ok  # the same results written up again


def test_the_weights_file_names_what_they_were_trained_on_and_is_the_same_twice(tmp_path):
    import json
    import pickle
    slices(tmp_path, np.random.default_rng(1))
    tp.confirm(tmp_path, 1.0, 10.0, 0.5, tmp_path / "eval", tmp_path / "unused.json")
    with (tmp_path / "confirm.pkl").open("rb") as f:
        r = pickle.load(f)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    tp.export(r, a)
    tp.export(r, b)
    w = json.loads(a.read_text(encoding="utf-8"))
    assert a.read_text() == b.read_text()
    assert w["features"] == list(tp.FEATURES) and len(w["beta"]) == len(tp.FEATURES) + 1 and len(w["mean"]) == len(w["scale"]) == len(tp.FEATURES)
    assert w["training"]["pages"] == 80 and w["training"]["cases"] == 80 and len(w["training"]["manifest_sha256"]) == 64


def test_a_detector_with_nothing_to_see_is_not_given_a_weights_file(tmp_path):
    slices(tmp_path, np.random.default_rng(2), signal=False)
    weights = tmp_path / "w.json"
    summary = tp.confirm(tmp_path, 1.0, 10.0, 0.5, tmp_path / "eval", weights)
    assert not summary["go"] and not weights.exists()


def test_measurements_made_with_another_feature_list_are_refused_not_mixed_in(tmp_path):
    import pickle
    fake_slice("old", tmp_path, 4, np.random.default_rng(0))
    path = tmp_path / "features" / "old.pkl"
    rows = pickle.load(path.open("rb"))
    for r in rows:
        r["X"] = r["X"][:, :-1]  # a list that was one measure shorter
    pickle.dump(rows, path.open("wb"))
    with pytest.raises(SystemExit, match="another feature list"):
        tp.load(["old"], tmp_path)


def test_a_lift_raises_the_threshold_by_a_share_of_the_distance_from_the_median_page():
    best = [0.0, 1.0, 2.0, 3.0, 4.0]
    t0 = tp.threshold(best, 0)
    assert tp.threshold(best, 0, lift=0.5) == pytest.approx(t0 + 0.5 * (t0 - 2.0))
    assert tp.threshold(best, 5, lift=0.5) == float("-inf")  # nothing to hold back, so nothing to lift


def test_the_threshold_set_on_the_other_folds_is_tried_on_the_fold_left_out_and_a_lift_keeps_the_top_page_out():
    pages = [{"case": f"c{i}", "edit": None} for i in range(50)]
    scores = [np.array([0.01 * i]) for i in range(50)]  # the last page is the highest, and nothing else comes near it
    assert tp.held_out_false(pages, scores, range(50)) == 1  # it sits above the top of the other four folds
    assert tp.held_out_false(pages, scores, range(50), lift=1.0) == 0


def test_the_detector_scores_a_row_the_way_the_training_script_does():
    from docforensics.forensics import learned_patches as lp
    rng = np.random.default_rng(3)
    X = rng.normal(0, 2, (50, len(tp.FEATURES)))
    X[::7, 3] = np.nan
    mu, sd = tp.standardiser(X)
    beta = rng.normal(0, 1, len(tp.FEATURES) + 1)
    w = {"mean": mu.tolist(), "scale": sd.tolist(), "clip": tp.CLIP, "beta": beta.tolist()}
    assert lp.score(X, w) == pytest.approx(tp.decision(tp.prep(X, mu, sd), beta))


def test_the_confirm_run_lifts_the_threshold_as_told_and_says_so_in_the_report_and_the_weights(tmp_path):
    import json
    runs = {}
    for lift in (0.0, 0.5):
        root = tmp_path / f"lift{lift}"
        root.mkdir()
        slices(root, np.random.default_rng(1))
        runs[lift] = tp.confirm(root, 1.0, 10.0, lift, root / "eval", root / "w.json")["run"]
    assert runs[0.5]["lift"] == 0.5 and runs[0.0]["lift"] == 0.0 and runs[0.5]["t"] > runs[0.0]["t"]
    assert "lift 0.5" in (tmp_path / "lift0.5" / "eval" / "acceptance.md").read_text(encoding="utf-8")
    if (tmp_path / "lift0.5" / "w.json").exists():
        assert json.loads((tmp_path / "lift0.5" / "w.json").read_text(encoding="utf-8"))["threshold_lift"] == 0.5
