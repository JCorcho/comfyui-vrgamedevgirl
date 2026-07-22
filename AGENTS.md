# Agent Instructions for This Fork

These instructions travel with the `comfyui-vrgamedevgirl` fork. Follow the parent ComfyUI installation instructions as well.

## Mandatory safeguards

1. **Git safe points**
   - Check `git status` before editing and preserve unrelated user changes.
   - Commit every completed implementation with a precise conventional-style message.
   - Push completed commits to the user's fork remote. Never force-push, reset, or discard work without explicit owner approval.

2. **LLM-oriented reproduction documentation**
   - For every successful implementation, add or update a guide in `docs/llm-guides/`.
   - Name the changed files, data/settings path, exact reproduction steps, model/node constraints, and non-rendering validation.
   - Write it so a future, lower-context agent can adapt the feature without reverse-engineering the codebase.

3. **Strict editor/Wizard parity**
   - Every option, model, configuration, and advanced setting added to the normal Builder/editor must be added to the Video Wizard before the feature is complete.
   - The two surfaces must pass the same persisted field names into the same backend render logic. Do not make a Wizard-only render path.
   - Follow and maintain `docs/llm-guides/WIZARD_EDITOR_PARITY.md`.

## Current project invariants

- Pony T2I is selected with `image_model_mode: "pony"` and is rendered through the existing `VioletsT2I(Pony).json` route.
- The Violets LTX 2.3 FP8 profile is selected with `i2v_model_profile: "violets_ltx23_fp8"`. The backend, not either UI, injects DMD at `1.0` and JoyAI at `0.5`.
- Do not copy a user's standalone workflow into the Builder. Preserve the shared repository workflow graph and patch only the loader seam required by a profile.
- Script-to-Film is a separate `project_mode`, not a Music Video variation. Keep it out of source-audio upload, Whisper/SRT timing, lyric parsing, source-audio crop, and Music Video mux paths. Its complete handoff guide is `docs/llm-guides/SCRIPT_TO_FILM_IMPLEMENTATION.md`.
- Script-to-Film Prompt Creator instructions live only in `prompts/ScriptToFilm_PromptCreator_System.txt`; preserve its exact GROK start/end markers when editing it.
