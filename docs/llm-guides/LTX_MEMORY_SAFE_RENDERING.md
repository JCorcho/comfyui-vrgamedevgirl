# LTX 2.3 low-VRAM rendering guide

## Scope

This guide describes the memory-safe path used by the Script-to-Film `Film/T2AV + Character Ref` profile. It is intentionally isolated from the repository-default GGUF Music Video graph. The profile is selected by `i2v_model_profile: "violets_ltx23_fp8"`.

## Why the OOM happened

The original Script-to-Film graph sent the full LTX model directly into both sampler passes and decoded the complete video latent through a single `VAEDecode` node. Long clips therefore created two avoidable peaks: transformer feed-forward activations during denoising and a large decoded-frame allocation at the output leg.

## Graph changes

The profile patch lives in `VRGDG_WorkflowRunnerNodes.py`, inside `_patch_violets_ltx23_fp8_profile`:

1. The full `.safetensors` checkpoint and the locked DMD/JoyAI LoRA chain remain unchanged.
2. `LTXVChunkFeedForward` is inserted once per sampler pass. Pass 1 wraps the model output used by `218:185`; pass 2 wraps the model output used by `219:188`.
3. The existing `VAEDecode` node is replaced only for this profile with `VHS_VAEDecodeBatched`, preserving its latent and VAE connections and adding `per_batch`.
4. `VRGDG_NormalizeVideoFrames` flattens the optional `[batch, frames, height, width, channels]` shape emitted by the LTX VAE into ComfyUI's `[frames, height, width, channels]` IMAGE batch. This is required because VHS's video writer expects one frame per batch item.
5. The final `VHS_VideoCombine` still receives the normalized video frames and native LTX audio, so audio routing and stitching behavior are unchanged.

The rewiring happens before the wrapper nodes are inserted. That ordering is important: otherwise a global reference replacement can accidentally turn each chunk node's source model into a self-reference.

## Controls and defaults

The normal editor and Wizard expose the same values:

- `ltx_chunk_feed_forward_enabled`: enabled by default.
- `ltx_chunk_feed_forward_chunks`: `2` by default; larger values lower activation peaks but add compute.
- `ltx_chunk_feed_forward_dim_threshold`: `4096` by default; KJNodes chunks dimensions at or above this threshold.
- `ltx_vhs_vae_batch_size`: `8` frames by default; lower it if the VAE/output leg still peaks too high.

The editor controls are in the I2V Advanced Settings panel under **LTX Memory Safety**. The Wizard has the same card on its Settings step. The browser cache-busting version is maintained in `VRGDG_MusicVideoBuilderUI.js`.

Payload fields are copied into each Script-to-Film scene by `i2vVideoSettingsPayload(segment)`. The backend clamps the values to safe ranges (`chunks 1..100`, threshold `0..16384`, VAE batch `1..4096`).

## Tuning procedure

1. Start with the defaults at a small resolution and a 9-frame scene.
2. If the transformer still runs out of VRAM, increase feed-forward chunks to `3` or `4`.
3. If the error occurs during VAE decode or video combine, lower VAE frames per batch to `4`, then `2`.
4. Keep the profile's DMD LoRA at `1.0` and JoyAI LoRA at `0.5`; they are backend-locked and are not part of the memory tuning surface.
5. Do not add `VHS_BatchManager` to this graph as a substitute. That node requeues an existing video/image input stream and its own documentation says it does not reduce the model's VRAM use; this generated graph has no such input stream. Chunk feed-forward is the appropriate control for the LTX denoising peak, while batched VAE decode protects the output leg.

## Reproduction checklist for another agent

1. Query `/object_info/LTXVChunkFeedForward` and `/object_info/VHS_VAEDecodeBatched` to confirm the installed node signatures.
2. Locate `_patch_violets_ltx23_fp8_profile` and insert the two chunk wrappers around the pass-1/pass-2 model references before adding the wrapper nodes.
3. Replace only the profile's `VAEDecode` with `VHS_VAEDecodeBatched` and set `per_batch` from the payload.
4. Add the four payload fields to `defaultI2VVideoSettings`, panel synchronization, save/payload functions, Wizard controls, and `applyWizardSettings`.
5. Restart ComfyUI so the Python module is reloaded, build a 9-frame graph through `/vrgdg/script_to_film/build_t2av_prompt`, and verify:
   - both `LTXVChunkFeedForward` nodes exist;
   - their `model` inputs point to the JoyAI output;
   - `218:185` and `219:188` point to the respective chunk nodes;
   - the decode node is `VHS_VAEDecodeBatched` with the requested `per_batch`;
   - `VRGDG_NormalizeVideoFrames` sits between the decode node and the writer;
   - `VHS_VideoCombine` still has both image and native-audio inputs.
6. Queue that graph, inspect `/history/{prompt_id}`, and probe the resulting MP4 with FFprobe before claiming success.
