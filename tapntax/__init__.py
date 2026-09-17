"""Tap n' tax: a card payment becomes one question, and one tap files it.

    from tapntax import Payment, Memory, decide, learn, message

    mem = Memory.load("memory.json")
    p = Payment("ADOBE SYSTEMS GMBH", 59.49, "Business Visa 4821")
    d = decide(p, mem)          # ask, file or ignore, with the reason
    print(message(p, d)["body"])
    learn(p, "business", mem)   # what the person answered
    mem.save()

Nothing here needs a network, a model or an account. The HTTP service in
`tapntax.server` is one way to use it, not the only one.
"""

from .classify import AUTO_LIMIT, CONFIRMATIONS_FOR_AUTO, decide, learn
from .ledger import Ledger
from .memory import Memory
from .models import Decision, Hint, Payment
from .notify import message, send_ntfy, send_webhook

__version__ = "0.1.0"
__all__ = ["Payment", "Decision", "Hint", "Memory", "Ledger", "decide", "learn",
           "message", "send_ntfy", "send_webhook", "AUTO_LIMIT",
           "CONFIRMATIONS_FOR_AUTO", "__version__"]
