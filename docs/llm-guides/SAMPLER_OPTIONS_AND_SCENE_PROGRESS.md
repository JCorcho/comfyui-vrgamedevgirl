# Sampler Options and Scene Progress

## Purpose

This implementation expands LTX advanced sampling controls to ComfyUI's native sampler vocabulary (including `lcm`) and reports live sampler iteration progress for scene-video renders.

## Files changed

- `web/VRGDG_SamplerOptions.js` — shared fallback list matching the native ComfyUI KSampler/KSamplerSelect sampler names, default name, and list merge helper.
- `web/VRGDG_MusicVideoBuilderUI.js` — consumes the shared list, refreshes it from the backend, and displays an iteration progress bar plus `current/total` and `s/it` during normal and Script-to-Film scene renders.
- `web/VRGDG_MusicVideoWizardUI.js` — uses the same shared sampler list through `wizardSnapshot()` and returns the existing `pass1_sampler_name`, `pass1_sigmas`, `pass2_sampler_name`, and `pass2_sigmas` fields.
- `web/VRGDG_VideoBuilderNodeUI.js` and `web/VRGDG_FaceFixUI.js` — expose the same full fallback list in their advanced sampler controls.
- `VRGDG_WorkflowRunnerNodes.py` — derives the live sampler list from `comfy.samplers.KSampler.SAMPLERS`, serves it in `/vrgdg/workflow_runner/i2v_choices`, and validates/normalizes every sampler override before patching the API graph.
- `VRGDG_FaceFix.py` — uses the same backend sampler normalization for its LTX Face Fix graph.
- `AI_DEVELOPMENT_RULES.md` — persistent rules for parity, sampler updates, progress reporting, commits, and guides.

## Data flow

1. ComfyUI's running backend exposes its core sampler names from `comfy.samplers.KSampler.SAMPLERS` through `/vrgdg/workflow_runner/i2v_choices` as `samplers`.
2. The Builder merges that live list with the shared fallback and current persisted values, then refreshes both pass dropdowns. Its `wizardSnapshot()` exports the same list as `i2vSamplerOptions`.
3. The Wizard builds its controls from that snapshot and returns the exact persisted field names used by the Builder.
4. `VRGDG_WorkflowRunnerNodes.py` receives the selected strings and `_sampler_name()` keeps valid names unchanged (including `lcm`) while replacing stale values with the profile's existing default. The graph still receives the value at the existing `KSamplerSelect` nodes (`218:186` and `219:187` for LTX two-pass workflows).
5. During a queued scene video, `waitForVideos()` subscribes to ComfyUI's `progress` event for the active prompt. The shared progress window shows a second bar and `Sampler iterations: current/total • seconds s/it`; the original scene-level bar and history/fallback polling remain intact.

## Reproduction / verification

1. Restart ComfyUI after changing Python custom-node code. Hard-refresh the ComfyUI browser page after changing frontend modules.
2. Open the Builder's I2V Advanced Sampling controls and confirm `lcm` plus the other native names are present in both pass dropdowns.
3. Open the Wizard's Settings step and confirm the same list appears in both pass dropdowns. Change either pass to `lcm`, apply Wizard Settings, and confirm the Builder retains `pass1_sampler_name`/`pass2_sampler_name`.
4. Query `GET http://127.0.0.1:8188/vrgdg/workflow_runner/i2v_choices` and verify `samplers` contains `lcm`.
5. Exercise the backend without rendering by POSTing a normal I2V build payload with `pass1_sampler_name: "lcm"` and/or `pass2_sampler_name: "lcm"`; inspect the returned API prompt and verify the corresponding `KSamplerSelect.inputs.sampler_name` values are `lcm`.
6. Queue a short, low-resolution scene video. While it samples, the progress window should show `Sampler iterations: .../... • ... s/it`; when the pass resets, the iteration timer resets for the new pass. Completion still uses the existing history output/fallback collection path.

## Compatibility notes

- The list is ComfyUI-native, not LTX-specific. Some samplers may not be quality-tuned for every LTX profile; existing defaults remain unchanged.
- Custom-node sampler extensions may add names to the live ComfyUI node metadata. The core backend list is deliberately used as the safe baseline; a future extension can add its choices to the shared merge without changing persisted fields.
- The progress listener is optional. If an older frontend does not emit `progress`, scene history polling continues and the normal scene progress text remains functional.
