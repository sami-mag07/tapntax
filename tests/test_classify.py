"""The rules that must not bend. If one of these goes red, the product is wrong,
not the test."""

import unittest

from tapntax import Memory, Payment, decide, learn
from tapntax.classify import AUTO_LIMIT
from tapntax.models import Hint

SOFTWARE = Payment("ADOBE SYSTEMS GMBH", 59.49, "Business Visa •• 4821")
SHOP = Payment("REWE SAGT DANKE 4821", 38.40, "Business Visa •• 4821")
GROCERIES = Payment("REWE Köpenicker 122", 21.30, "Visa 1111")
OPAQUE = Payment("SUMUP *K42", 24.00, "Business Visa •• 4821")


def confirmed(payment, times=2, category=None):
    mem = Memory()
    for _ in range(times):
        learn(payment, "business", mem, category)
    return mem


class FirstSight(unittest.TestCase):
    def test_business_card_and_clear_trade_asks_once(self):
        d = decide(SOFTWARE, Memory())
        self.assertEqual(d.action, "ask")
        self.assertEqual(d.category, "software")

    def test_private_card_at_an_ambiguous_merchant_never_interrupts(self):
        self.assertEqual(decide(GROCERIES, Memory()).action, "ignore")

    def test_a_payment_processor_is_always_a_question(self):
        d = decide(OPAQUE, Memory())
        self.assertEqual(d.action, "ask")
        self.assertEqual(d.purpose, "unknown")

    def test_no_memory_at_all_still_answers(self):
        self.assertIn(decide(SOFTWARE).action, ("ask", "ignore", "file"))


class Learning(unittest.TestCase):
    def test_two_confirmations_stop_the_question(self):
        d = decide(SOFTWARE, confirmed(SOFTWARE, 2, "software"))
        self.assertEqual(d.action, "file")
        self.assertEqual(d.rule, "memory.confirmed")

    def test_one_confirmation_is_not_enough(self):
        self.assertEqual(decide(SOFTWARE, confirmed(SOFTWARE, 1)).action, "ask")

    def test_a_different_spelling_hits_the_same_memory(self):
        mem = confirmed(SOFTWARE, 2, "software")
        self.assertEqual(decide(Payment("ADOBE", 59.49, "Business Visa 7788"), mem).action, "file")

    def test_marked_private_means_no_more_pushes(self):
        mem = Memory()
        learn(SOFTWARE, "private", mem)
        self.assertEqual(decide(SOFTWARE, mem).action, "ignore")

    def test_changing_the_answer_starts_over(self):
        mem = confirmed(SOFTWARE, 2, "software")
        learn(SOFTWARE, "private", mem)
        self.assertEqual(mem.get(SOFTWARE.key())["count"], 1)

    def test_revoking_sends_the_merchant_back_to_questions(self):
        mem = confirmed(SOFTWARE, 2, "software")
        mem.revoke(SOFTWARE.key())
        self.assertEqual(decide(SOFTWARE, mem).action, "ask")


class RulesThatMustNotBend(unittest.TestCase):
    def test_frequency_never_files_an_ambiguous_merchant(self):
        mem = confirmed(SHOP, 10)
        d = decide(SHOP, mem)
        self.assertEqual(d.action, "ask")
        self.assertEqual(d.rule, "guard.ambiguous")

    def test_nothing_over_the_limit_files_itself(self):
        mem = confirmed(SOFTWARE, 5, "software")
        big = Payment("ADOBE", AUTO_LIMIT + 0.01, "Business Visa 4821")
        self.assertEqual(decide(big, mem).rule, "guard.amount")

    def test_an_outlier_asks_again(self):
        mem = confirmed(SOFTWARE, 5, "software")
        big = Payment("ADOBE", 59.49 * 3, "Business Visa 4821")
        self.assertEqual(decide(big, mem).rule, "guard.outlier")

    def test_a_hint_can_sharpen_a_question_but_never_files(self):
        hint = Hint(purpose="business", category="software", confidence=0.99, source="receipt")
        d = decide(Payment("Kleine Agentur", 40.0, "Visa 1111"), Memory(), hint)
        self.assertEqual(d.action, "ask")

    def test_every_decision_carries_a_reason_and_a_rule(self):
        for p in (SOFTWARE, SHOP, GROCERIES, OPAQUE):
            d = decide(p, Memory())
            self.assertTrue(d.reason and d.rule)

    def test_a_broken_payment_becomes_a_question_not_a_crash(self):
        d = decide(Payment("", 0, ""), Memory())
        self.assertIn(d.action, ("ask", "ignore"))


class Money(unittest.TestCase):
    def test_a_refund_is_read_as_its_amount(self):
        mem = confirmed(SOFTWARE, 2, "software")
        self.assertEqual(decide(Payment("ADOBE", -59.49, "Business Visa 4821"), mem).action, "file")

    def test_groceries_get_the_reduced_vat_hint(self):
        self.assertEqual(decide(SHOP, Memory()).vat_rate, "7")

    def test_software_gets_the_full_rate(self):
        self.assertEqual(decide(SOFTWARE, Memory()).vat_rate, "19")


if __name__ == "__main__":
    unittest.main()
