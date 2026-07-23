"""Dependency-free Civitai recipe research helper.

This module is intentionally separate from the ComfyUI node layer.  It queries
the public Civitai image endpoint with ``withMeta=true``, filters the returned
metadata locally, resolves public resource names where available, and returns
candidate recipes as JSON-compatible dictionaries.  It never writes to the
Concept/Pose Knowledge Base: saving remains an explicit human-review action in
the node layer.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_SAFE_API_ROOT = "https://civitai.com/api/v1"
_ADULT_API_ROOT = "https://civitai.red/api/v1"
_SAFE_SITE_ROOT = "https://civitai.com"
_ADULT_SITE_ROOT = "https://civitai.red"
_USER_AGENT = "VRGDG-Concept-Research/1.0 (local ComfyUI recipe researcher)"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_PROMPT_CHARS = 16000
_MAX_NEGATIVE_CHARS = 12000
_MAX_NOTES_CHARS = 12000
_URN_VERSION_PATTERN = re.compile(r"civitai:(?P<model>\d+)@(?P<version>\d+)", re.IGNORECASE)
_LORA_TAG_PATTERN = re.compile(r"<lora:(?P<name>[^:>]+)(?::(?P<weight>-?\d+(?:\.\d+)?))?[^>]*>", re.IGNORECASE)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NOISE_TOKENS = {
    "a", "an", "and", "at", "by", "for", "from", "image", "in", "of", "on",
    "photo", "pose", "recipe", "scene", "style", "the", "to", "with",
}
_QUERY_PHRASE_ALIASES = {
    # Civitai metadata often uses the spaced phrase even when a user searches
    # its common single-token shorthand. Keep this limited and literal: it
    # improves recall without pretending a broad semantic match is exact.
    "doggystyle": ("doggy style", "doggy-style", "from behind", "rear entry"),
    "doggy style": ("doggystyle", "doggy-style", "from behind", "rear entry"),
    "doggy-style": ("doggystyle", "doggy style", "from behind", "rear entry"),
}


class CivitaiAPIError(RuntimeError):
    """A clear, user-safe failure returned by the external Civitai helper."""


def _text(value: Any, limit: int = 12000) -> str:
    return str(value or "").strip()[:limit]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _int_text(value: Any) -> str:
    candidate = _text(value, 80)
    return candidate if candidate.isdigit() else ""


def _normalise_base_model(value: Any) -> str:
    """Normalize only for comparison, while preserving Civitai's display name."""
    compact = re.sub(r"[^a-z0-9]+", "", _text(value, 300).lower())
    aliases = {
        "pony": "pony",
        "ponydiffusion": "pony",
        "ponydiffusionv6": "pony",
        "ponyxl": "pony",
        "anima": "anima",
        "animaxl": "anima",
    }
    return aliases.get(compact, compact)


def _base_models_match(requested: str, actual: str) -> bool:
    wanted = _normalise_base_model(requested)
    found = _normalise_base_model(actual)
    if not wanted or wanted == "any":
        return True
    if not found:
        return False
    return found == wanted or found.startswith(wanted) or wanted.startswith(found)


def _query_tokens(query: str) -> list[str]:
    tokens = []
    seen = set()
    for token in _TOKEN_PATTERN.findall(_text(query, 500).lower()):
        if len(token) < 2 or token in _NOISE_TOKENS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _relevance_score(query: str, prompt: str) -> float:
    """Score explicit prompt evidence without claiming visual understanding."""
    normalized_query = re.sub(r"[_\-]+", " ", _text(query, 500).lower()).strip()
    normalized_prompt = _text(prompt, _MAX_PROMPT_CHARS).lower()
    tokens = _query_tokens(query)
    if not tokens or not normalized_prompt:
        return 0.0
    phrase_variants = (normalized_query,) + _QUERY_PHRASE_ALIASES.get(normalized_query, ())
    phrase_hit = any(variant and variant in normalized_prompt for variant in phrase_variants)
    hits = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", normalized_prompt))
    token_ratio = hits / len(tokens)
    # A direct phrase is strong evidence.  Otherwise retain partial semantic
    # matches for human review but rank them below direct prompt matches.
    return min(1.0, (0.65 if phrase_hit else 0.0) + token_ratio * 0.35)


def _meta_value(meta: dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): value for key, value in meta.items()}
    for key in keys:
        if key in meta:
            return meta[key]
        candidate = lowered.get(key.lower())
        if candidate not in (None, ""):
            return candidate
    return ""


def _metadata_completeness(meta: dict[str, Any], has_loras: bool) -> dict[str, Any]:
    fields = {
        "positive_prompt": _text(_meta_value(meta, "prompt"), _MAX_PROMPT_CHARS),
        "negative_prompt": _text(_meta_value(meta, "negativePrompt", "negative_prompt"), _MAX_NEGATIVE_CHARS),
        "seed": _text(_meta_value(meta, "seed"), 120),
        "cfg": _text(_meta_value(meta, "cfgScale", "cfg", "guidance"), 120),
        "steps": _text(_meta_value(meta, "steps"), 120),
        "sampler": _text(_meta_value(meta, "sampler"), 300),
        "model": _text(_meta_value(meta, "Model", "model"), 1024),
        "loras": "present" if has_loras else "",
    }
    present = [name for name, value in fields.items() if value]
    # LoRAs are useful but optional, so the core score has seven fields.
    core = [name for name in fields if name != "loras"]
    return {
        "present_fields": present,
        "core_fields_present": sum(1 for name in core if fields[name]),
        "core_fields_total": len(core),
        "has_lora_metadata": bool(has_loras),
    }


def _as_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _version_id_from_value(value: Any) -> str:
    direct = _int_text(value)
    if direct:
        return direct
    match = _URN_VERSION_PATTERN.search(_text(value, 1000))
    return match.group("version") if match else ""


def _model_id_from_value(value: Any) -> str:
    match = _URN_VERSION_PATTERN.search(_text(value, 1000))
    return match.group("model") if match else ""


def _resource_references(meta: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return LoRA refs and checkpoint version IDs from mixed Civitai metadata."""
    loras: list[dict[str, Any]] = []
    seen_loras: dict[str, int] = {}
    checkpoints: list[str] = []

    def add_lora(version_id: str, name: str, weight: Any) -> None:
        clean_name = _text(name, 1024)
        clean_version = _int_text(version_id) or _version_id_from_value(clean_name)
        key = clean_version or clean_name.lower()
        if not key:
            return
        record = {
            "model_version_id": clean_version,
            "model_id": _model_id_from_value(clean_name),
            "name_hint": clean_name,
            "weight": max(-5.0, min(5.0, _number(weight, 1.0))),
        }
        if key in seen_loras:
            # The more descriptive resource shape commonly carries strength.
            loras[seen_loras[key]].update({k: v for k, v in record.items() if v not in ("", None)})
        else:
            seen_loras[key] = len(loras)
            loras.append(record)

    for resource in _as_list(meta.get("additionalResources")):
        resource_type = _text(resource.get("type", "")).lower()
        raw_name = _text(resource.get("name", resource.get("modelName", "")), 1024)
        version_id = _version_id_from_value(resource.get("modelVersionId", raw_name))
        if resource_type == "lora":
            add_lora(version_id, raw_name, resource.get("strength", resource.get("weight", 1.0)))
        elif resource_type in {"checkpoint", "model"} and version_id:
            checkpoints.append(version_id)

    for resource in _as_list(meta.get("civitaiResources")) + _as_list(meta.get("resources")):
        resource_type = _text(resource.get("type", "")).lower()
        version_id = _version_id_from_value(resource.get("modelVersionId", resource.get("versionId", "")))
        raw_name = _text(resource.get("name", resource.get("modelName", "")), 1024)
        if resource_type == "lora":
            add_lora(version_id, raw_name, resource.get("weight", resource.get("strength", 1.0)))
        elif resource_type in {"checkpoint", "model"} and version_id:
            checkpoints.append(version_id)

    # Civitai.red image metadata commonly represents the checkpoint only as a
    # Model URN. Treat that as a checkpoint resource so the later short-list
    # resolution can validate its base model without scraping pages.
    model_version_id = _version_id_from_value(_meta_value(meta, "Model", "model"))
    if model_version_id:
        checkpoints.append(model_version_id)

    prompt = _text(_meta_value(meta, "prompt"), _MAX_PROMPT_CHARS)
    for match in _LORA_TAG_PATTERN.finditer(prompt):
        add_lora("", match.group("name"), match.group("weight") or 1.0)

    deduplicated_checkpoints = []
    for version_id in checkpoints:
        if version_id and version_id not in deduplicated_checkpoints:
            deduplicated_checkpoints.append(version_id)
    return loras[:48], deduplicated_checkpoints[:8]


def _version_label(payload: dict[str, Any]) -> str:
    model = payload.get("model", {}) if isinstance(payload.get("model"), dict) else {}
    model_name = _text(model.get("name", payload.get("modelName", "")), 1000)
    version_name = _text(payload.get("name", payload.get("versionName", "")), 1000)
    if model_name and version_name and version_name.lower() not in model_name.lower():
        return f"{model_name} — {version_name}"
    return model_name or version_name


def _recipe_score(relevance: float, completeness: dict[str, Any], stats: dict[str, Any]) -> float:
    core_score = _number(completeness.get("core_fields_present"), 0.0) / max(1.0, _number(completeness.get("core_fields_total"), 7.0))
    reactions = _number(stats.get("likeCount"), 0.0) + _number(stats.get("heartCount"), 0.0) * 1.5
    # This is a review priority, not a claim that the output is objectively
    # good.  The KB's quality_score stays zero until the human selects it.
    return round(min(100.0, relevance * 50.0 + core_score * 35.0 + min(15.0, math.log10(reactions + 1.0) * 3.5)), 2)


def _source_urls(image_id: str, post_id: str, site_root: str = _SAFE_SITE_ROOT) -> tuple[str, str]:
    root = _text(site_root, 500).rstrip("/") or _SAFE_SITE_ROOT
    image_url = f"{root}/images/{image_id}" if image_id else ""
    post_url = f"{root}/posts/{post_id}" if post_id else ""
    return image_url, post_url


def _image_preview_url(item: dict[str, Any]) -> str:
    """Keep Civitai's public CDN image URL when the API supplies one.

    This is presentation-only provenance. The Civitai image page remains the
    durable review link because CDN URLs may be resized or expire over time.
    """
    value = _text(item.get("url", item.get("imageUrl", item.get("image_url", ""))), 4000)
    return value if value.startswith(("https://", "http://")) else ""


@dataclass
class CivitaiClient:
    """Polite JSON client for the public Civitai API.

    ``token`` is optional.  Public recipe research does not require it, but an
    owner can set ``CIVITAI_API_TOKEN`` when their Civitai account/API policy
    needs authenticated access.  No browser cookies or login profile are read.
    """

    token: str = ""
    api_root: str = _SAFE_API_ROOT
    site_root: str = _SAFE_SITE_ROOT
    timeout_seconds: float = 20.0
    min_request_interval: float = 0.35
    max_retries: int = 3
    _sleep: Callable[[float], None] = time.sleep
    _monotonic: Callable[[], float] = time.monotonic
    _last_request_at: float = field(default=-1000000.0, init=False)
    version_cache: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.token = _text(self.token or os.environ.get("CIVITAI_API_TOKEN", ""), 4000)
        self.api_root = _text(self.api_root, 500).rstrip("/")
        self.site_root = _text(self.site_root, 500).rstrip("/")
        allowed_pairs = {
            (_SAFE_API_ROOT, _SAFE_SITE_ROOT),
            (_ADULT_API_ROOT, _ADULT_SITE_ROOT),
        }
        if (self.api_root, self.site_root) not in allowed_pairs:
            raise CivitaiAPIError("Civitai client was configured with an unsupported API endpoint.")
        self.timeout_seconds = max(1.0, float(self.timeout_seconds))
        self.min_request_interval = max(0.0, float(self.min_request_interval))
        self.max_retries = max(0, min(8, int(self.max_retries)))

    def _url(self, path_or_url: str, params: dict[str, Any] | None = None) -> str:
        url = path_or_url if str(path_or_url).startswith(("https://", "http://")) else f"{self.api_root}/{str(path_or_url).lstrip('/')}"
        if not params:
            return url
        encoded = urlencode([(key, value) for key, value in params.items() if value not in (None, "")], doseq=True)
        if not encoded:
            return url
        return url + ("&" if "?" in url else "?") + encoded

    def _pause_before_request(self) -> None:
        remaining = self.min_request_interval - (self._monotonic() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    def get_json(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._url(path_or_url, params)
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(self.max_retries + 1):
            self._pause_before_request()
            try:
                request = Request(url, headers=headers)
                self._last_request_at = self._monotonic()
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise CivitaiAPIError("Civitai returned a non-object JSON response.")
                return payload
            except HTTPError as exc:
                retry_after = _number(exc.headers.get("Retry-After", 0) if exc.headers else 0, 0.0)
                retryable = exc.code in _RETRYABLE_STATUS_CODES
                failure = f"Civitai HTTP {exc.code}"
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                retry_after = 0.0
                retryable = True
                failure = f"Civitai request failed: {type(exc).__name__}"
            except CivitaiAPIError:
                raise
            if not retryable or attempt >= self.max_retries:
                raise CivitaiAPIError(f"{failure}. Try again later or check CIVITAI_API_TOKEN if your account requires it.")
            backoff = retry_after if retry_after > 0 else min(12.0, 0.75 * (2 ** attempt))
            self._sleep(backoff)
        raise CivitaiAPIError("Civitai request retry loop ended unexpectedly.")

    def model_version(self, version_id: str) -> dict[str, Any]:
        identifier = _int_text(version_id)
        if not identifier:
            return {}
        if identifier not in self.version_cache:
            try:
                self.version_cache[identifier] = self.get_json(f"/model-versions/{identifier}")
            except CivitaiAPIError:
                self.version_cache[identifier] = {}
        return self.version_cache[identifier]


def _image_pages(client: CivitaiClient, query: str, base_model: str, safe_only: bool, max_pages: int) -> tuple[list[dict[str, Any]], list[str]]:
    params: dict[str, Any] = {
        "limit": 100,
        "withMeta": "true",
        "sort": "Most Reactions",
        "period": "AllTime",
        "query": query,
    }
    # Explicitly send both values. Omitting ``nsfw`` does *not* mean
    # adult-allowed on Civitai's image API; it can silently return the default
    # safe-only result set. The user-selected content mode must be preserved.
    params["nsfw"] = "false" if safe_only else "true"
    if base_model and _normalise_base_model(base_model) != "any":
        # Civitai accepts a base-model filter but its current search behaviour
        # can be broad; research_concept repeats the check against metadata.
        params["baseModels"] = base_model
    images: list[dict[str, Any]] = []
    warnings: list[str] = []
    path_or_url = "/images"
    for page_index in range(max(1, min(3, int(max_pages)))):
        payload = client.get_json(path_or_url, params if page_index == 0 else None)
        page_items = _as_list(payload.get("items"))
        images.extend(page_items)
        metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
        next_page = _text(metadata.get("nextPage", metadata.get("nextCursor", "")), 4000)
        if not next_page:
            break
        # An opaque cursor needs the original path plus the cursor query.  A
        # full nextPage URL can be passed straight through the client.
        if next_page.startswith(("http://", "https://")):
            path_or_url = next_page
        else:
            warnings.append("Civitai returned an opaque pagination cursor; the helper used the first result page only.")
            break
    return images, warnings


def _candidate_shell(
    item: dict[str, Any],
    query: str,
    requested_base: str,
    safe_only: bool,
    site_root: str = _SAFE_SITE_ROOT,
) -> dict[str, Any] | None:
    meta = item.get("meta", {}) if isinstance(item.get("meta"), dict) else {}
    prompt = _text(_meta_value(meta, "prompt"), _MAX_PROMPT_CHARS)
    if not prompt:
        return None
    nsfw_level = _text(item.get("nsfwLevel", meta.get("nsfwLevel", "")), 80).lower()
    if safe_only and (bool(item.get("nsfw", False)) or nsfw_level in {"mature", "x", "xxx"}):
        return None
    actual_base = _text(_meta_value(meta, "baseModel", "base_model") or item.get("baseModel", ""), 300)
    # The server has already been asked for the requested base model. Some
    # adult Civitai metadata omits meta.baseModel, so defer that validation to
    # the checkpoint version resolver when the field is absent. Explicitly
    # present mismatches remain rejected here.
    if requested_base and actual_base and not _base_models_match(requested_base, actual_base):
        return None
    lora_refs, checkpoint_ids = _resource_references(meta)
    completeness = _metadata_completeness(meta, bool(lora_refs))
    # At least prompt plus four core settings makes an entry useful as a recipe;
    # the human still decides whether it deserves a KB quality score.
    if completeness["core_fields_present"] < 5:
        return None
    relevance = _relevance_score(query, prompt)
    if relevance <= 0.0:
        return None
    image_id = _int_text(item.get("id", ""))
    if not image_id:
        return None
    post_id = _int_text(item.get("postId", ""))
    source_url, post_url = _source_urls(image_id, post_id, site_root)
    return {
        "candidate_id": f"civitai_image_{image_id}",
        "civitai_image_id": image_id,
        "civitai_post_id": post_id,
        "source_url": source_url,
        "post_url": post_url,
        "image_preview_url": _image_preview_url(item),
        "creator": _text(item.get("username", ""), 300),
        "base_model": actual_base,
        "base_model_verification": "metadata" if actual_base else "server_filter_only",
        "positive_prompt": prompt,
        "negative_prompt": _text(_meta_value(meta, "negativePrompt", "negative_prompt"), _MAX_NEGATIVE_CHARS),
        "seed": _text(_meta_value(meta, "seed"), 120),
        "cfg": _number(_meta_value(meta, "cfgScale", "cfg", "guidance"), 0.0),
        "steps": max(0, int(_number(_meta_value(meta, "steps"), 0))),
        "sampler": _text(_meta_value(meta, "sampler"), 300),
        "model_name": _text(_meta_value(meta, "Model", "model"), 1024),
        "loras": lora_refs,
        "_checkpoint_ids": checkpoint_ids,
        "metadata_completeness": completeness,
        "relevance_score": round(relevance, 3),
        "reactions": item.get("stats", {}) if isinstance(item.get("stats"), dict) else {},
    }


def _resolve_candidate_resources(candidate: dict[str, Any], client: CivitaiClient) -> dict[str, Any]:
    resolved_loras = []
    lora_notes = []
    for item in candidate.get("loras", []):
        version_id = _int_text(item.get("model_version_id", ""))
        version = client.model_version(version_id) if version_id else {}
        resolved_name = _version_label(version) or _text(item.get("name_hint", ""), 1024)
        if not resolved_name:
            resolved_name = f"Civitai LoRA version {version_id}" if version_id else "Unnamed Civitai LoRA"
        resolved_loras.append({"name": resolved_name, "weight": max(-5.0, min(5.0, _number(item.get("weight"), 1.0)))})
        if version_id:
            model_id = _int_text(version.get("modelId", "")) or _text(item.get("model_id", ""), 80)
            lora_notes.append(f"{resolved_name} (Civitai model {model_id or '?'} version {version_id}) @ {resolved_loras[-1]['weight']:g}")
    candidate["loras"] = resolved_loras

    model_name = candidate.get("model_name", "")
    for version_id in candidate.get("_checkpoint_ids", []):
        version = client.model_version(version_id)
        label = _version_label(version)
        if label:
            model_name = label
        if not candidate.get("base_model"):
            candidate["base_model"] = _text(version.get("baseModel", ""), 300)
        if model_name:
            break
    candidate["model_name"] = _text(model_name, 1024)
    candidate["resource_notes"] = lora_notes
    candidate.pop("_checkpoint_ids", None)
    candidate["candidate_score"] = _recipe_score(
        _number(candidate.get("relevance_score"), 0.0),
        candidate.get("metadata_completeness", {}),
        candidate.get("reactions", {}),
    )
    candidate["quality_score"] = 0.0
    candidate["notes"] = _text(
        f"Imported for human review from Civitai image {candidate['civitai_image_id']}"
        + (f" (post {candidate['civitai_post_id']})" if candidate.get("civitai_post_id") else "")
        + ". Set a local quality score only after testing this recipe."
        + ("\nLoRA provenance: " + "; ".join(lora_notes) if lora_notes else ""),
        _MAX_NOTES_CHARS,
    )
    candidate["tags"] = ["civitai", "research-candidate"]
    return candidate


def research_concept(
    concept_query: str,
    base_model: str = "Pony",
    max_candidates: int = 8,
    safe_only: bool = True,
    max_pages: int = 1,
    client: CivitaiClient | None = None,
) -> dict[str, Any]:
    """Research public Civitai metadata and return human-review candidates.

    The function has no knowledge-base side effects.  It performs one image
    search (up to three pages if requested) and resolves resources only for the
    small pre-ranked candidate pool, which keeps Civitai traffic polite.
    """
    query = _text(concept_query, 500)
    if not query:
        raise ValueError("Concept query is required.")
    requested_base = _text(base_model, 300)
    limit = max(1, min(20, int(max_candidates)))
    content_mode = "safe_only" if safe_only else "adult_allowed"
    api = client
    warnings: list[str] = []
    if api is None:
        primary_api_root, primary_site_root = (
            (_SAFE_API_ROOT, _SAFE_SITE_ROOT) if safe_only else (_ADULT_API_ROOT, _ADULT_SITE_ROOT)
        )
        api = CivitaiClient(api_root=primary_api_root, site_root=primary_site_root)
        try:
            images, warnings = _image_pages(api, query, requested_base, bool(safe_only), max_pages)
        except CivitaiAPIError as primary_error:
            if safe_only:
                raise
            # Civitai.red is the intentional primary adult endpoint. Its API
            # can be transiently unavailable, so retain adult-allowed search
            # through the public API rather than silently falling back to SFW.
            api = CivitaiClient(api_root=_SAFE_API_ROOT, site_root=_SAFE_SITE_ROOT)
            images, warnings = _image_pages(api, query, requested_base, False, max_pages)
            warnings.insert(
                0,
                "Civitai.red was temporarily unavailable; the search used Civitai.com with its explicit adult-content API filter instead. "
                f"Original endpoint error: {primary_error}",
            )
    else:
        images, warnings = _image_pages(api, query, requested_base, bool(safe_only), max_pages)

    site_root = _text(getattr(api, "site_root", ""), 500) or (_SAFE_SITE_ROOT if safe_only else _ADULT_SITE_ROOT)
    shells = [
        shell
        for shell in (
            _candidate_shell(item, query, requested_base, bool(safe_only), site_root)
            for item in images
        )
        if shell
    ]
    shells.sort(
        key=lambda item: (
            -_recipe_score(item["relevance_score"], item["metadata_completeness"], item["reactions"]),
            -_number(item["reactions"].get("likeCount"), 0.0),
            item["candidate_id"],
        )
    )
    # Resolve only the shortlisted records.  This avoids dozens of model
    # requests when Civitai sends a broad semantic-search result page.
    shortlisted = shells[: max(limit * 2, limit)]
    candidates = [_resolve_candidate_resources(candidate, api) for candidate in shortlisted]
    validated_candidates = []
    for candidate in candidates:
        resolved_base = _text(candidate.get("base_model", ""), 300)
        if requested_base and resolved_base and not _base_models_match(requested_base, resolved_base):
            continue
        if requested_base and not resolved_base:
            # The request itself was filtered server-side, but the returned
            # metadata gave us no version/base-model field to independently
            # inspect. Keep it available for human review and mark that fact.
            candidate["base_model"] = requested_base
            candidate["base_model_verification"] = "server_filter_only"
        elif resolved_base:
            candidate["base_model_verification"] = "metadata"
        validated_candidates.append(candidate)
    candidates = validated_candidates
    candidates.sort(key=lambda item: (-_number(item.get("candidate_score"), 0.0), item["candidate_id"]))
    candidates = candidates[:limit]
    if not candidates:
        warnings.append(
            f"No {'safe' if safe_only else 'adult-allowed'} public images matched both the requested base model and enough visible generation metadata. "
            "Try a broader concept phrase, another base model, or retry later."
        )
    for candidate in candidates:
        candidate.pop("reactions", None)
    return {
        "schema_version": 1,
        "provider": "civitai_public_api",
        "access_mode": "public_api_with_metadata",
        "content_mode": content_mode,
        "api_endpoint": _text(getattr(api, "api_root", ""), 500) or "injected_test_client",
        "query": query,
        "base_model_filter": requested_base or "Any",
        "safe_only": bool(safe_only),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "warnings": warnings,
        "review_required": True,
    }


def render_review_text(research_result: dict[str, Any]) -> str:
    """Human-friendly text that stays JSON-compatible with ComfyUI strings."""
    return json.dumps(research_result, ensure_ascii=False, indent=2, sort_keys=True)
