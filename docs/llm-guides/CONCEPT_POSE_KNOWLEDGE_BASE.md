# Concept / Pose Knowledge Base — Phase 1

This guide covers the local, manually curated recipe library introduced in Phase 1. It is a standalone store for reproducible pose, body-mechanics, camera-angle, and concept recipes. It is not a Character Bible, LoRA metadata store, prompt generator, Civitai research tool, or Music Video feature.

## Scope boundary

- **Character Bible** stays identity and visual-continuity only.
- **LoRA Knowledge Base** stays LoRA-specific technical metadata only.
- **Concept / Pose Knowledge Base** stores complete model-generation recipes for a reusable concept.
- **Music Video** is untouched. Do not import this module into `VRGDG_MusicVideoBuilderNodes.py`, `VRGDG_WorkflowRunnerNodes.py`, or either Music Video UI in Phase 1.
- No network calls, Civitai browser automation, prompt injection, ranking feedback, or scene matching belongs in this phase.

## Files and layout

| Path | Role |
| --- | --- |
| `VRGDG_ConceptPoseKnowledgeBase.py` | JSON store helpers plus five thin ComfyUI nodes. |
| `knowledge_base/concepts/examples/arched_back.json` | Tracked example with Pony and Anima full recipes. |
| `knowledge_base/concepts/examples/low_crouch.json` | Second tracked example with Pony and Anima full recipes. |
| `knowledge_base/concepts/local/` | User-created local concept overrides. JSON files here are ignored by Git. |
| `tests/test_concept_pose_knowledge_base.py` | CRUD, filtering, sample-data, registration, and isolation tests. |

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

## Phase 2 handoff

A future research helper may write only the same normalized local JSON schema. It should create candidate recipes with a clear external `source`, leave `quality_score` at an appropriate unreviewed value, and require human review before promoting the data. Do not implement that behavior until Phase 2 is explicitly requested.
