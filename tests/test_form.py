import unittest

from pianwen.form import evaluate_form


LEVEL = {"id": "level", "pingze": "平", "rhyme": "下平聲七陽"}
OBLIQUE = {"id": "oblique", "pingze": "仄", "rhyme": "去聲二十三漾"}


def word(*candidates, selected=None):
    return {"char": "望", "candidates": list(candidates), "selected": selected}


def rule(line=1, position="end", **constraints):
    return {"line": line, "position": position, **constraints}


def counts(report):
    return report["denominator"], report["lower"], report["upper"]


class TestFormEvidence(unittest.TestCase):
    def test_lan_follows_the_declared_edition_and_keeps_original_evidence(self):
        old = {"pingze": "平", "rhyme": "上平聲十四寒"}
        for char in ("斓", "斕"):
            for candidates in ([old], []):
                with self.subTest(char=char, candidates=candidates):
                    annotation = {"char": char, "candidates": candidates, "selected": old if candidates else None}
                    slots = [rule(rhyme_group="上平聲十五刪"), rule(position=1, rhyme_group="上平聲十四寒")]
                    report = evaluate_form(slots, [[annotation]])
                    accepted, rejected = report["slots"]
                    self.assertEqual(counts(accepted), (1, 1, 1))
                    self.assertEqual(counts(rejected), (1, 0, 0))
                    self.assertEqual(accepted["observed"], annotation)
                    self.assertEqual(accepted["reading_status"], "edition_ruling")
                    self.assertEqual(accepted["edition_reading"]["rhyme_group"], "上平聲十五刪")
                    self.assertEqual(bool(report["dictionary_gaps"]), not candidates)

    def test_context_takes_precedence_over_another_possible_reading(self):
        slots = [rule(tone="平", rhyme_group=LEVEL["rhyme"], character="望")]
        report = evaluate_form(slots, [[word(LEVEL, OBLIQUE, selected=OBLIQUE)]])
        self.assertEqual(counts(report), (1, 0, 0))
        self.assertEqual(counts(report["axes"]["character"]), (1, 1, 1))
        self.assertEqual(report["slots"][0]["reading_status"], "context_reviewed")

    def test_axes_can_be_individually_possible_but_jointly_impossible(self):
        slots = [rule(tone="平", rhyme_group=OBLIQUE["rhyme"])]
        report = evaluate_form(slots, [[word(LEVEL, OBLIQUE)]])
        self.assertEqual(counts(report), (1, 0, 0))
        for axis in ("tone", "rhyme_group"):
            self.assertEqual(counts(report["axes"][axis]), (1, 0, 1))
        self.assertEqual(counts(report["axes"]["character"]), (0, 0, 0))

    def test_end_can_alias_numeric_position_without_double_counting_a_reading(self):
        slots = [rule(position=1, tone="平"), rule(tone="仄")]
        report = evaluate_form(slots, [[word(LEVEL, OBLIQUE)]])
        self.assertEqual(counts(report), (2, 1, 1))
        self.assertEqual(counts(report["axes"]["tone"]), (2, 1, 1))
        for slot in report["slots"]:
            self.assertEqual(counts(slot), (1, 0, 1))

    def test_missing_positions_remain_in_denominator(self):
        slots = [rule(line=i, tone="平") for i in range(1, 6)]
        slots.append(rule(line=3, position=2, tone="平"))
        report = evaluate_form(slots, [[word(LEVEL)], None, [word(LEVEL)], []])
        self.assertEqual(counts(report), (6, 2, 2))
        self.assertEqual(counts(report["axes"]["tone"]), (6, 2, 2))
        self.assertEqual(report["missing_slots"], [
            {"line": 2, "position": "end"}, {"line": 4, "position": "end"},
            {"line": 5, "position": "end"}, {"line": 3, "position": 2},
        ])
        self.assertEqual(report["dictionary_gaps"], [])

    def test_gap_leaves_characters_observable_and_phonology_unknown(self):
        slots = [rule(tone="仄", character="望"), rule(line=2, tone="仄", character="水")]
        report = evaluate_form(slots, [[word()], [word()]])
        self.assertEqual(counts(report), (2, 0, 1))
        self.assertEqual(counts(report["axes"]["character"]), (2, 1, 1))
        self.assertEqual(counts(report["axes"]["tone"]), (2, 0, 2))
        self.assertEqual(report["missing_slots"], [])
        self.assertEqual(len(report["dictionary_gaps"]), 2)

    def test_invalid_declarations_and_context_selection_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate slot"):
            evaluate_form([rule(tone="平"), rule(character="望")], [])
        for invalid in [rule(position=0, tone="平"), rule(line=True, tone="平"), rule(), rule(tone="入")]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate_form([invalid], [])
        with self.assertRaisesRegex(ValueError, "source candidates"):
            evaluate_form([rule(tone="平")], [[word(LEVEL, selected=OBLIQUE)]])

    def test_malformed_observations_are_rejected_even_outside_expected_slots(self):
        for invalid in [None, {}, {"char": "."}, {"char": "中", "candidates": None},
                        word(None), word({"pingze": "仄"}), word(LEVEL, {}, selected=LEVEL)]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate_form([rule(tone="平")], [[word(LEVEL)], [invalid]])
        for char in ("。", "A"):
            with self.subTest(char=char), self.assertRaisesRegex(ValueError, "Han character"):
                evaluate_form([rule(character=char)], [])
