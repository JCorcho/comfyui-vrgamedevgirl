"""Local Concept / Pose Knowledge Base nodes.

Phase 1 is deliberately a small, file-backed recipe library. It has no Civitai
network calls, no prompt-generation hooks, and no links to the Character Bible,
LoRA Knowledge Base, Script-to-Film, or Music Video renderer. Future research
tools can read and write the same documented JSON files without importing this
module.
"""

import copy
import datetime as _datetime
import json
import os
import re
import tempfile
import uuid


_ROOT = os.path.dirname(os.path.abspath(__file__))
_CONCEPTS_ROOT = os.path.join(_ROOT, "knowledge_base", "concepts")
_EXAMPLES_DIRNAME = "examples"
_LOCAL_DIRNAME = "local"
_STORE_VERSION = 1


def _utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value, limit=12000):
    return str(value or "").strip()[:limit]


def _finite_number(value, default=0.0):
    try:
        result = float(value)
    except Exception:
        return float(default)
    return result if result == result and abs(result) != float("inf") else float(default)


def _concept_key(value):
    key = re.sub(r"[^a-z0-9]+", "_", _safe_text(value, 240).lower()).strip("_")
    if not key:
        raise ValueError("Concept key needs at least one letter or number.")
    return key[:120]


def _root_paths(root=None):
    selected = os.path.abspath(root or _CONCEPTS_ROOT)
    examples = os.path.join(selected, _EXAMPLES_DIRNAME)
    local = os.path.join(selected, _LOCAL_DIRNAME)
    return selected, examples, local


def _json_list(value, field_name):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as exc:
            raise ValueError(f"{field_name} must be valid JSON: {type(exc).__name__}")
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array.")
    return value


def _string_list(value, field_name, limit=80):
    if isinstance(value, str):
        values = re.split(r"[,\n;]", value)
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = []
    result = []
    seen = set()
    for item in values:
        clean = _safe_text(item, 300)
        identity = clean.lower()
        if clean and identity not in seen:
            seen.add(identity)
            result.append(clean)
    return result[:limit]


def _normalise_loras(value):
    raw = _json_list(value, "loras") if isinstance(value, str) else (value if isinstance(value, list) else [])
    result = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each LoRA must be an object with name and weight.")
        name = _safe_text(item.get("name", ""), 1024).replace("\\", "/")
        if not name:
            raise ValueError("Each LoRA needs a name.")
        identity = name.lower()
        if identity in seen:
            continue
        seen.add(identity)
        result.append({
            "name": name,
            "weight": max(-5.0, min(5.0, _finite_number(item.get("weight", 1.0), 1.0))),
        })
    return result[:48]


def _normalise_recipe(value, existing=None):
    source = value if isinstance(value, dict) else {}
    old = existing if isinstance(existing, dict) else {}
    recipe_id = _safe_text(source.get("recipe_id", old.get("recipe_id", "")), 180) or f"recipe_{uuid.uuid4().hex[:16]}"
    tags = source.get("tags", old.get("tags", []))
    if isinstance(tags, str) and tags.lstrip().startswith("["):
        tags = _json_list(tags, "tags")
    return {
        "recipe_id": recipe_id,
        "source": _safe_text(source.get("source", old.get("source", "local")), 500) or "local",
        "positive_prompt": _safe_text(source.get("positive_prompt", old.get("positive_prompt", "")), 16000),
        "negative_prompt": _safe_text(source.get("negative_prompt", old.get("negative_prompt", "")), 12000),
        "loras": _normalise_loras(source.get("loras", old.get("loras", []))),
        "seed": _safe_text(source.get("seed", old.get("seed", "")), 120),
        "cfg": max(0.0, min(100.0, _finite_number(source.get("cfg", old.get("cfg", 0.0)), 0.0))),
        "steps": max(0, min(1000, int(_finite_number(source.get("steps", old.get("steps", 0)), 0)))),
        "sampler": _safe_text(source.get("sampler", old.get("sampler", "")), 300),
        "model_name": _safe_text(source.get("model_name", old.get("model_name", "")), 1024),
        # The per-recipe family is optional but makes best-match selection
        # precise when a concept has recipes for several base families.
        "base_model": _safe_text(source.get("base_model", old.get("base_model", "")), 300),
        "notes": _safe_text(source.get("notes", old.get("notes", "")), 12000),
        "quality_score": max(0.0, min(10.0, _finite_number(source.get("quality_score", old.get("quality_score", 0.0)), 0.0))),
        "date_added": _safe_text(source.get("date_added", old.get("date_added", "")), 64) or _utc_now(),
        "tags": _string_list(tags, "tags"),
    }


def _normalise_concept(value, fallback_key=""):
    source = value if isinstance(value, dict) else {}
    key = _concept_key(source.get("concept_key", fallback_key))
    recipes = source.get("recipes", [])
    if not isinstance(recipes, list):
        recipes = []
    normalised_recipes = []
    seen = set()
    for raw in recipes:
        if not isinstance(raw, dict):
            continue
        recipe = _normalise_recipe(raw)
        identity = recipe["recipe_id"].lower()
        if identity not in seen:
            seen.add(identity)
            normalised_recipes.append(recipe)
    return {
        "schema_version": _STORE_VERSION,
        "concept_key": key,
        "display_name": _safe_text(source.get("display_name", key.replace("_", " ").title()), 500) or key.replace("_", " ").title(),
        "compatible_base_models": _string_list(source.get("compatible_base_models", []), "compatible_base_models", 40),
        "recipes": normalised_recipes,
    }


def _read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except Exception:
        return None


def _atomic_write_json(path, payload):
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(prefix="concept_recipe_", suffix=".json", dir=parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, path)
    finally:
        try:
            if os.path.isfile(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass


def _concept_file_paths(root=None):
    _selected, examples, local = _root_paths(root)
    # Examples are read first. A local file with the same concept key is an
    # explicit user override, so it is read second and wins without modifying
    # the tracked sample file.
    result = []
    for folder in (examples, local):
        if not os.path.isdir(folder):
            continue
        for filename in sorted(os.listdir(folder), key=str.lower):
            if filename.lower().endswith(".json"):
                result.append(os.path.join(folder, filename))
    return result


def list_concepts(root=None, include_recipes=False):
    concepts = {}
    for path in _concept_file_paths(root):
        raw = _read_json_file(path)
        if not isinstance(raw, dict):
            continue
        try:
            concept = _normalise_concept(raw, os.path.splitext(os.path.basename(path))[0])
        except ValueError:
            continue
        concepts[concept["concept_key"]] = concept
    records = []
    for concept in sorted(concepts.values(), key=lambda item: (item["display_name"].lower(), item["concept_key"])):
        if include_recipes:
            records.append(copy.deepcopy(concept))
        else:
            records.append({
                "concept_key": concept["concept_key"],
                "display_name": concept["display_name"],
                "compatible_base_models": concept["compatible_base_models"],
                "recipe_count": len(concept["recipes"]),
            })
    return records


def get_concept(concept_key, root=None):
    target = _concept_key(concept_key)
    for concept in list_concepts(root, include_recipes=True):
        if concept["concept_key"] == target:
            return concept
    return None


def _local_concept_path(concept_key, root=None):
    _selected, _examples, local = _root_paths(root)
    key = _concept_key(concept_key)
    return os.path.join(local, f"{key}.json")


def save_recipe(concept_key, display_name, compatible_base_models, recipe, root=None):
    key = _concept_key(concept_key)
    concept = get_concept(key, root) or {
        "schema_version": _STORE_VERSION,
        "concept_key": key,
        "display_name": key.replace("_", " ").title(),
        "compatible_base_models": [],
        "recipes": [],
    }
    if _safe_text(display_name, 500):
        concept["display_name"] = _safe_text(display_name, 500)
    models = _string_list(compatible_base_models, "compatible_base_models", 40)
    if models:
        concept["compatible_base_models"] = models
    incoming_id = _safe_text(recipe.get("recipe_id", ""), 180) if isinstance(recipe, dict) else ""
    existing = next((item for item in concept["recipes"] if incoming_id and item["recipe_id"] == incoming_id), None)
    clean_recipe = _normalise_recipe(recipe, existing)
    if existing is None:
        concept["recipes"].append(clean_recipe)
        action = "added"
    else:
        position = concept["recipes"].index(existing)
        concept["recipes"][position] = clean_recipe
        action = "updated"
    clean_concept = _normalise_concept(concept, key)
    _atomic_write_json(_local_concept_path(key, root), clean_concept)
    return {"action": action, "concept": clean_concept, "recipe": clean_recipe}


def delete_recipe(concept_key, recipe_id, root=None):
    concept = get_concept(concept_key, root)
    if concept is None:
        raise ValueError(f"Concept '{_concept_key(concept_key)}' does not exist.")
    target_id = _safe_text(recipe_id, 180)
    if not target_id:
        raise ValueError("Recipe ID is required for deletion.")
    remaining = [recipe for recipe in concept["recipes"] if recipe["recipe_id"] != target_id]
    if len(remaining) == len(concept["recipes"]):
        raise ValueError(f"Recipe '{target_id}' was not found in concept '{concept['concept_key']}'.")
    concept["recipes"] = remaining
    clean_concept = _normalise_concept(concept, concept["concept_key"])
    # A test/local-only concept should disappear completely once its final
    # recipe is deleted.  This avoids littering the user's library with empty
    # records, and removing a local override also correctly reveals a tracked
    # example concept again when one exists.
    if not clean_concept["recipes"]:
        local_path = _local_concept_path(clean_concept["concept_key"], root)
        if os.path.isfile(local_path):
            os.remove(local_path)
        visible_concept = get_concept(clean_concept["concept_key"], root)
        return {
            "deleted": True,
            "concept": visible_concept or clean_concept,
            "deleted_recipe_id": target_id,
            "removed_empty_local_concept": True,
        }
    _atomic_write_json(_local_concept_path(clean_concept["concept_key"], root), clean_concept)
    return {"deleted": True, "concept": clean_concept, "deleted_recipe_id": target_id}


def retrieve_best_recipes(concept_key, base_model="", limit=5, root=None):
    concept = get_concept(concept_key, root)
    if concept is None:
        raise ValueError(f"Concept '{_concept_key(concept_key)}' does not exist.")
    requested = _safe_text(base_model, 300).lower()
    compatible = {item.lower() for item in concept["compatible_base_models"]}
    if requested and compatible and requested not in compatible:
        return {"concept": concept, "base_model": base_model, "recipes": []}
    recipes = []
    for recipe in concept["recipes"]:
        recipe_base = _safe_text(recipe.get("base_model", ""), 300).lower()
        if requested and recipe_base and recipe_base != requested:
            continue
        recipes.append(copy.deepcopy(recipe))
    recipes.sort(key=lambda item: (-_finite_number(item.get("quality_score", 0), 0), str(item.get("date_added", "")), item["recipe_id"]))
    return {
        "concept": {
            "concept_key": concept["concept_key"],
            "display_name": concept["display_name"],
            "compatible_base_models": concept["compatible_base_models"],
        },
        "base_model": _safe_text(base_model, 300),
        "recipes": recipes[:max(1, min(100, int(limit)))],
    }


def _json_output(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _text_ui_result(text, *result):
    """Make standalone V1 knowledge nodes readable directly in the canvas."""
    return {"ui": {"text": [text]}, "result": result}


class VRGDG_ConceptRecipeList:
    """List concept keys and recipe counts without changing the store."""

    CATEGORY = "VRGDG/Knowledge/Concept Recipes"
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("concepts_json", "concept_count")
    FUNCTION = "list_recipes"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"include_recipes": ("BOOLEAN", {"default": False})}}

    def list_recipes(self, include_recipes=False):
        concepts = list_concepts(include_recipes=bool(include_recipes))
        text = _json_output(concepts)
        return _text_ui_result(text, text, len(concepts))


class VRGDG_ConceptRecipeView:
    """View every full recipe stored for one concept key."""

    CATEGORY = "VRGDG/Knowledge/Concept Recipes"
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("concept_json", "recipe_count")
    FUNCTION = "view"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"concept_key": ("STRING", {"default": "arched_back"})}}

    def view(self, concept_key):
        concept = get_concept(concept_key)
        if concept is None:
            raise ValueError(f"Concept '{_concept_key(concept_key)}' does not exist.")
        text = _json_output(concept)
        return _text_ui_result(text, text, len(concept["recipes"]))


class VRGDG_ConceptRecipeSave:
    """Create or edit a complete local generation recipe."""

    CATEGORY = "VRGDG/Knowledge/Concept Recipes"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("concept_json", "recipe_id")
    FUNCTION = "save"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "concept_key": ("STRING", {"default": "arched_back"}),
                "display_name": ("STRING", {"default": "Arched Back"}),
                "compatible_base_models": ("STRING", {"default": "Pony, Anima"}),
                "source": ("STRING", {"default": "local"}),
                "positive_prompt": ("STRING", {"default": "", "multiline": True}),
                "negative_prompt": ("STRING", {"default": "", "multiline": True}),
                "loras_json": ("STRING", {"default": "[]", "multiline": True}),
                "seed": ("STRING", {"default": ""}),
                "cfg": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "steps": ("INT", {"default": 28, "min": 0, "max": 1000, "step": 1}),
                "sampler": ("STRING", {"default": "euler"}),
                "model_name": ("STRING", {"default": ""}),
                "base_model": ("STRING", {"default": "Pony"}),
                "notes": ("STRING", {"default": "", "multiline": True}),
                "quality_score": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                "tags": ("STRING", {"default": ""}),
            },
            "optional": {"recipe_id": ("STRING", {"default": ""})},
        }

    def save(self, concept_key, display_name, compatible_base_models, source, positive_prompt, negative_prompt, loras_json, seed, cfg, steps, sampler, model_name, base_model, notes, quality_score, tags, recipe_id=""):
        result = save_recipe(concept_key, display_name, compatible_base_models, {
            "recipe_id": recipe_id,
            "source": source,
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "loras": loras_json,
            "seed": seed,
            "cfg": cfg,
            "steps": steps,
            "sampler": sampler,
            "model_name": model_name,
            "base_model": base_model,
            "notes": notes,
            "quality_score": quality_score,
            "tags": tags,
        })
        text = _json_output(result["concept"])
        return _text_ui_result(text, text, result["recipe"]["recipe_id"])


class VRGDG_ConceptRecipeDelete:
    """Delete one recipe by its stable recipe ID."""

    CATEGORY = "VRGDG/Knowledge/Concept Recipes"
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("concept_json", "recipe_count")
    FUNCTION = "delete"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "concept_key": ("STRING", {"default": "arched_back"}),
            "recipe_id": ("STRING", {"default": ""}),
        }}

    def delete(self, concept_key, recipe_id):
        result = delete_recipe(concept_key, recipe_id)
        text = _json_output(result["concept"])
        return _text_ui_result(text, text, len(result["concept"]["recipes"]))


class VRGDG_ConceptRecipeBestMatch:
    """Return a concept's highest-scored recipes compatible with one base model."""

    CATEGORY = "VRGDG/Knowledge/Concept Recipes"
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("recipes_json", "recipe_count")
    FUNCTION = "retrieve"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "concept_key": ("STRING", {"default": "arched_back"}),
            "base_model": ("STRING", {"default": "Pony"}),
            "limit": ("INT", {"default": 5, "min": 1, "max": 100, "step": 1}),
        }}

    def retrieve(self, concept_key, base_model, limit):
        result = retrieve_best_recipes(concept_key, base_model, limit)
        text = _json_output(result)
        return _text_ui_result(text, text, len(result["recipes"]))


NODE_CLASS_MAPPINGS = {
    "VRGDG_ConceptRecipeList": VRGDG_ConceptRecipeList,
    "VRGDG_ConceptRecipeView": VRGDG_ConceptRecipeView,
    "VRGDG_ConceptRecipeSave": VRGDG_ConceptRecipeSave,
    "VRGDG_ConceptRecipeDelete": VRGDG_ConceptRecipeDelete,
    "VRGDG_ConceptRecipeBestMatch": VRGDG_ConceptRecipeBestMatch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGDG_ConceptRecipeList": "VRGDG Concept Recipes: List Concepts",
    "VRGDG_ConceptRecipeView": "VRGDG Concept Recipes: View Concept",
    "VRGDG_ConceptRecipeSave": "VRGDG Concept Recipes: Save Recipe",
    "VRGDG_ConceptRecipeDelete": "VRGDG Concept Recipes: Delete Recipe",
    "VRGDG_ConceptRecipeBestMatch": "VRGDG Concept Recipes: Best Match",
}
