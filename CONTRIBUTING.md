# Contributing

The useful contributions, in the order they help most:

1. **Merchant knowledge.** `tapntax/rules.py` is a list of names. Adding the shops,
   processors and trades of your own country is the highest value change anyone can
   make, and it needs no understanding of the rest.
2. **A second country's tax rules.** The thresholds, the VAT rates and the
   self-written voucher rules in `README.md` are German. The structure is not: a
   country module with its own limits would generalise it.
3. **Storage and notification backends.** `Memory` is four methods and `notify` is
   two senders. Postgres, Redis, APNs and Firebase all fit behind them.

Keep it dependency free. The point of this library is that anyone can vendor one
folder into an existing app without a supply chain conversation.

Tests: `python3 -m unittest discover -s tests -t .` Everything under
`RulesThatMustNotBend` in `tests/test_classify.py` is the specification. Changing one
of those is a product decision, not a refactor, so say why in the pull request.
