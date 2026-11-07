"""The model and the judging of the learned patch detector (evaluation/train_patches.py): small, deterministic, no scans."""
import numpy as np

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
