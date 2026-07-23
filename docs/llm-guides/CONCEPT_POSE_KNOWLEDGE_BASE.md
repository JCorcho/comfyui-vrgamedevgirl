# Concept / Pose Knowledge Base — Phase 1

This guide covers the local, manually curated recipe library introduced in Phase 1 and its human-reviewed Civitai research intake added in Phase 2. It is a standalone store for reproducible pose, body-mechanics, camera-angle, and concept recipes. It is not a Character Bible, LoRA metadata store, prompt generator, or Music Video feature.

## Scope boundary

- **Character Bible** stays identity and visual-continuity only.
- **LoRA Knowledge Base** stays LoRA-specific technical metadata only.
- **Concept / Pose Knowledge Base** stores complete model-generation recipes for a reusable concept.
- **Music Video** is untouched. Do not import this module into `VRGDG_MusicVideoBuilderNodes.py`, `VRGDG_WorkflowRunnerNodes.py`, or either Music Video UI in Phase 1.
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
| `Workflows/KnowledgeBase/` | Five GUI-format, source-controlled test canvases deployed to the user's `Workflows/VRGDG Concept Recipe Tests/` subfolder. |

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

The only networked code is `tools/civitai_concept_researcher/researcher.py`. It uses Civitai's public `/api/v1/images` endpoint with `withMeta=true`, requests up to one 100-item page by default, then locally requires visible prompt evidence, the requested visible `meta.baseModel`, and at least five of seven core recipe fields. Server-side semantic/base-model filtering is treated as a hint, not as a trusted guarantee.

For its small pre-ranked pool, the helper resolves checkpoint and LoRA IDs through `/api/v1/model-versions/<id>`. It spaces requests by at least 0.35 seconds, retries temporary network/429/5xx failures, and honors a `Retry-After` header. It uses only the standard library. Public metadata requires no login; an optional `CIVITAI_API_TOKEN` environment variable is read only at runtime if an owner needs authenticated access. Never put a token in source, JSON, workflow metadata, or documentation examples.

Candidates contain `candidate_id`, Civitai image/post URLs, all visible recipe data, `metadata_completeness`, and a `candidate_score`. The latter is only a sort priority. Each candidate deliberately starts with `quality_score: 0.0`. The user must select a candidate ID and set their own local quality score after review/testing.

### Research nodes

All Phase 2 nodes live in **VRGDG → Knowledge → Concept Research**.

| Node | Role |
| --- | --- |
| `VRGDG Concept Research: Search Civitai` | Calls the external helper and outputs review-only candidate JSON. Offers Pony, Anima, Any, or an optional custom base-model override. |
| `VRGDG Concept Research: View Candidate` | Displays one exact candidate (full prompts, LoRAs, parameters, URLs, completeness) by its `candidate_id`. |
| `VRGDG Concept Research: Save Approved Candidates` | Explicitly saves one or more comma-separated IDs, or `all`, through `save_recipe()` into `knowledge_base/concepts/local/`. Re-saving an image updates the stable `civitai_image_<id>` recipe instead of duplicating it. |

The save node reuses the Phase 1 schema: `source` carries the image URL plus post ID, `notes` carries resource provenance, and `loras` remains an array of `{name, weight}`. It does not write to the Character Bible, LoRA Knowledge Base, Script-to-Film, or Music Video paths.

## GUI test-workflow deployment

The repository tracks five GUI-format workflows under `Workflows/KnowledgeBase/`. Deploy identical copies to `ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/` using these exact filenames: `Search and Review.json`, `Approve and Save.json`, `Browse Local Recipes.json`, `Manual Add or Edit Test Recipe.json`, and `Delete Manual Test Recipe.json`. Use `workflow_layout.auto_layout()` and `inspect()` before handoff. The canvases are intentionally split by side effect:

1. Search + review has no save node.
2. Approval + save has a non-matching candidate-ID placeholder, so it errors harmlessly until the user explicitly pastes a reviewed ID.
3. Browsing runs List, View, and Best Match only.
4. Manual Add/Edit writes only a clearly named disposable record, `manual_test_pose_01`.
5. Delete removes only that disposable record.

The companion frontend script `web/VRGDG_ConceptResearchResults.js` renders
the backend's review-only `ui.text` payload directly inside the three Concept
Research nodes. Preserve this behavior when changing their return data: Search
must show the actual `candidate_count` plus a concise candidate directory;
View Candidate must show the selected candidate's full recipe fields; Save
Approved must show the local save result. The normal STRING/INT outputs remain
the source of truth for graph wiring.

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
