"""Contract tests for Film Prompt Creator structured-output recovery."""

import json
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import VRGDG_ScriptToFilmPromptPlan as FILM  # noqa: E402


class ScriptToFilmPromptPlanTests(unittest.TestCase):
    def test_complete_object_and_root_array_are_accepted(self):
        object_scenes, object_mode = FILM.extract_film_scene_plan(
            '{"scenes":[{"label":"one"},{"label":"two"}]}', json.loads
        )
        list_scenes, list_mode = FILM.extract_film_scene_plan(
            '[{"label":"one"},{"label":"two"}]', json.loads
        )
        self.assertEqual("complete_document", object_mode)
        self.assertEqual("complete_document", list_mode)
        self.assertEqual(["one", "two"], [scene["label"] for scene in object_scenes])
        self.assertEqual(["one", "two"], [scene["label"] for scene in list_scenes])

    def test_partial_array_keeps_only_complete_scene_records(self):
        text = '{"scenes":[{"label":"one"},{"label":"two"},{"label":"unfinished"'
        scenes, mode = FILM.extract_film_scene_plan(text, json.loads)
        self.assertEqual("partial_array", mode)
        self.assertEqual(["one", "two"], [scene["label"] for scene in scenes])

    def test_film_context_floor_preserves_explicit_larger_value(self):
        self.assertEqual(16384, FILM.film_prompt_creator_settings({"n_ctx": 8000})["n_ctx"])
        self.assertEqual(24576, FILM.film_prompt_creator_settings({"n_ctx": 24576})["n_ctx"])


if __name__ == "__main__":
    unittest.main()
