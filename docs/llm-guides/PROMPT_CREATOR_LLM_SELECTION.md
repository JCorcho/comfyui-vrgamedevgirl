# Local Text LLM Selection: Editor, Wizard, and Prompt Creator

## Purpose

The Music Video Builder must use the local GGUF text model selected by the user. The normal editor, Video Wizard, and Prompt Creator are different UI surfaces for the same project-level text-model choice.

This guide documents the implementation that prevents a selection from silently reverting to the repository default. Use this pattern when adding another local text GGUF model; do not special-case its filename.

## Model discovery

`LLM.py` is the source of truth for local text-GGUF discovery.

- `VRGDG_SuperGemmaGGUFChat._list_local_text_gguf_choices()` scans every `.gguf` under `ComfyUI/models/LLM` (including configured custom model roots).
- It excludes only files whose name includes `mmproj`, because those are vision projection files, not text models.
- It deliberately does **not** require `Gemma`, `gemma`, or any other substring in the filename.
- `_list_local_gemma_gguf_choices()` remains a compatibility alias for older callers only.
- `/vrgdg/music_builder/gemma_choices` in `VRGDG_MusicVideoBuilderNodes.py` exposes this shared list to all UI surfaces.

To add a model, copy its `.gguf` into an LLM model directory, restart ComfyUI, and select its exact filename. No rename is required.

## Shared Builder state

`web/VRGDG_MusicVideoBuilderUI.js` owns these project fields:

| Persisted key | Builder state | Meaning |
| --- | --- | --- |
| `text_gemma_model` | `state.textGemmaModel` | Text-only prompt-generation model |
| `vision_gemma_model` | `state.visionGemmaModel` | Vision-capable prompt model |
| `mmproj_file` | `state.gemmaMmprojFile` | Projection file paired with the vision model |

The control groups are synchronized by these helpers in the same file:

- `setSharedTextGemmaModel(value)` updates T2I, Ernie text, I2V text, and Krea two-pass text controls.
- `setSharedVisionGemmaModel(value)` updates the normal Editor vision controls.
- `setSharedGemmaMmproj(value)` updates the normal Editor projection controls.

Each helper updates the state first, then any control that currently has the requested option. This ordering matters: a saved project can restore its selection before the asynchronous model list has populated, and `refreshGemmaChoices()` then selects the saved value once it is available.

`currentSessionData()` saves the three keys. `loadSessionFromProject()` restores them. `_MODEL_DEFAULT_KEYS` in `VRGDG_MusicVideoBuilderNodes.py` includes them so model defaults retain the same selection.

## Editor and Wizard parity

`wizardSnapshot()` passes the current text model, vision model, projection file, and available choices into `VRGDG_MusicVideoWizardUI.js`. The Wizard returns the exact keys above.

`applyWizardSettings()` must call the three shared setter functions, never assign a single select directly. It then runs the existing save routine and project autosave. This is the only correct Wizard-to-Editor handoff.

`refreshGemmaChoices()` must preserve `state.textGemmaModel` when it repopulates dropdown options. It may use `DEFAULT_NON_VISION_GEMMA_MODEL` only as a first-run fallback when there is no valid saved or current selection. Do not reintroduce an unconditional `select.value = preferred...` assignment.

## Prompt Creator persistence

The standalone Prompt Creator uses `web/VRGDG_MusicVideoPromptCreatorUI.js` and `VRGDG_MusicVideoPromptCreatorNodes.py`.

1. The Builder opens it with `textGemmaModel` and receives `onTextGemmaModelChange`.
2. Prompt Creator selects the passed model when it refreshes its local GGUF list, unless its project draft contains a valid `text_gemma_model`.
3. Its payload sends both `model_file` (the execution field) and `text_gemma_model` (the explicit persistence field).
4. `_save_prompt_creator_draft()` writes `text_gemma_model`; `applyDraft()` restores it.
5. When Prompt Creator changes its selection, the Builder immediately updates shared state and quietly saves the project session.

This keeps a selection made in Prompt Creator, Editor, or Wizard consistent downstream.

## Runtime verification

For every local run, the backend prints one of these lines before resolving the file path:

```text
[VRGDG Music Builder] <operation>: selected local text GGUF: <filename>
[VRGDG Prompt Creator] selected local text GGUF: <filename>
```

Use the ComfyUI terminal/logs to verify the filename. The route result also carries `used_model` for prompt-generation requests that expose it.

## Reproduction checklist

1. Put a test text model in `ComfyUI/models/LLM` with a filename that does **not** contain `gemma`.
2. Restart ComfyUI and confirm it appears in both the Builder/Wizard lists and Prompt Creator list.
3. Select it in the Editor, save the project, reopen it, and confirm all text-model controls retain it.
4. Select a different model in the Wizard, apply settings, reopen the Editor and Wizard, and confirm both show that model.
5. Open Prompt Creator, confirm it inherits the same model, save a draft, close and reopen it, and confirm the saved model remains selected.
6. Run one prompt action and verify the matching runtime log line names the selected file.
