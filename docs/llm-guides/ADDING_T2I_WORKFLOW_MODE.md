# Adding a text-to-image workflow mode

## Purpose

This is the handoff guide for an LLM agent adding a model-specific T2I mode to the v10 Music Video Builder. Pony is the reference implementation. Follow the same pattern for a future workflow such as `Anima`; do not inspect or reuse modifications from the legacy pre-v10 extension.

## Current repositories and safe points

- Main v10 fork: `https://github.com/JCorcho/comfyui-vrgamedevgirl`, active custom branch: `custom/pony-t2i`.
- Upstream remote: `vrgamegirl19/comfyui-vrgamedevgirl`; its push URL is intentionally disabled. Push project work only to `origin`.
- Companion runtime adapter: `https://github.com/JCorcho/comfyui-violets-integration` (private), branch `main`.
- First Pony feature commits:
  - Main fork: `196a02f feat(t2i): integrate Pony Violets workflow`
  - Adapter: `36de570 feat(adapter): add VioletsT2I runtime workflow bridge`

Make one focused commit per logical change and push it before beginning the next feature. Run `git diff --check`, inspect `git status --short`, and use a descriptive conventional commit message before every handoff.

## Architecture and Pony data flow

```text
Music Video Builder / Wizard
  -> state.imageModelMode = "pony"
  -> Gemma prompt request with builder_instruction_key = "pony_t2i"
  -> VRGDG_MusicVideoBuilderNodes.py resolves default or project override
  -> segment.t2i_prompt
  -> POST /violets_t2i/build_prompt
  -> ComfyUI API prompt built from VioletsT2I(Pony).json
  -> normal ComfyUI queue + result archival into the scene
```

### Main v10 extension files

1. `web/VRGDG_MusicVideoBuilderUI.js`
   - Owns the Builder UI, `state.imageModelMode`, session persistence, Image All, full-build routing, prompt generation, queueing, and result archival.
   - `builderImageInstructionKey(imageMode)` maps `pony` to `pony_t2i`.
   - `generateStoryboardT2IPromptForSegment(...)` sends that key to `/vrgdg/storyboard/gemma_image_prompt`.
   - `createPonyImageForSegment(...)` calls `/violets_t2i/build_prompt`, queues the returned API prompt with the existing `queueWorkflowPrompt(...)`, waits for images, and archives them to the current scene.
   - The Pony card, panel, single-scene control, Image All, full-video pass, mode normalization, and batch chooser are all in this file.

2. `web/VRGDG_MusicVideoWizardUI.js`
   - This is a different UI from the Builder Image tab. It has its own visible Text-to-Image selector.
   - Its fallback options include `{ value: "pony", label: "Pony" }`.
   - Its Pony settings card is workflow-managed: it displays the source workflow and intentionally does not expose unrelated UNet/CLIP/VAE fields.
   - It saves `image_model_mode: "pony"` and `image_settings: {}`. The Builder receives that session state and performs the actual render.

3. `VRGDG_MusicVideoBuilderNodes.py`
   - The central source of truth for all Builder LLM instruction defaults.
   - `_PONY_T2I_INSTRUCTIONS` is the version-controlled Pony default.
   - `_BUILDER_INSTRUCTION_DEFAULTS`, `_BUILDER_INSTRUCTION_LABELS`, `_BUILDER_INSTRUCTION_PRESET_GROUPS`, and `_BUILDER_INSTRUCTION_PRESET_GROUP_LABELS` must all contain `pony_t2i`.
   - The editable override API resolves a scene override first, then an all-scenes project override, then the built-in default.

### Companion adapter files

1. `../ComfyUI-Violets-Integration/pony_adapter.py`
   - Registers `POST /violets_t2i/build_prompt` and `POST /violets_t2i/validate`.
   - Reads `user/default/workflows/VioletsT2I(Pony).json` by default, or the `VIOLETS_T2I_WORKFLOW` environment override.
   - Converts the saved UI workflow to an API prompt, injects the scene text into positive `CLIPTextEncode` node `3`, and validates the prompt.
   - The saved workflow currently has an unambiguous missing `model` link on active second-pass sampler `55`; the adapter repairs it in memory using the only sampler model source. Never rewrite the source workflow merely to make this repair.

2. `../ComfyUI-Violets-Integration/__init__.py`
   - Imports the route module so ComfyUI registers the adapter at startup.

## Pony prompt instructions and future edits

The built-in Pony default is in `VRGDG_MusicVideoBuilderNodes.py` as `_PONY_T2I_INSTRUCTIONS`.

During a Builder project, select **Pony** in the Image tab and use **Edit Pony Prompt Instructions**:

- **Save for This Scene** writes `<project>\\project_context\\custom_builder_instructions\\scenes\\<scene-id>\\pony_t2i.txt`.
- **Save for All Scenes** writes `<project>\\project_context\\custom_builder_instructions\\pony_t2i.txt`.
- **Save Preset** stores a reusable preset beneath ComfyUI output at `VRGDG_LLM_Instruction_Presets\\builder\\pony_t2i\\`.

Pony’s default generates a single comma-separated positive tag sequence beginning exactly with:

```text
score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, rating_safe,
```

It leaves negative terms to VioletsT2I(Pony)’s existing negative-conditioning node. The full Pony V6 prompt template uses this score sequence and supports optional source/rating tags; the workflow is already configured with CLIP skip -2, which is also the model-card recommendation. See the [Pony Diffusion V6 XL model card](https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL) when changing the grammar.

## Pony workflow testing mode

See [PONY_TESTING_MODE.md](PONY_TESTING_MODE.md) before changing the saved `VioletsT2I(Pony).json` graph. This workflow-level switch is shared by the Builder and Music Video Wizard through the same Pony adapter, so it preserves Editor/Wizard parity without duplicating a UI control.

## Reproduction recipe: add an `Anima` mode

Use this only after deciding whether Anima needs a separate saved ComfyUI workflow. Do not assume it can reuse the Pony workflow.

1. **Version control first**
   - Start from a clean `git status` in both repositories.
   - Create a focused branch from `custom/pony-t2i`.
   - Keep the v10 UI change and any adapter change in separate commits/repositories.

2. **Create or extend the runtime adapter**
   - Save and validate the Anima UI workflow under `ComfyUI/user/default/workflows`.
   - Prefer a separate named endpoint such as `/anima_t2i/build_prompt` and `/anima_t2i/validate` if its injection, validation, or output behavior differs from Pony.
   - Build API-format prompts from the saved graph at request time. Identify the positive text node from the actual workflow; do not hard-code Pony node IDs for Anima.
   - Inject only the intended scene prompt. Preserve model, LoRA, sampler, VAE, resolution, and negative-conditioning settings in the workflow.
   - Add a no-render `validate` endpoint and verify it before any generation.

3. **Add a dedicated LLM instruction key**
   - Add `_ANIMA_T2I_INSTRUCTIONS` in `VRGDG_MusicVideoBuilderNodes.py`.
   - Register `anima_t2i` in each of the four Builder instruction maps listed above.
   - Give it a separate preset group when its grammar differs from Pony or the generic models.
   - Change `builderImageInstructionKey("anima")` to return `anima_t2i`.

4. **Wire the Builder UI**
   - Add an `animaCard`, a workflow-managed mode panel, **Gemma T2I**, **Edit Anima Prompt Instructions**, and **Create with Anima** controls.
   - Implement `createAnimaImageForSegment(...)` by following the Pony method: build API prompt, queue through the shared queue helper, wait, archive to the scene, then refresh the preview.
   - Include Anima in `syncFluxKleinPanel()` card/panel visibility, session state, image-label helpers, batch/Image All handling, the confirmation dialog, and full-build routing.
   - Do not route a new model through ZImage’s generator merely because both are local workflows.

5. **Wire the Music Video Wizard**
   - Add `anima` to the Builder wizard snapshot `imageModeOptions` and to the Wizard fallback list.
   - Accept it in `normalizeWizardImageMode(...)`.
   - Render a workflow-managed Wizard panel, not generic model-picker controls, when the workflow owns its stack.
   - Save `image_model_mode: "anima"` and an empty `image_settings` object for workflow-managed modes.

6. **Verify without rendering**
   - `node --check web/VRGDG_MusicVideoBuilderUI.js`
   - `node --check web/VRGDG_MusicVideoWizardUI.js`
   - Compile the modified Python module with the active ComfyUI Python interpreter.
   - Restart ComfyUI after Python changes, then call the model adapter’s `POST .../validate` endpoint; do not queue `/prompt` for validation.
   - Fetch the served JavaScript assets with a cache-busting query and assert the new option, instruction key, endpoint, and workflow panel are present.
   - Confirm `/queue` has no running or pending prompts unless generation was explicitly requested.
   - Run `git diff --check`, commit, push, and record the commit SHA in the handoff.

## Non-negotiable invariants

- Never generate media unless the user explicitly asks to generate it.
- Never modify legacy pre-v10 code as a design reference.
- Never silently alter the saved source workflow. Any required compatibility repair must be explicit, deterministic, documented, and applied only to the runtime API prompt.
- Keep prompt instruction keys model-specific when their prompt grammar differs.
- Treat the Builder and Music Video Wizard as separate frontend entry points; update and test both.
