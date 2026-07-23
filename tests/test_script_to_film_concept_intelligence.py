"""Contract tests for Phase 3 Script-to-Film Concept Intelligence."""

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import VRGDG_ConceptPoseKnowledgeBase as concept_kb  # noqa: E402
import VRGDG_ScriptToFilmConceptIntelligence as intelligence  # noqa: E402


def recipe(recipe_id, base_model, score, seed):
    return {
        "recipe_id": recipe_id,
        "source": "local",
        "positive_prompt": f"{base_model.lower()} cinematic low crouch, balanced stance",
        "negative_prompt": "extra limbs, broken anatomy",
        "loras": [{"name": "PoseHelper.safetensors", "weight": 0.65}],
        "seed": seed,
        "cfg": 5.5,
        "steps": 30,
        "sampler": "euler",
        "model_name": f"{base_model} test model",
        "base_model": base_model,
        "notes": "Temporary contract-test recipe.",
        "quality_score": score,
        "tags": ["pose", "test"],
    }


class ScriptToFilmConceptIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store_root = os.path.join(self.temporary.name, "concepts")
        concept_kb.save_recipe("low_crouch", "Low Crouch", ["Pony", "Anima"], recipe("pony_low", "Pony", 7.5, "101"), self.store_root)
        concept_kb.save_recipe("low_crouch", "Low Crouch", ["Pony", "Anima"], recipe("pony_high", "Pony", 9.3, "102"), self.store_root)
        concept_kb.save_recipe("low_crouch", "Low Crouch", ["Pony", "Anima"], recipe("anima_high", "Anima", 9.8, "103"), self.store_root)
        self.scene = {
            "id": "film_scene_0001",
            "label": "The courier takes a low crouch behind the barricade",
            "physical_state_progression": "Drops into a low crouch, then holds a balanced stance.",
            "character_bible": {"summary": "Red-haired courier with a scar over one eyebrow."},
            "t2i_prompt": "a courier behind a rain-soaked barricade",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def test_inference_suggests_quality_ranked_recipes_for_selected_base_model(self):
        pony = intelligence.suggest_scene_recipes(self.scene, "Pony", 3, root=self.store_root)
        self.assertEqual("low_crouch", pony["concept"]["concept_key"])
        self.assertEqual("scene_text", pony["concept"]["inference"])
        self.assertEqual(["pony_high", "pony_low"], [item["recipe_id"] for item in pony["recipes"]])
        self.assertEqual("102", pony["recipes"][0]["seed"])
        self.assertEqual(5.5, pony["recipes"][0]["cfg"])
        self.assertEqual(30, pony["recipes"][0]["steps"])
        self.assertTrue(pony["recipes"][0]["positive_prompt_preview"])

        anima = intelligence.suggest_scene_recipes(self.scene, "Anima", 3, root=self.store_root)
        self.assertEqual(["anima_high"], [item["recipe_id"] for item in anima["recipes"]])

    def test_apply_copies_recipe_metadata_without_contaminating_character_bible(self):
        result = intelligence.apply_recipe_to_scene(self.scene, "low_crouch", "pony_high", "Pony", root=self.store_root)
        applied = result["scene"]
        self.assertIn("pony cinematic low crouch", applied["t2i_prompt"])
        self.assertEqual("extra limbs, broken anatomy", applied["concept_recipe_negative_fragment"])
        self.assertEqual("102", applied["concept_recipe_settings"]["seed"])
        self.assertEqual(5.5, applied["concept_recipe_settings"]["cfg"])
        self.assertEqual(30, applied["concept_recipe_settings"]["steps"])
        self.assertEqual("euler", applied["concept_recipe_settings"]["sampler"])
        self.assertEqual([{"name": "PoseHelper.safetensors", "weight": 0.65}], applied["concept_recipe_loras"])
        self.assertEqual("pony_high", applied["applied_concept_recipe"]["recipe_id"])
        self.assertEqual(self.scene["character_bible"], applied["character_bible"])
        self.assertNotIn("PoseHelper", str(applied["character_bible"]))
        self.assertEqual(["t2i_prompt", "concept_recipe_positive_fragment", "concept_recipe_negative_fragment", "concept_recipe_loras", "concept_recipe_settings", "applied_concept_recipe"], result["applied_fields"])

    def test_explicit_concept_allows_empty_library_research_and_new_local_save_refreshes_suggestions(self):
        scene = {"id": "film_scene_0002", "concept_key": "arched_back", "t2i_prompt": "character arches back"}
        before = intelligence.suggest_scene_recipes(scene, "Pony", 3, root=self.store_root)
        self.assertEqual("arched_back", before["concept"]["concept_key"])
        self.assertEqual([], before["recipes"])
        concept_kb.save_recipe("arched_back", "Arched Back", ["Pony"], recipe("new_local", "Pony", 9.1, "104"), self.store_root)
        after = intelligence.suggest_scene_recipes(scene, "Pony", 3, root=self.store_root)
        self.assertEqual(["new_local"], [item["recipe_id"] for item in after["recipes"]])

    def test_research_more_delegates_to_phase_two_and_node_registration_is_available(self):
        calls = []
        original = intelligence.research_concept
        try:
            intelligence.research_concept = lambda query, base, maximum, safe: calls.append((query, base, maximum, safe)) or {
                "query": query,
                "base_model_filter": base,
                "candidate_count": 0,
                "candidates": [],
            }
            result = intelligence.research_more_for_scene("low_crouch", "Anima", 4, False)
        finally:
            intelligence.research_concept = original
        self.assertEqual([("low_crouch", "Anima", 4, False)], calls)
        self.assertEqual("low_crouch", result["query"])
        expected = {
            "VRGDG_ScriptToFilmRecipeSuggestions",
            "VRGDG_ScriptToFilmApplyRecipe",
            "VRGDG_ScriptToFilmResearchMore",
        }
        self.assertTrue(expected.issubset(intelligence.NODE_CLASS_MAPPINGS))

    def test_phase_three_module_stays_outside_music_video_and_lora_character_implementations(self):
        with open(intelligence.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("VRGDG_MusicVideo", source)
        self.assertNotIn("VRGDG_LoraKnowledgeBase", source)


if __name__ == "__main__":
    unittest.main()
