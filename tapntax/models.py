"""The three things this library passes around. Plain dataclasses, no framework."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Payment:
    """What a card payment tells us. The Wallet automation sends the first three;
    everything else is optional and only ever improves the decision."""
    merchant: str
    amount: float
    card: str = ""
    currency: str = "EUR"
    ts: str = field(default_factory=_now)
    mcc: str | None = None          # merchant category code, present in bank data
    country: str | None = None
    source: str = "wallet"          # wallet | bank | manual
    id: str | None = None

    def key(self) -> str:
        """Stable across spellings of the merchant and across card renewals."""
        from .rules import brand, card_class
        return f"{brand(self.merchant)}|{card_class(self.card)}"

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class Hint:
    """An outside opinion: a model, an e-invoice, a receipt that was already read.
    A hint can sharpen a question. It can never file something by itself."""
    purpose: str | None = None       # business | private
    category: str | None = None
    confidence: float = 0.0
    source: str = "model"


@dataclass
class Decision:
    action: str                      # file | ask | ignore
    purpose: str                     # business | private | unknown
    category: str
    confidence: float
    reason: str
    rule: str                        # which rule decided, for the audit trail
    needs_receipt: bool = True
    vat_rate: str = "19"
    deductible: bool | None = None

    def dict(self) -> dict:
        return asdict(self)
