# Concept / Pose Knowledge Base — Phases 1–3

This guide covers the local, manually curated recipe library introduced in Phase 1, its human-reviewed Civitai research intake added in Phase 2, and the Script-to-Film-only generation-time suggestions added in Phase 3. It is a standalone store for reproducible pose, body-mechanics, camera-angle, and concept recipes. It is not a Character Bible, LoRA metadata store, prompt generator, or Music Video feature.

## Scope boundary

- **Character Bible** stays identity and visual-continuity only.
- **LoRA Knowledge Base** stays LoRA-specific technical metadata only.
- **Concept / Pose Knowledge Base** stores complete model-generation recipes for a reusable concept.
- **Music Video** is untouched. Do not import the Concept/Pose store into `VRGDG_MusicVideoBuilderNodes.py` or `VRGDG_WorkflowRunnerNodes.py`.
- **Phase 3 exception:** `VRGDG_ScriptToFilmConceptIntelligence.py` may be called only by `VRGDG_ScriptToFilmNodes.py` and the shared `VRGDG_ScriptToFilmUI.js` planner. `VRGDG_MusicVideoBuilderUI.js` may pass the Film-only `keyframe_model` into its existing `isScriptToFilmMode()` branch because Builder and Wizard open that same planner. Do not call this code from a Music Video render, prompt, or timeline path.
- The Phase 2 Civitai client remains outside ComfyUI nodes under `tools/civitai_concept_researcher/`. Nodes must not acquire network/scraping logic.
- Civitai candidates are review-only. Never auto-save, auto-apply, or promote their `candidate_score` to a local `quality_score`; only an explicit user selection writes a local recipe.
- Browser automation is not used for Phase 2. Do not add cookies, browser profiles, or credentials to the repository merely to research public Civitai metadata.

## Files and layout

| Path | Role |
| --- | --- |
| `VRGDG_ConceptPoseKnowledgeBase.py` | JSON store helpers plus five thin ComfyUI nodes. |
| `knowledge_base/concepts/examples/arched_back.json` | Tracked example with Pony and Anima full recipes. |
| `knowledge_base/concepts/examples/low_crouch.json` | Second tracked example with Pony and Anima full recipes. |
| `knowledge_base/concepts/local/` | User-created local concept overrides. JSON files here are ignored by Git. |
| `tests/test_concept_pose_knowledge_base.py` | CRUD, filtering, sample-data, registration, and isolation tests. |
| `tools/civitai_concept_researcher/researcher.py` | Dependency-free external Civitai API client and metadata-to-candidate extraction. |
| `tools/civitai_concept_researcher_cli.py` | Embedded-Python-safe command-line launcher. |
| `VRGDG_ConceptResearchNodes.py` | Three thin ComfyUI review/save nodes; no scraping logic. |
| `tests/test_civitai_concept_researcher.py` | Mocked full-metadata extraction, review/save flow, registration, and isolation tests. |
| `Workflows/KnowledgeBase/` | Six GUI-format, source-controlled test canvases deployed to the user's `Workflows/VRGDG Concept Recipe Tests/` subfolder. |
| `VRGDG_ScriptToFilmConceptIntelligence.py` | Phase 3 deterministic local matching, compact suggestion data, recipe application, Phase 2 research delegation, and three thin canvas nodes. |
| `VRGDG_ScriptToFilmNodes.py` | Film-only HTTP routes under `/vrgdg/script_to_film/concept_intelligence/`; it normalizes the applied recipe metadata so it persists in a Film plan. |
| `web/VRGDG_ScriptToFilmUI.js` | Shared Builder/Wizard Film Planner UI: base-model choice, scene suggestions, Apply, research review, and explicit save. |
| `tests/test_script_to_film_concept_intelligence.py` | Temporary-store suggestions, Pony/Anima filtering, application, research delegation, and scope-registration tests. |

The source scans `examples/` first and `local/` second. A local JSON file with the same `concept_key` deliberately overrides the example, so editing a sample never changes tracked source data. All user writes are atomic file replacements.

## Schema

Each file is one concept and is named `<concept_key>.json`:

```json
{
  "schema_version": 1,
  "concept_key": "arched_back",
  "display_name": "Arched Back",
  "compatible_base_models": ["Pony", "Anima"],
  "recipes": [
    {
      "recipe_id": "arched_back_pony_studio_01",
      "source": "local",
      "positive_prompt": "full recipe prompt",
      "negative_prompt": "full negative prompt",
      "loras": [{"name": "Example.safetensors", "weight": 0.7}],
      "seed": "18420591",
      "cfg": 5.5,
      "steps": 30,
      "sampler": "euler",
      "model_name": "Pony base workflow",
      "base_model": "Pony",
      "notes": "Why this setup works.",
      "quality_score": 8.2,
      "date_added": "2026-07-22T00:00:00Z",
      "tags": ["pose", "studio"]
    }
  ]
}
```

`base_model` is an intentional Phase 1 extension. It lets a concept hold Pony, Anima, or future-model recipes while `Best Match` returns only the appropriate family. `recipe_id` is the stable identifier required for edit and delete operations.

## Nodes

All nodes live in **VRGDG → Knowledge → Concept Recipes**.

| Node | Use |
| --- | --- |
| `VRGDG Concept Recipes: List Concepts` | Lists keys, display names, compatible models, and recipe counts. |
| `VRGDG Concept Recipes: View Concept` | Returns every full recipe for one `concept_key`. |
| `VRGDG Concept Recipes: Save Recipe` | Adds a recipe or updates the record whose `recipe_id` matches the optional input. Writes only `knowledge_base/concepts/local/`. |
| `VRGDG Concept Recipes: Delete Recipe` | Deletes the specified recipe ID and writes a local override. |
| `VRGDG Concept Recipes: Best Match` | Filters one concept by `base_model`, sorts by descending `quality_score`, then returns up to `limit` recipes. |

All node payloads are JSON strings so they can be inspected, saved, or forwarded without a custom opaque datatype. `loras_json` must be an array such as `[ {"name":"Example.safetensors", "weight":0.7} ]`.

## Phase 2: Civitai research intake

The only networked code is `tools/civitai_concept_researcher/researcher.py`. It uses Civitai's `/api/v1/images` endpoint with `withMeta=true`, requests up to one 100-item page by default, then locally requires visible prompt evidence and at least five of seven core recipe fields. It validates a visible `meta.baseModel` or a resolved checkpoint base model when either is present. If Civitai omits both, the candidate may be retained only under the server-side base-model filter and is marked `base_model_verification: server_filter_only` for human review. `safe_only=True` explicitly sends `nsfw=false` to `civitai.com`; `safe_only=False` explicitly sends `nsfw=true` to `civitai.red`, then falls back to `civitai.com` with the same adult filter if Red is unavailable. Never implement adult-allowed mode by omitting the `nsfw` parameter: that can silently return a safe-only result set.

For its small pre-ranked pool, the helper resolves checkpoint and LoRA IDs through `/api/v1/model-versions/<id>`. It spaces requests by at least 0.35 seconds, retries temporary network/429/5xx failures, and honors a `Retry-After` header. It uses only the standard library. Public metadata requires no login; an optional `CIVITAI_API_TOKEN` environment variable is read only at runtime if an owner needs authenticated access. Never put a token in source, JSON, workflow metadata, or documentation examples.

Candidates contain `candidate_id`, durable Civitai image/post URLs, an optional public-CDN `image_preview_url`, all visible recipe data, `metadata_completeness`, and a `candidate_score`. The latter is only a sort priority. Each candidate deliberately starts with `quality_score: 0.0`. The user must select a candidate and set their own local quality score after review/testing.

### Research nodes

All Phase 2 nodes live in **VRGDG → Knowledge → Concept Research**.

| Node | Role |
| --- | --- |
| `VRGDG Concept Research: Search Civitai` | Calls the external helper and outputs review-only candidate JSON. Offers Pony, Anima, Any, an optional custom base-model override, and a Safe-only search switch (on = SFW, off = adult-allowed). |
| `VRGDG Concept Research: View Candidate` | Displays one exact candidate (full prompts, LoRAs, parameters, URLs, completeness) by its full `candidate_id` or one-based result number. A missing selection returns an instructional review result instead of throwing an execution error. |
| `VRGDG Concept Research: Save Approved Candidates` | Explicitly saves one or more comma-separated exact IDs, one-based result numbers, or `all`, through `save_recipe()` into `knowledge_base/concepts/local/`. Re-saving an image updates the stable `civitai_image_<id>` recipe instead of duplicating it. Invalid selections return review guidance in the node instead of throwing. |

The save node reuses the Phase 1 schema: `source` carries the image URL plus post ID, `notes` carries resource provenance, and `loras` remains an array of `{name, weight}`. It does not write to the Character Bible, LoRA Knowledge Base, Script-to-Film, or Music Video paths.

## Phase 3: Script-to-Film generation-time intelligence

Phase 3 does not change the Concept/Pose JSON schema. It reads the same Phase 1 `retrieve_best_recipes()` result and calls the same Phase 2 `research_concept()` / `save_approved_candidates()` functions. It adds no network logic to a ComfyUI node.

### Scene matching and suggestions

`infer_scene_concept(scene)` first uses an explicit `concept_key` (the Film Planner's **Concept / pose** field). If it is blank, it deterministically matches existing local concept keys against the scene label, script beat, physical-state progression, position-continuity notes, and keyframe/LTX prompts. It does not invoke an LLM. `suggest_scene_recipes(scene, base_model, limit)` then delegates ranking and filtering to Phase 1 `retrieve_best_recipes()`.

The result cards deliberately show only what is useful at edit time: quality score, seed, CFG, steps, sampler, LoRAs, and a short positive-prompt preview. The full recipe remains in the local store and can still be viewed with Phase 1 nodes.

The Film project's `script_to_film.keyframe_model` is `pony` or `anima` (default `pony`). It is a Script-to-Film-only selection. The shared Film Planner owns it; Builder and Wizard both open that same modal. The Builder's Film render branch uses it to call the matching existing Violets T2I adapter for a missing keyframe. Do not replace the global Music Video `image_model_mode` with this value.

### Applying a recipe safely

`apply_recipe_to_scene()` appends the full local positive prompt as a fragment to `scene.t2i_prompt` / `scene.keyframe_prompt`. It also stores the selected recipe's negative prompt, LoRAs, seed, CFG, steps, sampler, source, and ID under these Film-scene-only fields:

```text
concept_key
concept_recipe_positive_fragment
concept_recipe_negative_fragment
concept_recipe_loras
concept_recipe_settings
applied_concept_recipe
```

The fields are metadata transfer, not a silent mutation of a saved T2I workflow. The Pony/Anima adapters inject only the positive scene prompt and intentionally preserve each workflow's negative conditioning, sampler, checkpoint, LoRA stack, and save behavior. Never copy a recipe LoRA into `lora_knowledge_refs` automatically: those are a separate technical store and require deliberate local mapping. Never copy recipe text or triggers into `character_bible`.

### Research-more flow

The Film Planner's **Research more for this concept** calls the Phase 2 helper with the inferred/explicit concept and selected Pony/Anima base model. It returns candidates only. The planner displays the same review data (prompt, settings, LoRAs) with checkboxes; `save_researched_scene_recipes()` delegates only checked IDs to Phase 2 `save_approved_candidates()`. Toggling the Film Planner's Safe-only checkbox immediately launches a replacement search in the selected safe/adult-allowed mode and clears the prior candidate checks, preventing a stale safe-only result from being mistaken for an adult-allowed one. After a successful explicit save, the planner invalidates its scene suggestion cache and re-queries the local store. No candidate can be auto-saved or applied.

Canvas nodes live in **VRGDG → Knowledge → Script-to-Film Concept Intelligence**:

| Node | Role |
| --- | --- |
| `VRGDG Film Concepts: Suggest Local Recipes` | Returns compact Phase 1 Best Match suggestions for one scene JSON record. |
| `VRGDG Film Concepts: Apply Recipe to Scene` | Returns a new scene JSON record with an explicitly selected recipe's transferred metadata. |
| `VRGDG Film Concepts: Research More (Review First)` | Delegates a review-only Civitai search to the Phase 2 helper. Feed its result to Phase 2 **Save Approved Candidates** after human review. |

## GUI test-workflow deployment

The repository tracks six GUI-format workflows under `Workflows/KnowledgeBase/`. Deploy identical copies to `ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/` using these exact filenames: `Search and Review.json`, `Approve and Save.json`, `Browse Local Recipes.json`, `Manual Add or Edit Test Recipe.json`, `Delete Manual Test Recipe.json`, and `Script-to-Film Concept Intelligence.json`. Use `workflow_layout.auto_layout()` and `inspect()` before handoff. The canvases are intentionally split by side effect:

1. Search + review has no save node.
2. Approval + save has a non-matching candidate-ID placeholder, so it errors harmlessly until the user explicitly pastes a reviewed ID.
3. Browsing runs List, View, and Best Match only.
4. Manual Add/Edit writes only a clearly named disposable record, `manual_test_pose_01`.
5. Delete removes only that disposable record.
6. Script-to-Film Concept Intelligence is a review/apply/research test canvas; its Research More node is review-only and cannot write to the local library.

The companion frontend script `web/VRGDG_ConceptResearchResults.js` renders
the backend's review-only `ui.text` payload directly inside the three Concept
Research nodes. Preserve this behavior when changing their return data: Search
must show the actual `candidate_count`, a concise candidate directory, and an
**Open image #** action for each candidate. When linked to a View Candidate
node, it must show **Review result #** actions that fill the exact full ID;
when linked to Save Approved, it must show **Prepare save #** actions that fill
the exact full ID without triggering a save. View and Save both accept the
displayed result number (for example `2`) for manual use. View Candidate must
show the selected candidate's full recipe fields; Save Approved must show the
local save result. The normal STRING/INT outputs remain the source of truth for
graph wiring.

Do not combine the save or delete actions into the research/review canvas. That would make a routine test queue capable of mutating a user's persistent local library.

## Reproduction steps

1. Add `VRGDG_ConceptPoseKnowledgeBase` to `_VRGDG_SUBMODULES` in `__init__.py`.
2. Keep all storage helpers inside the new module; do not import the LoRA or Film modules.
3. Create tracked illustrative files under `knowledge_base/concepts/examples/` and an ignored `local/` override directory.
4. Use atomic writes for local JSON. Never overwrite an example file through a node.
5. Expose only list, view, save, delete, and best-match nodes in Phase 1.
6. Test CRUD and base-model filtering in a temporary root, then restart ComfyUI and verify node registration.

## Validation

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\custom_nodes\comfyui-vrgamedevgirl\tests\test_concept_pose_knowledge_base.py -v
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe -m py_compile .\custom_nodes\comfyui-vrgamedevgirl\VRGDG_ConceptPoseKnowledgeBase.py
```

After restarting ComfyUI, search the node menu for `VRGDG Concept Recipes`. Run **List Concepts**, then **View Concept** for `arched_back`, and verify it returns two full sample recipes. Do not queue an image/video generation as part of this Phase 1 store test.

## Reproducing Phase 2

1. Keep the public API/network code in `tools/civitai_concept_researcher/`; expose only `research_concept()` to the node file.
2. Add `VRGDG_ConceptResearchNodes` to `_VRGDG_SUBMODULES` in `__init__.py` after the Phase 1 store module so `save_recipe()` is importable.
3. Search with `withMeta=true`, default safe-only mode, a 100-item maximum page, and a local base-model check. Do not claim that a Civitai filter alone is exact.
4. Require a prompt plus at least five core visible recipe fields before making a candidate reviewable. Resolve only the shortlisted checkpoint/LoRA version IDs and retain URLs/IDs in provenance notes.
5. Keep `quality_score` at zero in all research output. The save node may only run after `candidate_ids` are explicitly supplied by the user.
6. Save through the existing `save_recipe()` helper, never by writing a separate database format. Confirm the Phase 1 `View Concept` and `Best Match` nodes read the approved recipe.
7. Run the mocked unit tests, then a live public API smoke with a safe Pony or Anima concept. Restart/reload ComfyUI and verify the three node types in `/object_info` before declaring the integration complete.

### Validation

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\custom_nodes\comfyui-vrgamedevgirl\tests\test_civitai_concept_researcher.py -v
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\custom_nodes\comfyui-vrgamedevgirl\tests\test_concept_pose_knowledge_base.py -v
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\custom_nodes\comfyui-vrgamedevgirl\tools\civitai_concept_researcher_cli.py --concept "arched back" --base-model Pony --limit 1
```

## Reproducing Phase 3

1. Add `VRGDG_ScriptToFilmConceptIntelligence` to `_VRGDG_SUBMODULES` immediately after `VRGDG_ScriptToFilmNodes`. The Film routes may import the helper during startup, so preserve its direct-import fallback.
2. Keep deterministic concept inference, compact-card formatting, and apply logic in `VRGDG_ScriptToFilmConceptIntelligence.py`. It may import only Phase 1/2 public helpers; it must not import Music Video, Character Bible, or LoRA Knowledge Base modules.
3. Add Film-only routes in `VRGDG_ScriptToFilmNodes.py`: `suggest`, `apply`, `research`, and `save_research` under `/vrgdg/script_to_film/concept_intelligence/`. All Civitai saves must delegate to `save_approved_candidates()`.
4. Preserve the six applied-recipe fields in `_normalize_scene()` so a reflow/save/reopen does not erase an approved recipe transfer.
5. Extend only `web/VRGDG_ScriptToFilmUI.js` for Film Planner controls. The Builder and Wizard must both use that same modal. If the Film render branch accepts a new keyframe-model field, keep it inside `isScriptToFilmMode()` and never change Music Video image-mode behavior.
6. Deploy `Workflows/KnowledgeBase/Script-to-Film Concept Intelligence.json` to `ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/` and use `workflow_layout.py` inspection before handoff.

### Validation

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\custom_nodes\comfyui-vrgamedevgirl\tests\test_script_to_film_concept_intelligence.py -v
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe -m py_compile .\custom_nodes\comfyui-vrgamedevgirl\VRGDG_ScriptToFilmConceptIntelligence.py .\custom_nodes\comfyui-vrgamedevgirl\VRGDG_ScriptToFilmNodes.py
```

After restarting ComfyUI, confirm the three `VRGDG Film Concepts` node types appear in `/object_info`. Run the installed test workflow's suggestion and apply nodes, then verify the result scene JSON has the six applied fields while its Character Bible is unchanged. In the Film Planner, select Pony and Anima in turn and verify the local cards are filtered to the selected family. Use **Research more** only with a non-sensitive test concept, explicitly check a returned candidate, save it, and confirm the refreshed Film-scene suggestions include it. Finally switch to Music Video and verify no Concept/Pose controls or render behavior appear there.
