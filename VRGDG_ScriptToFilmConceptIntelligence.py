"""Script-to-Film-only concept recipe suggestions and review helpers.

This is the small integration layer between the existing Phase 1 Concept/Pose
Knowledge Base and the Phase 2 Civitai researcher.  It deliberately stores no
new knowledge format and does not import, write, or interpret Music Video,
Character Bible, or LoRA Knowledge Base data.

The planner calls the public helpers below through lightweight HTTP routes.
The three nodes make the same actions available on a normal ComfyUI canvas for
testing and advanced workflows.  Research is always review-only; saving still
uses Phase 2's explicit ``Save Approved Candidates`` node/action.
"""

from __future__ import annotations

import copy
import datetime as _datetime
import json
import re
from typing import Any


try:
    from .VRGDG_ConceptPoseKnowledgeBase import (
        _concept_key,
        _json_output,
        _text_ui_result,
        get_concept,
        list_concepts,
        retrieve_best_recipes,
    )
    from .VRGDG_ConceptResearchNodes import CivitaiAPIError, research_concept, save_approved_candidates
except ImportError:  # Direct-module fallback used by ComfyUI's resilient loader.
    from VRGDG_ConceptPoseKnowledgeBase import (  # type: ignore
        _concept_key,
        _json_output,
        _text_ui_result,
        get_concept,
        list_concepts,
        retrieve_best_recipes,
    )
    from VRGDG_ConceptResearchNodes import CivitaiAPIError, research_concept, save_approved_candidates  # type: ignore


_CATEGORY = "VRGDG/Knowledge/Script-to-Film Concept Intelligence"
_SUPPORTED_BASE_MODELS = {"pony": "Pony", "anima": "Anima"}


def _text(value: Any, limit: int = 16000) -> str:
    return str(value or "").strip()[:limit]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if result == result and abs(result) != float("inf") else float(default)


def _normalise_base_model(value: Any) -> str:
    raw = _text(value, 300)
    canonical = _SUPPORTED_BASE_MODELS.get(raw.lower())
    if canonical:
        return canonical
    if not raw:
        return "Pony"
    return raw


def _json_object(value: Any, field_name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    try:
        parsed = json.loads(_text(value, 2_000_000))
    except Exception as exc:
        raise ValueError(f"{field_name} must be valid JSON: {type(exc).__name__}")
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object.")
    return parsed


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _scene_text(scene: dict[str, Any]) -> str:
    """Return only scene-facing text suitable for a deterministic local match."""
    fields = (
        "label",
        "title",
        "script_beat",
        "story_beat",
        "physical_state_progression",
        "position_continuity_notes",
        "keyframe_prompt",
        "t2i_prompt",
        "unified_ltx_prompt",
        "i2v_prompt",
        "notes",
    )
    return " ".join(_text(scene.get(field, ""), 12000) for field in fields if _text(scene.get(field, ""), 12000))


def _normalised_phrase(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value, 12000).lower()).strip()


def _explicit_scene_concept(scene: dict[str, Any]) -> tuple[str, str]:
    for field in ("concept_key", "pose_concept", "concept", "concept_hint"):
        value = _text(scene.get(field, ""), 300)
        if value:
            return _concept_key(value), field
    return "", ""


def infer_scene_concept(scene: Any, root: str | None = None) -> dict[str, Any]:
    """Infer one local concept key without calling an LLM or external service.

    An explicit concept field wins.  Otherwise match known local concept names
    against the scene's pose/action/continuity text, preferring the longest
    exact phrase.  This keeps a suggestion predictable and gives the user a
    simple ``Concept / pose`` override in the planner when inference is vague.
    """
    source = scene if isinstance(scene, dict) else _json_object(scene, "scene")
    explicit_key, source_field = _explicit_scene_concept(source)
    known = list_concepts(root=root, include_recipes=False)
    known_by_key = {item["concept_key"]: item for item in known if isinstance(item, dict) and item.get("concept_key")}
    if explicit_key:
        item = known_by_key.get(explicit_key)
        return {
            "concept_key": explicit_key,
            "display_name": _text((item or {}).get("display_name", ""), 500) or explicit_key.replace("_", " ").title(),
            "inference": "explicit",
            "source_field": source_field,
            "is_local_concept": bool(item),
        }

    haystack = f" {_normalised_phrase(_scene_text(source))} "
    matches: list[tuple[int, str, dict[str, Any]]] = []
    for item in known:
        if not isinstance(item, dict):
            continue
        key = _text(item.get("concept_key", ""), 120)
        phrase = _normalised_phrase(key.replace("_", " "))
        if not phrase:
            continue
        needle = f" {phrase} "
        count = haystack.count(needle)
        if count:
            matches.append((count * 1000 + len(phrase), key, item))
    if not matches:
        return {
            "concept_key": "",
            "display_name": "",
            "inference": "none",
            "source_field": "",
            "is_local_concept": False,
        }
    _score, key, item = sorted(matches, key=lambda value: (-value[0], value[1]))[0]
    return {
        "concept_key": key,
        "display_name": _text(item.get("display_name", ""), 500) or key.replace("_", " ").title(),
        "inference": "scene_text",
        "source_field": "label/script_beat/continuity/prompts",
        "is_local_concept": True,
    }


def _prompt_preview(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", _text(value, 16000)).strip()
    return text if len(text) <= limit else text[: max(1, limit - 1)].rstrip() + "…"


def _compact_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    """Return the compact card needed in a scene editor, keeping full data internal."""
    loras = recipe.get("loras", []) if isinstance(recipe.get("loras"), list) else []
    return {
        "recipe_id": _text(recipe.get("recipe_id", ""), 180),
        "source": _text(recipe.get("source", ""), 500),
        "quality_score": _number(recipe.get("quality_score", 0), 0),
        "seed": _text(recipe.get("seed", ""), 120),
        "cfg": _number(recipe.get("cfg", 0), 0),
        "steps": max(0, int(_number(recipe.get("steps", 0), 0))),
        "sampler": _text(recipe.get("sampler", ""), 300),
        "model_name": _text(recipe.get("model_name", ""), 1024),
        "base_model": _text(recipe.get("base_model", ""), 300),
        "loras": copy.deepcopy(loras),
        "positive_prompt_preview": _prompt_preview(recipe.get("positive_prompt", "")),
        "negative_prompt_preview": _prompt_preview(recipe.get("negative_prompt", "")),
        "tags": copy.deepcopy(recipe.get("tags", [])) if isinstance(recipe.get("tags"), list) else [],
    }


def suggest_scene_recipes(scene: Any, base_model: Any = "Pony", limit: int = 3, root: str | None = None) -> dict[str, Any]:
    """Reuse Phase 1's quality-ranked Best Match result for one Film scene."""
    source = scene if isinstance(scene, dict) else _json_object(scene, "scene")
    model = _normalise_base_model(base_model)
    match = infer_scene_concept(source, root=root)
    key = match["concept_key"]
    if not key or not match["is_local_concept"]:
        return {
            "base_model": model,
            "scene_id": _text(source.get("id", ""), 180),
            "concept": match,
            "recipes": [],
            "message": "Add a Concept / pose value or describe a saved local concept in the scene to see recipe suggestions.",
        }
    result = retrieve_best_recipes(key, model, max(1, min(12, int(limit))), root=root)
    recipes = [_compact_recipe(recipe) for recipe in result.get("recipes", []) if isinstance(recipe, dict)]
    return {
        "base_model": model,
        "scene_id": _text(source.get("id", ""), 180),
        "concept": {**match, "display_name": result.get("concept", {}).get("display_name", match["display_name"])},
        "recipes": recipes,
        "message": "" if recipes else f"No {model}-compatible local recipes are saved for {match['display_name']} yet.",
    }


def _recipe_for_apply(concept_key: Any, recipe_id: Any, base_model: Any, root: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    key = _concept_key(concept_key)
    wanted_id = _text(recipe_id, 180)
    if not wanted_id:
        raise ValueError("Select a recipe before applying it to the Film scene.")
    concept = get_concept(key, root=root)
    if concept is None:
        raise ValueError(f"Concept '{key}' does not exist in the local Knowledge Base.")
    selected = next((item for item in concept.get("recipes", []) if isinstance(item, dict) and _text(item.get("recipe_id", ""), 180) == wanted_id), None)
    if selected is None:
        raise ValueError(f"Recipe '{wanted_id}' is not available under concept '{key}'.")
    model = _normalise_base_model(base_model)
    concept_models = {_text(item, 300).lower() for item in concept.get("compatible_base_models", []) if _text(item, 300)}
    recipe_model = _text(selected.get("base_model", ""), 300).lower()
    if (concept_models and model.lower() not in concept_models) or (recipe_model and recipe_model != model.lower()):
        raise ValueError(f"Recipe '{wanted_id}' is not compatible with the selected {model} keyframe model.")
    return concept, copy.deepcopy(selected)


def _append_prompt(existing: Any, fragment: Any) -> str:
    primary = _text(existing, 16000)
    extra = _text(fragment, 16000)
    if not extra:
        return primary
    if extra.lower() in primary.lower():
        return primary
    return f"{primary}, {extra}".strip(" ,")[:16000]


def apply_recipe_to_scene(scene: Any, concept_key: Any, recipe_id: Any, base_model: Any = "Pony", root: str | None = None) -> dict[str, Any]:
    """Apply a reviewed local recipe to one Film scene without changing the KB.

    The saved Pony/Anima workflows own their own sampler and negative nodes, so
    the selected recipe's seed/CFG/steps/sampler/negative prompt are retained
    as explicit scene metadata.  The positive fragment is appended to the Film
    keyframe prompt immediately.  This prevents a historical Civitai recipe
    from silently rewriting a workflow-managed negative stack or loading a
    LoRA the user has not deliberately mapped into their workflow.
    """
    target = scene if isinstance(scene, dict) else _json_object(scene, "scene")
    concept, recipe = _recipe_for_apply(concept_key, recipe_id, base_model, root=root)
    target = copy.deepcopy(target)
    positive = _text(recipe.get("positive_prompt", ""), 16000)
    negative = _text(recipe.get("negative_prompt", ""), 12000)
    target["keyframe_prompt"] = _append_prompt(target.get("keyframe_prompt", target.get("t2i_prompt", "")), positive)
    target["t2i_prompt"] = target["keyframe_prompt"]
    target["concept_key"] = concept["concept_key"]
    target["concept_recipe_positive_fragment"] = positive
    target["concept_recipe_negative_fragment"] = negative
    target["concept_recipe_loras"] = copy.deepcopy(recipe.get("loras", [])) if isinstance(recipe.get("loras"), list) else []
    target["concept_recipe_settings"] = {
        "seed": _text(recipe.get("seed", ""), 120),
        "cfg": _number(recipe.get("cfg", 0), 0),
        "steps": max(0, int(_number(recipe.get("steps", 0), 0))),
        "sampler": _text(recipe.get("sampler", ""), 300),
        "model_name": _text(recipe.get("model_name", ""), 1024),
    }
    target["applied_concept_recipe"] = {
        "concept_key": concept["concept_key"],
        "display_name": _text(concept.get("display_name", ""), 500),
        "recipe_id": _text(recipe.get("recipe_id", ""), 180),
        "source": _text(recipe.get("source", ""), 500),
        "base_model": _normalise_base_model(base_model),
        "applied_at": _utc_now(),
    }
    return {
        "scene": target,
        "concept": {
            "concept_key": concept["concept_key"],
            "display_name": _text(concept.get("display_name", ""), 500),
        },
        "recipe": _compact_recipe(recipe),
        "applied_fields": [
            "t2i_prompt",
            "concept_recipe_positive_fragment",
            "concept_recipe_negative_fragment",
            "concept_recipe_loras",
            "concept_recipe_settings",
            "applied_concept_recipe",
        ],
    }


def research_more_for_scene(concept_query: Any, base_model: Any = "Pony", max_candidates: int = 8, safe_only: bool = True) -> dict[str, Any]:
    """Delegate to Phase 2's public researcher; no candidate is saved here."""
    query = _text(concept_query, 300)
    if not query:
        raise ValueError("Add or infer a Concept / pose before researching more recipes.")
    try:
        return research_concept(query, _normalise_base_model(base_model), max(1, min(20, int(max_candidates))), bool(safe_only))
    except (ValueError, CivitaiAPIError) as exc:
        raise ValueError(f"Civitai concept research failed: {exc}")


def save_researched_scene_recipes(
    candidates_payload: Any,
    candidate_ids: Any,
    concept_key: Any,
    base_model: Any = "Pony",
    quality_score: float = 6.0,
    review_notes: Any = "",
) -> dict[str, Any]:
    """Delegate explicit human-approved saves to Phase 2's existing writer."""
    key = _concept_key(concept_key)
    selected_model = _normalise_base_model(base_model)
    return save_approved_candidates(
        candidates_payload,
        candidate_ids,
        key,
        key.replace("_", " ").title(),
        selected_model,
        max(0.0, min(10.0, _number(quality_score, 6.0))),
        _text(review_notes, 10000),
        "civitai, reviewed, script_to_film",
    )


class VRGDG_ScriptToFilmRecipeSuggestions:
    """Get quality-ranked local Concept/Pose recipe suggestions for one Film scene."""

    CATEGORY = _CATEGORY
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("suggestions_json", "suggestion_count")
    FUNCTION = "suggest"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_json": ("STRING", {"default": "{}", "multiline": True}),
            "base_model": (["Pony", "Anima"], {"default": "Pony"}),
            "limit": ("INT", {"default": 3, "min": 1, "max": 12, "step": 1}),
        }}

    def suggest(self, scene_json, base_model, limit):
        result = suggest_scene_recipes(scene_json, base_model, limit)
        text = _json_output(result)
        return _text_ui_result(text, text, len(result["recipes"]))


class VRGDG_ScriptToFilmApplyRecipe:
    """Apply a selected local Concept/Pose recipe to one Film scene JSON record."""

    CATEGORY = _CATEGORY
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("scene_json", "applied_recipe_id")
    FUNCTION = "apply"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_json": ("STRING", {"default": "{}", "multiline": True}),
            "concept_key": ("STRING", {"default": "arched_back"}),
            "recipe_id": ("STRING", {"default": ""}),
            "base_model": (["Pony", "Anima"], {"default": "Pony"}),
        }}

    def apply(self, scene_json, concept_key, recipe_id, base_model):
        result = apply_recipe_to_scene(scene_json, concept_key, recipe_id, base_model)
        text = _json_output(result["scene"])
        return _text_ui_result(text, text, result["recipe"]["recipe_id"])


class VRGDG_ScriptToFilmResearchMore:
    """Research review-only candidates using the existing Phase 2 helper."""

    CATEGORY = _CATEGORY
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("candidates_json", "candidate_count")
    FUNCTION = "research"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "concept_query": ("STRING", {"default": "arched_back"}),
            "base_model": (["Pony", "Anima"], {"default": "Pony"}),
            "max_candidates": ("INT", {"default": 8, "min": 1, "max": 20, "step": 1}),
            "safe_only": ("BOOLEAN", {"default": True, "label_on": "Safe-only search", "label_off": "Adult-allowed search"}),
        }}

    def research(self, concept_query, base_model, max_candidates, safe_only):
        result = research_more_for_scene(concept_query, base_model, max_candidates, safe_only)
        text = _json_output(result)
        return _text_ui_result(text, text, len(result.get("candidates", [])))


NODE_CLASS_MAPPINGS = {
    "VRGDG_ScriptToFilmRecipeSuggestions": VRGDG_ScriptToFilmRecipeSuggestions,
    "VRGDG_ScriptToFilmApplyRecipe": VRGDG_ScriptToFilmApplyRecipe,
    "VRGDG_ScriptToFilmResearchMore": VRGDG_ScriptToFilmResearchMore,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGDG_ScriptToFilmRecipeSuggestions": "VRGDG Film Concepts: Suggest Local Recipes",
    "VRGDG_ScriptToFilmApplyRecipe": "VRGDG Film Concepts: Apply Recipe to Scene",
    "VRGDG_ScriptToFilmResearchMore": "VRGDG Film Concepts: Research More (Review First)",
}
