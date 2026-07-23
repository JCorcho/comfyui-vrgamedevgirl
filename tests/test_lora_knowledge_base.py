"""Non-rendering contract tests for Script-to-Film LoRA metadata resolution."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import VRGDG_LoraKnowledgeBase as kb  # noqa: E402


class LoraKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self.temporary.name, "lora_knowledge_base.json")
        kb.save_store({
            "entries": {
                "TestCharacterPony.safetensors": {
                    "lora_name": "TestCharacterPony.safetensors",
                    "base_model_recommendation": "pony",
                    "trigger_map": {
                        "base": "testponyhero",
                        "outfit_casual": "test casual jacket",
                        "action_kneeling": "test kneeling pose",
                        "style_anime": "test anime linework",
                    },
                    "recommended_weight": 0.8,
                    "example_positive_patterns": ["testponyhero, cinematic close-up"],
                    "example_negative_patterns": ["identity drift"],
                    "notes": "Synthetic test fixture only.",
                },
                "TestCharacterLTX.safetensors": {
                    "lora_name": "TestCharacterLTX.safetensors",
                    "base_model_recommendation": "ltx",
                    "trigger_map": {
                        "base": "testltxhero",
                        "action_kneeling": "test ltx kneeling motion",
                        "action_standing": "test ltx standing motion",
                    },
                    "recommended_weight": 1.0,
                },
            },
        }, self.store_path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_scene_specific_trigger_selection_and_bible_sanitization(self):
        kneeling_scene = {
            "physical_state_progression": "The adult performer wears a casual jacket while kneeling.",
            "position_continuity_notes": "She remains kneeling at the center of the set.",
            "character_bible": {"summary": "testponyhero is a red-haired adult performer."},
        }
        standing_scene = {
            "physical_state_progression": "The adult performer stands after the previous shot.",
            "position_continuity_notes": "Standing in a moonlit corridor, she turns toward camera.",
            "camera_language": "A clean anime-inspired medium shot.",
        }
        names = ["TestCharacterPony.safetensors", "TestCharacterLTX.safetensors"]
        pony_kneeling = kb.resolve_scene_triggers(kneeling_scene, names, "pony", self.store_path)
        pony_standing = kb.resolve_scene_triggers(standing_scene, names, "pony", self.store_path)
        ltx_kneeling = kb.resolve_scene_triggers(kneeling_scene, names, "ltx", self.store_path)
        ltx_standing = kb.resolve_scene_triggers(standing_scene, names, "ltx", self.store_path)

        self.assertIn("test kneeling pose", kb.resolution_fragment(pony_kneeling))
        self.assertIn("test casual jacket", kb.resolution_fragment(pony_kneeling))
        self.assertNotIn("test kneeling pose", kb.resolution_fragment(pony_standing))
        self.assertIn("test ltx kneeling motion", kb.resolution_fragment(ltx_kneeling))
        self.assertIn("test ltx standing motion", kb.resolution_fragment(ltx_standing))

        bible = kb.sanitize_character_bible(kneeling_scene["character_bible"], names, self.store_path)
        self.assertNotIn("testponyhero", bible["summary"].lower())
        self.assertNotIn("test casual jacket", bible["summary"].lower())

    def test_embedded_civitai_model_id_is_autofilled_without_user_input(self):
        with patch.object(kb, "_installed_lora_path", return_value="C:/models/TestCharacterPony.safetensors"), patch.object(
            kb, "_read_safetensors_metadata", return_value={"civitai_model_id": "123456"}
        ):
            result = kb.auto_detect_civitai("TestCharacterPony.safetensors", self.store_path)
        self.assertTrue(result["found"])
        self.assertEqual("embedded_metadata", result["match_method"])
        self.assertEqual("123456", result["entry"]["civitai_model_id"])
        stored = kb.load_store(self.store_path)["entries"]["TestCharacterPony.safetensors"]
        self.assertEqual("123456", stored["civitai_model_id"])

    def test_civitai_trigger_words_merge_into_the_selected_version_map(self):
        store = kb.load_store(self.store_path)
        entry = store["entries"]["TestCharacterPony.safetensors"]
        entry["notes"] = "Auto-imported from the installed LoRA file."
        entry["civitai_model_id"] = "900"
        entry["civitai_model_version_id"] = "222"
        kb.save_store(store, self.store_path)
        remote_model = {
            "name": "Test Character",
            "modelVersions": [
                {"id": 111, "name": "Wrong version", "baseModel": "SDXL", "trainedWords": ["wrongtoken"]},
                {
                    "id": 222,
                    "name": "Exact Pony version",
                    "baseModel": "Pony",
                    "trainedWords": ["testponyhero,", "red skin, orange eyes, facial mark, tattoo, twi'lek,"],
                },
            ],
        }
        with patch.object(kb, "_civitai_request", return_value=remote_model):
            result = kb.research_civitai("TestCharacterPony.safetensors", self.store_path)
        self.assertTrue(result["researched"])
        self.assertEqual("222", result["entry"]["civitai_model_version_id"])
        self.assertEqual(
            ["testponyhero", "red skin", "orange eyes", "facial mark", "tattoo", "twi'lek"],
            result["entry"]["civitai_trigger_words"],
        )
        self.assertEqual(
            "testponyhero, red skin, orange eyes, facial mark, tattoo, twi'lek",
            result["entry"]["trigger_map"]["base"],
        )
        self.assertIn("action_kneeling", result["entry"]["trigger_map"])
        resolved = kb.resolve_scene_triggers(
            {"physical_state_progression": "The adult performer is kneeling."},
            ["TestCharacterPony.safetensors"],
            "pony",
            self.store_path,
        )
        self.assertIn("orange eyes", kb.resolution_fragment(resolved))

    def test_unique_verified_trigger_word_can_resolve_a_scene_lora_reference(self):
        store = kb.load_store(self.store_path)
        entry = store["entries"]["TestCharacterPony.safetensors"]
        entry["base_model_recommendation"] = "anima"
        entry["civitai_trigger_words"] = ["testponyhero"]
        entry["trigger_map"]["base"] = "testponyhero"
        kb.save_store(store, self.store_path)

        names = kb.canonical_lora_names(["testponyhero"], self.store_path)
        self.assertEqual(["TestCharacterPony.safetensors"], names)
        resolved = kb.resolve_scene_triggers(
            {"physical_state_progression": "The adult performer is kneeling."},
            ["testponyhero"],
            "anima",
            self.store_path,
        )
        self.assertIn("testponyhero", kb.resolution_fragment(resolved))


if __name__ == "__main__":
    unittest.main()
