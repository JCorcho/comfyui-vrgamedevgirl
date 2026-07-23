# Concept / Pose Recipe Library

This is a small local library for saving generation setups that reliably produce a pose, body mechanic, camera angle, or other reusable concept. It does not alter your Character Bible, LoRA metadata, or Music Video projects. In **Script-to-Film** only, the Film Planner can now suggest and apply a recipe to the scene you are editing.

## Use local recipes while editing a Film scene

1. Open the Builder or Wizard, switch to **Script-to-Film**, then choose **Film Planner**. Both buttons open the same planner and use the same saved Film plan.
2. Choose the Film **Keyframe base model**: **Pony** or **Anima**. Suggestions are filtered to that model family, and the same selection chooses the corresponding saved Violets T2I workflow when the Film renders a missing keyframe.
3. Open a Film scene. The planner automatically looks for a local concept name in the scene's label, action/continuity text, and prompts. For a deterministic match, fill in **Concept / pose** yourself, for example `low_crouch` or `arched_back`.
4. Review the compact local recipe cards. They show the quality score, seed, CFG, steps, sampler, LoRAs, and a short positive-prompt preview. Choose **Apply recipe to this scene** only after you have reviewed one.
5. Applying copies the positive fragment into the scene's keyframe prompt and records the recipe's negative fragment, LoRAs, seed, CFG, steps, sampler, source, and recipe ID in that Film scene. It never writes trigger words to the Character Bible and never silently changes the workflow-managed negative conditioning, sampler, or LoRA stack inside `VioletsT2I(Pony)` / `VioletsT2I(Anima)`.
6. If the library has no suitable result, choose **Research more for this concept**. The returned Civitai candidates display embedded previews in the Film Planner, alongside their prompts and settings. Check only the candidates you approve, then choose **Approve selected and save to local recipes**. The planner immediately refreshes the local suggestions after the save. Safe-only research is on by default; clearing it immediately re-runs the search as adult-allowed and clears any prior candidate checks.

The **Concept / pose** field and the applied-recipe metadata are stored only in the Script-to-Film scene plan. They have no effect in Music Video mode.

## Ready-to-open test workflows

Six working canvases are already installed in ComfyUI's **Workflows** sidebar,
inside the **VRGDG Concept Recipe Tests** subfolder. Refresh that sidebar and
open these files in order:

1. **Search and Review** — review-only research; it cannot save anything. Turn **Safe-only search** on for SFW results or off for adult-allowed results.
2. **Approve and Save** — click **Prepare save #** for the candidate you reviewed, choose your local score, then queue it. The button only fills the selection; it never saves automatically.
3. **Browse Local Recipes** — lists, views, and runs Best Match without writing.
4. **Manual Add or Edit Test Recipe** — creates a disposable `manual_test_pose_01`; queue it again after changing a field to test updates.
5. **Delete Manual Test Recipe** — removes only that disposable manual test record.
6. **Script-to-Film Concept Intelligence** — a review-only canvas for the Script-to-Film suggestion, apply, and research nodes; its research node does not save candidates.

The tracked source copies live in `custom_nodes/comfyui-vrgamedevgirl/Workflows/KnowledgeBase/`; the installed copies live in `ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/`. None of these canvases loads a generation model or touches the Music Video pipeline.
After workflow 05 runs, the local-only `manual_test_pose` concept is removed entirely rather than being left behind as an empty record.

After a Search and Review run, the **Search** node itself shows a readable
`Search summary`, `Candidate directory`, and one **Open image #** button for
each returned result. Click **Open image #** to view its Civitai image without
copying a link. Click **Review result #** to fill the connected Review node for
you, then queue the workflow. You can also enter a result number such as `2` in
the Review node's **Candidate ID** field, or use **Candidate number**; full
`civitai_image_…` IDs still work. `max_candidates` is an upper limit, not a
promise: the summary reports the actual count returned.

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
2. In the Search node, click **Open image #** to inspect a photo and **Review result #** to select it in the connected **VRGDG Concept Research: View Candidate** node. You can instead enter the displayed result number (such as `2`) or a full `civitai_image_123456` ID manually. It shows the original Civitai image/post links, prompts, LoRAs, seed, sampler, CFG, steps, model, and metadata completeness.
3. After you have reviewed it, connect the search JSON to **VRGDG Concept Research: Save Approved Candidates**. Click its connected Search node's **Prepare save #** action (or enter a selected result number such as `3`, a full ID, comma-separated selections, or `all`), choose a local `quality_score`, add your test notes, and run it.
4. Use **VRGDG Concept Recipes: View Concept** or **Best Match** to confirm the approved recipe is now in your local library.

The search defaults to safe-only public Civitai results. Turn **Safe-only
search** off when you intentionally want adult-allowed results. That mode uses
the Civitai.red API first; if it is temporarily unavailable, it retries through
Civitai.com with an explicit adult filter rather than silently changing back to
safe-only. The search summary tells you which endpoint was used. Civitai's
labels are not a guarantee about every prompt, so review every candidate before
using it. The local library stores only the candidates you explicitly save.
Saving the same Civitai image again updates that recipe instead of creating a
duplicate.

If you prefer the terminal, run:

```powershell
& C:\AI\ComfyUI\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe .\tools\civitai_concept_researcher_cli.py --concept "arched back" --base-model Pony --limit 5
```

No login is needed for public metadata. If Civitai later requires one for your account, set `CIVITAI_API_TOKEN` in the environment that launches ComfyUI—do not paste it into a node, workflow, or project file.
