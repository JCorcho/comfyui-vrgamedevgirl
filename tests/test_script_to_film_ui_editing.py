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

    def test_async_scene_refreshes_keep_the_scene_context(self):
        with open(UI_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("const expandedSceneIds = new Set();", source)
        self.assertIn("const captureSceneViewState = () =>", source)
        self.assertIn('details.dataset.sceneId = sceneId;', source)
        self.assertIn('details.open = previousView.hasSceneState ? expandedSceneIds.has(sceneId) : index === 0;', source)
        self.assertIn('body.scrollTop = previousView.scrollTop;', source)

    def test_shared_planner_reflects_completed_film_clips(self):
        with open(UI_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn('video ready', source)
        self.assertIn('onSceneComplete:', source)
        self.assertIn('Film scene ${sceneNumber || ""} is rendered and visible in this Planner.', source)

    def test_completed_clip_is_persisted_before_the_next_film_scene(self):
        builder_path = os.path.join(ROOT, "web", "VRGDG_MusicVideoBuilderUI.js")
        with open(builder_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn('"/vrgdg/script_to_film/save_plan"', source)
        self.assertIn('if (Array.isArray(savedPlan?.scenes)) mergeScriptToFilmTimeline(savedPlan.scenes);', source)


if __name__ == "__main__":
    unittest.main()
