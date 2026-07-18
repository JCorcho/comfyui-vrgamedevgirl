# Wizard and Editor Parity

Treat the normal Builder editor and the Video Wizard as two views of the same project configuration. A feature is incomplete until it is present in both surfaces and both save the same persisted field names.

## Source of truth

- The normal editor owns persisted project/scene settings in `web/VRGDG_MusicVideoBuilderUI.js`.
- `wizardSnapshot()` supplies the Wizard with the current values and available choices.
- `web/VRGDG_MusicVideoWizardUI.js` only renders controls and returns a settings object.
- `applyWizardSettings()` assigns those values to the editor controls, calls `saveI2VVideoSettingsFromPanel()`, and saves the project. It is the single Wizard-to-editor handoff.
- Backend workflow patches in `VRGDG_WorkflowRunnerNodes.py` remain the single renderer. Do not add a Wizard-only workflow runner.

## Required checklist for a new setting

1. Add the setting to its editor default/clone/sync/save/payload lifecycle.
2. Add the current value and valid choices to `wizardSnapshot()`.
3. Render the matching Wizard control in `VRGDG_MusicVideoWizardUI.js`.
4. Return the exact editor field name from **Apply Wizard Settings**.
5. Consume it in `applyWizardSettings()` before `saveI2VVideoSettingsFromPanel()` runs.
6. Preserve per-scene behavior: when the selected scene uses custom video settings, the existing save routine writes to that scene; otherwise it writes to the project settings.
7. Validate both source paths without queuing a render.

## Current parity examples

| Feature | Persisted fields / route |
| --- | --- |
| Pony T2I | `image_model_mode: "pony"`; the Builder's normal image stage calls `VioletsT2I(Pony).json` through `/violets_t2i/build_prompt`. |
| Local text LLM selection | `text_gemma_model`, `vision_gemma_model`, and `mmproj_file`; Editor and Wizard use the shared setters in `VRGDG_MusicVideoBuilderUI.js`, and Prompt Creator persists `text_gemma_model` in its draft. See `PROMPT_CREATOR_LLM_SELECTION.md`. |
| Violets LTX 2.3 FP8 | `i2v_model_profile`, `violets_ltx23_checkpoint_name`, `ltx_audio_text_encoder_name`; backend injects DMD `1.0` and JoyAI `0.5`. |
| Two-pass I2V sampling | `pass1_sampler_name`, `pass1_sigmas`, `pass2_sampler_name`, `pass2_sigmas`. |

Do not represent mandatory model adapters as optional Wizard LoRA controls. Put their enforcement in the backend profile patch and show their locked status in both UI surfaces.
