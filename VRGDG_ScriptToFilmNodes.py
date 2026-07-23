"""Isolated Script-to-Film planning, native-audio LTX routing, and final mix routes.

This module deliberately does not change the Music Video workflow.  Its API routes
use a separate Film project schema and a separate API workflow template.  The only
shared implementation seam is the existing Violets LTX 2.3 FP8 loader-profile
patch, which keeps its mandatory DMD/JoyAI LoRAs locked in the backend.
"""

import asyncio
import copy
import json
import math
import os
import shutil
import subprocess
import time
import uuid

import folder_paths
from aiohttp import web
from PIL import Image
from server import PromptServer

from .VRGDG_LoraKnowledgeBase import (
    list_knowledge,
    load_style_profile,
    normalize_lora_names,
    prompt_creator_context,
    refresh_knowledge,
    research_civitai,
    resolution_fragment,
    resolve_scene_triggers,
    sanitize_character_bible,
    store_path as lora_knowledge_store_path,
    upsert_entry,
)
from .VRGDG_MusicVideoPromptCreatorNodes import _extract_json_object, _run_text_gemma_custom
from .VRGDG_ScriptToFilmConceptIntelligence import (
    apply_recipe_to_scene,
    research_more_for_scene,
    save_researched_scene_recipes,
    suggest_scene_recipes,
)
from .VRGDG_WorkflowRunnerNodes import (
    _DEFAULT_I2V_PASS1_SIGMAS,
    _DEFAULT_I2V_PASS2_SIGMAS,
    _I2V_MODEL_PROFILE_VIOLETS_LTX23_FP8,
    _MAX_LORA_SLOTS,
    _NONE_LORA,
    _VIOLETS_LTX23_FP8_CHECKPOINT,
    _VIOLETS_LTX23_TEXT_ENCODER,
    _clean_lora_name,
    _find_ffmpeg_path,
    _float_payload,
    _int_payload,
    _load_api_template,
    _normalize_sigma_list_text,
    _patch_i2v_node_overrides,
    _patch_violets_ltx23_fp8_profile,
    _prepare_optional_input_image_name,
    _scene_render_output_folder,
    _set_api_input,
)


_SCRIPT_TO_FILM_ROUTES_REGISTERED = False
_FRAME_INTERVAL = 8
_MIN_FRAMES = 9
_DEFAULT_FPS = 25
_DEFAULT_TARGET_SECONDS = 4.0
_MAX_SCENE_SECONDS = 120.0
_FILM_PROFILE = "film_t2av_character_ref"
_FILM_PROFILE_LABEL = "Film/T2AV + Character Ref"
_ROOT = os.path.dirname(os.path.abspath(__file__))
_FILM_PLACEHOLDER_IMAGE_NAME = "vrgdg_script_to_film_placeholder.png"
_SCRIPT_PROMPT_JOBS = {}
_SCRIPT_PROMPT_JOB_TTL_SECONDS = 1800
_FILM_KEYFRAME_MODELS = {"pony", "anima"}


def _template_path():
    return os.path.join(_ROOT, "Workflows", "UsedForUIDoNotTouch", "ScriptToFilm_T2AV_CharacterRef_API.json")


def _system_prompt_path():
    return os.path.join(_ROOT, "prompts", "ScriptToFilm_PromptCreator_System.txt")


def _safe_project_folder(value):
    project = os.path.abspath(str(value or "").strip().strip('"'))
    if not project:
        raise ValueError("Project folder is empty.")
    output_root = os.path.abspath(folder_paths.get_output_directory())
    try:
        if os.path.commonpath([project, output_root]) != output_root:
            raise ValueError("Script-to-Film projects must stay inside ComfyUI's output directory.")
    except ValueError:
        raise ValueError("Script-to-Film project folder is not valid for this machine.")
    os.makedirs(project, exist_ok=True)
    return project


def _read_system_prompt():
    path = _system_prompt_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Script-to-Film system prompt was not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as handle:
        text = handle.read().strip()
    if "# [GROK_EXPAND_SYSTEM_PROMPT_START]" not in text or "# [GROK_EXPAND_SYSTEM_PROMPT_END]" not in text:
        raise ValueError("Script-to-Film system prompt is missing its required GROK swap markers.")
    return text, path


def _ensure_film_placeholder_load_image():
    """Create a valid non-trivial image for bypassed T2AV reference nodes.

    Comfy still executes a LoadImage node even when LTX I2V conditioning is
    bypassed. The legacy 1×1 placeholder is rejected by the current PyAV image
    loader, so Film owns a 64×64 RGB placeholder without altering music paths.
    """
    input_dir = folder_paths.get_input_directory()
    os.makedirs(input_dir, exist_ok=True)
    path = os.path.join(input_dir, _FILM_PLACEHOLDER_IMAGE_NAME)
    if os.path.isfile(path) and os.path.getsize(path) > 128:
        return _FILM_PLACEHOLDER_IMAGE_NAME
    Image.new("RGB", (64, 64), (15, 23, 42)).save(path, format="PNG")
    return _FILM_PLACEHOLDER_IMAGE_NAME


def _finite_number(value, default=0.0):
    try:
        number = float(value)
    except Exception:
        return float(default)
    return number if math.isfinite(number) else float(default)


def _safe_text(value, limit=12000):
    return str(value or "").strip()[:limit]


def _film_keyframe_model(value):
    """Keep the Film-only T2I base model explicit and restricted to adapters.

    A Film plan can use either installed workflow-managed keyframe adapter.  It
    never changes the Builder's global Music Video image-mode selection.
    """
    selected = _safe_text(value, 100).lower()
    return selected if selected in _FILM_KEYFRAME_MODELS else "pony"


def _frame_plan(seconds, fps):
    clean_fps = max(1, min(120, int(fps or _DEFAULT_FPS)))
    requested_seconds = max(0.05, min(_MAX_SCENE_SECONDS, _finite_number(seconds, _DEFAULT_TARGET_SECONDS)))
    # LTX accepts lengths where (frames - 1) is divisible by eight. Round upward
    # so a planned action is never cut short just to meet the latent constraint.
    intervals = max(_FRAME_INTERVAL, int(math.ceil((requested_seconds * clean_fps) / _FRAME_INTERVAL)) * _FRAME_INTERVAL)
    frames = intervals + 1
    return {
        "fps": clean_fps,
        "planned_frames": frames,
        "target_duration_seconds": intervals / clean_fps,
    }


def _valid_frames(value):
    try:
        frames = int(value)
    except Exception:
        return 0
    if frames < _MIN_FRAMES or (frames - 1) % _FRAME_INTERVAL:
        return 0
    return frames


def _normalize_character_bible(value):
    source = value if isinstance(value, dict) else {"summary": _safe_text(value, 2000)}
    raw_refs = source.get("face_refs", source.get("face_references", []))
    if isinstance(raw_refs, str):
        raw_refs = [raw_refs] if raw_refs.strip() else []
    if not isinstance(raw_refs, list):
        raw_refs = []
    return {
        "face_refs": [_safe_text(item, 1024) for item in raw_refs if _safe_text(item, 1024)],
        "body_type": _safe_text(source.get("body_type", ""), 1000),
        "distinguishing_features": _safe_text(source.get("distinguishing_features", ""), 2000),
        "clothing_state": _safe_text(source.get("clothing_state", ""), 2000),
        "summary": _safe_text(source.get("summary", ""), 3000),
    }


def _payload_lora_names(payload, scene=None):
    """Select per-scene knowledge refs, falling back to Film-project refs.

    A scene may deliberately narrow a project's active character/style LoRAs.
    When it does not, the project selection is the non-destructive default.
    """
    source_scene = scene if isinstance(scene, dict) else {}
    direct = normalize_lora_names(source_scene.get("lora_knowledge_refs", []))
    if direct:
        return direct
    source_payload = payload if isinstance(payload, dict) else {}
    direct = normalize_lora_names(source_payload.get("lora_knowledge_loras", source_payload.get("lora_knowledge_refs", [])))
    if direct:
        return direct
    film_config = source_payload.get("script_to_film", {})
    return normalize_lora_names(film_config.get("lora_knowledge_loras", [])) if isinstance(film_config, dict) else []


def _payload_style_profile(payload):
    source = payload if isinstance(payload, dict) else {}
    film_config = source.get("script_to_film", {}) if isinstance(source.get("script_to_film"), dict) else {}
    return load_style_profile(
        source.get("style_profile", film_config.get("style_profile")),
        source.get("style_profile_path", film_config.get("style_profile_path", "")),
    )


def _append_prompt_fragment(prompt, fragment, target):
    text = _safe_text(prompt, 12000)
    extra = _safe_text(fragment, 4000)
    if not extra:
        return text
    missing = []
    lower_text = text.lower()
    for value in [piece.strip() for piece in extra.split(",") if piece.strip()]:
        if value.lower() not in lower_text:
            missing.append(value)
    if not missing:
        return text
    joined = ", ".join(missing)
    if target == "keyframe":
        return _safe_text(f"{joined}, {text}".strip(" ,"), 12000)
    sentence = f" Exact visual reference tokens for this shot: {joined}."
    return _safe_text(f"{text.rstrip()} {sentence}".strip(), 12000)


def _resolve_scene_lora_knowledge(scene, payload=None):
    """Resolve Film-only LoRA metadata without contaminating Character Bible.

    The keyframe and LTX prompts are resolved separately because a Pony/SDXL
    LoRA must never be presented as an LTX-compatible adapter, and vice versa.
    The stored trigger strings are attached only to the shot prompts.
    """
    source = scene if isinstance(scene, dict) else {}
    scene_specific_names = normalize_lora_names(source.get("lora_knowledge_refs", []))
    selected_names = _payload_lora_names(payload or {}, source)
    style_profile = _payload_style_profile(payload or {})
    keyframe_resolved = resolve_scene_triggers(source, selected_names, "pony")
    ltx_resolved = resolve_scene_triggers(source, selected_names, "ltx")
    source["character_bible"] = sanitize_character_bible(source.get("character_bible", {}), selected_names)
    # Preserve an empty per-scene field so it continues to inherit any future
    # project-level selection change. The resolved list records what this shot
    # actually used at this point in time.
    source["lora_knowledge_refs"] = scene_specific_names
    source["resolved_lora_knowledge_refs"] = selected_names
    source["resolved_lora_triggers"] = {
        "keyframe": keyframe_resolved,
        "ltx": ltx_resolved,
    }
    source["style_profile_link"] = {
        "path": style_profile.get("path", ""),
        "name": style_profile.get("name", ""),
    }
    keyframe_fragment = ", ".join(item for item in (
        resolution_fragment(keyframe_resolved),
        _safe_text(style_profile.get("keyframe_fragment", ""), 4000),
    ) if item)
    ltx_fragment = ", ".join(item for item in (
        resolution_fragment(ltx_resolved),
        _safe_text(style_profile.get("ltx_fragment", ""), 4000),
    ) if item)
    source["keyframe_prompt"] = _append_prompt_fragment(
        source.get("keyframe_prompt", source.get("t2i_prompt", "")), keyframe_fragment, "keyframe"
    )
    source["unified_ltx_prompt"] = _append_prompt_fragment(
        source.get("unified_ltx_prompt", source.get("i2v_prompt", "")), ltx_fragment, "ltx"
    )
    source["t2i_prompt"] = source["keyframe_prompt"]
    source["i2v_prompt"] = source["unified_ltx_prompt"]
    return source


def _normalize_intensity(value):
    source = value if isinstance(value, dict) else {"summary": _safe_text(value, 2000)}
    return {
        "start": _safe_text(source.get("start", ""), 1000),
        "middle": _safe_text(source.get("middle", ""), 1000),
        "end": _safe_text(source.get("end", ""), 1000),
        "peak_moment": _safe_text(source.get("peak_moment", ""), 1000),
        "summary": _safe_text(source.get("summary", ""), 2000),
    }


def _normalize_scene(raw_scene, index, fps):
    source = raw_scene if isinstance(raw_scene, dict) else {}
    scene_number = max(1, int(_finite_number(source.get("scene_number", index + 1), index + 1)))
    # Local LLMs are not asked to invent an internal Builder identifier.  Give
    # every normalized scene a deterministic ID before it crosses the API/UI
    # boundary, so Builder timeline reconciliation never treats several scenes
    # as one blank-keyed record.
    scene_id = _safe_text(source.get("id", ""), 180) or f"film_scene_{scene_number:04d}"
    requested_duration = source.get("target_duration_seconds", source.get("duration_seconds", _DEFAULT_TARGET_SECONDS))
    planned_frames = _valid_frames(source.get("planned_frames"))
    frame_plan = _frame_plan(requested_duration, fps)
    if planned_frames:
        frame_plan["planned_frames"] = planned_frames
        frame_plan["target_duration_seconds"] = (planned_frames - 1) / frame_plan["fps"]
    render_mode = _safe_text(source.get("film_render_mode", source.get("render_mode", "i2v_t2av")), 80).lower()
    if render_mode not in {"t2av", "i2v_t2av"}:
        render_mode = "i2v_t2av"
    ducking = max(0.0, min(1.0, _finite_number(source.get("ducking_level", 0.25), 0.25)))
    record = {
        "id": scene_id,
        "scene_number": scene_number,
        "label": _safe_text(source.get("label", source.get("title", f"Film scene {index + 1}")), 500),
        "script_beat": _safe_text(source.get("script_beat", source.get("story_beat", "")), 6000),
        "keyframe_prompt": _safe_text(source.get("keyframe_prompt", source.get("t2i_prompt", source.get("image_prompt", ""))), 8000),
        "unified_ltx_prompt": _safe_text(source.get("unified_ltx_prompt", source.get("i2v_prompt", source.get("ltx_prompt", ""))), 12000),
        "spoken_dialogue": _safe_text(source.get("spoken_dialogue", source.get("dialogue", "")), 5000),
        "character_bible": _normalize_character_bible(source.get("character_bible", {})),
        # These are generation-metadata references only.  Trigger strings are
        # resolved later into shot prompts and are never copied into the Bible.
        "lora_knowledge_refs": normalize_lora_names(source.get("lora_knowledge_refs", source.get("lora_refs", []))),
        "lora_trigger_keys": source.get("lora_trigger_keys", {}) if isinstance(source.get("lora_trigger_keys", {}), (dict, list)) else {},
        "physical_state_progression": _safe_text(source.get("physical_state_progression", ""), 4000),
        "position_continuity_notes": _safe_text(source.get("position_continuity_notes", ""), 4000),
        "action_intensity_curve": _normalize_intensity(source.get("action_intensity_curve", {})),
        "camera_language": _safe_text(source.get("camera_language", ""), 4000),
        "sound_design_prompt": _safe_text(source.get("sound_design_prompt", ""), 6000),
        "optional_music_bed_path": _safe_text(source.get("optional_music_bed_path", ""), 4096),
        "ducking_level": ducking,
        "transition_ambience_notes": _safe_text(source.get("transition_ambience_notes", ""), 4000),
        "transition_cut_type": _safe_text(source.get("transition_cut_type", "auto"), 80).lower() or "auto",
        "transition_overlap_seconds": max(0.0, min(2.0, _finite_number(source.get("transition_overlap_seconds", 0.25), 0.25))),
        "reference_image_path": _safe_text(source.get("reference_image_path", source.get("character_reference_path", "")), 4096),
        "reference_image_name": _safe_text(source.get("reference_image_name", ""), 512),
        "film_render_mode": render_mode,
        # Phase 3 recipe metadata belongs to the Film scene only. It records
        # an applied local recipe without changing the separate KB schema or
        # silently rewriting the saved Pony/Anima workflow settings.
        "concept_key": _safe_text(source.get("concept_key", source.get("pose_concept", source.get("concept", ""))), 240),
        "concept_recipe_positive_fragment": _safe_text(source.get("concept_recipe_positive_fragment", ""), 16000),
        "concept_recipe_negative_fragment": _safe_text(source.get("concept_recipe_negative_fragment", ""), 12000),
        "concept_recipe_loras": source.get("concept_recipe_loras", []) if isinstance(source.get("concept_recipe_loras", []), list) else [],
        "concept_recipe_settings": source.get("concept_recipe_settings", {}) if isinstance(source.get("concept_recipe_settings", {}), dict) else {},
        "applied_concept_recipe": source.get("applied_concept_recipe", {}) if isinstance(source.get("applied_concept_recipe", {}), dict) else {},
        "rendered_video_path": _safe_text(source.get("rendered_video_path", source.get("video_path", "")), 4096),
        "video_path": _safe_text(source.get("video_path", source.get("rendered_video_path", "")), 4096),
        "actual_duration_seconds": max(0.0, _finite_number(source.get("actual_duration_seconds", 0), 0)),
        "timing_source": _safe_text(source.get("timing_source", "planned"), 80) or "planned",
        **frame_plan,
    }
    # Builder compatibility aliases keep the Film scene record editable by the
    # shared scene tools while the canonical Film names above remain explicit.
    record["t2i_prompt"] = record["keyframe_prompt"]
    record["i2v_prompt"] = record["unified_ltx_prompt"]
    record["dialogue"] = record["spoken_dialogue"]
    record["character_reference_path"] = record["reference_image_path"]
    record["start"] = max(0.0, _finite_number(source.get("start", 0), 0))
    record["end"] = max(record["start"], _finite_number(source.get("end", record["start"] + record["target_duration_seconds"]), record["start"] + record["target_duration_seconds"]))
    return record


def _reflow_scenes(raw_scenes, fps):
    if not isinstance(raw_scenes, list):
        raise ValueError("Script-to-Film scenes must be a list.")
    scenes = []
    seen_scene_ids = set()
    cursor = 0.0
    for index, source in enumerate(raw_scenes):
        scene = _normalize_scene(source, index, fps)
        # An externally authored plan can still reuse a scene_number or ID.
        # Preserve its first ID and make later duplicates deterministic rather
        # than allowing ambiguous Builder-side scene merging.
        base_id = scene["id"] or f"film_scene_{index + 1:04d}"
        scene_id = base_id
        duplicate_number = 2
        while scene_id in seen_scene_ids:
            scene_id = f"{base_id}_{duplicate_number}"
            duplicate_number += 1
        scene["id"] = scene_id
        seen_scene_ids.add(scene_id)
        duration = scene["actual_duration_seconds"] or scene["target_duration_seconds"]
        scene["start"] = cursor
        scene["end"] = cursor + duration
        scene["timeline_duration_seconds"] = duration
        scenes.append(scene)
        cursor = scene["end"]
    return scenes, cursor


def _plan_payload(payload):
    fps = _int_payload(payload, "fps", _DEFAULT_FPS, 1, 120)
    raw_scenes = payload.get("scenes", payload.get("film_scenes", []))
    scenes, duration = _reflow_scenes(raw_scenes, fps)
    selected_loras = _payload_lora_names(payload)
    style_profile = _payload_style_profile(payload)
    film_config = payload.get("script_to_film", {}) if isinstance(payload.get("script_to_film"), dict) else {}
    keyframe_model = _film_keyframe_model(payload.get("keyframe_model", film_config.get("keyframe_model", "pony")))
    for scene in scenes:
        _resolve_scene_lora_knowledge(scene, {
            **(payload if isinstance(payload, dict) else {}),
            "lora_knowledge_loras": selected_loras,
            "style_profile": style_profile,
        })
    return {
        "project_mode": "script_to_film",
        "fps": fps,
        "frame_constraint": "(frames - 1) % 8 == 0",
        "profile": _FILM_PROFILE,
        "profile_label": _FILM_PROFILE_LABEL,
        "keyframe_model": keyframe_model,
        "scenes": scenes,
        "lora_knowledge_loras": selected_loras,
        "style_profile_path": style_profile.get("path", ""),
        "total_duration_seconds": duration,
    }


def _recovered_scene_from_unstructured_output(script, raw_text):
    """Keep Film planning usable when a local model ignores JSON mode.

    This is deliberately a visible, one-scene recovery—not a silent claim that
    the LLM populated every schema field. It gives the owner an editable plan
    built from their script rather than discarding an otherwise usable session.
    """
    source_text = _safe_text(raw_text, 12000)
    script_text = _safe_text(script, 12000)
    prompt_text = source_text if len(source_text) >= 40 else script_text
    return {
        "scene_number": 1,
        "label": "Recovered Film scene",
        "script_beat": script_text,
        "keyframe_prompt": prompt_text,
        "unified_ltx_prompt": prompt_text,
        "spoken_dialogue": "",
        "character_bible": {"summary": script_text},
        "physical_state_progression": "Maintain physical and wardrobe continuity within the shot.",
        "position_continuity_notes": "Establish the opening positions clearly and preserve them through the shot.",
        "action_intensity_curve": {"start": "establish", "middle": "develop", "end": "resolve", "peak_moment": "primary action beat", "summary": "Recovered from the supplied script."},
        "camera_language": "Use a coherent cinematic shot that preserves subject and position continuity.",
        "sound_design_prompt": "Use location-appropriate ambience and synchronized action sound.",
        "optional_music_bed_path": "",
        "ducking_level": 0.25,
        "transition_ambience_notes": "",
        "transition_cut_type": "auto",
        "transition_overlap_seconds": 0.25,
        "target_duration_seconds": _DEFAULT_TARGET_SECONDS,
        "planned_frames": 0,
        "reference_image_path": "",
        "reference_image_name": "",
        "film_render_mode": "i2v_t2av",
        "actual_duration_seconds": 0,
        "timing_source": "planned",
    }


def _validate_film_prompt_creator_capacity(payload):
    """Reject an impossible all-GPU local GGUF load before it starves ComfyUI.

    The Film Planner normally runs beside ComfyUI's image/video process.  A
    model selected in a Wizard field can otherwise begin loading, exhaust the
    shared 16 GiB card, and surface as an opaque browser 502.  This only
    preflights the local builtin runner; remote runners retain their own
    capacity management.
    """
    runner = _safe_text(payload.get("text_gemma_runner", payload.get("text_runner", "builtin")), 80).lower() or "builtin"
    if runner != "builtin":
        return
    selected_model = _safe_text(payload.get("model_file", payload.get("text_gemma_model", "")), 4096)
    if not selected_model:
        return
    settings = payload.get("llm_settings") if isinstance(payload.get("llm_settings"), dict) else {}
    n_ctx = max(512, int(_finite_number(settings.get("n_ctx", 8192), 8192)))
    n_gpu_layers = int(_finite_number(settings.get("n_gpu_layers", 99), 99))
    if n_gpu_layers <= 0:
        return
    try:
        import torch
        from .LLM import VRGDG_SuperGemmaGGUFChat

        if not torch.cuda.is_available():
            return
        resolver = VRGDG_SuperGemmaGGUFChat()
        model_path = resolver._resolve_dropdown_path(selected_model, resolver.MISSING_MODEL_OPTION)
        model_bytes = int(os.path.getsize(model_path))
        total_bytes = int(torch.cuda.get_device_properties(torch.cuda.current_device()).total_memory)
    except Exception:
        # The LLM loader supplies the normal detailed error if model discovery
        # itself fails. Never turn a diagnostic preflight failure into a false
        # model-selection failure.
        return

    mib = 1024 * 1024
    gib = 1024 * mib
    runtime_allowance = max(512 * mib, int(model_bytes * 0.08))
    context_allowance = max(128 * mib, min(2 * gib, int(n_ctx * 96 * 1024)))
    safety_reserve = max(gib, int(total_bytes * 0.10))
    estimated_required = model_bytes + runtime_allowance + context_allowance + safety_reserve
    if estimated_required > total_bytes:
        raise ValueError(
            f"Selected Film Prompt Creator model '{os.path.basename(model_path)}' needs about "
            f"{estimated_required / (1024 ** 3):.1f} GiB with {n_gpu_layers} GPU layers, but this GPU has "
            f"{total_bytes / (1024 ** 3):.1f} GiB. Choose the smaller Qwen model for this machine, or lower "
            "the GPU-layer setting before intentionally running a larger model. The model was not loaded."
        )


def _create_prompt_creator_output(payload):
    script = _safe_text(payload.get("script", payload.get("raw_script", "")), 40000)
    if not script:
        raise ValueError("Paste a script before creating a Script-to-Film plan.")
    system_prompt, system_path = _read_system_prompt()
    runner_payload = dict(payload or {})
    selected_loras = _payload_lora_names(runner_payload)
    style_profile = _payload_style_profile(runner_payload)
    generation_context = prompt_creator_context(selected_loras, style_profile)
    prompt_creator_input = script
    if generation_context["active_loras"] or generation_context["style_profile"].get("prompt_context"):
        # This is project data, not a second instruction block. The sole Film
        # instruction source remains ScriptToFilm_PromptCreator_System.txt.
        prompt_creator_input += "\n\n[GENERATION_METADATA_CONTEXT]\n"
        prompt_creator_input += json.dumps(generation_context, ensure_ascii=False, indent=2)
        prompt_creator_input += "\n[/GENERATION_METADATA_CONTEXT]"
    # The Film contract is a complete JSON object with an array of scene
    # records, not a one-paragraph prompt. This opt-in leaves Music Video's
    # historical output cleanup untouched.
    runner_payload["preserve_structured_output"] = True
    _validate_film_prompt_creator_capacity(runner_payload)
    result = _run_text_gemma_custom(
        runner_payload.get("model_file", runner_payload.get("text_gemma_model", "")),
        system_prompt,
        prompt_creator_input,
        runner_payload.get("llm_settings"),
        runner_payload,
    )
    recovery_message = ""
    try:
        parsed = _extract_json_object(result.get("text", ""))
        source_scenes = parsed.get("scenes", parsed.get("film_scenes", [])) if isinstance(parsed, dict) else []
    except Exception as exc:
        parsed = {}
        source_scenes = []
        recovery_message = f"The selected model did not return a JSON scene plan ({type(exc).__name__}); one editable recovery scene was created from your script."
    if not isinstance(source_scenes, list) or not source_scenes:
        source_scenes = [_recovered_scene_from_unstructured_output(script, result.get("text", ""))]
        if not recovery_message:
            recovery_message = "The selected model returned JSON without a usable scenes array; one editable recovery scene was created from your script."
    plan = _plan_payload({
        "fps": payload.get("fps", _DEFAULT_FPS),
        "scenes": source_scenes,
        "lora_knowledge_loras": selected_loras,
        "style_profile": style_profile,
    })
    plan.update({
        "raw_text": result.get("text", ""),
        "used_model": result.get("used_model", ""),
        "runner": result.get("runner", "builtin"),
        "system_prompt_path": system_path,
        "recovery_message": recovery_message,
    })
    print(
        "[VRGDG Script-to-Film] Prompt Creator completed: "
        f"scenes={len(plan['scenes'])}, recovered={bool(recovery_message)}, "
        f"model={plan['used_model'] or 'unknown'}"
    )
    return plan


def _prune_script_prompt_jobs():
    cutoff = time.time() - _SCRIPT_PROMPT_JOB_TTL_SECONDS
    for job_id, job in list(_SCRIPT_PROMPT_JOBS.items()):
        if float(job.get("created_at", 0)) < cutoff:
            _SCRIPT_PROMPT_JOBS.pop(job_id, None)


async def _run_script_prompt_job(job_id, payload):
    job = _SCRIPT_PROMPT_JOBS.get(job_id)
    if not job:
        return
    job["status"] = "running"
    try:
        result = await asyncio.to_thread(_create_prompt_creator_output, payload)
        job["status"] = "complete"
        job["result"] = result
    except Exception as exc:
        print(f"[VRGDG Script-to-Film] Prompt Creator failed: {type(exc).__name__}: {exc}")
        job["status"] = "error"
        job["error"] = str(exc)


def _save_plan(payload):
    project = _safe_project_folder(payload.get("project_folder", ""))
    plan = _plan_payload(payload)
    film_folder = os.path.join(project, "script_to_film")
    os.makedirs(film_folder, exist_ok=True)
    path = os.path.join(film_folder, "film_scene_plan.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return {"plan_path": path, **plan}


def _probe_duration(video_path):
    path = os.path.abspath(str(video_path or "").strip().strip('"'))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Rendered Film scene video was not found: {path}")
    ffmpeg_path = _find_ffmpeg_path()
    ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe" if os.name == "nt" else "ffprobe")
    if not os.path.isfile(ffprobe_path):
        ffprobe_path = "ffprobe"
    result = subprocess.run(
        [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
    )
    duration = _finite_number(result.stdout.strip(), 0.0)
    if duration <= 0.01:
        raise ValueError(f"Could not measure a usable duration from rendered Film scene: {path}")
    return duration


def _measure_and_reflow(payload):
    fps = _int_payload(payload, "fps", _DEFAULT_FPS, 1, 120)
    scenes = payload.get("scenes", [])
    target_id = _safe_text(payload.get("scene_id", ""), 180)
    target_number = int(_finite_number(payload.get("scene_number", 0), 0))
    duration = _probe_duration(payload.get("video_path", ""))
    matched = False
    for index, source in enumerate(scenes if isinstance(scenes, list) else []):
        source_id = _safe_text(source.get("id", ""), 180) if isinstance(source, dict) else ""
        source_number = int(_finite_number(source.get("scene_number", index + 1), index + 1)) if isinstance(source, dict) else index + 1
        if (target_id and source_id == target_id) or (not target_id and target_number and source_number == target_number):
            source["actual_duration_seconds"] = duration
            source["timing_source"] = "rendered_media"
            source["rendered_video_path"] = os.path.abspath(str(payload.get("video_path", "") or "").strip().strip('"'))
            matched = True
            break
    if not matched:
        raise ValueError("The rendered Film scene was not present in the supplied timeline.")
    reflowed, total = _reflow_scenes(scenes, fps)
    return {"fps": fps, "scenes": reflowed, "total_duration_seconds": total, "measured_duration_seconds": duration}


def _film_prompt_payload(payload):
    raw_scene = payload.get("scene", payload) if isinstance(payload, dict) else {}
    scene_payload = dict(payload or {})
    if isinstance(raw_scene, dict) and raw_scene is not payload:
        scene_payload.update(raw_scene)
    resolved_scene = _resolve_scene_lora_knowledge(scene_payload, payload)
    prompt = _safe_text(resolved_scene.get("unified_ltx_prompt", resolved_scene.get("i2v_prompt", "")), 12000)
    if not prompt:
        raise ValueError("Script-to-Film unified LTX prompt is empty.")
    project = _safe_project_folder(payload.get("project_folder", ""))
    fps = _int_payload(payload, "fps", _DEFAULT_FPS, 1, 120)
    requested_frames = _valid_frames(payload.get("planned_frames"))
    if requested_frames:
        planned_frames = requested_frames
        target_duration = (planned_frames - 1) / fps
    else:
        frame_plan = _frame_plan(payload.get("target_duration_seconds", _DEFAULT_TARGET_SECONDS), fps)
        planned_frames = frame_plan["planned_frames"]
        target_duration = frame_plan["target_duration_seconds"]
    use_reference = str(payload.get("film_render_mode", "i2v_t2av")).strip().lower() != "t2av"
    image_info = {
        "path": payload.get("reference_image_path", payload.get("character_reference_path", "")),
        "data": payload.get("reference_image_data", payload.get("character_reference_data", "")),
        "name": payload.get("reference_image_name", payload.get("character_reference_name", "film_keyframe.png")),
    }
    image_name = _prepare_optional_input_image_name(image_info) if use_reference else _ensure_film_placeholder_load_image()
    if use_reference and image_name == "(none)":
        raise ValueError("Film/T2AV + Character Ref needs a Pony keyframe or a character reference image. Choose pure T2AV for an unconditioned establishing shot.")

    _, template = _load_api_template(_template_path())
    prompt_graph = copy.deepcopy(template)
    # Script-to-Film intentionally has one supported model profile: its backend
    # profile enforces the required DMD/JoyAI LoRAs and exposes the selected LTX
    # audio text encoder. Music-video profiles remain untouched.
    profile = _safe_text(payload.get("i2v_model_profile", _I2V_MODEL_PROFILE_VIOLETS_LTX23_FP8), 100)
    if profile != _I2V_MODEL_PROFILE_VIOLETS_LTX23_FP8:
        raise ValueError("Script-to-Film currently requires the Violets LTX 2.3 FP8 profile so native audio and locked LoRAs remain reproducible.")
    _patch_violets_ltx23_fp8_profile(prompt_graph, payload)

    width = _int_payload(payload, "width", 1280, 64, 4096)
    height = _int_payload(payload, "height", 720, 64, 4096)
    seed = _int_payload(payload, "seed", 1, 0, 0xFFFFFFFFFFFFFFFF)
    scene_number = _int_payload(payload, "scene_number", 1, 1, 999999)
    output_folder = _scene_render_output_folder(project, "script_to_film_clips", {"scene_number": scene_number})
    _set_api_input(prompt_graph, "736:424", "value", fps)
    _set_api_input(prompt_graph, "736:425", "value", width)
    _set_api_input(prompt_graph, "736:426", "value", height)
    _set_api_input(prompt_graph, "736:449", "value", seed)
    _set_api_input(prompt_graph, "film:frames", "value", planned_frames)
    _set_api_input(prompt_graph, "film:character_reference", "image", image_name)
    _set_api_input(prompt_graph, "218:222", "bypass", not use_reference)
    _set_api_input(prompt_graph, "218:222", "strength", _float_payload(payload, "pass1_inplace_strength", 1.0, 0.0, 1.0))
    _set_api_input(prompt_graph, "219:221", "bypass", not use_reference)
    _set_api_input(prompt_graph, "219:221", "strength", _float_payload(payload, "pass2_inplace_strength", 1.0, 0.0, 1.0))
    _set_api_input(prompt_graph, "933", "text", prompt)
    _set_api_input(prompt_graph, "933", "output_mode", "string")
    _set_api_input(prompt_graph, "film:output_prefix", "value", os.path.join(output_folder, "script_to_film"))
    _set_api_input(prompt_graph, "273", "frame_rate", ["736:424", 0])
    _set_api_input(prompt_graph, "273", "crf", _int_payload(payload, "crf", 19, 0, 51))
    _set_api_input(prompt_graph, "937", "use_custom_loras", bool(payload.get("use_custom_loras", False)))
    _set_api_input(prompt_graph, "937", "lora_count", _int_payload(payload, "lora_count", 0, 0, _MAX_LORA_SLOTS))
    for slot in range(1, _MAX_LORA_SLOTS + 1):
        legacy = _float_payload(payload, f"strength_{slot}", 1.0)
        _set_api_input(prompt_graph, "937", f"lora_{slot}", _clean_lora_name(payload.get(f"lora_{slot}", _NONE_LORA)))
        _set_api_input(prompt_graph, "937", f"first_pass_strength_{slot}", _float_payload(payload, f"first_pass_strength_{slot}", legacy))
        _set_api_input(prompt_graph, "937", f"second_pass_strength_{slot}", _float_payload(payload, f"second_pass_strength_{slot}", legacy))
    _patch_i2v_node_overrides(prompt_graph, payload)
    # The generic I2V patch accepts user bypass values. Film establishes its
    # conditioning contract here: pure T2AV cannot accidentally retain image
    # conditioning, while I2V/T2AV always uses the supplied character keyframe.
    _set_api_input(prompt_graph, "218:222", "bypass", not use_reference)
    _set_api_input(prompt_graph, "219:221", "bypass", not use_reference)
    return {
        "workflow_path": _template_path(),
        "output_folder": output_folder,
        "prompt": prompt_graph,
        "profile": _FILM_PROFILE,
        "profile_label": _FILM_PROFILE_LABEL,
        "native_audio": True,
        "reference_conditioning": use_reference,
        "planned_frames": planned_frames,
        "target_duration_seconds": target_duration,
        "fps": fps,
        "resolved_lora_triggers": resolved_scene.get("resolved_lora_triggers", {}),
        "lora_knowledge_refs": resolved_scene.get("resolved_lora_knowledge_refs", []),
        "resolved_unified_ltx_prompt": prompt,
    }


def _film_stitch(payload):
    """Stitch embedded native audio and carry short previous-scene ambience over cuts.

    The underlying video concat remains a hard video edit. When requested, a faded
    tail from the previous scene is mixed at the beginning of the next scene. This
    preserves the generated dialogue's timeline while carrying ambience/action beds
    across a position change. Explicit hard cuts skip the overlap.
    """
    from .VRGDG_WorkflowRunnerNodes import _stitch_scene_videos

    project = _safe_project_folder(payload.get("project_folder", ""))
    scenes = payload.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("No Script-to-Film scenes were supplied for stitching.")
    paths = []
    scene_records = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Film scene {index} is invalid.")
        raw_path = str(scene.get("rendered_video_path", scene.get("video_path", "")) or "").strip().strip('"')
        if not raw_path:
            raise ValueError(f"Film scene {index} is missing its rendered video path.")
        path = os.path.abspath(raw_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Film scene {index} rendered video was not found: {path}")
        paths.append(path)
        scene_records.append(scene)
    result = _stitch_scene_videos({
        "scene_paths": paths,
        "audio_path": "",
        "use_embedded_scene_audio": True,
        "project_folder": project,
        "width": _int_payload(payload, "width", 0, 0, 8192),
        "height": _int_payload(payload, "height", 0, 0, 8192),
        "output_prefix": payload.get("output_prefix", "SCRIPT_TO_FILM"),
    })

    overlap_items = []
    cursor = 0.0
    for index, scene in enumerate(scene_records[:-1]):
        duration = max(0.05, _finite_number(scene.get("actual_duration_seconds") or scene.get("timeline_duration_seconds") or scene.get("target_duration_seconds"), _DEFAULT_TARGET_SECONDS))
        next_scene = scene_records[index + 1]
        cut_type = _safe_text(next_scene.get("transition_cut_type", scene.get("transition_cut_type", "auto")), 80).lower()
        notes = _safe_text(next_scene.get("transition_ambience_notes", scene.get("transition_ambience_notes", "")), 4000)
        overlap = max(0.0, min(2.0, _finite_number(next_scene.get("transition_overlap_seconds", scene.get("transition_overlap_seconds", 0.25)), 0.25)))
        if cut_type == "hard_cut" or not notes or overlap <= 0:
            cursor += duration
            continue
        overlap_items.append({"path": paths[index], "start_at": cursor + duration, "duration": min(overlap, duration)})
        cursor += duration

    music_bed = _safe_text(payload.get("optional_music_bed_path", ""), 4096)
    ducking = max(0.0, min(1.0, _finite_number(payload.get("ducking_level", 0.25), 0.25)))
    if not overlap_items and not music_bed:
        result["ambience_overlaps_applied"] = 0
        return result

    final_path = result["final_video_path"]
    ffmpeg = _find_ffmpeg_path()
    working_dir = os.path.join(project, "rendered_scene_videos", "_script_to_film_audio_mix")
    os.makedirs(working_dir, exist_ok=True)
    temp_output = os.path.join(working_dir, f"film_mix_{int(time.time() * 1000)}.mp4")
    command = [ffmpeg, "-y", "-i", final_path]
    for item in overlap_items:
        command.extend(["-sseof", f"-{item['duration']:.6f}", "-i", item["path"]])
    use_music = bool(music_bed and os.path.isfile(os.path.abspath(music_bed)))
    if use_music:
        command.extend(["-stream_loop", "-1", "-i", os.path.abspath(music_bed)])
    filters = []
    mix_inputs = ["[0:a]"]
    for index, item in enumerate(overlap_items, start=1):
        delay = int(max(0.0, item["start_at"]) * 1000)
        filters.append(f"[{index}:a]afade=t=out:st=0:d={item['duration']:.6f},adelay={delay}|{delay}[tail{index}]")
        mix_inputs.append(f"[tail{index}]")
    if use_music:
        music_index = len(overlap_items) + 1
        filters.append(f"[{music_index}:a]volume={ducking:.4f},atrim=duration=86400[music]")
        mix_inputs.append("[music]")
    filters.append("".join(mix_inputs) + f"amix=inputs={len(mix_inputs)}:duration=first:normalize=0[aout]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", temp_output])
    try:
        subprocess.run(command, capture_output=True, text=True, errors="replace", check=True)
        shutil.move(temp_output, final_path)
    finally:
        try:
            if os.path.isfile(temp_output):
                os.remove(temp_output)
        except OSError:
            pass
    result["ambience_overlaps_applied"] = len(overlap_items)
    result["optional_music_bed_applied"] = use_music
    result["ducking_level"] = ducking if use_music else 0.0
    return result


def _ensure_routes():
    global _SCRIPT_TO_FILM_ROUTES_REGISTERED
    if _SCRIPT_TO_FILM_ROUTES_REGISTERED:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return

    @server.routes.get("/vrgdg/script_to_film/config")
    async def script_to_film_config(_request):
        return web.json_response({
            "ok": True,
            "project_mode": "script_to_film",
            "profile": _FILM_PROFILE,
            "profile_label": _FILM_PROFILE_LABEL,
            "frame_constraint": "(frames - 1) % 8 == 0",
            "default_fps": _DEFAULT_FPS,
            "default_target_seconds": _DEFAULT_TARGET_SECONDS,
            "keyframe_model_choices": ["pony", "anima"],
            "system_prompt_path": _system_prompt_path(),
            "system_prompt_exists": os.path.isfile(_system_prompt_path()),
            "workflow_template_path": _template_path(),
            "workflow_template_exists": os.path.isfile(_template_path()),
            "lora_knowledge_store_path": lora_knowledge_store_path(),
            "reference_conditioning": "Direct LTX I2V keyframe/reference-image conditioning. IP-Adapter and InstantID are not loaded on this ComfyUI install.",
        })

    @server.routes.get("/vrgdg/script_to_film/lora_knowledge")
    async def script_to_film_lora_knowledge(_request):
        try:
            return web.json_response({"ok": True, **await asyncio.to_thread(list_knowledge)})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/lora_knowledge/refresh")
    async def script_to_film_lora_knowledge_refresh(_request):
        try:
            return web.json_response({"ok": True, **await asyncio.to_thread(refresh_knowledge)})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/lora_knowledge/upsert")
    async def script_to_film_lora_knowledge_upsert(request):
        try:
            payload = await request.json()
            return web.json_response({"ok": True, **await asyncio.to_thread(upsert_entry, payload)})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/lora_knowledge/research_civitai")
    async def script_to_film_lora_knowledge_research(request):
        try:
            payload = await request.json()
            return web.json_response({"ok": True, **await asyncio.to_thread(research_civitai, payload.get("lora_name", ""))})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/resolve_lora_prompts")
    async def script_to_film_resolve_lora_prompts(request):
        try:
            payload = await request.json()
            raw_scene = payload.get("scene", payload) if isinstance(payload, dict) else {}
            scene = _normalize_scene(raw_scene, 0, _int_payload(payload, "fps", _DEFAULT_FPS, 1, 120))
            scene = _resolve_scene_lora_knowledge(scene, payload)
            return web.json_response({
                "ok": True,
                "scene": scene,
                "resolved_lora_triggers": scene.get("resolved_lora_triggers", {}),
            })
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/plan")
    async def script_to_film_plan(request):
        try:
            return web.json_response({"ok": True, **_plan_payload(await request.json())})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/concept_intelligence/suggest")
    async def script_to_film_concept_suggest(request):
        """Return compact, quality-ranked Phase 1 recipes for one Film scene."""
        try:
            payload = await request.json()
            scene = payload.get("scene", payload) if isinstance(payload, dict) else {}
            result = await asyncio.to_thread(
                suggest_scene_recipes,
                scene,
                payload.get("base_model", payload.get("keyframe_model", "Pony")),
                _int_payload(payload, "limit", 3, 1, 12),
            )
            return web.json_response({"ok": True, **result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/concept_intelligence/apply")
    async def script_to_film_concept_apply(request):
        """Apply one user-selected local recipe to a Film scene record."""
        try:
            payload = await request.json()
            scene = payload.get("scene", {}) if isinstance(payload, dict) else {}
            result = await asyncio.to_thread(
                apply_recipe_to_scene,
                scene,
                payload.get("concept_key", ""),
                payload.get("recipe_id", ""),
                payload.get("base_model", payload.get("keyframe_model", "Pony")),
            )
            return web.json_response({"ok": True, **result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/concept_intelligence/research")
    async def script_to_film_concept_research(request):
        """Start an explicit review-only Phase 2 search from the Film Planner."""
        try:
            payload = await request.json()
            result = await asyncio.to_thread(
                research_more_for_scene,
                payload.get("concept_query", payload.get("concept_key", "")),
                payload.get("base_model", payload.get("keyframe_model", "Pony")),
                _int_payload(payload, "max_candidates", 8, 1, 20),
                bool(payload.get("safe_only", True)),
            )
            return web.json_response({"ok": True, **result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/concept_intelligence/save_research")
    async def script_to_film_concept_save_research(request):
        """Save only explicitly checked/reviewed Phase 2 candidates, then refresh."""
        try:
            payload = await request.json()
            result = await asyncio.to_thread(
                save_researched_scene_recipes,
                payload.get("candidates_payload", payload.get("candidates_json", {})),
                payload.get("candidate_ids", ""),
                payload.get("concept_key", ""),
                payload.get("base_model", payload.get("keyframe_model", "Pony")),
                _float_payload(payload, "quality_score", 6.0, 0.0, 10.0),
                payload.get("review_notes", ""),
            )
            return web.json_response({"ok": True, **result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/create_prompt_plan")
    async def script_to_film_create_prompt_plan(request):
        try:
            payload = await request.json()
            _prune_script_prompt_jobs()
            job_id = uuid.uuid4().hex
            _SCRIPT_PROMPT_JOBS[job_id] = {
                "created_at": time.time(),
                "status": "queued",
            }
            asyncio.create_task(_run_script_prompt_job(job_id, payload))
            # Do not hold a browser HTTP request open for the several-minute
            # local GGUF generation. The browser polls the short status route.
            return web.json_response({"ok": True, "status": "queued", "job_id": job_id}, status=202)
        except Exception as exc:
            # Browser callers receive this same message, but recording it in
            # Comfy's logs makes future LLM/JSON failures diagnosable after the
            # modal has been closed. Do not log raw scripts or model output.
            print(f"[VRGDG Script-to-Film] Prompt Creator failed: {type(exc).__name__}: {exc}")
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.get("/vrgdg/script_to_film/create_prompt_plan_status")
    async def script_to_film_create_prompt_plan_status(request):
        _prune_script_prompt_jobs()
        job_id = _safe_text(request.query.get("job_id", ""), 80)
        job = _SCRIPT_PROMPT_JOBS.get(job_id)
        if not job:
            return web.json_response({"ok": False, "error": "Film Prompt Creator job was not found."}, status=404)
        status = str(job.get("status", "queued"))
        if status == "error":
            return web.json_response({"ok": False, "status": status, "job_id": job_id, "error": job.get("error", "Film Prompt Creator failed.")}, status=400)
        if status != "complete":
            return web.json_response({"ok": True, "status": status, "job_id": job_id})
        return web.json_response({"ok": True, "status": status, "job_id": job_id, **(job.get("result") or {})})

    @server.routes.post("/vrgdg/script_to_film/client_error")
    async def script_to_film_client_error(request):
        """Record a browser-only Planner failure without exposing project text."""
        try:
            payload = await request.json()
            stage = _safe_text(payload.get("stage", "unknown"), 160)
            message = _safe_text(payload.get("message", "unknown"), 2000)
            print(f"[VRGDG Script-to-Film] Planner client error at {stage}: {message}")
        except Exception as exc:
            print(f"[VRGDG Script-to-Film] Planner client-error report failed: {type(exc).__name__}: {exc}")
        return web.json_response({"ok": True})

    @server.routes.post("/vrgdg/script_to_film/save_plan")
    async def script_to_film_save_plan(request):
        try:
            return web.json_response({"ok": True, **_save_plan(await request.json())})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/measure_and_reflow")
    async def script_to_film_measure_and_reflow(request):
        try:
            payload = await request.json()
            result = await asyncio.to_thread(_measure_and_reflow, payload)
            return web.json_response({"ok": True, **result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/build_t2av_prompt")
    async def script_to_film_build_t2av_prompt(request):
        try:
            return web.json_response({"ok": True, **_film_prompt_payload(await request.json())})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @server.routes.post("/vrgdg/script_to_film/stitch_native_audio")
    async def script_to_film_stitch_native_audio(request):
        try:
            payload = await request.json()
            result = await asyncio.to_thread(_film_stitch, payload)
            return web.json_response({"ok": True, **result})
        except subprocess.CalledProcessError as exc:
            return web.json_response({"ok": False, "error": exc.stderr or exc.stdout or str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    _SCRIPT_TO_FILM_ROUTES_REGISTERED = True


_ensure_routes()

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
