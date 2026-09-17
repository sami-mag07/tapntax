"""Three payments, start to finish. Run it: python3 examples/quickstart.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tapntax import Ledger, Memory, Payment, decide, learn, message   # noqa: E402

memory, ledger = Memory(), Ledger()


def pay(merchant, amount, card="Business Visa •• 4821", answer=None):
    p = Payment(merchant, amount, card)
    d = decide(p, memory)
    print(f"\n{merchant} {amount:.2f}")
    print(f"  -> {d.action}: {d.reason}")
    msg = message(p, d)
    if msg["send"]:
        print(f"  push: {msg['body']}")
        print(f"  buttons: {', '.join(msg['actions'])}")
    entry = ledger.add(p, d, "rule") if d.action != "ignore" else None
    if answer and entry:
        learn(p, answer, memory, d.category if d.category != "other" else None)
        ledger.answer(entry["id"], answer)
        print(f"  you answered: {answer}")
    return entry


pay("ADOBE SYSTEMS GMBH", 59.49, answer="business")
pay("Adobe", 59.49, answer="business")
pay("ADOBE SYSTEMS", 59.49)                       # now it files itself
pay("ADOBE", 890.00)                              # too big, asks anyway
pay("REWE SAGT DANKE 4821", 38.40, answer="business")
pay("REWE Köpenicker 122", 41.10, answer="business")
pay("REWE", 39.00)                                # still asks, and always will
pay("REWE Köpenicker 122", 21.30, card="Visa 1111")   # private card, no push

week = ledger.week()
print(f"\nFriday: {week['filed']} filed, {week['total']:.2f} EUR, "
      f"estimated effect {week['estimated_effect']:.2f} EUR at {week['rate_used']:.0%}")
print(f"missing receipts: {len(week['missing_receipts'])}")
