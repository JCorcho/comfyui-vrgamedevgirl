"""Persistent, model-aware LoRA metadata for the isolated Script-to-Film path.

This module deliberately stores *generation* knowledge separately from Film
character bibles.  A character bible describes identity and continuity; this
store owns trigger words, base-model compatibility, recommended weights, and
prompt examples.  It has no Music Video routes or workflow patches.
"""

import copy
import datetime as _datetime
import json
import os
import re
import struct
import tempfile
import urllib.request

import folder_paths


_ROOT = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_ROOT, "data")
_STORE_PATH = os.path.join(_DATA_DIR, "lora_knowledge_base.json")
_MAX_SAFETENSORS_HEADER_BYTES = 16 * 1024 * 1024
_MAX_STYLE_PROFILE_BYTES = 1024 * 1024
_STORE_VERSION = 1
_TRIGGER_GENERIC_WORDS = {
    "1girl", "1boy", "girl", "boy", "woman", "man", "solo", "outdoors",
    "indoors", "portrait", "close-up", "full body", "looking at viewer",
    "from side", "profile", "night", "day", "sky", "background",
}
_ACTION_TAGS = {
    "kneeling": "action_kneeling",
    "sitting": "action_sitting",
    "standing": "action_standing",
    "running": "action_running",
    "lying": "action_lying",
    "bent over": "action_bent_over",
    "spread legs": "action_spread_legs",
    "on back": "action_on_back",
}
_CAMERA_TAGS = {
    "from behind": "camera_from_behind",
    "from side": "camera_from_side",
    "profile": "camera_profile",
    "close-up": "camera_close_up",
    "cowboy shot": "camera_cowboy_shot",
}
_TARGET_SYNONYMS = {
    "pony": {"pony", "ponyxl", "sdxl"},
    "ltx": {"ltx", "ltxv", "ltx2", "ltx2.3", "ltx23"},
}


def _utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value, limit=12000):
    return str(value or "").strip()[:limit]


def normalize_lora_names(value):
    if isinstance(value, str):
        values = re.split(r"[,\n;]", value)
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = []
    result = []
    seen = set()
    for item in values:
        name = _safe_text(item, 1024).replace("\\", "/").lstrip("/")
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            result.append(name)
    return result


def _default_store():
    return {"version": _STORE_VERSION, "last_refreshed": "", "entries": {}}


def store_path():
    return _STORE_PATH


def _normalize_trigger_map(value):
    source = value if isinstance(value, dict) else {}
    result = {}
    for key, trigger in source.items():
        clean_key = re.sub(r"[^a-z0-9_]+", "_", _safe_text(key, 120).lower()).strip("_")
        clean_trigger = _safe_text(trigger, 2000)
        if clean_key and clean_trigger:
            result[clean_key] = clean_trigger
    return result


def _normalize_patterns(value):
    if isinstance(value, str):
        value = [line.strip() for line in value.splitlines() if line.strip()]
    if not isinstance(value, list):
        return []
    return [_safe_text(item, 2000) for item in value if _safe_text(item, 2000)][:80]


def _finite_number(value, default=1.0):
    try:
        number = float(value)
    except Exception:
        return float(default)
    return number if number == number and abs(number) != float("inf") else float(default)


def _normalize_entry(name, value=None):
    source = value if isinstance(value, dict) else {}
    lora_name = _safe_text(source.get("lora_name", name), 1024).replace("\\", "/").lstrip("/")
    if not lora_name:
        raise ValueError("LoRA metadata needs a LoRA filename.")
    return {
        "lora_name": lora_name,
        "civitai_model_id": _safe_text(source.get("civitai_model_id", ""), 120),
        "base_model_recommendation": _safe_text(source.get("base_model_recommendation", "unknown"), 300).lower() or "unknown",
        "trigger_map": _normalize_trigger_map(source.get("trigger_map", {})),
        "recommended_weight": max(-5.0, min(5.0, _finite_number(source.get("recommended_weight", 1.0), 1.0))),
        "example_positive_patterns": _normalize_patterns(source.get("example_positive_patterns", [])),
        "example_negative_patterns": _normalize_patterns(source.get("example_negative_patterns", [])),
        "notes": _safe_text(source.get("notes", ""), 8000),
        "last_updated": _safe_text(source.get("last_updated", ""), 64) or _utc_now(),
        "installed": bool(source.get("installed", False)),
        "source_metadata": source.get("source_metadata") if isinstance(source.get("source_metadata"), dict) else {},
    }


def load_store(path=None):
    selected_path = os.path.abspath(path or _STORE_PATH)
    if not os.path.isfile(selected_path):
        return _default_store()
    try:
        with open(selected_path, "r", encoding="utf-8-sig") as handle:
            source = json.load(handle)
    except Exception:
        return _default_store()
    entries = source.get("entries") if isinstance(source, dict) else {}
    if isinstance(entries, list):
        entries = {str(item.get("lora_name", "")): item for item in entries if isinstance(item, dict) and item.get("lora_name")}
    if not isinstance(entries, dict):
        entries = {}
    normalized = {}
    for name, entry in entries.items():
        try:
            result = _normalize_entry(name, entry)
            normalized[result["lora_name"]] = result
        except Exception:
            continue
    return {
        "version": _STORE_VERSION,
        "last_refreshed": _safe_text(source.get("last_refreshed", ""), 64) if isinstance(source, dict) else "",
        "entries": normalized,
    }


def save_store(store, path=None):
    selected_path = os.path.abspath(path or _STORE_PATH)
    os.makedirs(os.path.dirname(selected_path), exist_ok=True)
    clean = load_store(path=selected_path)
    source_entries = store.get("entries", {}) if isinstance(store, dict) else {}
    if isinstance(source_entries, list):
        source_entries = {str(item.get("lora_name", "")): item for item in source_entries if isinstance(item, dict) and item.get("lora_name")}
    clean["entries"] = {}
    for name, entry in (source_entries.items() if isinstance(source_entries, dict) else []):
        normalized = _normalize_entry(name, entry)
        clean["entries"][normalized["lora_name"]] = normalized
    clean["last_refreshed"] = _safe_text(store.get("last_refreshed", ""), 64) if isinstance(store, dict) else ""
    fd, temporary_path = tempfile.mkstemp(prefix="lora_knowledge_", suffix=".json", dir=os.path.dirname(selected_path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(clean, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, selected_path)
    finally:
        try:
            if os.path.isfile(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass
    return clean


def _read_safetensors_metadata(path):
    if not str(path or "").lower().endswith(".safetensors"):
        return {}
    try:
        with open(path, "rb") as handle:
            header_size = struct.unpack("<Q", handle.read(8))[0]
            if header_size <= 0 or header_size > _MAX_SAFETENSORS_HEADER_BYTES:
                return {}
            header = json.loads(handle.read(header_size).decode("utf-8"))
        metadata = header.get("__metadata__", {}) if isinstance(header, dict) else {}
        return metadata if isinstance(metadata, dict) else {}
    except Exception:
        return {}


def _flatten_tag_frequency(value):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except Exception:
        parsed = {}
    result = {}
    if not isinstance(parsed, dict):
        return result
    for frequencies in parsed.values():
        if not isinstance(frequencies, dict):
            continue
        for tag, count in frequencies.items():
            tag_text = _safe_text(tag, 300).lower()
            try:
                numeric = int(count)
            except Exception:
                numeric = 0
            if tag_text:
                result[tag_text] = max(result.get(tag_text, 0), numeric)
    return result


def _infer_base_model(name, metadata):
    evidence = " ".join([
        _safe_text(metadata.get("ss_base_model_version", ""), 300),
        _safe_text(metadata.get("modelspec.architecture", ""), 300),
        _safe_text(metadata.get("ss_sd_model_name", ""), 300),
        _safe_text(name, 300),
    ]).lower()
    for key, label in (
        ("ltx", "ltx"), ("pony", "pony"), ("anima", "anima"),
        ("flux", "flux"), ("sdxl", "sdxl"), ("illustrious", "illustrious"),
        ("wan", "wan"), ("sd1", "sd1.5"),
    ):
        if key in evidence:
            return label
    return "unknown"


def _auto_trigger_map(metadata):
    frequencies = _flatten_tag_frequency(metadata.get("ss_tag_frequency", ""))
    trained_words = metadata.get("trainedWords", metadata.get("trained_words", []))
    if isinstance(trained_words, str):
        trained_words = [item.strip() for item in trained_words.split(",") if item.strip()]
    result = {}
    for word in trained_words if isinstance(trained_words, list) else []:
        clean = _safe_text(word, 300)
        if clean:
            result["base"] = clean
            break
    if "base" not in result:
        candidates = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
        for tag, _count in candidates:
            if tag not in _TRIGGER_GENERIC_WORDS and len(tag) >= 3:
                result["base"] = tag
                break
    for tag, key in _ACTION_TAGS.items():
        if tag in frequencies:
            result[key] = tag
    for tag, key in _CAMERA_TAGS.items():
        if tag in frequencies:
            result[key] = tag
    if "anime" in frequencies:
        result["style_anime"] = "anime"
    return result


def _metadata_summary(metadata, path):
    return {
        "file_size_bytes": int(os.path.getsize(path)) if path and os.path.isfile(path) else 0,
        "modified_at": int(os.path.getmtime(path)) if path and os.path.isfile(path) else 0,
        "base_model_hint": _safe_text(metadata.get("ss_base_model_version", metadata.get("modelspec.architecture", "")), 300),
        "title": _safe_text(metadata.get("modelspec.title", metadata.get("ss_output_name", "")), 500),
    }


def _installed_lora_paths():
    result = {}
    try:
        names = folder_paths.get_filename_list("loras")
    except Exception:
        names = []
    for raw_name in names if isinstance(names, list) else []:
        name = _safe_text(raw_name, 1024).replace("\\", "/").lstrip("/")
        if not name:
            continue
        try:
            full_path = folder_paths.get_full_path("loras", name)
        except Exception:
            full_path = ""
        result[name] = full_path or ""
    return result


def _entry_list(store):
    entries = []
    for entry in store.get("entries", {}).values():
        clean = copy.deepcopy(entry)
        clean.pop("source_metadata", None)
        entries.append(clean)
    return sorted(entries, key=lambda item: item["lora_name"].lower())


def list_knowledge(path=None):
    store = load_store(path)
    installed = _installed_lora_paths()
    for name, entry in store["entries"].items():
        entry["installed"] = name in installed
    return {
        "store_path": os.path.abspath(path or _STORE_PATH),
        "last_refreshed": store.get("last_refreshed", ""),
        "entries": _entry_list(store),
        "installed_loras": sorted(installed.keys(), key=str.lower),
    }


def refresh_knowledge(path=None):
    store = load_store(path)
    installed = _installed_lora_paths()
    created = 0
    updated = 0
    for name, full_path in installed.items():
        existing = store["entries"].get(name)
        metadata = _read_safetensors_metadata(full_path)
        auto_map = _auto_trigger_map(metadata)
        auto_summary = _metadata_summary(metadata, full_path)
        if existing is None:
            entry = _normalize_entry(name, {
                "lora_name": name,
                "base_model_recommendation": _infer_base_model(name, metadata),
                "trigger_map": auto_map,
                "recommended_weight": 1.0,
                "notes": "Auto-imported from the installed LoRA file. Verify or enrich trigger_map before production use.",
                "installed": True,
                "source_metadata": auto_summary,
            })
            store["entries"][name] = entry
            created += 1
            continue
        changed = False
        existing["installed"] = True
        if not existing.get("base_model_recommendation") or existing.get("base_model_recommendation") == "unknown":
            inferred = _infer_base_model(name, metadata)
            if inferred != "unknown":
                existing["base_model_recommendation"] = inferred
                changed = True
        if not existing.get("trigger_map") and auto_map:
            existing["trigger_map"] = auto_map
            changed = True
        if existing.get("source_metadata") != auto_summary:
            existing["source_metadata"] = auto_summary
            changed = True
        if changed:
            existing["last_updated"] = _utc_now()
            updated += 1
    for name, entry in store["entries"].items():
        entry["installed"] = name in installed
    store["last_refreshed"] = _utc_now()
    saved = save_store(store, path)
    return {**list_knowledge(path), "created_count": created, "updated_count": updated, "entry_count": len(saved["entries"])}


def upsert_entry(payload, path=None):
    source = payload.get("entry", payload) if isinstance(payload, dict) else {}
    lora_name = _safe_text(source.get("lora_name", ""), 1024)
    store = load_store(path)
    existing = store["entries"].get(lora_name, {})
    merged = {**existing, **(source if isinstance(source, dict) else {})}
    entry = _normalize_entry(lora_name, merged)
    entry["last_updated"] = _utc_now()
    entry["installed"] = entry["lora_name"] in _installed_lora_paths()
    store["entries"][entry["lora_name"]] = entry
    save_store(store, path)
    return {"entry": copy.deepcopy(entry), **list_knowledge(path)}


def research_civitai(lora_name, path=None):
    store = load_store(path)
    name = _safe_text(lora_name, 1024)
    entry = store["entries"].get(name)
    if not entry:
        raise ValueError("Import this LoRA into the Knowledge Base before researching it.")
    model_id = _safe_text(entry.get("civitai_model_id", ""), 120)
    if not model_id.isdigit():
        raise ValueError("Enter a numeric Civitai model ID for this LoRA before researching it.")
    request = urllib.request.Request(
        f"https://civitai.com/api/v1/models/{model_id}",
        headers={"User-Agent": "ComfyUI-VRGDG-LoRA-Knowledge/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            remote = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Civitai metadata lookup failed: {type(exc).__name__}: {exc}")
    versions = remote.get("modelVersions", []) if isinstance(remote, dict) else []
    version = versions[0] if isinstance(versions, list) and versions and isinstance(versions[0], dict) else {}
    base_model = _safe_text(version.get("baseModel", remote.get("baseModel", "")), 300).lower()
    if base_model:
        entry["base_model_recommendation"] = base_model
    words = version.get("trainedWords", []) if isinstance(version, dict) else []
    if isinstance(words, str):
        words = [item.strip() for item in words.split(",") if item.strip()]
    if not entry.get("trigger_map") and isinstance(words, list) and words:
        entry["trigger_map"] = {"base": ", ".join(_safe_text(word, 300) for word in words[:8] if _safe_text(word, 300))}
    title = _safe_text(remote.get("name", ""), 500)
    if title and title.lower() not in str(entry.get("notes", "")).lower():
        entry["notes"] = _safe_text(f"{entry.get('notes', '').strip()}\nCivitai research: {title}".strip(), 8000)
    entry["last_updated"] = _utc_now()
    store["entries"][name] = _normalize_entry(name, entry)
    save_store(store, path)
    return {"entry": copy.deepcopy(store["entries"][name]), "civitai_name": title}


def _target_compatible(entry, target):
    requested = _safe_text(target, 80).lower()
    if requested not in _TARGET_SYNONYMS:
        return True
    recommendation = _safe_text(entry.get("base_model_recommendation", "unknown"), 300).lower()
    return any(alias in recommendation for alias in _TARGET_SYNONYMS[requested])


def _scene_text(scene):
    values = [
        scene.get("script_beat", ""), scene.get("physical_state_progression", ""),
        scene.get("position_continuity_notes", ""), scene.get("camera_language", ""),
        scene.get("keyframe_prompt", scene.get("t2i_prompt", "")),
        scene.get("unified_ltx_prompt", scene.get("i2v_prompt", "")),
    ]
    intensity = scene.get("action_intensity_curve", {})
    if isinstance(intensity, dict):
        values.extend(intensity.values())
    return " ".join(_safe_text(value, 12000).lower().replace("_", " ") for value in values)


def _manual_trigger_keys(scene, lora_name):
    raw = scene.get("lora_trigger_keys", {}) if isinstance(scene, dict) else {}
    if isinstance(raw, list):
        return {str(item).strip().lower() for item in raw if str(item).strip()}
    if not isinstance(raw, dict):
        return set()
    value = raw.get(lora_name, raw.get("*", []))
    if isinstance(value, str):
        value = re.split(r"[,\n;]", value)
    return {str(item).strip().lower() for item in value if str(item).strip()} if isinstance(value, list) else set()


def _key_matches_scene(key, scene_text, manual_keys):
    if key == "base" or key in manual_keys:
        return True
    words = [word for word in key.split("_") if word and word not in {"action", "outfit", "style", "camera", "pose", "state", "scene", "environment", "lighting"}]
    if not words:
        return False
    phrase = " ".join(words)
    return phrase in scene_text or all(word in scene_text for word in words)


def _selected_entries(names, path=None):
    store = load_store(path)
    lookup = {name.lower(): entry for name, entry in store["entries"].items()}
    selected = []
    for name in normalize_lora_names(names):
        entry = lookup.get(name.lower())
        if entry:
            selected.append(copy.deepcopy(entry))
    return selected


def resolve_scene_triggers(scene, lora_names, target, path=None):
    source = scene if isinstance(scene, dict) else {}
    scene_text = _scene_text(source)
    result = []
    for entry in _selected_entries(lora_names, path):
        if not _target_compatible(entry, target):
            continue
        manual_keys = _manual_trigger_keys(source, entry["lora_name"])
        selected = []
        for key, trigger in entry.get("trigger_map", {}).items():
            if _key_matches_scene(key, scene_text, manual_keys):
                selected.append((key, trigger))
        if not selected:
            continue
        seen = set()
        triggers = []
        keys = []
        for key, trigger in selected:
            identity = trigger.lower()
            if identity in seen:
                continue
            seen.add(identity)
            keys.append(key)
            triggers.append(trigger)
        result.append({
            "lora_name": entry["lora_name"],
            "base_model_recommendation": entry["base_model_recommendation"],
            "recommended_weight": entry["recommended_weight"],
            "keys": keys,
            "triggers": triggers,
        })
    return result


def resolution_fragment(resolved):
    values = []
    seen = set()
    for item in resolved if isinstance(resolved, list) else []:
        for trigger in item.get("triggers", []) if isinstance(item, dict) else []:
            clean = _safe_text(trigger, 2000)
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                values.append(clean)
    return ", ".join(values)


def all_trigger_terms(entries):
    terms = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        terms.extend(entry.get("trigger_map", {}).values() if isinstance(entry.get("trigger_map"), dict) else [])
        name = _safe_text(entry.get("lora_name", ""), 1024)
        if name:
            terms.extend([name, os.path.splitext(os.path.basename(name))[0]])
    return sorted({_safe_text(term, 2000) for term in terms if _safe_text(term, 2000)}, key=len, reverse=True)


def sanitize_character_bible(value, selected_lora_names, path=None):
    entries = _selected_entries(selected_lora_names, path)
    terms = all_trigger_terms(entries)

    def clean_text(text):
        result = _safe_text(text, 3000)
        for term in terms:
            result = re.sub(re.escape(term), "", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s*,\s*,+", ", ", result).strip(" ,;:-")
        return result

    source = value if isinstance(value, dict) else {"summary": value}
    refs = source.get("face_refs", source.get("face_references", []))
    if isinstance(refs, str):
        refs = [refs]
    if not isinstance(refs, list):
        refs = []
    return {
        "face_refs": [clean_text(item) for item in refs if clean_text(item)],
        "body_type": clean_text(source.get("body_type", "")),
        "distinguishing_features": clean_text(source.get("distinguishing_features", "")),
        "clothing_state": clean_text(source.get("clothing_state", "")),
        "summary": clean_text(source.get("summary", "")),
    }


def load_style_profile(value=None, path_value=""):
    source = value if isinstance(value, dict) else None
    path = _safe_text(path_value, 4096) or (_safe_text(source.get("path", ""), 4096) if isinstance(source, dict) else "")
    if source is None and path:
        candidate = os.path.abspath(path.strip('"'))
        if not os.path.isfile(candidate):
            raise ValueError("Style Profile JSON file was not found.")
        if os.path.getsize(candidate) > _MAX_STYLE_PROFILE_BYTES:
            raise ValueError("Style Profile JSON file is too large.")
        try:
            with open(candidate, "r", encoding="utf-8-sig") as handle:
                source = json.load(handle)
        except Exception as exc:
            raise ValueError(f"Style Profile JSON could not be read: {type(exc).__name__}")
        path = candidate
    if not isinstance(source, dict):
        return {"path": path, "name": "", "prompt_context": "", "keyframe_fragment": "", "ltx_fragment": ""}
    def first_text(*keys):
        for key in keys:
            candidate = _safe_text(source.get(key, ""), 4000)
            if candidate:
                return candidate
        return ""
    return {
        "path": path,
        "name": first_text("name", "title", "profile_name"),
        "prompt_context": first_text("prompt_context", "description", "visual_style", "style_prompt", "positive_prompt", "prompt"),
        "keyframe_fragment": first_text("keyframe_fragment", "keyframe_prompt", "t2i_prompt", "positive_prompt", "style_prompt", "prompt"),
        "ltx_fragment": first_text("ltx_fragment", "ltx_prompt", "i2v_prompt", "video_prompt", "style_prompt", "prompt"),
    }


def prompt_creator_context(lora_names, style_profile=None, path=None):
    entries = _selected_entries(lora_names, path)
    return {
        "active_loras": [{
            "lora_name": entry["lora_name"],
            "base_model_recommendation": entry["base_model_recommendation"],
            "recommended_weight": entry["recommended_weight"],
            "available_trigger_keys": sorted(entry.get("trigger_map", {}).keys()),
            "notes": entry.get("notes", ""),
        } for entry in entries],
        "style_profile": style_profile or {},
    }
