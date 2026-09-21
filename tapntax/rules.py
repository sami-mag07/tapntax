"""What we know about merchants, kept in one place so it can be edited without
touching the decision logic.

Everything here is a heuristic over the merchant string a card terminal sends.
Those strings are mangled ("SUMUP *K42", "PAYPAL *STEAM", "REWE SAGT DANKE"),
so the rules stay deliberately coarse and the classifier asks whenever they do
not settle a case. Adding a name here is safe. Removing the ambiguity list is
not: it is what keeps a supermarket from ever filing itself.
"""

from __future__ import annotations

import re

# Trades where a business card makes the purpose obvious enough to stop asking
# after the user has confirmed it. Key is the category we file it under.
TRADES: dict[str, tuple[str, ...]] = {
    "software": (
        "adobe", "figma", "github", "gitlab", "notion", "slack", "linear", "openai",
        "anthropic", "jetbrains", "atlassian", "vercel", "netlify", "hetzner",
        "digitalocean", "aws", "amazon web services", "google cloud", "microsoft 365",
        "zoom", "dropbox", "1password", "sentry", "cloudflare",
    ),
    "office supplies": (
        "staples", "viking", "office discount", "buerobedarf", "burobedarf",
        "papier", "mcpaper", "idealo office",
    ),
    "hardware": (
        "apple store", "gravis", "cyberport", "notebooksbilliger", "conrad",
        "reichelt", "alternate", "mediamarkt business", "saturn business",
    ),
    "travel": (
        "db vertrieb", "deutsche bahn", "db fernverkehr", "bvg", "hvv", "mvg",
        "flixbus", "lufthansa", "eurowings", "trainline", "sixt", "europcar",
    ),
    "professional services": (
        "datev", "lexoffice", "sevdesk", "notar", "rechtsanwalt", "steuerberater",
        "ihk", "handelsregister", "bundesanzeiger",
    ),
    "education": (
        "udemy", "coursera", "pluralsight", "oreilly", "leanpub", "masterclass",
    ),
}

# Merchants whose trade says nothing about why you were there. They may be
# remembered, they may never file themselves. Frequency is not a reason.
AMBIGUOUS: tuple[str, ...] = (
    "rewe", "edeka", "lidl", "aldi", "kaufland", "netto", "penny", "norma",
    "dm ", "dm-", "rossmann", "mueller", "müller",
    "amazon", "paypal", "ebay", "etsy", "temu", "shein", "zalando", "otto",
    "sumup", "zettle", "izettle", "stripe", "vivawallet",
    "restaurant", "pizzeria", "cafe", "café", "bakery", "baeckerei", "bäckerei",
    "mcdonald", "burger", "starbucks", "kfc", "subway", "lieferando", "wolt",
    "bar ", "club", "kiosk", "spaeti", "späti",
    "hotel", "airbnb", "booking", "uber", "bolt", "freenow", "taxi",
    "shell", "aral", "esso", "total", "jet ", "tankstelle", "agip",
    "apotheke", "fitness", "gym", "netflix", "spotify", "disney", "steam",
)

# Card descriptors that hide the real merchant behind a payment processor.
# When we see one, we cannot resolve the trade at all and must ask.
OPAQUE: tuple[str, ...] = ("sumup", "zettle", "izettle", "stripe", "paypal",
                           "vivawallet", "shopify", "square")

# Reduced VAT in Germany applies to food, books, transport under 50 km and a few
# others. We only use this to pre-fill a suggestion the user can correct.
REDUCED_VAT = ("rewe", "edeka", "lidl", "aldi", "kaufland", "netto", "penny",
               "baeckerei", "bäckerei", "buch", "thalia", "hugendubel")

FULL_RATE = "19"
REDUCED_RATE = "7"


def normalise(s: str | None) -> str:
    """Lowercase, strip the noise a terminal adds, collapse whitespace."""
    s = (s or "").lower()
    s = re.sub(r"[*/#|]+", " ", s)
    s = re.sub(r"\b(gmbh|ag|kg|ohg|ug|se|e\.?k\.?|inc|ltd|bv|sarl)\b", " ", s)
    s = re.sub(r"\b(sagt danke|danke|filiale|fil|str|nr)\b", " ", s)
    s = re.sub(r"[^a-z0-9äöüß ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def trade_of(merchant: str | None) -> tuple[str, bool]:
    """Return (category, settled). settled is True only when the merchant's
    trade alone tells us what this purchase was."""
    m = f" {normalise(merchant)} "
    for category, names in TRADES.items():
        if any(f" {n.strip()} " in m or n.strip() in m for n in names):
            return category, True
    if any(a.strip() in m for a in AMBIGUOUS):
        return "", False
    return "", False


def is_opaque(merchant: str | None) -> bool:
    m = normalise(merchant)
    return any(o in m for o in OPAQUE)


def vat_hint(merchant: str | None) -> str:
    m = normalise(merchant)
    return REDUCED_RATE if any(r in m for r in REDUCED_VAT) else FULL_RATE


def looks_like_business_card(card: str | None) -> bool:
    c = normalise(card)
    return any(w in c for w in ("business", "corporate", "firmen", "geschaeft", "geschäft"))


def brand(merchant: str | None) -> str:
    """The stable part of a merchant string.

    Terminals write the same shop a dozen ways: "ADOBE", "ADOBE SYSTEMS GMBH",
    "REWE SAGT DANKE 4821", "REWE Kopenicker 122". Memory keyed on the raw string
    would learn each spelling separately and never stop asking. So we pull out a
    known name when we recognise one, and otherwise keep the first two words
    without digits, which is what survives across receipts.
    """
    m = normalise(merchant)
    if not m:
        return ""
    known = [n.strip() for names in TRADES.values() for n in names]
    known += [a.strip() for a in AMBIGUOUS]
    hits = [n for n in known if n and n in m]
    if hits:
        return max(hits, key=len)
    words = [w for w in m.split() if not w.isdigit()]
    return " ".join(words[:2])


def card_class(card: str | None) -> str:
    """Business or private. The last four digits are not part of the identity:
    a replacement card must not make the app forget everything."""
    return "business" if looks_like_business_card(card) else "private"
