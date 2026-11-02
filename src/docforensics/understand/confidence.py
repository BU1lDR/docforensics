"""Field confidence (design 7.3): never higher than the page it was read from, the label that located it, or the check on
its value. A recogniser's own score can only lower it: it does not flag misread digits (docs/spike.md)."""
from collections.abc import Iterable

from ..config import Thresholds
from ..read.quality import reliability


def field_conf(word_confs: Iterable[float], page_class: str, label_score: float, validator: float, th: Thresholds) -> float:
    return max(0.0, min([*word_confs, reliability(page_class, th), label_score, validator, 1.0]))
