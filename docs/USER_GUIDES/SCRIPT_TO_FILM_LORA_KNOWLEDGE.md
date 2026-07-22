# Script-to-Film: LoRA Knowledge Base

Use this feature when a character or style LoRA has special trigger words, preferred weights, or prompt habits that you do not want mixed into the character's identity description.

1. Open **Film Planner** from either the Builder or Wizard.
2. In **LoRA Knowledge Base**, click **Import / Refresh LoRA Metadata**. This scans LoRAs already installed in ComfyUI; it does not download anything.
3. Select one or more entries in **Active LoRA knowledge for this Film project**. Choose records that match the model family: Pony/SDXL records guide Pony keyframes, and LTX records guide LTX shots.
4. Select an entry under **Edit LoRA metadata**. Add its Civitai model ID if you know it, then click **Research selected Civitai ID**. Otherwise enter its base model, trigger map, recommended weight, examples, and notes yourself, then click **Save LoRA Metadata**.
5. The trigger map is structured. Keep the always-needed character token in `base`, then add context-specific keys such as `action_kneeling`, `outfit_casual`, `action_running`, or `style_anime`.
6. Optionally paste the path to a Character Style Profile JSON file in **Character Style Profile JSON**. Its visual style is used alongside the LoRA knowledge, but it does not alter the Character Bible.
7. Create or edit Film scenes normally. Leave **Scene LoRA metadata refs** blank to inherit the project selection, or list specific LoRA filenames to narrow that one shot.
8. Build the Film. Before Pony/LTX starts, the system reads the scene's physical state and position continuity, selects matching trigger-map keys, and applies only those words to that shot's prompt.

The Character Bible remains clean: it stores only who the person is and their ongoing visual state. Trigger words, weights, Civitai IDs, and LoRA notes stay in the Knowledge Base.

Example trigger map:

```json
{
  "base": "charactertrigger",
  "outfit_casual": "charactertrigger casual jacket",
  "action_kneeling": "charactertrigger kneeling pose",
  "style_anime": "charactertrigger anime linework"
}
```

After a scene resolves, its card can show the selected trigger-map keys for Pony and LTX. If the key is wrong, change the scene's physical/position notes or edit the map—do not add the trigger word to Character Bible.

The feature is Script-to-Film only. Music Video projects and their existing LoRA/workflow settings are unchanged.
