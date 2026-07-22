# Script-to-Film: isolated Pony → LTX native-audio pipeline

This guide is the handoff document for the non-music **Script-to-Film** mode. It was added beside—not inside—the Music Video pipeline. Do not route a Film project through audio upload, Whisper, SRT splitting, lyric timing, source-audio crop, or Music Video mux nodes.

## Contract

- Persisted project switch: `project_mode: "music_video" | "script_to_film"`.
- Persisted Film configuration: `script_to_film`, including `script`, `fps`, `default_target_duration_seconds`, the authoritative local/remote `prompt_creator_model` selection, active `lora_knowledge_loras`, and an optional `style_profile_path`.
- A Film project uses `image_model_mode: "pony"` for its optional keyframes and the backend-enforced `violets_ltx23_fp8` LTX profile for video/audio.
- The Film profile label is **Film/T2AV + Character Ref**. It uses direct LTX I2V reference conditioning because IP-Adapter and InstantID nodes are not installed on this machine. Do not add unavailable node types merely to display a feature label.
- The backend locks `LTX2.3_DMD_reshaped_r256.safetensors` at `1.0` and `JoyAI-Echo-content_r256.safetensors` at `0.5`; these are not optional UI LoRAs.
- `target_duration_seconds` is authoritative before rendering. The planned length is always snapped so `(planned_frames - 1) % 8 == 0`. After rendering, actual media duration replaces the target duration for timeline placement and all following scene start times are reflowed.

## Files and ownership

| File | Role |
| --- | --- |
| `VRGDG_ScriptToFilmNodes.py` | Separate Film-only API routes, scene normalization/reflow, native-audio LTX prompt assembly, and stitching. |
| `VRGDG_LoraKnowledgeBase.py` | Local JSON metadata store, safe installed-LoRA header importer, model-family compatibility, per-shot trigger resolver, Character Bible sanitization, and optional Style Profile reader. |
| `Workflows/UsedForUIDoNotTouch/ScriptToFilm_T2AV_CharacterRef_API.json` | Dedicated API graph. Generated deterministically from the source I2V graph by the script below; never modify `Singlei2vForUI_API.json` for Film work. |
| `tools/build_script_to_film_template.py` | Rebuilds the Film graph from the maintained I2V source and topology-prunes Music Video-only nodes. |
| `prompts/ScriptToFilm_PromptCreator_System.txt` | The only location for Script-to-Film LLM instructions. It must retain the exact GROK start/end markers. |
| `web/VRGDG_ScriptToFilmUI.js` | Shared duration-first Film Planner used from both Builder and Wizard. |
| `web/VRGDG_MusicVideoBuilderUI.js` | Owns session persistence, dispatches the Film graph, measures/reflows each completed clip, and calls Film stitching. |
| `web/VRGDG_MusicVideoWizardUI.js` | Mirrors the project-type switch. In Film mode its Audio/Lyrics steps become Script/Film Scenes and open the same shared planner. |
| `VRGDG_WorkflowRunnerNodes.py` | Shared collection/fallback only. Its `script_to_film` output finder recognizes regular Film MP4 names. |

`__init__.py` imports `VRGDG_ScriptToFilmNodes`, so restart ComfyUI after changing the backend module.

## Film scene schema

Every scene returned by `/vrgdg/script_to_film/plan` or Prompt Creator has these canonical fields:

```text
id, scene_number, label, script_beat,
keyframe_prompt, unified_ltx_prompt, spoken_dialogue,
target_duration_seconds, planned_frames, actual_duration_seconds,
character_bible { face_refs, body_type, distinguishing_features, clothing_state, summary },
physical_state_progression, position_continuity_notes,
action_intensity_curve { start, middle, end, peak_moment, summary },
camera_language, sound_design_prompt,
optional_music_bed_path, ducking_level,
transition_ambience_notes, transition_cut_type, transition_overlap_seconds,
reference_image_path, film_render_mode, rendered_video_path,
start, end, timeline_duration_seconds, timing_source,
lora_knowledge_refs, resolved_lora_knowledge_refs, resolved_lora_triggers
```

For compatibility with shared Builder scene controls, normalization also retains the aliases `t2i_prompt`, `i2v_prompt`, `dialogue`, `character_reference_path`, and `video_path`. Preserve the aliases when adding new Film UI controls; the canonical Film fields remain the source of truth for external plans.

### LoRA Knowledge and Character Bible boundary

The Film-only Knowledge Base is intentionally not an arbitrary graph-LoRA loader. It stores technical generation metadata for an installed LoRA: model-family recommendation, a structured `trigger_map`, recommended weight, examples, notes, and optional Civitai model/version IDs. Verified Civitai `trainedWords` are stored as `civitai_trigger_words` and merged into the always-applied base prompt fragment while preserving structured action/camera keys. The runtime store is `data/lora_knowledge_base.json`, is atomic-write local user data, and is ignored by Git.

`character_bible` must contain only identity/continuity data. It must never receive a LoRA filename, trigger text, model family, Civitai ID, or recommended weight. The resolver sanitizes it before returning a Film scene. A scene inherits `script_to_film.lora_knowledge_loras` unless it supplies `lora_knowledge_refs`; its prompts receive only compatible, context-matching triggers for that shot. An optional Style Profile JSON may be linked at `style_profile_path` and is resolved alongside metadata without altering the Bible. See [LORA_KNOWLEDGE_BASE.md](LORA_KNOWLEDGE_BASE.md) for the exact contract and [the user guide](../USER_GUIDES/SCRIPT_TO_FILM_LORA_KNOWLEDGE.md) for operation.

## Prompt Creator swap point

The route `POST /vrgdg/script_to_film/create_prompt_plan` reads the entire system prompt from exactly:

```text
prompts/ScriptToFilm_PromptCreator_System.txt
```

It must include exactly one `# [GROK_EXPAND_SYSTEM_PROMPT_START]` and one `# [GROK_EXPAND_SYSTEM_PROMPT_END]`. The Python route does not concatenate a second Film instruction block. To change how the selected local/remote LLM writes scene records, edit only this text file, retaining the required JSON schema and a single natural-language `unified_ltx_prompt` rather than tag soup.

### Structured-output safeguard

Script-to-Film calls the shared local LLM runner with `preserve_structured_output: true`. The legacy Music Video path intentionally keeps only the first output paragraph because it normally consumes a single prompt; that cleanup corrupts multi-scene JSON if a model separates scene records with blank lines. The opt-in is inserted only by `_create_prompt_creator_output` and is forwarded by `_run_text_gemma_custom` to `VRGDG_SuperGemmaGGUFChat`. The base LLM runner skips its one-paragraph cleanup only when this explicit flag is present. For local GGUF models, it also enables llama.cpp's `response_format: {"type": "json_object"}` so the model cannot wrap the requested scene object in conversational prose. Do not make this the default: Music Video behavior must remain unchanged.

The Film route also logs the exception class and error message (never the raw script or model completion) as `[VRGDG Script-to-Film] Prompt Creator failed: ...`, so a failed UI request can be diagnosed from ComfyUI logs later.

If a local model still ignores the JSON contract, the route no longer abandons the plan. It returns one clearly labeled editable recovery scene derived from the supplied script and sets `recovery_message` in the response; the shared Builder/Wizard planner displays that warning. This is a continuity-preserving fallback, not a substitute for a correctly structured LLM plan. Successful and recovered requests are logged with scene count and recovery status only.

### Planner handoff safeguards

The local Prompt Creator contract does **not** require an LLM to fabricate Builder-internal `id` values. `_normalize_scene` therefore assigns a deterministic `film_scene_####` ID before every response leaves the server, and `_reflow_scenes` suffixes any duplicate external IDs. The shared Planner repeats the same lightweight validation before handing a plan to the Builder/Wizard, so an older server response or manually imported plan cannot reintroduce blank/duplicate IDs.

`mergeScriptToFilmTimeline` deliberately ignores blank IDs when building its lookup map and falls back to scene position for those legacy records. Without this, four blank IDs collapse into the last map entry and corrupt the post-LLM handoff even though the selected model completed successfully.

Browser-only failures are posted to `POST /vrgdg/script_to_film/client_error` and logged as `[VRGDG Script-to-Film] Planner client error ...`. The report contains only a short stage and error message—never the script or raw LLM completion. This route is diagnostic only; all Builder and Wizard data continues through the same Planner and `applyPlan` path.

### Prompt Creator model ownership and capacity guard

The shared Film Planner now exposes **Film Prompt Creator model** directly in its source card. Select the exact local GGUF (or retain a configured remote runner) there; it is persisted as `script_to_film.prompt_creator_model`, sent as `model_file`, and mirrored back to the shared Builder text-model setting. This Planner is the same component opened from Builder and Wizard, so the selection cannot depend on whether a Wizard settings form was separately applied.

For local GPU-offloaded GGUFs, the Film backend estimates the model file, runtime, context, and safety reserve before loading. A model whose full GPU-offload requirement exceeds the installed card fails immediately with a clear capacity message; it must never be loaded until ComfyUI becomes memory-starved and returns an opaque 502. A large model can still be used deliberately after lowering GPU layers in the shared LLM settings, while the smaller Qwen profile is the appropriate test choice on this 16 GiB GPU.

Local GGUF generation is queued in the backend rather than held in one browser request. The local 8B Qwen run can take several minutes; the Planner polls `create_prompt_plan_status` and keeps showing progress. This avoids the WebView/HTTP gateway's approximately 120-second request limit even when the server continues the generation successfully.

## Film graph construction

Run this after modifying the maintained source I2V graph or the generator:

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\tools\build_script_to_film_template.py
```

The builder starts from `Singlei2vForUI_API.json`, then makes these structural substitutions:

1. Adds `film:frames`, `film:character_reference`, and `film:output_prefix` inputs.
2. Routes `film:frames` to both the video and `LTXVEmptyLatentAudio` length.
3. Routes the reference/Pony image into both LTX I2V pass-conditioning nodes.
4. Routes `LTXVEmptyLatentAudio` into first-pass AV latent assembly; source audio encoding and its noise-mask path are unreachable.
5. Routes `LTXVAudioVAEDecode` straight to `VHS_VideoCombine` alongside decoded video.
6. Topology-prunes audio load/SRT split/audio crop/image-folder/trim/mux nodes. The generator fails if any banned Music Video node remains reachable.

`film_render_mode: "i2v_t2av"` uses the character/Pony image. `film_render_mode: "t2av"` forcibly bypasses both LTX reference-conditioning nodes after generic sampler overrides run. A Film-specific 64×64 RGB input placeholder is still loaded because ComfyUI executes `LoadImage` even for a bypassed node; do not replace it with the legacy 1×1 placeholder, which current PyAV rejects.

## Render and stitch routes

| Route | Purpose |
| --- | --- |
| `GET /vrgdg/script_to_film/config` | Live contract/template check. |
| `POST /vrgdg/script_to_film/plan` | Normalize fields and duration/frame plan without writing. |
| `POST /vrgdg/script_to_film/create_prompt_plan` | Queue the selected Prompt Creator model and return a short-lived job ID. |
| `GET /vrgdg/script_to_film/create_prompt_plan_status` | Poll a queued Prompt Creator job until its structured Film plan is ready. |
| `POST /vrgdg/script_to_film/client_error` | Record a sanitized browser-only Planner failure in ComfyUI logs. |
| `GET /vrgdg/script_to_film/lora_knowledge` | Read the Film-only local LoRA metadata store and installed-LoRA availability. |
| `POST /vrgdg/script_to_film/lora_knowledge/refresh` | Import/refresh basic metadata from already installed `.safetensors` headers; never downloads a model. |
| `POST /vrgdg/script_to_film/lora_knowledge/upsert` | Validate and persist an edited LoRA metadata record. |
| `POST /vrgdg/script_to_film/lora_knowledge/research_civitai` | Auto-detect the selected record's Civitai model ID from embedded metadata, exact file hash, or a high-confidence name match, then refresh its public metadata. |
| `POST /vrgdg/script_to_film/resolve_lora_prompts` | Resolve per-shot model-compatible trigger fragments and sanitize its Character Bible. |
| `POST /vrgdg/script_to_film/save_plan` | Persist `script_to_film/film_scene_plan.json` under the project folder. |
| `POST /vrgdg/script_to_film/build_t2av_prompt` | Produce the isolated API graph with Violets LTX loader/LoRA enforcement. |
| `POST /vrgdg/script_to_film/measure_and_reflow` | Probe actual clip duration and return the updated full scene timeline. |
| `POST /vrgdg/script_to_film/stitch_native_audio` | Concatenate embedded native-audio clips, optionally carry a faded previous ambience/action tail over a cut, and optionally mix an external music bed at `ducking_level`. |

Only `transition_cut_type: "hard_cut"` skips the requested ambience overlap. Any other cut type with non-empty `transition_ambience_notes` and a positive `transition_overlap_seconds` carries the previous clip tail across the cut. Generated dialogue remains in the embedded scene audio; no source-song mux is used.

## Builder and Wizard parity

1. Builder: open **Script-to-Film Planner**, or switch project type and open it. The Builder forces Pony for Film keyframes but sends the existing project-level advanced Violets audio-encoder/sampler/sigma settings into the Film backend.
2. Wizard: **Settings → Script-to-Film → Open Film Planner**. The rail presents **Script** and **Film Scenes** in the former Audio/Lyrics locations; both open the same `VRGDG_ScriptToFilmUI.js` modal, not a copied planner.
3. In either surface, use the shared **LoRA Knowledge Base** card to import installed metadata, select active compatible records, and optionally link a Style Profile. The same card and persisted `script_to_film` fields are used by both surfaces.
4. In either surface, create/edit the Film plan, save it, then choose **Build T2I → I2V Film**. Builder resolves the scene’s LoRA metadata just before Pony and again before Film LTX assembly, queues Pony only for ref-conditioned shots without a supplied keyframe path, queues Film LTX clips, measures each output, persists the reflow, then calls Film stitching.

If adding a Film field, add it in all four places: backend `_normalize_scene`, planner editing UI, Builder session/history persistence, and Wizard’s shared planner entry point. Update `WIZARD_EDITOR_PARITY.md` in the same commit.

## Validation and smoke test

Run after changes:

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe -m py_compile .\VRGDG_ScriptToFilmNodes.py .\VRGDG_WorkflowRunnerNodes.py
node --check .\web\VRGDG_ScriptToFilmUI.js
node --check .\web\VRGDG_MusicVideoBuilderUI.js
node --check .\web\VRGDG_MusicVideoWizardUI.js
git diff --check
```

Then restart ComfyUI and verify `/vrgdg/script_to_film/config`. The implementation smoke test used a two-scene project under ComfyUI output:

1. Generate a Pony keyframe through `/violets_t2i/build_prompt`.
2. Build/queue a ref-conditioned 9-frame Film clip at 512×512 and confirm the completed MP4 has an H.264 video stream plus AAC audio stream.
3. Build/queue a pure-T2AV 9-frame Film clip and verify both reference bypasses are `true`; confirm its MP4 has both streams.
4. Call `measure_and_reflow` for each output and verify scene 2 starts at scene 1’s measured end time, with both `rendered_video_path` values retained.
5. Call `stitch_native_audio` once with `hard_cut` and once with `transition_ambience_notes`; the latter must report `ambience_overlaps_applied: 1` and retain an AAC track.

Do not commit generated smoke images, clips, or project folders.
