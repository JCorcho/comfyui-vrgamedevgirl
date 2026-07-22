# Script-to-Film: isolated Pony → LTX native-audio pipeline

This guide is the handoff document for the non-music **Script-to-Film** mode. It was added beside—not inside—the Music Video pipeline. Do not route a Film project through audio upload, Whisper, SRT splitting, lyric timing, source-audio crop, or Music Video mux nodes.

## Contract

- Persisted project switch: `project_mode: "music_video" | "script_to_film"`.
- Persisted Film configuration: `script_to_film`, including `script`, `fps`, and `default_target_duration_seconds`.
- A Film project uses `image_model_mode: "pony"` for its optional keyframes and the backend-enforced `violets_ltx23_fp8` LTX profile for video/audio.
- The Film profile label is **Film/T2AV + Character Ref**. It uses direct LTX I2V reference conditioning because IP-Adapter and InstantID nodes are not installed on this machine. Do not add unavailable node types merely to display a feature label.
- The backend locks `LTX2.3_DMD_reshaped_r256.safetensors` at `1.0` and `JoyAI-Echo-content_r256.safetensors` at `0.5`; these are not optional UI LoRAs.
- `target_duration_seconds` is authoritative before rendering. The planned length is always snapped so `(planned_frames - 1) % 8 == 0`. After rendering, actual media duration replaces the target duration for timeline placement and all following scene start times are reflowed.

## Files and ownership

| File | Role |
| --- | --- |
| `VRGDG_ScriptToFilmNodes.py` | Separate Film-only API routes, scene normalization/reflow, native-audio LTX prompt assembly, and stitching. |
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
start, end, timeline_duration_seconds, timing_source
```

For compatibility with shared Builder scene controls, normalization also retains the aliases `t2i_prompt`, `i2v_prompt`, `dialogue`, `character_reference_path`, and `video_path`. Preserve the aliases when adding new Film UI controls; the canonical Film fields remain the source of truth for external plans.

## Prompt Creator swap point

The route `POST /vrgdg/script_to_film/create_prompt_plan` reads the entire system prompt from exactly:

```text
prompts/ScriptToFilm_PromptCreator_System.txt
```

It must include exactly one `# [GROK_EXPAND_SYSTEM_PROMPT_START]` and one `# [GROK_EXPAND_SYSTEM_PROMPT_END]`. The Python route does not concatenate a second Film instruction block. To change how the selected local/remote LLM writes scene records, edit only this text file, retaining the required JSON schema and a single natural-language `unified_ltx_prompt` rather than tag soup.

### Structured-output safeguard

Script-to-Film calls the shared local LLM runner with `preserve_structured_output: true`. The legacy Music Video path intentionally keeps only the first output paragraph because it normally consumes a single prompt; that cleanup corrupts multi-scene JSON if a model separates scene records with blank lines. The opt-in is inserted only by `_create_prompt_creator_output` and is forwarded by `_run_text_gemma_custom` to `VRGDG_SuperGemmaGGUFChat`. The base LLM runner skips its one-paragraph cleanup only when this explicit flag is present. Do not make this the default: Music Video behavior must remain unchanged.

The Film route also logs the exception class and error message (never the raw script or model completion) as `[VRGDG Script-to-Film] Prompt Creator failed: ...`, so a failed UI request can be diagnosed from ComfyUI logs later.

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
| `POST /vrgdg/script_to_film/create_prompt_plan` | Run selected Prompt Creator model with the dedicated system file. |
| `POST /vrgdg/script_to_film/save_plan` | Persist `script_to_film/film_scene_plan.json` under the project folder. |
| `POST /vrgdg/script_to_film/build_t2av_prompt` | Produce the isolated API graph with Violets LTX loader/LoRA enforcement. |
| `POST /vrgdg/script_to_film/measure_and_reflow` | Probe actual clip duration and return the updated full scene timeline. |
| `POST /vrgdg/script_to_film/stitch_native_audio` | Concatenate embedded native-audio clips, optionally carry a faded previous ambience/action tail over a cut, and optionally mix an external music bed at `ducking_level`. |

Only `transition_cut_type: "hard_cut"` skips the requested ambience overlap. Any other cut type with non-empty `transition_ambience_notes` and a positive `transition_overlap_seconds` carries the previous clip tail across the cut. Generated dialogue remains in the embedded scene audio; no source-song mux is used.

## Builder and Wizard parity

1. Builder: open **Script-to-Film Planner**, or switch project type and open it. The Builder forces Pony for Film keyframes but sends the existing project-level advanced Violets audio-encoder/sampler/sigma settings into the Film backend.
2. Wizard: **Settings → Script-to-Film → Open Film Planner**. The rail presents **Script** and **Film Scenes** in the former Audio/Lyrics locations; both open the same `VRGDG_ScriptToFilmUI.js` modal, not a copied planner.
3. In either surface, create/edit the Film plan, save it, then choose **Build T2I → I2V Film**. Builder queues Pony only for ref-conditioned shots without a supplied keyframe path, queues Film LTX clips, measures each output, persists the reflow, then calls Film stitching.

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
