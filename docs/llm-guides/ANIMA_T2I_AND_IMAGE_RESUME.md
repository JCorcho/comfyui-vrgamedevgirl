# Anima T2I and Project Image Resume Guide

This guide documents the Anima implementation and the scene-image cache used by the Music Video Builder. It is written as a handoff for another agent working on the v10 fork.

## Anima routing

The saved ComfyUI editor workflow is the source of truth:

`<ComfyUI>/user/default/workflows/VioletsT2I(Anima).json`

The companion custom node repository contains `comfyui-violets-integration/anima_adapter.py`. It reads that file on every request, converts the editor graph to an API prompt with the same graph converter used by Pony, finds the one active prompt encoder that reaches the sampler's `positive` conditioning input, and replaces only that node's `text` input. This supports both the standard `CLIPTextEncode` node and `CyberdeliaPromptFormatEncode` (the Positive prompt node in the current Violets Anima workflow), while leaving its negative prompt untouched. The selected workflow therefore retains its own Anima checkpoint, LoRAs, sampler, VAE, dimensions, and save-node behavior. The endpoints are:

- `POST /anima_t2i/build_prompt` with `{ "prompt": "..." }`
- `POST /anima_t2i/validate` with `{ "prompt": "..." }`

The Builder UI (`web/VRGDG_MusicVideoBuilderUI.js`) uses `imageModelMode === "anima"`, maps its prompt instructions to `anima_t2i`, and queues the returned API prompt. The Wizard (`web/VRGDG_MusicVideoWizardUI.js`) treats Anima as a workflow-managed image mode, displays the same workflow source, and saves `image_model_mode: "anima"` with an empty `image_settings` object. The Builder wizard snapshot must include the Anima option so both surfaces stay in parity.

Prompt-generation instructions live in `VRGDG_MusicVideoBuilderNodes.py` under the `anima_t2i` instruction maps. They follow the local Anima recipe in the ComfyUI skill: lowercase Danbooru-style tags or a clean hybrid, `masterpiece, best quality, score_7, safe,` prefix, visible subject count first, and no animation/video language.

## Image resume/cache behavior

Canonical scene images are saved as `zimage_approved/image_####.<ext>` under the project folder. A generated preview in `scene_image_previews/scene_####/` is a fallback when no canonical image exists.

`VRGDG_MusicVideoBuilderNodes.py` exposes `POST /vrgdg/music_builder/scene_media_status`. The route accepts a project folder and scene-number list, checks canonical PNG/JPG/JPEG/WEBP files first, then returns the newest preview path. It performs no writes.

Before Image All and Build Full Video dispatch, the Builder calls `hydrateExistingProjectImagesForBuild(sceneScope)`. For each scene that has no in-memory image and has not been explicitly cleared, the returned path is added to `image_history`; canonical paths also become `approved_image_path`. `imageAllSegmentsForMode("resume_missing", ...)` then filters those scenes out, so no Gemma prompt pass, T2I queue, or model load is performed for an existing image. Explicit “redo” modes still regenerate as requested.

When changing this logic, preserve `image_assignment_cleared`: an owner who deliberately clears a scene image must not have that image silently resurrected from disk. Keep the route read-only and use absolute paths returned by the existing project media conventions.

## Reproduce or add another workflow mode

1. Copy the Anima pattern in `ADDING_T2I_WORKFLOW_MODE.md` and choose a unique mode key.
2. Add the key to the Builder instruction defaults, labels, preset maps, display label, chooser card, workflow-managed panel, prompt adapter functions, batch dispatcher, wizard snapshot, and mode normalizer.
3. Add the same value to the Wizard fallback options and treat it as workflow-managed in its model card and `image_settings` serializer.
4. Create a companion adapter with a named endpoint and a saved workflow filename. Reuse the graph converter, replace only positive prompt text, and expose a validation route.
5. Run `node --check` on both UI files, `py_compile` on the Python node/adapter, validate the adapter through the live ComfyUI HTTP route, and verify that `scene_media_status` returns a known existing image.
6. Commit the main fork and companion adapter separately with focused messages. Never stage unrelated SRT/session files.
