# Concept / Pose Recipe Library

This is a small local library for saving generation setups that reliably produce a pose, body mechanic, camera angle, or other reusable concept. It does not alter your Character Bible, LoRA metadata, Music Video projects, or renders by itself.

## Ready-to-open test workflows

Five working canvases are already installed in ComfyUI's **Workflows** sidebar,
inside the **VRGDG Concept Recipe Tests** subfolder. Refresh that sidebar and
open these files in order:

1. **Search and Review** — safe research only; it cannot save anything.
2. **Approve and Save** — paste the candidate ID you reviewed in the first workflow, choose your local score, then queue it.
3. **Browse Local Recipes** — lists, views, and runs Best Match without writing.
4. **Manual Add or Edit Test Recipe** — creates a disposable `manual_test_pose_01`; queue it again after changing a field to test updates.
5. **Delete Manual Test Recipe** — removes only that disposable manual test record.

The tracked source copies live in `custom_nodes/comfyui-vrgamedevgirl/Workflows/KnowledgeBase/`; the installed copies live in `ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/`. None of these canvases loads a generation model or touches the Music Video pipeline.
After workflow 05 runs, the local-only `manual_test_pose` concept is removed entirely rather than being left behind as an empty record.

1. In ComfyUI, search for **VRGDG Concept Recipes: List Concepts**. Run it to see the available concepts.
2. Connect **View Concept** and enter a key such as `arched_back` to inspect its recipes.
3. To save your own, use **Save Recipe**. Enter the concept key, model family, full positive/negative prompts, LoRAs as JSON, seed, sampler settings, notes, and a `quality_score` from 0–10.
4. Leave `recipe_id` blank to add a new recipe. Reuse the returned ID in a later Save node to edit that exact recipe.
5. Use **Best Match** with a concept key and base model such as `Pony` or `Anima`. It returns recipes from highest to lowest quality score.
6. Use **Delete Recipe** only with the exact recipe ID you intend to remove.

Your recipes are saved as readable JSON under:

```text
custom_nodes/comfyui-vrgamedevgirl/knowledge_base/concepts/local/
```

The included `arched_back` and `low_crouch` files are examples. Editing either through a node creates a personal local override, so the original sample remains intact. Phase 1 does not research Civitai or automatically apply a recipe to a scene; those are planned for later phases.

Each node also displays its returned JSON directly in the ComfyUI node result, so it can be inspected without adding a separate text-preview node.

## Research a Civitai recipe, then approve it

1. Search for **VRGDG Concept Research: Search Civitai**. Enter a concept such as `arched_back`, select **Pony** or **Anima**, and run it. It returns a small list of review candidates; it does not save or apply anything automatically.
2. Copy the `candidate_id` you want to inspect, such as `civitai_image_123456`, into **VRGDG Concept Research: View Candidate**. It shows the original Civitai image/post links, prompts, LoRAs, seed, sampler, CFG, steps, model, and metadata completeness.
3. After you have reviewed it, connect the search JSON to **VRGDG Concept Research: Save Approved Candidates**. Enter the selected ID (or comma-separated IDs), choose a local `quality_score`, add your test notes, and run it.
4. Use **VRGDG Concept Recipes: View Concept** or **Best Match** to confirm the approved recipe is now in your local library.

The search defaults to safe-only public Civitai results. It relies on Civitai's labels, so still review every candidate before using it. The local library stores only the candidates you explicitly save. Saving the same Civitai image again updates that recipe instead of creating a duplicate.

If you prefer the terminal, run:

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\tools\civitai_concept_researcher_cli.py --concept "arched back" --base-model Pony --limit 5
```

No login is needed for public metadata. If Civitai later requires one for your account, set `CIVITAI_API_TOKEN` in the environment that launches ComfyUI—do not paste it into a node, workflow, or project file.
