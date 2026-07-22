# Script-to-Film LoRA Knowledge Base

This guide documents the Film-only metadata layer that separates character identity from model-specific LoRA knowledge. It is deliberately outside Music Video mode.

## Ownership boundary

- `character_bible` contains stable identity and visual continuity only: face references, body type, distinguishing features, clothing state, and summary.
- `lora_knowledge_refs` links a Film scene to a metadata record. It never contains trigger strings itself.
- The local Knowledge Base is the only location for trigger maps, Civitai IDs, compatible base models, recommended weights, prompt examples, and LoRA notes.
- `resolved_lora_triggers` is an audit record placed on the generated scene. It records which map keys were selected for Pony and LTX prompts; it is not copied into `character_bible`.

Do not add trigger text to `character_bible`, even if a model has been trained on a character. `_resolve_scene_lora_knowledge` calls `sanitize_character_bible` before the scene crosses the Film API boundary.

## Files

| File | Responsibility |
| --- | --- |
| `VRGDG_LoraKnowledgeBase.py` | JSON storage, safe `.safetensors` header scan, Civitai lookup, target compatibility, trigger selection, Character Bible sanitization, and optional Style Profile loading. |
| `VRGDG_ScriptToFilmNodes.py` | Film-only API routes, Prompt Creator metadata context, per-shot resolution, and LTX prompt injection. |
| `web/VRGDG_ScriptToFilmUI.js` | Shared Builder/Wizard Knowledge Base controls, active project LoRA selection, metadata editor, optional Style Profile path, and per-scene overrides. |
| `web/VRGDG_MusicVideoBuilderUI.js` | Resolves the current Film scene immediately before Pony and again before LTX graph construction. It does not change Music Video rendering. |
| `prompts/ScriptToFilm_PromptCreator_System.txt` | Instructs the Film Prompt Creator to keep LoRA technical details out of Character Bible and optionally choose supplied metadata record names. |
| `docs/USER_GUIDES/SCRIPT_TO_FILM_LORA_KNOWLEDGE.md` | User-facing workflow. |

## Persistent store

The runtime-created JSON store is:

```text
custom_nodes/comfyui-vrgamedevgirl/data/lora_knowledge_base.json
```

It is intentionally local user data, not a source-controlled workflow setting. Writes are atomic (`os.replace`) so a ComfyUI interruption cannot leave a partial JSON file.

Each entry is keyed by the installed LoRA filename and has this minimum contract:

```json
{
  "lora_name": "ExampleCharacterPony.safetensors",
  "civitai_model_id": "",
  "civitai_model_version_id": "",
  "civitai_trigger_words": ["examplecharacter", "red skin", "orange eyes"],
  "base_model_recommendation": "pony",
  "trigger_map": {
    "base": "examplecharacter, red skin, orange eyes",
    "outfit_casual": "example casual jacket",
    "action_kneeling": "example kneeling pose",
    "style_anime": "example anime linework"
  },
  "recommended_weight": 0.8,
  "example_positive_patterns": ["examplecharacter, cinematic close-up"],
  "example_negative_patterns": ["identity drift"],
  "notes": "Confirm trigger map from the creator or Civitai.",
  "last_updated": "2026-07-22T00:00:00Z"
}
```

`Import / Refresh LoRA Metadata` scans the currently visible ComfyUI LoRA list and reads only `.safetensors` headers. It can infer base family and proposes a non-destructive trigger map from embedded training tags when present. It never downloads a model or overwrites an existing non-empty trigger map. If a header already contains a Civitai model ID, it is captured immediately.

Selecting a LoRA automatically attempts to fill its Civitai model ID. The resolver tries embedded metadata first, then Civitai's exact-file-hash endpoint (calculating a local SHA-256 only for the selected file), then a deliberately conservative filename search. A temporary Civitai outage or an ambiguous name leaves the ID blank with a non-error status; it never invents an unverified association. **Auto-detect / Refresh Civitai Metadata** retries this process and enriches the record when a verified ID is found.

On successful research, the selected Civitai **model version** is retained when known; otherwise its base-model family selects the closest version. Its `trainedWords` are flattened into `civitai_trigger_words` and also merged into the always-applied `trigger_map.base` fragment for header-derived records. Therefore every verified Civitai trigger word is visible in the Planner and sent to the relevant shot prompt. Existing action/camera/outfit keys are preserved.

## Resolution contract

1. The project stores its active records in `script_to_film.lora_knowledge_loras`.
2. A scene may narrow that list with `scene.lora_knowledge_refs`. An empty scene list means it inherits the project list.
3. Resolver input is the scene's `physical_state_progression`, `position_continuity_notes`, action curve, camera language, and shot prompts.
4. `base` triggers always apply for a compatible selected record. Other map keys apply only when their descriptive key text matches the current shot (or is explicitly named in `lora_trigger_keys`).
5. Compatibility is model-aware: Pony/SDXL records resolve into the Pony keyframe prompt; LTX records resolve into the LTX native-audio prompt. An incompatible LoRA is skipped rather than writing its trigger into the wrong model family.
6. A project Style Profile may be linked with `script_to_film.style_profile_path`. Its visual prompt fields are added beside the matching LoRA result, while the Character Bible remains unchanged.
7. The resulting fragment is injected only into the active shot. Every render calls the resolver again, so manual edits to physical or positional continuity cannot leave stale triggers in the graph.

`recommended_weight` is intentionally metadata, not an automatic graph mutation. The Film LTX profile continues to own its mandatory DMD/JoyAI adapters. Loading arbitrary user LoRAs into the graph would be a separate, model-compatible workflow feature and must not be inferred from a prompt-metadata selection.

## API routes

| Route | Purpose |
| --- | --- |
| `GET /vrgdg/script_to_film/lora_knowledge` | Read stored metadata and installed-LoRA availability without writing. |
| `POST /vrgdg/script_to_film/lora_knowledge/refresh` | Scan installed LoRA headers and merge basic metadata into the local store. |
| `POST /vrgdg/script_to_film/lora_knowledge/upsert` | Validate and save an edited metadata record. |
| `POST /vrgdg/script_to_film/lora_knowledge/research_civitai` | Auto-detect a Civitai model ID for the selected record, then refresh its public metadata when a verified match is available. |
| `POST /vrgdg/script_to_film/resolve_lora_prompts` | Normalize one Film scene, sanitize its Character Bible, and return target-specific trigger results. |

All routes are registered in `VRGDG_ScriptToFilmNodes.py`; no Music Video API route is changed.

## Reproduction and validation

1. Restart ComfyUI after changing either Python module.
2. Open the shared **Script-to-Film Planner** from Builder and Wizard; both must display the same Knowledge Base card.
3. Select **Import / Refresh LoRA Metadata**. Confirm installed entries appear and any embedded header trigger data is proposed as an object map.
4. Select compatible Pony and/or LTX records for the Film project. Create two scenes with different action/position terms such as `kneeling` and `standing`.
5. Call `POST /vrgdg/script_to_film/resolve_lora_prompts` or build the scenes. Verify their `resolved_lora_triggers` differ by map key and that no trigger appears in `character_bible`.
6. Confirm a Music Video project does not call the Film resolver and that its prompt/UI behavior is unchanged.
7. Run:

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\custom_nodes\comfyui-vrgamedevgirl\tests\test_lora_knowledge_base.py -v
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe -m py_compile .\custom_nodes\comfyui-vrgamedevgirl\VRGDG_LoraKnowledgeBase.py .\custom_nodes\comfyui-vrgamedevgirl\VRGDG_ScriptToFilmNodes.py
node --check .\custom_nodes\comfyui-vrgamedevgirl\web\VRGDG_ScriptToFilmUI.js
node --check .\custom_nodes\comfyui-vrgamedevgirl\web\VRGDG_MusicVideoBuilderUI.js
```

The unit fixture creates a multi-key map and proves that two scenes resolve different triggers while a Character Bible is scrubbed of the trigger token. It uses a temporary JSON store and does not alter the user's real metadata.
