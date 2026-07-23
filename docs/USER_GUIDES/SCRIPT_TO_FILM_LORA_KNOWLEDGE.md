# Script-to-Film: LoRA Knowledge Base

Use this feature when a character or style LoRA has special trigger words, preferred weights, or prompt habits that you do not want mixed into the character's identity description.

1. Open **Film Planner** from either the Builder or Wizard.
2. In **LoRA Knowledge Base**, click **Import / Refresh LoRA Metadata**. This scans LoRAs already installed in ComfyUI; it does not download anything.
3. Select one or more entries in **Active LoRA knowledge for this Film project**. Choose records that match the current keyframe family: Pony/SDXL records guide Pony keyframes, while Anima records guide Anima keyframes. LTX records guide only LTX shots.
4. Select an entry under **Edit LoRA metadata**. Its Civitai model ID is filled automatically where Civitai can verify the installed file (embedded metadata, exact file hash, then a high-confidence filename match). Use **Auto-detect / Refresh Civitai Metadata** to retry or refresh it—there is no need to memorize model IDs. You may still override an ID only when you have a specific reason.
5. The **Civitai trigger words (auto-imported)** field shows every verified word from Civitai’s Trigger Words section. For an auto-imported record they are also placed together in `trigger_map.base`, so all required identity tokens apply to every shot. Context-specific keys such as `action_kneeling`, `outfit_casual`, `action_running`, or `style_anime` remain separate.
6. Optionally paste the path to a Character Style Profile JSON file in **Character Style Profile JSON**. Its visual style is used alongside the LoRA knowledge, but it does not alter the Character Bible.
7. Create or edit Film scenes normally. Leave **Scene LoRA metadata refs** blank to inherit the project selection, or list specific LoRA filenames to narrow that one shot. This field is a LoRA selection, not a prompt field: use `Darth TalonDG_Anima_V1.safetensors`, not `dtalongdg`. For convenience, a uniquely verified Civitai/base trigger such as `dtalongdg` is recognized and converted to its installed metadata filename; ambiguous words are never guessed.
8. Build the Film. Before Pony/Anima/LTX starts, the system reads the scene's physical state and position continuity, selects matching trigger-map keys, and applies only those words to that shot's prompt. The Knowledge Base adds prompt tokens; the actual character LoRA must remain enabled in the matching `VioletsT2I(Pony)` or `VioletsT2I(Anima)` workflow, where its model loading and weight are intentionally controlled.

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
