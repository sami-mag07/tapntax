"""The text on the lock screen, and the ways to get it there.

The notification is the product. It arrives while the receipt is still in the
person's hand, which is the only moment it exists, so it has to say the amount,
what we think it was, and what one tap will do. No emoji, no exclamation marks,
no "we noticed you spent". Two languages, because the phone has a language and
the tax office has a country.
"""

from __future__ import annotations

import json
import urllib.request

from .models import Decision, Payment

TEXT = {
    "de": {
        "ask_business": "{amount} bei {merchant}. Sieht nach {category} aus. Als Betriebsausgabe buchen?",
        "ask_unknown": "{amount} bei {merchant}. War das geschäftlich?",
        "filed": "{amount} bei {merchant} als {category} gebucht. Beleg fotografieren.",
        "filed_done": "{amount} bei {merchant} als {category} gebucht.",
        "receipt": "Beleg fehlt noch für {merchant}, {amount}.",
        "week": "Diese Woche {count} Ausgaben gebucht, {total}. Geschätzte Steuerwirkung {effect}.",
    },
    "en": {
        "ask_business": "{amount} at {merchant}. Looks like {category}. File as a business expense?",
        "ask_unknown": "{amount} at {merchant}. Was this for work?",
        "filed": "{amount} at {merchant} filed as {category}. Photograph the receipt.",
        "filed_done": "{amount} at {merchant} filed as {category}.",
        "receipt": "Still missing the receipt for {merchant}, {amount}.",
        "week": "{count} expenses filed this week, {total}. Estimated tax effect {effect}.",
    },
}


def money(amount: float, currency: str = "EUR", lang: str = "de") -> str:
    s = f"{abs(float(amount)):,.2f}"
    if lang == "de":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} {'€' if currency == 'EUR' else currency}"
    return f"{'€' if currency == 'EUR' else currency} {s}"


def display_name(merchant: str | None) -> str:
    """What the person calls the shop. The terminal string is noise: they know
    Adobe, not ADOBE SYSTEMS GMBH, and they know REWE, not REWE SAGT DANKE 4821."""
    from .rules import brand
    name = brand(merchant) or (merchant or "")
    return " ".join(w.upper() if len(w) <= 3 else w.capitalize() for w in name.split())


def message(payment: Payment, decision: Decision, lang: str = "de") -> dict:
    """Title, body and the buttons the notification should carry."""
    t = TEXT.get(lang, TEXT["de"])
    amount = money(payment.amount, payment.currency, lang)
    merchant = display_name(payment.merchant)
    fields = {"amount": amount, "merchant": merchant, "category": decision.category}

    if decision.action == "ignore":
        return {"send": False, "title": "", "body": "", "actions": []}
    if decision.action == "file":
        key = "filed" if decision.needs_receipt else "filed_done"
        actions = (["receipt", "undo"] if decision.needs_receipt else ["undo"])
        return {"send": True, "title": "Tap n' tax", "body": t[key].format(**fields),
                "actions": actions, "decision": decision.action}
    key = "ask_business" if decision.category != "other" else "ask_unknown"
    return {"send": True, "title": "Tap n' tax", "body": t[key].format(**fields),
            "actions": ["business", "private", "receipt"], "decision": decision.action}


# --------------------------------------------------------------------- senders
# A sender takes the message dict and puts it on a screen. The Shortcut path
# needs none of these: the automation shows whatever the server answered. These
# exist for the server-driven case, where the payment arrives from a bank feed
# and nothing is running on the phone.

def shortcut_response(msg: dict) -> dict:
    """What the iPhone automation reads straight out of the HTTP response."""
    return {"notification": msg.get("body", ""), "actions": msg.get("actions", [])}


def send_ntfy(msg: dict, topic: str, server: str = "https://ntfy.sh") -> bool:
    """ntfy.sh: a topic is a URL, the phone app subscribes, no account needed.
    Good enough for a pilot, and the topic name is the only secret, so use a long
    random one and treat it as one."""
    if not msg.get("send"):
        return False
    req = urllib.request.Request(
        f"{server.rstrip('/')}/{topic}", data=msg["body"].encode("utf-8"),
        headers={"Title": msg.get("title", "Tap n' tax"), "Priority": "default"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300
    except OSError:
        return False


def send_webhook(msg: dict, url: str, extra: dict | None = None) -> bool:
    """Anything else: your own push service, APNs behind your backend, Slack."""
    if not msg.get("send"):
        return False
    body = json.dumps({**msg, **(extra or {})}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300
    except OSError:
        return False
