# Pony T2I testing-mode switch

## Purpose

`VioletsT2I(Pony).json` now has a workflow-level **Testing Mode** Boolean. It makes prompt and composition testing fast without destroying the normal production pipeline.

- `true` — first sampling pass only. It skips latent upscale, the second sampler, and FaceDetailer.
- `false` — original production route: first sampler, latent upscale, second sampler, decode, and FaceDetailer.

The current saved default is `true`, because this was added for temporary prompt testing. Change it to `false` in the ComfyUI canvas before a normal final-quality run.

## Why this is a lazy switch rather than node bypass

The Music Video Builder reads the saved UI workflow and converts it to an API prompt through `../ComfyUI-Violets-Integration/pony_adapter.py`. Canvas `mode: 4` bypass/mute flags are presentation-state flags and are not a reliable execution gate in that conversion. Do not use bypass/mute to disable the second pass or FaceDetailer for Builder jobs.

`LazySwitchKJ` from the installed `ComfyUI-KJNodes` pack is an execution gate. Its inactive `on_false` or `on_true` input is marked lazy, so ComfyUI does not execute that upstream branch. This works for normal ComfyUI canvas runs and for requests made through both Music Video Builder entry points.

## Saved workflow location and recovery point

- Active workflow: `ComfyUI/user/default/workflows/VioletsT2I(Pony).json`
- Pre-switch backup: `ComfyUI/user/default/workflows/VioletsT2I(Pony).pre-testing-mode-20260720-0712.bak`

The active workflow is ComfyUI user data rather than a file tracked by this extension repository. Keep a dated `.bak` copy before any structural workflow edit. This document is versioned in the v10 fork to record the intended architecture.

## Node wiring

The switch group uses these node IDs in the current workflow. Preserve the data-flow relationship if IDs change after a later rewrite.

| Node | Type | Purpose |
| --- | --- | --- |
| `57` | `BOOLConstant` | `Testing Mode (true = first pass only)` Boolean, connected to both switches. |
| `58` | `LazySwitchKJ` | Chooses the decoded latent source. `on_true` receives first sampler `55`; `on_false` receives second sampler `53`. Its output feeds `VAEDecode` `7`. |
| `59` | `LazySwitchKJ` | Chooses the final image. `on_true` receives `VAEDecode` `7`; `on_false` receives `FaceDetailer` `15`. Its output feeds `SaveImage` `8`. |

The retained production branch is:

```text
KSamplerAdvanced 55
  -> LatentUpscale 54
  -> KSamplerAdvanced 53
  -> LazySwitchKJ 58 on_false
  -> VAEDecode 7
  -> FaceDetailer 15
  -> LazySwitchKJ 59 on_false
  -> SaveImage 8
```

The testing branch is:

```text
KSamplerAdvanced 55
  -> LazySwitchKJ 58 on_true
  -> VAEDecode 7
  -> LazySwitchKJ 59 on_true
  -> SaveImage 8
```

Nodes `54`, `53`, and `15` must remain normal active nodes (`mode: 0`). The lazy switches control execution; canvas bypass would prevent the false/production route from working in an ordinary canvas run.

## Reproduction recipe for another workflow

Use this pattern for a future model workflow that needs a fast test path.

1. Copy the workflow to a timestamped `.bak` file and make sure `ComfyUI-KJNodes` is installed.
2. Identify the earliest expensive stage to skip, the image/latent immediately before it, and the final output node.
3. Add one `BOOLConstant` named clearly, with `true` meaning the short testing route and `false` meaning the original production route.
4. Add a first `LazySwitchKJ` before the decoder (or before the first downstream consumer). Connect `on_true` to the inexpensive source and `on_false` to the full-quality source.
5. Add a second `LazySwitchKJ` before the save/output node whenever an expensive image post-process stage must also be skipped. Connect `on_true` to the pre-detail image and `on_false` to the detailed image.
6. Remove only the replaced direct output links. Retain the internal production chain, then set its nodes to `mode: 0`.
7. Verify every link has matching source/output and destination/input entries. Keep the new nodes clear of existing nodes in the canvas.
8. Call the relevant adapter's no-render `/validate` endpoint. Do not use `/prompt` or queue a generation merely to validate the graph.
9. Refresh/reopen the workflow in ComfyUI. Confirm `true` skips the intended branch and `false` follows the original route.

## Adapter compatibility and verification

`pony_adapter.py` reads the saved workflow on each request, so no ComfyUI restart is required for a saved switch-state change. It repairs the existing unambiguous missing model link for first sampler `55` only in the API prompt it builds; it does not modify the source workflow.

Validated after this change without a render:

- Both `BOOLConstant` and `LazySwitchKJ` were reported by the live ComfyUI node registry.
- The saved UI graph had no broken link references.
- `POST /violets_t2i/validate` returned `ok: true`, `valid: true`, and did not place work in the ComfyUI queue.
- The adapter output includes the two lazy switches, and it attaches the repaired model input to sampler `55` in memory.
