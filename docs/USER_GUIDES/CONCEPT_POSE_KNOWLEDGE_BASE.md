# Concept / Pose Recipe Library

This is a small local library for saving generation setups that reliably produce a pose, body mechanic, camera angle, or other reusable concept. It does not alter your Character Bible, LoRA metadata, Music Video projects, or renders by itself.

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
