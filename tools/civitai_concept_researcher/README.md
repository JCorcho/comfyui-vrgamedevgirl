# Civitai Concept Research Helper

This is the Phase 2 external helper used by the thin **VRGDG / Knowledge /
Concept Research** nodes. It calls Civitai's public image API with metadata
enabled, performs conservative local filtering, and emits review-only JSON. It
does not write recipes by itself.

## Command line

From the `comfyui-vrgamedevgirl` custom-node directory on this machine:

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\tools\civitai_concept_researcher_cli.py --concept "arched back" --base-model Pony --limit 5
```

Use `--base-model Anima` for Anima, `--base-model Any` for no local model-family
filter, and `--include-nsfw` when an adult-content review is intentionally
required. The normal node defaults to safe-only research; its **Safe-only
search** switch can be turned off for the same adult-allowed mode.

## Access and safety

- Public, visible recipe metadata does not require a login, browser profile, or
  API key.
- If the owner's Civitai policy requires authentication, set
  `CIVITAI_API_TOKEN` in the environment running ComfyUI; never save tokens in
  this repository or in knowledge-base JSON.
- Requests are spaced, retry only temporary failures, honor `Retry-After` when
  present, and resolve resource names only for the short candidate list.
- Civitai's search/base-model filters can be broad. The helper validates visible
  `meta.baseModel`, prompt evidence, and metadata completeness locally before
  returning a candidate.
- A `safe_only` result relies on Civitai's public NSFW labels. It is not a
  visual moderation or a guarantee about every prompt's content.
- Adult-allowed research explicitly requests `nsfw=true` from the Civitai API.
  It uses `civitai.red/api/v1` first and falls back to `civitai.com/api/v1`
  with the same adult filter only when the Red endpoint is temporarily down.
  The returned image/post links identify the endpoint actually used.

## Output contract

Each candidate contains the full visible prompt/negative prompt, seed, CFG,
steps, sampler, resolved model and LoRA names where Civitai exposes them,
image/post URLs, metadata completeness, and a review priority. `quality_score`
is always `0.0` until a person reviews and saves the candidate through the
Phase 1 Knowledge Base.
