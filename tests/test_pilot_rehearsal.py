import unittest
from collections import Counter
from dataclasses import replace
from random import Random

from pianwen.pilot_board import (
    MODELS, PAIRS, WEIGHTS, Judge, eligible_panels, make_schedule, paired_intervals, tabulate,
)
from pianwen.rehearsal import (
    EQUAL, FAMILIES, JUDGES, STRONG, Reading, check_work, generate,
    leave_one_family_out, missing_receipts, simulate,
)


class PilotRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.panels = eligible_panels(FAMILIES, JUDGES)

    def test_six_balanced_panels_and_independent_reverse_slots(self):
        primary, audits = make_schedule(FAMILIES, self.panels, 30, Random(8))
        self.assertEqual((len(set(primary)), len(set(audits))), (540, 54))
        counts = Counter((s.pair, s.judge, s.left) for s in primary)
        self.assertEqual(set(counts.values()), {15})
        self.assertEqual(len(counts), 36)
        self.assertEqual(set(Counter((s.pair, s.judge) for s in audits).values()), {3})
        self.assertTrue(set(audits) <= {s.reversed() for s in primary})
        for a, b in PAIRS:
            self.assertEqual({j.family for j in self.panels[a, b]}, set("ABCDX") - {a, b})

    def test_expired_or_duplicate_family_cannot_fill_an_empty_seat(self):
        judges = (*JUDGES[:-1], replace(JUDGES[-1], qualified=False), Judge("another C", "C", True))
        panels = eligible_panels(FAMILIES, judges)
        self.assertEqual([j.family for j in panels["A", "B"]], ["C", "D"])
        with self.assertRaisesRegex(ValueError, "A–B needs three"):
            make_schedule(FAMILIES, panels, 30, Random(8))

    def test_hand_scored_votes_and_fixed_weights(self):
        primary, _ = make_schedule(FAMILIES, self.panels, 2, Random(3))
        checks = [{m: dict.fromkeys(("meaning", "form", "knowledge", "pairing"), 0.0)
                   for m in MODELS} for _ in range(2)]
        # A wins every comparison involving A, including when it is on the
        # right. All other opponents tie. B's second item earns all form points.
        votes = {s: ("left" if s.left == "A" else "right") if "A" in s.pair else "tie" for s in primary}
        checks[1]["B"]["form"] = 1.0
        result = tabulate(checks, primary, votes, FAMILIES)
        self.assertEqual(WEIGHTS, {"meaning": 30, "form": 20, "knowledge": 15, "pairing": 10, "taste": 25})
        self.assertAlmostEqual(result["primary_scores"]["A"], 25)
        self.assertAlmostEqual(result["primary_scores"]["B"], 25 / 3 + 10)
        self.assertAlmostEqual(result["primary_scores"]["C"], 25 / 3)
        self.assertEqual(result["head_to_head"]["A-B"]["wins"], 6)

        slot = next(s for s in primary if s.pair == ("A", "B") and s.item == 0)
        del votes[slot]
        slot2 = next(s for s in primary if s.pair == ("C", "D") and s.item == 0)
        votes[slot2] = "insufficient"
        missing = tabulate(checks, primary, votes, FAMILIES)
        ab, cd = (missing["head_to_head"][key] for key in ("A-B", "C-D"))
        self.assertEqual((ab["wins"], ab["losses"], ab["missing"]), (5, 0, 1))
        self.assertEqual((cd["ties"], cd["insufficient"], cd["missing"]), (5, 1, 0))
        self.assertIsNone(missing["primary_scores"])
        self.assertEqual(missing["rows"], {1: result["rows"][1]})

    def test_out_of_family_rule_checked_again_at_scoring(self):
        trial = simulate(6, STRONG)
        original = trial.primary[0]
        replacements = [
            replace(original, judge=Judge("wrong family", original.pair[0], True)),
            replace(original, judge=replace(original.judge, qualified=False)),
            original.reversed(),
        ]
        for slot in replacements:
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                replace(trial, primary=[slot, *trial.primary[1:]]).score()
        ledger = (1, -1) * 4
        work = generate(ledger, 0.8, 0, 0, Random(0))
        with self.assertRaisesRegex(ValueError, "outside the author family"):
            check_work(work, Reading(JUDGES[0], work.relations), ledger, "A")

    def test_reverse_answers_never_repair_or_reweight_primary_outcomes(self):
        trial = simulate(6, STRONG)
        original = trial.score()
        primary_only = {s: trial.replies[s] for s in trial.primary}
        self.assertEqual(replace(trial, replies=primary_only).score(), original)
        failures = missing_receipts(trial)
        votes = failures["missing_primary_tenth"]
        self.assertEqual(sum(r["missing"] for r in votes["head_to_head"].values()), 54)
        self.assertEqual(sum(r["scorable"] for r in votes["head_to_head"].values()), 486)
        work = failures["missing_work"]
        self.assertEqual(work["complete_items"], 29)
        self.assertEqual(work["unavailable_primary_verdicts"], 9)
        self.assertEqual(work["head_to_head"]["C-D"], original["head_to_head"]["C-D"])

    def test_bootstrap_repeats_both_twins_together(self):
        rows = {0: {"A": 80, "B": 40}, 1: {"A": 40, "B": 80}}
        ci = paired_intervals(rows, [0, 0], [("A", "B")], 42)
        self.assertEqual(ci["A", "B"], (0.0, 0.0))
        independent = paired_intervals(rows, [0, 1], [("A", "B")], 42)
        self.assertEqual(independent["A", "B"], (-40.0, 40.0))

    def test_model_labels_do_not_determine_ranks_and_style_probe_flips(self):
        scores = simulate(10, STRONG[::-1]).score()["primary_scores"]
        self.assertEqual(sorted(MODELS, key=scores.get, reverse=True), list("DCBA"))
        probe = leave_one_family_out(simulate(0, EQUAL, style_probe=True))
        self.assertAlmostEqual(probe["all"]["A_minus_B"], 25 / 27)
        self.assertAlmostEqual(probe["X"]["A_minus_B"], -25 / 9)
        self.assertEqual(probe["X"]["status"], "sensitivity_only")
        self.assertEqual(len(probe["X"]["pairs_below_three"]), 6)


if __name__ == "__main__":
    unittest.main()
