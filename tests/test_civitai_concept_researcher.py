"""Contract tests for the Phase 2 Civitai concept-recipe research layer."""

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
for path in (ROOT, TOOLS):
    if path not in sys.path:
        sys.path.insert(0, path)

import VRGDG_ConceptPoseKnowledgeBase as concept_kb  # noqa: E402
import VRGDG_ConceptResearchNodes as research_nodes  # noqa: E402
from civitai_concept_researcher import research_concept  # noqa: E402


class FakeCivitaiClient:
    """A no-network public-API fixture with full recipe metadata."""

    def __init__(self):
        self.calls = []
        self.versions = {
            "100": {
                "id": 100,
                "name": "V6 Test",
                "baseModel": "Pony",
                "model": {"id": 900, "name": "Pony Test Checkpoint"},
            },
            "200": {
                "id": 200,
                "name": "Pose Support v1",
                "baseModel": "Pony",
                "modelId": 901,
                "model": {"id": 901, "name": "Pose Support LoRA"},
            },
        }

    def get_json(self, path_or_url, params=None):
        self.calls.append((path_or_url, params or {}))
        if str(path_or_url).endswith("/images"):
            return {
                "items": [
                    {
                        "id": 101,
                        "postId": 202,
                        "username": "recipe_author",
                        "nsfw": False,
                        "nsfwLevel": "None",
                        "stats": {"likeCount": 150, "heartCount": 30},
                        "meta": {
                            "baseModel": "Pony",
                            "prompt": "adult dancer, arched back, balanced stance, studio light, full body",
                            "negativePrompt": "low quality, blurry, bad anatomy",
                            "seed": 123456,
                            "cfgScale": 5.5,
                            "steps": 30,
                            "sampler": "euler",
                            "Model": "urn:air:sdxl:checkpoint:civitai:900@100",
                            "additionalResources": [
                                {"type": "lora", "name": "urn:air:sdxl:lora:civitai:901@200", "strength": 0.7},
                            ],
                            "civitaiResources": [
                                {"type": "checkpoint", "modelVersionId": 100},
                                {"type": "lora", "modelVersionId": 200, "weight": 0.7},
                            ],
                        },
                    },
                    {
                        "id": 102,
                        "postId": 203,
                        "nsfw": False,
                        "nsfwLevel": "None",
                        "stats": {"likeCount": 1000, "heartCount": 100},
                        "meta": {
                            "baseModel": "Anima",
                            "prompt": "adult dancer, arched back, cinematic pose",
                            "negativePrompt": "blurry",
                            "seed": 222,
                            "cfgScale": 4.0,
                            "steps": 20,
                            "sampler": "euler",
                            "Model": "Anima test",
                        },
                    },
                    {
                        "id": 103,
                        "postId": 204,
                        "nsfw": True,
                        "nsfwLevel": "Mature",
                        "stats": {"likeCount": 9000, "heartCount": 1000},
                        "meta": {
                            "baseModel": "Pony",
                            "prompt": "adult dancer, arched back, studio pose",
                            "negativePrompt": "blurry",
                            "seed": 333,
                            "cfgScale": 5.0,
                            "steps": 25,
                            "sampler": "euler",
                            "Model": "Pony test",
                        },
                    },
                ],
                "metadata": {},
            }
        raise AssertionError(f"Unexpected API path: {path_or_url}")

    def model_version(self, version_id):
        self.calls.append((f"/model-versions/{version_id}", {}))
        return self.versions.get(str(version_id), {})


class CivitaiConceptResearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store_root = os.path.join(self.temporary.name, "concepts")

    def tearDown(self):
        self.temporary.cleanup()

    def test_research_extracts_complete_safe_pony_recipe_and_resolves_resources(self):
        client = FakeCivitaiClient()
        result = research_concept("arched_back", "Pony", 8, safe_only=True, client=client)
        self.assertEqual("civitai_public_api", result["provider"])
        self.assertTrue(result["review_required"])
        self.assertEqual(1, result["candidate_count"])
        candidate = result["candidates"][0]
        self.assertEqual("civitai_image_101", candidate["candidate_id"])
        self.assertEqual("https://civitai.com/images/101", candidate["source_url"])
        self.assertEqual("https://civitai.com/posts/202", candidate["post_url"])
        self.assertEqual("Pony", candidate["base_model"])
        self.assertEqual("Pony Test Checkpoint — V6 Test", candidate["model_name"])
        self.assertEqual("Pose Support LoRA — Pose Support v1", candidate["loras"][0]["name"])
        self.assertEqual(0.7, candidate["loras"][0]["weight"])
        self.assertEqual(7, candidate["metadata_completeness"]["core_fields_present"])
        self.assertEqual(0.0, candidate["quality_score"])
        self.assertGreater(candidate["candidate_score"], 0.0)
        image_call = client.calls[0]
        self.assertEqual("/images", image_call[0])
        self.assertEqual("true", image_call[1]["withMeta"])

    def test_reviewed_candidate_saves_to_phase_one_store_and_best_match_reads_it(self):
        payload = research_concept("arched_back", "Pony", 8, safe_only=True, client=FakeCivitaiClient())
        saved = research_nodes.save_approved_candidates(
            payload,
            "civitai_image_101",
            "arched_back",
            "Arched Back",
            "Pony, Anima",
            8.4,
            "Verified in a local quick test.",
            "pose, tested",
            root=self.store_root,
        )
        self.assertEqual(1, saved["saved_count"])
        self.assertEqual("added", saved["saved"][0]["action"])
        viewed = concept_kb.get_concept("arched_back", self.store_root)
        self.assertEqual(1, len(viewed["recipes"]))
        recipe = viewed["recipes"][0]
        self.assertEqual("civitai_image_101", recipe["recipe_id"])
        self.assertEqual("Pony", recipe["base_model"])
        self.assertIn("https://civitai.com/images/101", recipe["source"])
        self.assertEqual(8.4, recipe["quality_score"])
        self.assertIn("Verified in a local quick test.", recipe["notes"])
        best = concept_kb.retrieve_best_recipes("arched_back", "Pony", 5, self.store_root)
        self.assertEqual(["civitai_image_101"], [item["recipe_id"] for item in best["recipes"]])

    def test_save_node_template_placeholder_returns_instruction_without_writing(self):
        payload = research_concept("arched_back", "Pony", 8, safe_only=True, client=FakeCivitaiClient())
        node = research_nodes.VRGDG_ConceptResearchSaveApproved()
        result = node.save(
            __import__("json").dumps(payload),
            "PASTE_CANDIDATE_ID_FROM_WORKFLOW_01",
            "arched_back", "Arched Back", "Pony, Anima", 0.0, "", "civitai, reviewed",
        )
        message = __import__("json").loads(result["result"][0])
        self.assertEqual(0, message["saved_count"])
        self.assertTrue(message["review_required"])
        self.assertIn("Paste a reviewed candidate_id", message["action_required"])

    def test_node_registration_and_isolation_boundaries(self):
        expected_nodes = {
            "VRGDG_ConceptResearchCivitai",
            "VRGDG_ConceptResearchViewCandidate",
            "VRGDG_ConceptResearchSaveApproved",
        }
        self.assertTrue(expected_nodes.issubset(research_nodes.NODE_CLASS_MAPPINGS))
        with open(research_nodes.__file__, "r", encoding="utf-8") as handle:
            node_source = handle.read()
        helper_path = os.path.join(ROOT, "tools", "civitai_concept_researcher", "researcher.py")
        with open(helper_path, "r", encoding="utf-8") as handle:
            helper_source = handle.read()
        for forbidden in ("VRGDG_LoraKnowledgeBase", "VRGDG_ScriptToFilmNodes", "VRGDG_MusicVideo"):
            self.assertNotIn(forbidden, node_source)
            self.assertNotIn(forbidden, helper_source)


if __name__ == "__main__":
    unittest.main()
