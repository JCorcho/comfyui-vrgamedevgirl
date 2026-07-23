"""Contract tests for the independent Phase 1 Concept / Pose recipe store."""

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import VRGDG_ConceptPoseKnowledgeBase as concept_kb  # noqa: E402


class ConceptPoseKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store_root = os.path.join(self.temporary.name, "concepts")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def recipe(recipe_id, base_model, quality_score, seed):
        return {
            "recipe_id": recipe_id,
            "source": "local",
            "positive_prompt": f"Full recipe prompt for {recipe_id}",
            "negative_prompt": "broken anatomy, extra limbs",
            "loras": [{"name": "PoseHelper.safetensors", "weight": 0.65}],
            "seed": seed,
            "cfg": 5.5,
            "steps": 30,
            "sampler": "euler",
            "model_name": f"{base_model} test model",
            "base_model": base_model,
            "notes": "Temporary test recipe.",
            "quality_score": quality_score,
            "tags": ["pose", "test"],
        }

    def test_add_view_best_match_update_and_delete(self):
        first = concept_kb.save_recipe(
            "stable_crouch", "Stable Crouch", ["Pony", "Anima"], self.recipe("pony_low", "Pony", 7.1, "101"), self.store_root
        )
        second = concept_kb.save_recipe(
            "stable_crouch", "Stable Crouch", ["Pony", "Anima"], self.recipe("pony_high", "Pony", 9.2, "102"), self.store_root
        )
        concept_kb.save_recipe(
            "stable_crouch", "Stable Crouch", ["Pony", "Anima"], self.recipe("anima_best", "Anima", 9.8, "103"), self.store_root
        )
        listed = concept_kb.list_concepts(self.store_root)
        self.assertEqual(1, len(listed))
        self.assertEqual(3, listed[0]["recipe_count"])
        viewed = concept_kb.get_concept("stable_crouch", self.store_root)
        self.assertEqual("Stable Crouch", viewed["display_name"])
        self.assertEqual(3, len(viewed["recipes"]))
        best_pony = concept_kb.retrieve_best_recipes("stable_crouch", "Pony", 5, self.store_root)
        self.assertEqual(["pony_high", "pony_low"], [item["recipe_id"] for item in best_pony["recipes"]])
        self.assertEqual("Pony", best_pony["recipes"][0]["base_model"])
        updated = self.recipe("pony_low", "Pony", 9.5, "101")
        updated["notes"] = "Edited local recipe."
        updated_result = concept_kb.save_recipe("stable_crouch", "", [], updated, self.store_root)
        self.assertEqual("updated", updated_result["action"])
        best_after_edit = concept_kb.retrieve_best_recipes("stable_crouch", "Pony", 5, self.store_root)
        self.assertEqual("pony_low", best_after_edit["recipes"][0]["recipe_id"])
        deleted = concept_kb.delete_recipe("stable_crouch", first["recipe"]["recipe_id"], self.store_root)
        self.assertTrue(deleted["deleted"])
        self.assertEqual(2, len(deleted["concept"]["recipes"]))
        self.assertEqual("added", second["action"])

    def test_deleting_final_local_only_recipe_removes_the_empty_concept_file(self):
        created = concept_kb.save_recipe(
            "disposable_manual_test", "Disposable Manual Test", ["Pony"],
            self.recipe("disposable_recipe", "Pony", 5.0, "999"), self.store_root,
        )
        removed = concept_kb.delete_recipe(
            "disposable_manual_test", created["recipe"]["recipe_id"], self.store_root
        )
        self.assertTrue(removed["removed_empty_local_concept"])
        self.assertIsNone(concept_kb.get_concept("disposable_manual_test", self.store_root))
        self.assertFalse(os.path.isfile(os.path.join(self.store_root, "local", "disposable_manual_test.json")))

    def test_tracked_examples_and_node_registration_are_available(self):
        examples = concept_kb.list_concepts()
        keys = {item["concept_key"] for item in examples}
        self.assertTrue({"arched_back", "low_crouch"}.issubset(keys))
        for key in ("arched_back", "low_crouch"):
            self.assertGreaterEqual(len(concept_kb.get_concept(key)["recipes"]), 2)
        expected_nodes = {
            "VRGDG_ConceptRecipeList",
            "VRGDG_ConceptRecipeView",
            "VRGDG_ConceptRecipeSave",
            "VRGDG_ConceptRecipeDelete",
            "VRGDG_ConceptRecipeBestMatch",
        }
        self.assertTrue(expected_nodes.issubset(concept_kb.NODE_CLASS_MAPPINGS))

    def test_store_is_isolated_from_lora_character_and_music_video_modules(self):
        with open(concept_kb.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("VRGDG_LoraKnowledgeBase", source)
        self.assertNotIn("VRGDG_ScriptToFilmNodes", source)
        self.assertNotIn("VRGDG_MusicVideo", source)


if __name__ == "__main__":
    unittest.main()
