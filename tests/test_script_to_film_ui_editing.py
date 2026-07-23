"""Regression contract for Film Planner fields that refresh the shared modal."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_PATH = os.path.join(ROOT, "web", "VRGDG_ScriptToFilmUI.js")


class ScriptToFilmUiEditingTests(unittest.TestCase):
    def test_modal_rebuilding_fields_commit_after_composition(self):
        with open(UI_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("if (options.commitOnly)", source)
        self.assertIn('control.addEventListener("change", emitChange);', source)
        self.assertIn('field("Target duration (seconds)"', source)
        self.assertIn('{ type: "number", commitOnly: true }', source)
        self.assertIn('field("Concept / pose (optional override)"', source)
        self.assertIn('}, { commitOnly: true }),', source)


if __name__ == "__main__":
    unittest.main()
