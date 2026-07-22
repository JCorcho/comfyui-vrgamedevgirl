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


if __name__ == "__main__":
    unittest.main()
