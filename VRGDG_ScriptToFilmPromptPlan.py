"""Pure structured-plan helpers for the isolated Script-to-Film route.

Keeping this parsing layer free of ComfyUI imports lets it be contract-tested
without starting the node server. The route supplies its shared JSON cleanup
function so Music Video's historical cleanup remains untouched.
"""

import json
import re


FILM_PROMPT_CREATOR_MIN_CONTEXT = 16384


def film_prompt_creator_settings(value):
    """Return Film-only LLM settings with room for a multi-scene document."""
    settings = dict(value) if isinstance(value, dict) else {}
    try:
        requested_context = int(float(settings.get("n_ctx", 0) or 0))
    except (TypeError, ValueError):
        requested_context = 0
    settings["n_ctx"] = max(FILM_PROMPT_CREATOR_MIN_CONTEXT, requested_context)
    return settings


def scene_list_from_plan_value(value):
    """Return a scene array from the two supported structured JSON shapes."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        scenes = value.get("scenes", value.get("film_scenes", []))
        return scenes if isinstance(scenes, list) else []
    return []


def complete_scene_items_from_partial_json(text):
    """Keep complete direct scene objects from a response cut off mid-array."""
    source = str(text or "")
    array_match = re.search(r'"(?:scenes|film_scenes)"\s*:\s*\[', source, flags=re.IGNORECASE)
    if not array_match:
        return []
    decoder = json.JSONDecoder()
    cursor = array_match.end()
    recovered = []
    while cursor < len(source):
        while cursor < len(source) and source[cursor] in " \t\r\n,":
            cursor += 1
        if cursor >= len(source) or source[cursor] == "]":
            break
        try:
            item, cursor = decoder.raw_decode(source, cursor)
        except json.JSONDecodeError:
            break
        if not isinstance(item, dict):
            break
        recovered.append(item)
    return recovered


def extract_film_scene_plan(text, extract_json_object):
    """Parse normal, list-root, or safely usable partial Film model output.

    `extract_json_object` is passed in by the Film route to retain its shared
    legacy cleanup/repair behaviour before this Film-only shape validation.
    Returns `(scene_records, parse_mode)`.
    """
    parse_error = None
    try:
        parsed = extract_json_object(text)
        scenes = scene_list_from_plan_value(parsed)
        if scenes:
            return scenes, "complete_document"
    except Exception as exc:
        parse_error = exc

    partial_scenes = complete_scene_items_from_partial_json(text)
    if partial_scenes:
        return partial_scenes, "partial_array"

    if parse_error:
        raise parse_error
    raise ValueError("Film Prompt Creator JSON did not contain a scenes array.")
