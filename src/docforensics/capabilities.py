"""The capability matrix (design 9): what the tool does, partly does, plans and declines, kept in one JSON file next to this module.
The dossier prints it and the README quotes it; a status changes only when the evidence for it does."""
import json
from pathlib import Path


def load_capabilities() -> dict:
    """{"capabilities": [{name, status, evidence, note}], "limitations": [...], "assumptions": [...]}"""
    return json.loads(Path(__file__).with_name("capabilities.json").read_text(encoding="utf-8"))
