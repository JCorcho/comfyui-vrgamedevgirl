"""Thin ComfyUI nodes for reviewing and saving Civitai concept recipes.

Network access belongs to ``tools/civitai_concept_researcher``.  This module
only invokes that helper, displays its JSON, and explicitly saves human-selected
candidates through the existing Concept/Pose Knowledge Base API.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any


_ROOT = os.path.dirname(os.path.abspath(__file__))
_TOOLS_ROOT = os.path.join(_ROOT, "tools")
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

try:
    from .VRGDG_ConceptPoseKnowledgeBase import _concept_key, _json_output, _text_ui_result, get_concept, save_recipe
except ImportError:  # Direct-module fallback used by ComfyUI's resilient loader.
    from VRGDG_ConceptPoseKnowledgeBase import _concept_key, _json_output, _text_ui_result, get_concept, save_recipe

from civitai_concept_researcher import CivitaiAPIError, research_concept


_CATEGORY = "VRGDG/Knowledge/Concept Research"


def _text(value: Any, limit: int = 16000) -> str:
    return str(value or "").strip()[:limit]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if result == result and abs(result) != float("inf") else float(default)


def _parse_research_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        payload = value
    else:
        try:
            payload = json.loads(_text(value, 2_000_000))
        except Exception as exc:
            raise ValueError(f"Candidates JSON is invalid: {type(exc).__name__}")
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise ValueError("Candidates JSON must be the result of VRGDG Concept Research: Search Civitai.")
    return payload


def _candidate_id_list(value: Any) -> set[str]:
    raw = _text(value, 4000)
    if not raw:
        raise ValueError("Enter one or more candidate IDs from the review JSON, or use 'all'.")
    if raw.lower() == "all":
        return {"all"}
    return {item for item in re.split(r"[,;\n\s]+", raw) if item}


def _candidate_to_recipe(candidate: dict[str, Any], quality_score: float, extra_notes: str, extra_tags: str) -> dict[str, Any]:
    candidate_id = _text(candidate.get("candidate_id", ""), 180)
    image_id = _text(candidate.get("civitai_image_id", ""), 120)
    if not candidate_id or not image_id:
        raise ValueError("A selected candidate is missing its Civitai image identity.")
    source_url = _text(candidate.get("source_url", ""), 500) or f"https://civitai.com/images/{image_id}"
    post_id = _text(candidate.get("civitai_post_id", ""), 120)
    source = source_url + (f" (post {post_id})" if post_id else "")
    notes = _text(candidate.get("notes", ""), 10000)
    if extra_notes:
        notes = _text(f"{notes}\nLocal review notes: {extra_notes}".strip(), 12000)
    tag_values = list(candidate.get("tags", [])) if isinstance(candidate.get("tags"), list) else []
    tag_values.extend(item.strip() for item in re.split(r"[,;\n]", extra_tags) if item.strip())
    return {
        # The stable image-based ID means approving the same Civitai result
        # again updates it rather than silently duplicating a recipe.
        "recipe_id": candidate_id,
        "source": source,
        "positive_prompt": _text(candidate.get("positive_prompt", ""), 16000),
        "negative_prompt": _text(candidate.get("negative_prompt", ""), 12000),
        "loras": candidate.get("loras", []),
        "seed": _text(candidate.get("seed", ""), 120),
        "cfg": _number(candidate.get("cfg", 0.0), 0.0),
        "steps": max(0, int(_number(candidate.get("steps", 0), 0))),
        "sampler": _text(candidate.get("sampler", ""), 300),
        "model_name": _text(candidate.get("model_name", ""), 1024),
        "base_model": _text(candidate.get("base_model", ""), 300),
        "notes": notes,
        "quality_score": max(0.0, min(10.0, _number(quality_score, 0.0))),
        "tags": tag_values,
    }


def save_approved_candidates(
    candidates_payload: Any,
    candidate_ids: Any,
    concept_key: str,
    display_name: str = "",
    compatible_base_models: str = "",
    quality_score: float = 0.0,
    review_notes: str = "",
    additional_tags: str = "",
    root: str | None = None,
) -> dict[str, Any]:
    """Save explicitly selected review candidates through Phase 1's API.

    The optional ``root`` exists for contract tests.  Normal ComfyUI use always
    writes to the existing local Concept/Pose store.
    """
    payload = _parse_research_payload(candidates_payload)
    wanted = _candidate_id_list(candidate_ids)
    key = _concept_key(concept_key)
    candidates = [item for item in payload["candidates"] if isinstance(item, dict)]
    selected = candidates if "all" in wanted else [item for item in candidates if _text(item.get("candidate_id", ""), 180) in wanted]
    found_ids = {_text(item.get("candidate_id", ""), 180) for item in selected}
    missing = [] if "all" in wanted else sorted(wanted - found_ids)
    if missing:
        raise ValueError("Candidate IDs were not found in this research result: " + ", ".join(missing))
    if not selected:
        raise ValueError("No research candidates were selected for saving.")
    model_list = _text(compatible_base_models, 2000)
    if not model_list:
        inferred = []
        for candidate in selected:
            base_model = _text(candidate.get("base_model", ""), 300)
            if base_model and base_model.lower() not in {value.lower() for value in inferred}:
                inferred.append(base_model)
        model_list = ", ".join(inferred)
    label = _text(display_name, 500) or key.replace("_", " ").title()
    saved = []
    for candidate in selected:
        recipe = _candidate_to_recipe(candidate, quality_score, _text(review_notes, 10000), _text(additional_tags, 2000))
        result = save_recipe(key, label, model_list, recipe, root=root)
        saved.append({"candidate_id": recipe["recipe_id"], "action": result["action"], "recipe_id": result["recipe"]["recipe_id"]})
    return {
        "saved_count": len(saved),
        "concept_key": key,
        "saved": saved,
        "concept": get_concept(key, root=root),
        "review_required": False,
    }


class VRGDG_ConceptResearchCivitai:
    """Search public Civitai metadata and return review-only recipe candidates."""

    CATEGORY = _CATEGORY
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("candidates_json", "candidate_count")
    FUNCTION = "research"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "concept_query": ("STRING", {"default": "arched_back", "multiline": False}),
                "base_model": (["Pony", "Anima", "Any"], {"default": "Pony"}),
                "max_candidates": ("INT", {"default": 8, "min": 1, "max": 20, "step": 1}),
                "safe_only": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Safe-only search",
                        "label_off": "Adult-allowed search",
                        "tooltip": "On: search SFW Civitai results. Off: search adult-allowed results through Civitai.red, with an explicit Civitai.com adult-filter fallback if needed.",
                    },
                ),
            },
            "optional": {
                "custom_base_model": ("STRING", {"default": "", "placeholder": "Optional override, e.g. a future Civitai base family"}),
            },
        }

    def research(self, concept_query, base_model, max_candidates, safe_only, custom_base_model=""):
        selected_base = _text(custom_base_model, 300) or _text(base_model, 300)
        try:
            result = research_concept(concept_query, selected_base, max_candidates, bool(safe_only))
        except (ValueError, CivitaiAPIError) as exc:
            raise ValueError(f"Civitai concept research failed: {exc}")
        text = _json_output(result)
        return _text_ui_result(text, text, len(result.get("candidates", [])))


class VRGDG_ConceptResearchViewCandidate:
    """Display one full candidate recipe before the user approves it."""

    CATEGORY = _CATEGORY
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("candidate_json", "candidate_id")
    FUNCTION = "view"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "candidates_json": ("STRING", {"default": "{}", "multiline": True, "forceInput": True}),
                "candidate_id": ("STRING", {"default": "", "placeholder": "Paste a candidate_id; leave blank to view the first"}),
            }
        }

    def view(self, candidates_json, candidate_id=""):
        payload = _parse_research_payload(candidates_json)
        candidates = [item for item in payload["candidates"] if isinstance(item, dict)]
        selected_id = _text(candidate_id, 180)
        selected = next((item for item in candidates if _text(item.get("candidate_id", ""), 180) == selected_id), None) if selected_id else (candidates[0] if candidates else None)
        if not candidates:
            result = {
                "candidate_count": 0,
                "action_required": "No candidates were returned, so there is nothing to review yet. Broaden the concept, choose another base model, or retry the selected content mode.",
                "warnings": payload.get("warnings", []),
                "review_required": False,
            }
            text = _json_output(result)
            return _text_ui_result(text, text, "")
        if selected is None:
            raise ValueError("No matching candidate is available. Run Search Civitai first and use its candidate_id.")
        text = _json_output(selected)
        return _text_ui_result(text, text, _text(selected.get("candidate_id", ""), 180))


class VRGDG_ConceptResearchSaveApproved:
    """Save selected human-approved Civitai candidates into the Phase 1 store."""

    CATEGORY = _CATEGORY
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("save_result_json", "saved_count")
    FUNCTION = "save"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "candidates_json": ("STRING", {"default": "{}", "multiline": True, "forceInput": True}),
                "candidate_ids": ("STRING", {"default": "", "multiline": True, "placeholder": "Comma-separated candidate IDs, or all"}),
                "concept_key": ("STRING", {"default": "arched_back"}),
                "display_name": ("STRING", {"default": "Arched Back"}),
                "compatible_base_models": ("STRING", {"default": "Pony, Anima"}),
                "quality_score": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                "review_notes": ("STRING", {"default": "", "multiline": True, "placeholder": "Your notes after testing this candidate"}),
                "additional_tags": ("STRING", {"default": "civitai, reviewed"}),
            }
        }

    def save(self, candidates_json, candidate_ids, concept_key, display_name, compatible_base_models, quality_score, review_notes, additional_tags):
        placeholder = _text(candidate_ids, 4000).upper()
        if placeholder.startswith("PASTE_CANDIDATE_ID"):
            result = {
                "saved_count": 0,
                "saved": [],
                "action_required": "Paste a reviewed candidate_id from the Search and Review workflow before saving.",
                "review_required": True,
            }
            text = _json_output(result)
            return _text_ui_result(text, text, 0)
        result = save_approved_candidates(
            candidates_json,
            candidate_ids,
            concept_key,
            display_name,
            compatible_base_models,
            quality_score,
            review_notes,
            additional_tags,
        )
        text = _json_output(result)
        return _text_ui_result(text, text, int(result["saved_count"]))


NODE_CLASS_MAPPINGS = {
    "VRGDG_ConceptResearchCivitai": VRGDG_ConceptResearchCivitai,
    "VRGDG_ConceptResearchViewCandidate": VRGDG_ConceptResearchViewCandidate,
    "VRGDG_ConceptResearchSaveApproved": VRGDG_ConceptResearchSaveApproved,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGDG_ConceptResearchCivitai": "VRGDG Concept Research: Search Civitai",
    "VRGDG_ConceptResearchViewCandidate": "VRGDG Concept Research: View Candidate",
    "VRGDG_ConceptResearchSaveApproved": "VRGDG Concept Research: Save Approved Candidates",
}
