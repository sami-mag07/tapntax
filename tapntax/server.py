"""A small HTTP service around the library. Standard library only, so it runs
with `python3 -m tapntax.server` and deploys anywhere that can run Python.

Access: the entries are somebody's spending, so the service refuses to listen on
a public address without a token. Set `TAPNTAX_TOKEN` and send it as
`Authorization: Bearer <token>`. With no token set it binds to localhost only,
which is the right default for a phone on the same Wi-Fi through a tunnel.

    POST /v1/payment    a card payment happened      -> decision + notification
    POST /v1/answer     the person answered          -> learns, updates the entry
    POST /v1/receipt    a receipt was attached
    POST /v1/revoke     take an automatic entry back
    GET  /v1/entries    everything filed so far
    GET  /v1/week       the Friday summary
    GET  /v1/memory     what it has learned, in plain words
    GET  /v1/health

Nothing here is Taxfix specific. Point `TAPNTAX_WEBHOOK` at your own backend and
every decision is posted to you as well.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .classify import decide, learn
from .ledger import Ledger
from .memory import Memory
from .models import Hint, Payment
from .notify import message, send_ntfy, send_webhook, shortcut_response

STATE = os.environ.get("TAPNTAX_STATE", ".tapntax")
LANG = os.environ.get("TAPNTAX_LANG", "de")
RATE = float(os.environ.get("TAPNTAX_RATE", "0.42"))
NTFY = os.environ.get("TAPNTAX_NTFY_TOPIC", "")
HOOK = os.environ.get("TAPNTAX_WEBHOOK", "")
TOKEN = os.environ.get("TAPNTAX_TOKEN", "").strip()
# No wildcard. A browser page on any origin must not be able to read somebody's
# expenses, so cross origin access is off until you name the one page you serve.
ORIGIN = os.environ.get("TAPNTAX_ORIGIN", "").strip()
MAX_BODY = 64 * 1024

memory = Memory.load(f"{STATE}/memory.json")
ledger = Ledger(f"{STATE}/ledger.json")


def handle_payment(body: dict) -> dict:
    payment = Payment(
        merchant=str(body.get("merchant", "")), amount=float(body.get("amount") or 0),
        card=str(body.get("card", "")), currency=str(body.get("currency", "EUR")),
        mcc=body.get("mcc"), source=str(body.get("source", "wallet")))
    if body.get("ts"):
        payment.ts = str(body["ts"])
    hint = None
    if isinstance(body.get("hint"), dict):
        h = body["hint"]
        hint = Hint(purpose=h.get("purpose"), category=h.get("category"),
                    confidence=float(h.get("confidence") or 0),
                    source=str(h.get("source", "model")))

    decision = decide(payment, memory, hint)
    entry = None
    if decision.action != "ignore":
        entry = ledger.add(payment, decision, "model" if hint and decision.rule == "first.hint" else "rule")
    if decision.action == "file":
        memory.note_auto(payment.key())
        memory.save()

    msg = message(payment, decision, LANG)
    if msg["send"] and NTFY:
        send_ntfy(msg, NTFY)
    if msg["send"] and HOOK:
        send_webhook(msg, HOOK, {"entry": entry, "decision": decision.dict()})

    return {"decision": decision.dict(), "entry": entry,
            "notification": msg, "shortcut": shortcut_response(msg)}


def handle_answer(body: dict) -> dict:
    entry_id = int(body.get("id") or 0)
    answer = str(body.get("answer", "")).lower()
    entry = ledger.get(entry_id)
    if not entry:
        return {"error": f"no entry {entry_id}"}
    payment = Payment(merchant=entry["merchant"], amount=entry["amount"], card=entry["card"])
    category = body.get("category") or entry.get("category")
    if answer in ("business", "private"):
        learn(payment, answer, memory, category)
        memory.save()
        ledger.answer(entry_id, answer, category)
    return {"entry": ledger.get(entry_id), "learned": memory.get(payment.key())}


def handle_revoke(body: dict) -> dict:
    entry = ledger.revoke(int(body.get("id") or 0))
    if entry:
        memory.revoke(entry["key"])
        memory.save()
    return {"entry": entry, "learned": memory.get(entry["key"]) if entry else None}


def plain_memory() -> list[dict]:
    """What it learned, as sentences a person can check."""
    out = []
    for key, e in memory.data["merchants"].items():
        name, card = key.split("|", 1)
        state = ("files itself" if e["count"] >= 2 and e["purpose"] == "business"
                 else "still asking")
        out.append({"merchant": name, "card": card, "purpose": e["purpose"],
                    "confirmations": e["count"], "category": e.get("category"),
                    "state": state, "auto_filed": e.get("auto_filed", 0),
                    "revoked": e.get("revoked", 0)})
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "tapntax"

    def _send(self, code: int, payload) -> None:
        data = json.dumps(payload, indent=1, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorised(self) -> bool:
        """Constant time, so a wrong token tells an attacker nothing by timing."""
        if not TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        sent = header[7:] if header.lower().startswith("bearer ") else ""
        return hmac.compare_digest(sent, TOKEN)

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return None
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = urlparse(self.path).path
        if path != "/v1/health" and not self._authorised():
            return self._send(401, {"error": "missing or wrong bearer token"})
        if path == "/v1/health":
            return self._send(200, {"ok": True, "learned": len(memory),
                                    "entries": len(ledger.entries)})
        if path == "/v1/entries":
            return self._send(200, {"entries": ledger.entries})
        if path == "/v1/week":
            return self._send(200, ledger.week(rate=RATE))
        if path == "/v1/memory":
            return self._send(200, {"merchants": plain_memory()})
        return self._send(404, {"error": f"no route {path}"})

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._authorised():
            return self._send(401, {"error": "missing or wrong bearer token"})
        try:
            body = self._read_body()
            if body is None:
                return self._send(413, {"error": "body too large"})
        except ValueError:
            return self._send(400, {"error": "body must be JSON"})
        try:
            if path == "/v1/payment":
                return self._send(200, handle_payment(body))
            if path == "/v1/answer":
                return self._send(200, handle_answer(body))
            if path == "/v1/receipt":
                return self._send(200, {"entry": ledger.attach_receipt(
                    int(body.get("id") or 0), str(body.get("status", "ok")),
                    body.get("ref"))})
            if path == "/v1/revoke":
                return self._send(200, handle_revoke(body))
            return self._send(404, {"error": f"no route {path}"})
        except (ValueError, TypeError, KeyError) as e:
            return self._send(400, {"error": f"refused: {e}"})

    def log_message(self, fmt, *args):
        sys.stderr.write(f"  {self.command} {self.path}\n")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8799))
    bind = os.environ.get("TAPNTAX_BIND", "" if TOKEN else "127.0.0.1")
    if not TOKEN and bind not in ("127.0.0.1", "localhost", "::1"):
        sys.exit("refusing to listen on " + bind + " without TAPNTAX_TOKEN: "
                 "/v1/entries is somebody's spending. Set a token, or bind to 127.0.0.1 "
                 "and reach it through a tunnel.")
    host = bind or "0.0.0.0"
    print(f"tapntax on http://{host}:{port}  state in {STATE}/"
          f"  auth {'bearer token' if TOKEN else 'none, localhost only'}"
          f"  cors {ORIGIN or 'off'}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
