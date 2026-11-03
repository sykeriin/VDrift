"""App-independent task definitions. A step target is {sel: CSS, text: visible-text prefix (optional), nth: int} or {label: str}."""
from __future__ import annotations
from dataclasses import dataclass, field

def T(sel, text=None, nth=0): return {"sel": sel, "text": text, "nth": nth}

@dataclass
class Step:
    intent: str
    action: str            # click | type | key
    target: dict | None
    value: str | None = None
    by_version: dict = field(default_factory=dict)   # per-release override of `target`
    irreversible: bool = False

@dataclass
class Task:
    id: str
    instruction: str
    start: str
    steps: list
    check: callable
    setup: callable = lambda env: None
    viewport: tuple = (1280, 1200)
