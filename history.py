"""Purane videos ka record, taaki same topic repeat na ho."""
import json
from pathlib import Path

FILE = Path(__file__).parent / "data" / "history.json"


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def add(entry):
    h = load()
    h.append(entry)
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(h[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
