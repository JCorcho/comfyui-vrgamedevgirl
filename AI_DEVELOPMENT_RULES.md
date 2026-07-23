# AI Development Rules

These rules are persistent project constraints for every future agent working on this fork.

## Safe change workflow

- Check `git status` before editing and preserve unrelated user files.
- Commit each completed implementation with a precise conventional-style message.
- Push completed commits to the configured fork remote. Never force-push, reset, or discard owner changes.
- Add an LLM-oriented reproduction guide under `docs/llm-guides/` for every successful implementation.

## UI and backend parity

- Every option, model, configuration, or advanced setting added to the normal Builder/editor must also be present in the Wizard.
- Both surfaces must use the same persisted field names and the same backend renderer. Do not create a Wizard-only workflow path.
- For sampler changes, update the shared frontend fallback (`web/VRGDG_SamplerOptions.js`), the live sampler vocabulary returned by `/vrgdg/workflow_runner/i2v_choices`, the Builder snapshot consumed by the Wizard, and every backend sampler patcher that writes a `sampler_name` input.
- Validate sampler values against the running ComfyUI sampler list (`comfy.samplers.KSampler.SAMPLERS`) and preserve the existing default when a stale/invalid value is received.

## Progress reporting

- Scene-video waits must subscribe to ComfyUI `progress` events for the active prompt when available.
- Display current sampler iterations, total iterations, and seconds per iteration (`s/it`) in the shared progress window while retaining scene-level progress and cancellation behavior.

## Model/pipeline invariants

- Pony uses `image_model_mode: "pony"` and the existing VioletsT2I route.
- The Violets LTX profile injects DMD at `1.0` and JoyAI at `0.5` in the backend.
- Script-to-Film remains separate from Music Video audio/SRT/mux paths.
- The Concept / Pose Knowledge Base is a separate local recipe library under `knowledge_base/concepts/`. It must not write to Character Bible, LoRA metadata, Script-to-Film prompts, or Music Video paths unless a later explicitly approved phase adds that integration.
