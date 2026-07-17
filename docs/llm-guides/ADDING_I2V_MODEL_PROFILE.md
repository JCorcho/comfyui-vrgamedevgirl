# Adding an I2V Model Profile

This guide describes the `Violets LTX 2.3 FP8` profile added to the Builder. Use it as the pattern for a new I2V loader/model variant. Do not copy a user's standalone workflow into the Builder: preserve the repository's API template and alter only the loader seam needed by the profile.

## User-facing result

In **Video → Image to Video → Models**, select **Violets LTX 2.3 FP8 (.safetensors)**.

The profile is stored in the existing `i2v_video_settings` object, so the Builder's existing **custom scene video settings** toggle makes the profile, its checkpoint choices, and the shared sampler/sigma settings project-scoped by default and scene-scoped when enabled.

The profile uses these defaults from `VioletsI2V.json`:

- Full LTX checkpoint: `10Eros_v1.4_fp8mixed_learned.safetensors`
- Text encoder: `gemma-3-12b-it-ablit-norms-biproj-fp8mixed.safetensors`
- LTXV Audio Text Encoder checkpoint: `10Eros_v1.4_fp8mixed_learned.safetensors`
- Required DMD LoRA: `LTX2.3_DMD_reshaped_r256.safetensors` at `1.0`
- Required JoyAI LoRA: `JoyAI-Echo-content_r256.safetensors` at `0.5`

The Audio Text Encoder control selects the checkpoint passed to both `LTXAVTextEncoderLoader` and `LTXVAudioVAELoader`, matching the source workflow's loader arrangement. `Text encoder / Clip model 1` is the `text_encoder` input of `LTXAVTextEncoderLoader`.

The **Video Wizard → Settings** page exposes the same profile, full checkpoint, LTXV Audio Text Encoder checkpoint, locked-LoRA status, and two-pass sampler/sigma fields. Its **Apply Wizard Settings** action sends the normal persisted setting names back through the Builder's existing `saveI2VVideoSettingsFromPanel()` lifecycle; it does not have its own render implementation.

## Files and responsibilities

### `web/VRGDG_MusicVideoBuilderUI.js`

This file owns persisted Builder settings and UI controls.

1. Define a stable profile identifier and source-workflow defaults near the other I2V constants.
2. Add the profile selector and any profile-only pickers in the Video Models UI.
3. Add the values to all I2V settings paths:
   - `defaultI2VVideoSettings()`
   - `cloneI2VVideoSettings()`
   - `syncI2VVideoSettingsPanel()`
   - `saveI2VVideoSettingsFromPanel()`
   - `i2vVideoSettingsPayload()`
4. Add the model choices to `refreshModelChoices()`.
5. In `syncI2VVideoModelPickerVisibility()`, hide controls that do not apply to the profile rather than leaving editable values that the backend will ignore.
6. Keep the existing `pass1_sampler_name`, `pass1_sigmas`, `pass2_sampler_name`, and `pass2_sigmas` fields. The Builder already exposes them under **Video Settings → Advanced Settings**, with repository defaults and project/scene scoping.
7. Add every profile control to `wizardSnapshot()` and `applyWizardSettings()` so the Wizard uses the same persisted settings object as the normal editor. Then mirror the controls in `web/VRGDG_MusicVideoWizardUI.js`.

### `VRGDG_WorkflowRunnerNodes.py`

This file converts Builder settings into the API prompt used by ComfyUI.

1. Add the profile identifier and fixed required-resource constants near the existing I2V constants.
2. Extend `/vrgdg/workflow_runner/i2v_choices` with any model category needed by a new picker. The Violets profile uses the `checkpoints` category for full checkpoints and AV checkpoints.
3. Add a profile patch function called from `_patch_i2v_api_prompt()` before the normal loader fields are written.
4. Keep the original branch untouched for all other profiles.

## Violets graph patch details

The shared I2V template is `Workflows/UsedForUIDoNotTouch/Singlei2vForUI_API.json`. It remains the two-pass pipeline. The Violets patch changes only its loaders and inserts fixed LoRA nodes:

1. Collapse `Switch-use GGUF` and remove the GGUF loader.
2. Reuse the `DiffusionModelLoaderKJ` node ID as `CheckpointLoaderSimple`, loading the selected Violets full checkpoint.
3. Rewire all Video VAE consumers to output `2` of that checkpoint loader, then remove the separate Video VAE loader.
4. Convert the dual-CLIP loader to `LTXAVTextEncoderLoader` with the selected text encoder and LTXV Audio Text Encoder checkpoint.
5. Convert the Audio VAE loader to `LTXVAudioVAELoader` using the same selected AV checkpoint.
6. Insert a fixed `LoraLoaderModelOnly` for DMD at `1.0`.
7. Insert a fixed standard `LoraLoader` for JoyAI at model and CLIP strength `0.5`.
8. Rewire the shared optional two-pass LoRA node to receive the fixed JoyAI model output, and rewire text-conditioning nodes to receive the fixed JoyAI CLIP output.

The fixed nodes sit before the existing optional video-LoRA node. Consequently, optional LoRAs still work normally without allowing the two mandatory LoRAs to be removed, altered, or applied twice. The backend rejects attempts to add either required LoRA in an optional slot.

## Reproduction pattern for another profile

To add a different full-checkpoint profile, for example `Anima LTX`, do the following:

1. Create a new stable profile ID and source-workflow defaults in both frontend and backend.
2. Add the selector choice and profile-only model inputs to the frontend settings lifecycle above.
3. Add a backend patch function that validates the actual ComfyUI model categories before creating the prompt.
4. Reuse the shared I2V API template; replace only necessary loaders and references.
5. If required adapters exist, insert fixed loader nodes ahead of the optional user-LoRA node. Never express mandatory adapters as editable UI slots.
6. Branch in `_patch_i2v_api_prompt()` so the original repository path stays byte-for-byte equivalent for the default profile.
7. Mirror the new profile in the Wizard before considering the feature complete. The Wizard must send the exact setting names used by the Builder—not a parallel render payload.
8. Validate without rendering by loading the API template, applying the profile patch, and asserting loader classes, model/CLIP references, required adapter names/strengths, and sampler/sigma inputs.

## Validation expectations

Run at least:

```powershell
python -m py_compile VRGDG_WorkflowRunnerNodes.py
node --check web\VRGDG_MusicVideoBuilderUI.js
git diff --check
```

Then perform a non-rendering API-prompt build. Confirm that the final prompt contains the expected full checkpoint loader, AV text/audio loaders, DMD `1.0`, JoyAI model/CLIP `0.5`, and the untouched two-pass sampler/sigma nodes.

ComfyUI must be restarted after changing the Python backend before the new profile and checkpoint-choice endpoint are live.
