# Adaptive VRAM residency and scene submission manager

## Purpose

This is the handoff guide for the shared local-workflow scheduling policy used by the Music Video Builder and its Wizard. It prevents the image pass from explicitly evicting the same ComfyUI model after every scene, then reloading it for the next scene.

The first adopter is the Pony / VioletsT2I image path. The manager is model-agnostic: it reads the generated ComfyUI API graph, measures live CUDA memory, and resolves referenced local model files. Do not add GPU-specific checks or names such as `Pony`, `LTX`, or `16 GB` to the resource planner.

## Important execution truth

ComfyUI normally runs one queued workflow per GPU at a time. A queue window of `2` or more does **not** mean simultaneous sampling on one GPU. It means that multiple already-built scene jobs are waiting in the normal ComfyUI queue, which:

1. keeps matching workflows adjacent;
2. lets ComfyUI reuse its native model cache; and
3. removes browser/network idle time between scenes.

This is safe for VioletsT2I because every scene has a different prompt and the saved workflow contains a two-pass sampler plus FaceDetailer. Do not automatically rewrite that arbitrary graph into concurrent branches or increase its latent `batch_size`; that would change output cardinality, seed behavior, and result-to-scene archival.

If a future workflow explicitly provides a verified multi-prompt batching adapter, it can use the same resource assessment endpoint to set its own native batch size. Keep the existing bounded submission queue as the fallback for all other workflows.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `web/VRGDG_MusicVideoBuilderUI.js` | Shared Builder/Wizard image-stage scheduler, cache-residency advisory state, bounded queue submission, cancellation, and scene result archival. |
| `VRGDG_WorkflowRunnerNodes.py` | Read-only `POST /vrgdg/workflow_runner/assess_prompt_resources` endpoint. It resolves model references in an API graph, reads their file sizes, samples live CUDA free/total bytes, and computes a conservative plan. |
| `LLM.py` | Handles the non-ComfyUI boundary: before llama.cpp loads a GPU-offloaded GGUF prompt model, it only unloads ComfyUI models when the measured headroom cannot fit that GGUF estimate. |
| `web/VRGDG_MusicVideoWizardUI.js` | Has no separate scheduler or hidden policy. Its **Build Full Video** action enters the same Builder `zImageAllScenes(...)` path, preserving parity. |
| `docs/llm-guides/WIZARD_EDITOR_PARITY.md` | Records why this behavior has no separate persisted Wizard setting. |

## Runtime flow

```text
Builder Image All or Wizard Build Full Video
  -> zImageAllScenes({ imageMode: "pony" })
  -> build one VioletsT2I API prompt
  -> /vrgdg/workflow_runner/assess_prompt_resources
       -> model file sizes + CUDA free VRAM + safe queue window
  -> runAdaptiveSceneWorkflowQueue(...)
       -> queue N matching prompts without waiting for idle between each
       -> ComfyUI serially renders them and reuses its cache
       -> archive each completed image to its originating scene
  -> later local GGUF transition
       -> LLM._release_comfy_models_for_gguf_headroom(...)
       -> unload only if both stacks do not fit
```

## Resource-plan contract

The endpoint accepts:

```json
{
  "prompt": { "<Comfy node id>": { "class_type": "...", "inputs": {} } },
  "requested_jobs": 41,
  "resident_model_bytes": 0
}
```

It returns, among other fields:

- `model_fingerprint`: stable identity based on resolved model paths and file sizes.
- `model_bytes`, `activation_estimate_bytes`, and `working_set_estimate_bytes`.
- `vram.free_bytes` and `vram.total_bytes`, sampled at request time.
- `queue_window`: `1` through the generic safety cap. This is bounded submission depth, not GPU parallelism.
- `transition_requires_cleanup`: true only when the previous model estimate plus the next stack cannot fit the measured headroom.
- `confidence`: low/medium/high depending on whether all referenced model assets were resolved.

The parser only follows known model-input names (`ckpt_name`, `unet_name`, `lora_name`, `vae_name`, `clip_name`, and related names). It does not load models and it rejects path traversal when looking beneath ComfyUI model roots.

If the route is unavailable, errors, cannot resolve assets, or CUDA telemetry is unavailable, the frontend uses a queue window of `1`. Rendering remains functional; it simply uses the conservative scheduler.

## Reproduction recipe for another local T2I workflow

Use this pattern when adding a workflow such as `Anima`.

1. Follow `ADDING_T2I_WORKFLOW_MODE.md` to create a dedicated adapter endpoint and API-prompt builder. Do not modify the user's saved source workflow.
2. Split the existing single-scene function into:
   - `build<Mode>ImageWorkflow(segment)` returning `{ prompt, promptGraph }`; and
   - `complete<Mode>ImageForSegment(segment, prompt, images)` that archives images and updates the scene.
3. In the all-scenes image pass, call `runAdaptiveSceneWorkflowQueue(sceneItems, { ... })`:
   - `buildJob` must return the API graph as `prompt` plus the segment and original text needed for archival.
   - `completeJob` must update only the completed job's scene and autosave it.
   - pass `shouldCancel: () => state.batchCancelled`.
4. Do not call `runClearMemoryWorkflowQuiet(...)` inside the per-scene loop for the same model. Keep cleanup for explicit user actions, errors/cancellation, retries, or a resource-manager-required model transition.
5. If the mode has a dependency on the previous scene (for example image-to-image continuity), keep it serial until its adapter can prove independent jobs are safe.
6. Do not add a separate Wizard renderer. Ensure Wizard **Build Full Video** reaches the same Builder function and update `WIZARD_EDITOR_PARITY.md` if a new persisted setting is introduced.

## Verification without generating media

1. Compile the changed Python files with ComfyUI's embedded Python:

   ```powershell
   & "C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe" -m py_compile VRGDG_WorkflowRunnerNodes.py LLM.py
   ```

2. Check the browser source syntax:

   ```powershell
   node --check web\VRGDG_MusicVideoBuilderUI.js
   node --check web\VRGDG_MusicVideoWizardUI.js
   ```

3. Restart the source ComfyUI instance after Python changes, then use an existing adapter's no-render validation route to obtain an API graph. POST that graph to `/vrgdg/workflow_runner/assess_prompt_resources` and verify that `queue_window >= 1`, `renderer_parallelism` is `1`, and no `/prompt` request was made.
4. Confirm `GET /queue` reports no running or pending work unless the user explicitly requested a render.
5. Run `git diff --check`, commit the focused change, push `custom/pony-t2i`, and record the SHA in the handoff.

## Invariants

- Never advertise a bounded ComfyUI queue as simultaneous GPU rendering.
- Never hardcode a GPU capacity, a model name, or a model file size into the resource decision.
- Preserve the normal ComfyUI cache whenever the next matching workflow can use it.
- Before a separate non-ComfyUI GPU loader (the local GGUF runner) starts, force-clear ComfyUI only if the live fit calculation requires it.
- Keep error and cancel cleanup explicit; queued jobs must be interrupted and removed before error cleanup runs.
- Do not persist runtime residency guesses to project files. ComfyUI is authoritative about its actual model cache.
