"""Every payment, its decision, and what happened to it afterwards.

Two things make this more than a list. First, each entry records who decided it:
a rule, an outside model, or the person. When the tax office asks two years later
that column is the difference between an answer and a problem. Second, anything
filed automatically stays revocable, and the weekly summary exists so the user
sees those entries before the year closes, not after.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Decision, Payment


class Ledger:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text())
            except (OSError, ValueError):
                self.entries = []

    # ------------------------------------------------------------------ write
    def add(self, payment: Payment, decision: Decision, decided_by: str) -> dict:
        with self._lock:
            entry = {
                "id": len(self.entries) + 1,
                "ts": payment.ts,
                "merchant": payment.merchant,
                "amount": round(abs(float(payment.amount or 0)), 2),
                "currency": payment.currency,
                "card": payment.card,
                "key": payment.key(),
                "purpose": decision.purpose,
                "category": decision.category,
                "vat_rate": decision.vat_rate,
                "filed": decision.action == "file",
                "decided_by": decided_by,          # rule | model | person
                "rule": decision.rule,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "receipt": "missing" if decision.needs_receipt else "not needed",
                "revoked": False,
            }
            self.entries.append(entry)
            self._flush()
            return entry

    def answer(self, entry_id: int, purpose: str, category: str | None = None) -> dict | None:
        """The person answered the question. Their word overrides everything."""
        e = self.get(entry_id)
        if not e:
            return None
        with self._lock:
            e.update(purpose=purpose, filed=(purpose == "business"),
                     decided_by="person", reason="answered by you")
            if category:
                e["category"] = category
            self._flush()
        return e

    def attach_receipt(self, entry_id: int, status: str = "ok",
                       ref: str | None = None) -> dict | None:
        e = self.get(entry_id)
        if not e:
            return None
        with self._lock:
            e["receipt"] = status
            if ref:
                e["receipt_ref"] = ref
            self._flush()
        return e

    def revoke(self, entry_id: int) -> dict | None:
        e = self.get(entry_id)
        if not e:
            return None
        with self._lock:
            e.update(revoked=True, filed=False, reason="revoked by you")
            self._flush()
        return e

    # ------------------------------------------------------------------- read
    def get(self, entry_id: int) -> dict | None:
        return next((e for e in self.entries if e["id"] == entry_id), None)

    def filed(self) -> list[dict]:
        return [e for e in self.entries if e["filed"] and not e["revoked"]]

    def missing_receipts(self) -> list[dict]:
        return [e for e in self.filed() if e.get("receipt") == "missing"]

    def week(self, days: int = 7, rate: float = 0.42) -> dict:
        """The Friday push. `rate` is the user's marginal rate: what a deductible
        euro is actually worth to them. Never show the amount as the saving."""
        cut = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [e for e in self.filed() if _ts(e["ts"]) >= cut]
        total = round(sum(e["amount"] for e in recent), 2)
        return {
            "days": days,
            "filed": len(recent),
            "total": total,
            "estimated_effect": round(total * rate, 2),
            "rate_used": rate,
            "automatic": [e for e in recent if e["decided_by"] != "person"],
            "missing_receipts": [e for e in recent if e.get("receipt") == "missing"],
            "note": "estimated effect, not a refund: amount times your marginal rate",
        }

    # ----------------------------------------------------------------- helpers
    def _flush(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=1, ensure_ascii=False))


def _ts(s: str) -> datetime:
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
