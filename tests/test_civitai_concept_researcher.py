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
from civitai_concept_researcher.researcher import _relevance_score  # noqa: E402


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
                        "url": "https://image.civitai.com/test/101.webp",
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
        self.assertEqual("https://image.civitai.com/test/101.webp", candidate["image_preview_url"])
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
        self.assertEqual("false", image_call[1]["nsfw"])

    def test_adult_allowed_research_explicitly_requests_nsfw_and_keeps_adult_candidates(self):
        client = FakeCivitaiClient()
        result = research_concept("arched_back", "Pony", 8, safe_only=False, client=client)
        self.assertEqual("adult_allowed", result["content_mode"])
        self.assertEqual(2, result["candidate_count"])
        self.assertIn("civitai_image_103", [item["candidate_id"] for item in result["candidates"]])
        adult_candidate = next(item for item in result["candidates"] if item["candidate_id"] == "civitai_image_103")
        self.assertEqual("https://civitai.red/images/103", adult_candidate["source_url"])
        image_call = client.calls[0]
        self.assertEqual("true", image_call[1]["nsfw"])

    def test_review_node_reports_an_empty_search_without_throwing(self):
        node = research_nodes.VRGDG_ConceptResearchViewCandidate()
        result = node.view('{"candidates": [], "warnings": ["No candidates found."]}', "")
        message = __import__("json").loads(result["result"][0])
        self.assertEqual(0, message["candidate_count"])
        self.assertIn("nothing to review", message["action_required"])
        self.assertEqual("", result["result"][1])

    def test_review_node_accepts_a_result_number_and_returns_guidance_for_a_missing_selection(self):
        payload = {
            "candidates": [
                {"candidate_id": "civitai_image_101", "positive_prompt": "first"},
                {"candidate_id": "civitai_image_202", "positive_prompt": "second"},
            ]
        }
        node = research_nodes.VRGDG_ConceptResearchViewCandidate()
        second = node.view(__import__("json").dumps(payload), "2", 1)
        selected = __import__("json").loads(second["result"][0])
        self.assertEqual("civitai_image_202", selected["candidate_id"])
        self.assertEqual("candidate_number", selected["selection_mode"])

        missing = node.view(__import__("json").dumps(payload), "99", 1)
        guidance = __import__("json").loads(missing["result"][0])
        self.assertIn("not in this search result", guidance["action_required"])
        self.assertEqual(["#1: civitai_image_101", "#2: civitai_image_202"], guidance["candidate_directory"])

    def test_common_concept_aliases_match_visible_prompt_phrases(self):
        self.assertGreater(_relevance_score("doggystyle", "doggy style, from behind, detailed pose"), 0.0)

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

    def test_save_accepts_a_displayed_result_number_and_invalid_selection_stays_in_node_ui(self):
        payload = research_concept("arched_back", "Pony", 8, safe_only=True, client=FakeCivitaiClient())
        original = payload["candidates"][0]
        candidates = []
        for image_id in (101, 202, 303):
            candidate = __import__("copy").deepcopy(original)
            candidate["candidate_id"] = f"civitai_image_{image_id}"
            candidate["civitai_image_id"] = str(image_id)
            candidates.append(candidate)
        payload["candidates"] = candidates
        payload["candidate_count"] = len(candidates)

        saved = research_nodes.save_approved_candidates(
            payload, "3", "arched_back", "Arched Back", "Pony", 8.0, "Selected by result number.", "test", root=self.store_root,
        )
        self.assertEqual("civitai_image_303", saved["saved"][0]["candidate_id"])

        node = research_nodes.VRGDG_ConceptResearchSaveApproved()
        invalid = node.save(__import__("json").dumps(payload), "9", "arched_back", "Arched Back", "Pony", 8.0, "", "test")
        status = __import__("json").loads(invalid["result"][0])
        self.assertEqual(0, status["saved_count"])
        self.assertIn("not found", status["action_required"])
        self.assertEqual("#3: civitai_image_303", status["candidate_directory"][-1])

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
