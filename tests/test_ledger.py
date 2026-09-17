"""The ledger is the audit trail. It has to say who decided what, and it has to
let a person take an automatic entry back."""

import unittest

from tapntax import Ledger, Memory, Payment, decide

P = Payment("ADOBE SYSTEMS GMBH", 59.49, "Business Visa 4821")


class Entries(unittest.TestCase):
    def setUp(self):
        self.led = Ledger()
        self.d = decide(P, Memory())

    def test_an_entry_records_who_decided_it(self):
        e = self.led.add(P, self.d, "rule")
        self.assertEqual(e["decided_by"], "rule")
        self.assertTrue(e["rule"])

    def test_answering_makes_it_the_persons_decision(self):
        e = self.led.add(P, self.d, "rule")
        self.led.answer(e["id"], "business", "software")
        self.assertEqual(self.led.get(e["id"])["decided_by"], "person")

    def test_a_private_answer_unfiles_it(self):
        e = self.led.add(P, self.d, "rule")
        self.led.answer(e["id"], "private")
        self.assertFalse(self.led.get(e["id"])["filed"])

    def test_revoking_removes_it_from_the_file(self):
        e = self.led.add(P, self.d, "rule")
        self.led.answer(e["id"], "business")
        self.led.revoke(e["id"])
        self.assertEqual(self.led.filed(), [])

    def test_receipts_start_missing_and_can_be_attached(self):
        e = self.led.add(P, self.d, "rule")
        self.led.answer(e["id"], "business")
        self.assertEqual(len(self.led.missing_receipts()), 1)
        self.led.attach_receipt(e["id"], "ok", "IMG_0042")
        self.assertEqual(self.led.missing_receipts(), [])


class WeeklySummary(unittest.TestCase):
    def test_the_effect_is_the_rate_not_the_amount(self):
        led = Ledger()
        e = led.add(P, decide(P, Memory()), "rule")
        led.answer(e["id"], "business")
        week = led.week(rate=0.42)
        self.assertEqual(week["total"], 59.49)
        self.assertAlmostEqual(week["estimated_effect"], round(59.49 * 0.42, 2))
        self.assertNotEqual(week["estimated_effect"], week["total"])

    def test_the_summary_lists_what_was_filed_without_asking(self):
        led = Ledger()
        mem = Memory()
        for _ in range(2):
            mem.record(P.key(), "business", 59.49, "software")
        led.add(P, decide(P, mem), "rule")
        self.assertEqual(len(led.week()["automatic"]), 1)


if __name__ == "__main__":
    unittest.main()
