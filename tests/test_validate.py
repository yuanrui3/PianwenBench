import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from pianwen.validate import CANARY, ItemValidationError, main, validate_file


def item(split="dev", suffix="fixture"):
    return {
        "id": f"pw-{split}-{suffix}",
        "track": "diagnostic",
        "canary": CANARY,
        "prompt": "Placeholder prompt",
    }


class ValidateFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_accepts_dev_json_and_private_jsonl(self):
        dev = self.write("data/dev/example.json", json.dumps(item()))
        private = self.write(
            "private/items.test.jsonl",
            "\n".join(json.dumps(item("test", str(i))) for i in range(2)) + "\n",
        )
        self.assertEqual(validate_file(dev, repo_root=self.root), 1)
        self.assertEqual(validate_file(private, repo_root=self.root), 2)

    def test_copied_test_item_in_unmarked_jsonl_returns_failure(self):
        path = self.write(
            "data/dev/copied.jsonl",
            json.dumps(item()) + "\n" + json.dumps(item("test")) + "\n",
        )
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(main(["--repo-root", str(self.root), str(path)]), 1)
        self.assertIn(":2: test items must be inside private/", error.getvalue())
        self.assertNotIn("Placeholder prompt", error.getvalue())

    def test_test_filename_and_directory_are_rejected_outside_private(self):
        for relative_path in ("dev/items.test.jsonl", "data/test/items.json"):
            with self.subTest(relative_path=relative_path):
                path = self.write(relative_path, json.dumps(item()))
                with self.assertRaisesRegex(ItemValidationError, "inside private/"):
                    validate_file(path, repo_root=self.root)

    def test_test_item_symlinks_cannot_cross_private_boundary(self):
        outside = self.write("outside/item.json", json.dumps(item("test")))
        inside = self.write("private/item.json", json.dumps(item("test")))
        private_alias = self.root / "private" / "outside.json"
        public_alias = self.root / "outside" / "inside.json"
        private_alias.symlink_to(outside)
        public_alias.symlink_to(inside)
        for path in (private_alias, public_alias):
            with self.subTest(path=path.name):
                with self.assertRaisesRegex(ItemValidationError, "inside private/"):
                    validate_file(path, repo_root=self.root)

    def test_directory_scan_rejects_dangling_item_symlink(self):
        directory = self.root / "data" / "dev"
        directory.mkdir(parents=True)
        (directory / "missing.test.jsonl").symlink_to(self.root / "absent.jsonl")
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(main(["--repo-root", str(self.root), str(directory)]), 1)
        self.assertIn("cannot resolve item path", error.getvalue())

    def test_file_requires_literal_canary_and_each_row_requires_canary(self):
        path = self.write("missing.json", json.dumps(item()).replace("PIANWENBENCH", "missing"))
        with self.assertRaisesRegex(ItemValidationError, "missing literal canary"):
            validate_file(path, repo_root=self.root)

        path = self.write("escaped.json", json.dumps(item()).replace("PIANWENBENCH", "\\u0050IANWENBENCH"))
        with self.assertRaisesRegex(ItemValidationError, "missing literal canary"):
            validate_file(path, repo_root=self.root)

        row = item(suffix="second")
        del row["canary"]
        path = self.write("missing.jsonl", json.dumps(item()) + "\n" + json.dumps(row))
        with self.assertRaisesRegex(ItemValidationError, "canary"):
            validate_file(path, repo_root=self.root)

    def test_duplicate_id_property_cannot_hide_the_test_prefix(self):
        text = json.dumps(item("test")).replace(
            '"track":', '"id": "pw-dev-fixture", "track":'
        )
        path = self.write("ambiguous.json", text)
        with self.assertRaisesRegex(ItemValidationError, "duplicate JSON property"):
            validate_file(path, repo_root=self.root)

    def test_schema_enforces_track_requirements_and_character_bounds(self):
        row = dict(item(), track="lufu", form_rules={"assigned_rhymes": ["rhyme"] * 7})
        path = self.write("form.json", json.dumps(row))
        with self.assertRaisesRegex(ItemValidationError, "assigned_rhymes"):
            validate_file(path, repo_root=self.root)

        row["form_rules"] = {"assigned_rhymes": ["rhyme"] * 8, "length_chars": [300, 240]}
        path = self.write("form.json", json.dumps(row))
        with self.assertRaisesRegex(ItemValidationError, "minimum exceeds maximum"):
            validate_file(path, repo_root=self.root)


if __name__ == "__main__":
    unittest.main()
