"""What the user has already answered, per merchant and card.

This is the whole learning mechanism: counted confirmations, the amounts seen so
far, and the category that was chosen. No training, no model, nothing leaves the
device. It is small enough to read by hand, which is the point: a user can be
shown exactly why the app stopped asking.
"""

from __future__ import annotations

import json
import os
import statistics
import tempfile
import threading
from pathlib import Path
from typing import Any

SCHEMA = 1


class Memory:
    """Dict-backed, with an optional JSON file behind it."""

    def __init__(self, data: dict | None = None, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.data: dict[str, Any] = data or {"schema": SCHEMA, "merchants": {}}
        self.data.setdefault("merchants", {})
        # The server is threaded, so two payments from the same merchant can land
        # at once. Without this, one of them silently overwrites the other's count
        # and the merchant never reaches the confirmations it actually has.
        self._lock = threading.RLock()

    # ------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path: str | Path) -> "Memory":
        p = Path(path)
        try:
            return cls(json.loads(p.read_text()), p)
        except (OSError, ValueError):
            return cls(None, p)

    def save(self, path: str | Path | None = None) -> None:
        """Write through a temporary file, so a crash mid-write cannot leave the
        memory truncated. A half written memory means the app starts asking about
        merchants it had already learned."""
        target = Path(path) if path else self.path
        if not target:
            raise ValueError("no path to save to")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = json.dumps(self.data, indent=1, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ----------------------------------------------------------------- lookup
    def get(self, key: str) -> dict | None:
        with self._lock:
            return self.data["merchants"].get(key)

    def typical(self, key: str) -> float | None:
        """The amount this merchant usually costs, as a median so one big trip
        does not drag the bar up."""
        e = self.get(key)
        if not e or not e.get("amounts"):
            return None
        return float(statistics.median(e["amounts"]))

    # --------------------------------------------------------------- learning
    def record(self, key: str, purpose: str, amount: float,
               category: str | None = None) -> dict:
        """One confirmed answer. A changed answer resets the count, because the
        user just told us the old rule was wrong."""
        with self._lock:
            m = self.data["merchants"]
            e = m.setdefault(key, {"purpose": purpose, "count": 0, "amounts": [],
                                   "category": category, "auto_filed": 0, "revoked": 0})
            if e["purpose"] != purpose:
                e.update(purpose=purpose, count=0, amounts=[], auto_filed=0)
            e["count"] += 1
            e["amounts"] = (e["amounts"] + [round(float(amount), 2)])[-12:]
            if category:
                e["category"] = category
            return dict(e)

    def note_auto(self, key: str) -> None:
        with self._lock:
            e = self.data["merchants"].get(key)
            if e:
                e["auto_filed"] = e.get("auto_filed", 0) + 1

    def revoke(self, key: str) -> dict | None:
        """The user took an automatic entry back. That is the strongest signal we
        get, so the merchant goes back to being asked about."""
        with self._lock:
            e = self.data["merchants"].get(key)
            if not e:
                return None
            e["revoked"] = e.get("revoked", 0) + 1
            e["count"] = 0
            e["auto_filed"] = 0
            return dict(e)

    def forget(self, key: str) -> bool:
        with self._lock:
            return self.data["merchants"].pop(key, None) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self.data["merchants"])
