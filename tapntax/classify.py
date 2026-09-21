"""The decision: what should happen when a card payment arrives.

One function, no I/O, no network. Give it a payment and the memory, get back an
action with the reason it chose. The reason is not decoration: it is what the
weekly list shows the user and what an auditor reads two years later.

    file    put it in the tax file without asking. Only for merchants the user
            has confirmed repeatedly, whose trade is unambiguous, at an amount
            in line with the ones before.
    ask     show the question. The default whenever anything is unclear.
    ignore  do not interrupt at all. A private card at a merchant that says
            nothing about the reason is somebody buying milk.

The rules that must not bend, in order of importance:

1. Frequency is never a reason on its own. Ten visits to a supermarket are
   evidence of groceries, not of business, so ambiguous merchants never reach
   `file` no matter how often they were confirmed.
2. Nothing above AUTO_LIMIT files itself. Large amounts are where mistakes hurt.
3. An amount far off the ones seen before asks again.
4. An outside hint (a model, an e-invoice) can sharpen a question. It can never
   turn `ask` into `file`. Only a human's repeated answer does that.
"""

from __future__ import annotations

from .models import Decision, Hint, Payment
from .rules import is_opaque, looks_like_business_card, trade_of, vat_hint

CONFIRMATIONS_FOR_AUTO = 2      # answers the same way before we stop asking
AUTO_LIMIT = 250.0              # never file more than this without a human
OUTLIER_FACTOR = 2.5            # this far above the usual amount asks again
HINT_THRESHOLD = 0.7            # below this a hint is not worth showing


def decide(payment: Payment, memory=None, hint: Hint | None = None) -> Decision:
    """Never raises. An unreadable payment becomes a question, not a crash."""
    amount = abs(float(payment.amount or 0))
    category, settled = trade_of(payment.merchant)
    opaque = is_opaque(payment.merchant)
    business_card = looks_like_business_card(payment.card)
    vat = vat_hint(payment.merchant)
    known = memory.get(payment.key()) if memory else None

    if hint and hint.confidence >= HINT_THRESHOLD and hint.category and not category:
        category = hint.category

    # ------------------------------------------------ what we already learned
    if known:
        purpose = known["purpose"]
        count = known.get("count", 0)
        category = known.get("category") or category
        usual = memory.typical(payment.key()) or amount

        if purpose == "private":
            return Decision("ignore", "private", category or "other", 0.9,
                            "you have marked this merchant private before",
                            "memory.private", needs_receipt=False, vat_rate=vat,
                            deductible=False)
        if count < CONFIRMATIONS_FOR_AUTO:
            return Decision("ask", purpose, category or "other", 0.65,
                            f"answered this way {count} time(s), one more to be sure",
                            "memory.learning", vat_rate=vat)
        if opaque or not settled:
            return Decision("ask", purpose, category or "other", 0.7,
                            "this merchant sells both, so the reason is yours to give",
                            "guard.ambiguous", vat_rate=vat)
        if amount > AUTO_LIMIT:
            return Decision("ask", purpose, category or "other", 0.8,
                            f"over the {AUTO_LIMIT:.0f} {payment.currency} limit for filing without asking",
                            "guard.amount", vat_rate=vat)
        if amount > usual * OUTLIER_FACTOR:
            return Decision("ask", purpose, category or "other", 0.7,
                            f"larger than the {usual:.2f} {payment.currency} you usually spend here",
                            "guard.outlier", vat_rate=vat)
        return Decision("file", purpose, category or "other", 0.95,
                        f"filed the same way {count} times, amount is in range",
                        "memory.confirmed", vat_rate=vat,
                        deductible=(purpose == "business"))

    # ----------------------------------------------------- first time we see it
    if opaque:
        return Decision("ask", "unknown", category or "other", 0.4,
                        "the terminal hides the merchant behind a payment processor",
                        "first.opaque", vat_rate=vat)
    if business_card and settled:
        return Decision("ask", "business", category, 0.85,
                        "business card and the merchant's trade matches, confirm once",
                        "first.card_and_trade", vat_rate=vat)
    if business_card:
        return Decision("ask", "business", category or "other", 0.6,
                        "business card, but this merchant sells both",
                        "first.card_only", vat_rate=vat)
    if settled:
        return Decision("ask", "business", category, 0.5,
                        "the trade looks like business, the card does not",
                        "first.trade_only", vat_rate=vat)
    if hint and hint.purpose and hint.confidence >= HINT_THRESHOLD:
        return Decision("ask", hint.purpose, category or "other", hint.confidence,
                        f"{hint.source} thinks this is {hint.purpose}, confirm once",
                        "first.hint", vat_rate=vat)
    return Decision("ignore", "private", category or "other", 0.6,
                    "private card at a merchant that says nothing about the reason",
                    "first.nothing", needs_receipt=False, vat_rate=vat)


def learn(payment: Payment, answer: str, memory, category: str | None = None) -> dict:
    """Record what the user answered. `answer` is business, private or skip."""
    if answer not in ("business", "private", "skip"):
        raise ValueError("answer must be business, private or skip")
    if answer == "skip":
        return {}
    return memory.record(payment.key(), answer, abs(float(payment.amount or 0)), category)
