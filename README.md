# Tap n' tax

A card payment arrives. One second later the phone asks one question, and one tap
files the expense. Answer the same way twice and it stops asking for that merchant.

That is the whole product. This repository is the part worth sharing: the decision,
the memory, the notification text and a small server around them. No dependencies,
no account, no model. Standard library Python, one folder you can copy into an
existing app.

```python
from tapntax import Payment, Memory, decide, learn, message

mem = Memory.load("memory.json")
payment = Payment("ADOBE SYSTEMS GMBH", 59.49, "Business Visa 4821")

d = decide(payment, mem)
print(d.action, d.reason)        # ask, business card and the merchant's trade matches
print(message(payment, d)["body"])
# 59,49 € bei Adobe. Sieht nach software aus. Als Betriebsausgabe buchen?

learn(payment, "business", mem, "software")   # what the person answered
mem.save()
```

After two confirmations the same payment comes back as `file`, with the reason
`filed the same way 2 times, amount is in range`.

## Why a card payment and not a receipt scan

The receipt exists for about ninety seconds. It is in your hand at the counter and
gone by the time you are home, which is why expense apps are full of blurred photos
taken three weeks late. The card payment is the only event that happens at exactly
the right moment, so it is the trigger, and the question rides on it.

On iPhone this needs no app at all: Shortcuts has a Wallet automation that fires on
every Apple Pay payment and can POST to a URL. See [examples/shortcut.md](examples/shortcut.md).
For a production system the same events come from the bank over PSD2, which also
carries the merchant category code and settles cases the phone cannot.

## The four rules that do not bend

A wrong automatic entry is worse than a question, because the person signs the
return, not the software.

1. **Frequency is never a reason.** Ten visits to a supermarket are evidence of
   groceries, not of business. Merchants whose trade says nothing about why you were
   there never file themselves, however often they are confirmed. The list lives in
   `rules.py` and is meant to be edited.
2. **Nothing large files itself.** Above `AUTO_LIMIT` (250 by default) a human
   always answers.
3. **An unusual amount asks again.** Far above the median for that merchant, and the
   question comes back.
4. **An outside opinion can sharpen a question, never file one.** A model, an
   e-invoice or an already read receipt comes in as a `Hint`. Only a person's
   repeated answer turns a question into an automatic entry.

Every decision carries `rule`, `reason` and `confidence`, and every entry records
whether a rule, a model or a person decided it. Anything filed automatically shows
up in the weekly summary and can be revoked with one call, which resets the memory
for that merchant.

## What it deliberately does not do

- It does not decide your taxes. It proposes a category and a purpose. The person
  confirms, and their answer always wins.
- It does not claim input tax. VAT deduction needs the seller's invoice, and a card
  charge is not one. The library tracks which entries still have no receipt so you
  can chase them; it never pretends the charge is enough.
- It does not turn the amount into a saving. A deductible euro is worth your
  marginal rate, not its face value. `Ledger.week()` returns `estimated_effect` with
  the rate it used, and says in the payload that it is an estimate.
- It does not send your data anywhere. Memory is a JSON file you can read by hand.
  Notifications go only where you point them.

## Run the server

```
python3 -m tapntax.server 8799
```

| Call | What it does |
|---|---|
| `POST /v1/payment` | a payment happened. Returns the decision, the entry and the notification text |
| `POST /v1/answer` | `{id, answer: business\|private, category?}`, learns and updates the entry |
| `POST /v1/receipt` | `{id, status, ref?}` attach a receipt |
| `POST /v1/revoke` | `{id}` take an automatic entry back, and unlearn the merchant |
| `GET /v1/entries` | everything recorded |
| `GET /v1/week` | the Friday summary, with the estimated effect |
| `GET /v1/memory` | what it has learned, in sentences a person can check |
| `GET /v1/health` | |

Environment: `TAPNTAX_STATE` (default `.tapntax`), `TAPNTAX_LANG` (`de` or `en`),
`TAPNTAX_RATE` (marginal rate for the weekly estimate, default `0.42`),
`TAPNTAX_NTFY_TOPIC`, `TAPNTAX_WEBHOOK`.

The response to `POST /v1/payment` contains a `shortcut` object with just
`notification` and `actions`, so an iPhone automation can read it with no parsing.

## Build it into an existing app

Three seams, in the order you probably want them:

1. **Replace the trigger.** Anything that yields merchant, amount and card works:
   a bank feed, a webhook from your card issuer, a CSV import. `Payment.source`
   records where it came from.
2. **Replace the memory.** `Memory` is a thin wrapper over a dict with four methods
   (`get`, `record`, `revoke`, `typical`). Back it with your own store by keeping the
   same four.
3. **Replace the notification.** `notify.message()` returns title, body and the
   buttons. Feed that to APNs, to your own push service, or return it to a Shortcut.
   `send_ntfy` and `send_webhook` are there so a pilot needs no infrastructure.

The classifier itself is pure: `decide(payment, memory, hint)` does no I/O and never
raises. That is deliberate, so it can run on a device, in a queue worker, or inside a
test suite without anything around it.

## Tests

```
python3 -m unittest discover -s tests -t .
```

26 tests, and the ones under `RulesThatMustNotBend` are the specification. If one of
those goes red the product is wrong, not the test.

## Status and licence

Version 0.1.0, built at the Cursor Berlin hackathon at Taxfix on 17 September 2026 by
Sami Magdouli and Malek. MIT licence, so take it, fork it, ship it.

This is software, not tax advice. The rules encoded here follow German practice as
of 2026 and the thresholds are defaults, not law. Have someone qualified check the
numbers before anyone files anything real.
