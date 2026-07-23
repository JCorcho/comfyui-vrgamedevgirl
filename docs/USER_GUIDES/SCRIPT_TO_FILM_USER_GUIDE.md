# Script-to-Film user guide

Script-to-Film turns a written script into a sequence of Pony keyframes and LTX 2.3 video clips with **native generated audio**. It is a separate project mode: it does not need a song, lyrics, SRT file, Whisper pass, or Music Video audio settings.

## Before you start

1. Open the Music Video Builder and choose or create a **Project Folder**. This is where the saved plan and final Film video will be placed.
2. Refresh the browser page with `Ctrl+Shift+R` if the **Project Mode** control or Film controls are not visible.
3. Choose the Prompt Creator model you want to use in the Builder's normal Prompt Creator / LLM settings. Script-to-Film uses that same selected model; it does not silently substitute the repository's original Gemma model.

The Film renderer automatically uses:

- **Pony / VioletsT2I** for generated keyframes;
- **Film/T2AV + Character Ref** using the Violets LTX 2.3 FP8 profile;
- DMD LoRA at `1.0` and JoyAI LoRA at `0.5`;
- the Audio Text Encoder, sampler, and first-/second-pass sigma values selected in the shared advanced video controls.

Those LoRA strengths are intentionally locked for the Film profile.

## Start a Film project

Choose either entry point. They open the same Film Planner and save the same project data.

### From the Builder

1. In the Builder toolbar, set **Project Mode** to **Script-to-Film**.
2. Click **Film Planner**.

### From the Wizard

1. Open **Wizard**.
2. Open **Settings**.
3. Click **Script-to-Film**, then **Open Film Planner**.

In Script-to-Film mode, the Wizard's former Audio and Lyrics steps change into **Script** and **Film Scenes**. They are Film-planning steps, not requests to upload a song or lyrics file.

## Create a scene plan from a script

1. In **Film Planner**, choose the desired **Frame rate** and **Default shot duration**.
2. Paste your script into **Script**.
3. Click **Create structured film scenes**.
4. Review the generated scenes, then click **Save Film plan**.

The plan is saved here:

```text
<Project Folder>\script_to_film\film_scene_plan.json
```

The Prompt Creator writes one complete record for each shot. It creates a Pony keyframe prompt, a natural-language LTX visual-and-audio prompt, and the continuity information used across the sequence. To change the Prompt Creator's Film-writing behavior later, edit only:

```text
prompts\ScriptToFilm_PromptCreator_System.txt
```

The Film planner automatically gives the selected local model enough working context for a multi-shot JSON document. This is Film-only and does not change the normal Music Video prompt settings. A normal successful result shows multiple scene cards without a recovery warning.

Keep that file's GROK start and end markers intact.

## Review and adjust each Film scene

Open a scene in the **Film scenes** section to edit it. The most important choices are:

| Control | When to use it |
| --- | --- |
| **Target duration** | The intended length of the shot. This is the timeline authority before rendering. |
| **I2V/T2AV + Character Ref** | Normal choice for character, continuity, or art-directed shots. It uses the supplied reference image; if no image is supplied, the Builder makes a Pony keyframe from the scene's Pony prompt first. |
| **Pure T2AV establishing shot** | Use for an unconditioned environment or establishing shot when character/image conditioning is not wanted. |
| **Character / Pony keyframe image** | Supply a pre-made reference/keyframe when you want precise visual control. |
| **Unified natural-language LTX visual + audio prompt** | The single prompt LTX uses for visible action, dialogue, ambience, and sound. Keep this natural language rather than tag soup. |
| **Pony keyframe prompt** | The image-generation prompt used when a reference-conditioned shot needs a new keyframe. |
| **Transition cut** | Choose **Hard cut** to prevent ambience overlap; leave the normal setting to allow overlap when transition ambience is requested. |
| **Ambience overlap** | The amount of preceding atmosphere/action tail that can carry across a normal cut. |

The remaining continuity fields are deliberately first-class controls, not hidden metadata:

- **character bible** — face, body, visual identifiers, and clothing state;
- **physical state progression** — what has changed physically since the prior shot;
- **position continuity notes** — where subjects and objects should remain;
- **action intensity curve** — action level at the start, middle, end, and peak;
- **camera language** — framing, movement, and lens intent;
- **sound design prompt** — dialogue, action, environment, and atmosphere;
- **optional music bed path** and **ducking level** — optional external score below LTX's native sound;
- **transition ambience notes** — sound that should survive the cut.

`character bible` and `action intensity curve` are structured JSON fields. If you edit either manually, keep it valid JSON. If the planner says the value is invalid, correct the JSON before continuing.

## Understand duration and timeline behavior

LTX accepts only certain frame counts. The Planner automatically snaps every planned scene so this rule is true:

```text
(frames - 1) % 8 == 0
```

So a requested duration can change slightly when converted to frames. That is expected.

After each clip renders, the Builder measures its real duration, replaces the planned duration with the real value, and automatically shifts the start time of every following scene. Use **Reflow durations** after manual duration changes before you build.

## Build the Film

1. Confirm each scene has the desired render mode and prompt.
2. Click **Build T2I → I2V Film** in the Planner, or use the Script / Film Scenes action in the Wizard.
3. Let the build finish. It performs, in order:
   1. Pony T2I only when a reference-conditioned scene needs a missing keyframe;
   2. LTX 2.3 FP8 video plus native audio for each scene;
   3. actual-duration measurement and timeline reflow after each scene;
   4. Film-only stitching using the embedded audio in the rendered clips.

The final completion dialog shows the exact output path. Scene clips are kept in a `script_to_film_clips` folder under the selected project folder, and the final stitch is written to that project folder. Generated clips keep their LTX audio; the Film path does not remux a source song.

## Working with character continuity

For the current build, **Film/T2AV + Character Ref** locks the shot through LTX's direct image-reference conditioning. Give recurring characters a carefully-made Pony keyframe/reference image and keep the character bible, clothing state, physical state, and position notes consistent from one scene to the next.

The profile name leaves room for IP-Adapter/InstantID-style locking in a future environment, but those nodes are not installed in this ComfyUI setup today. Do not expect a separate IP-Adapter control in the current UI.

## Quick troubleshooting

| Symptom | What to do |
| --- | --- |
| I only see Music Video controls | Hard-refresh with `Ctrl+Shift+R`, then choose **Project Mode → Script-to-Film**. |
| The Wizard asks for a song or lyrics | Open **Settings**, switch to **Script-to-Film**, then reopen the Wizard step. |
| Prompt Creator uses the wrong model | Set the wanted model in the Builder's normal Prompt Creator / LLM settings before clicking **Create structured film scenes**. |
| The planner says it created one editable recovery scene | The selected model did not return a usable scene array. Do not build from that placeholder; retry after shortening the script or use a model with more usable context. If the warning says complete scene records were preserved, review those records—the model ended before finishing the rest of the plan. |
| A scene should not use a keyframe | Change its **Render mode** to **Pure T2AV establishing shot**. |
| The duration changed after planning | This is normal LTX frame snapping. Use **Reflow durations** and inspect the adjusted shot length. |
| A transition should be abrupt | Set **Transition cut** to **Hard cut**. |
| I need to alter the writing style of all future Film prompts | Edit `prompts\ScriptToFilm_PromptCreator_System.txt`; do not modify the Music Video lyric prompt instructions. |
| I need to change LTX sampling or its audio text encoder | Use the shared advanced video settings before the build; Script-to-Film inherits those controls. |

## Safe iteration workflow

1. Save the Film plan.
2. Make a short, low-duration one- or two-shot test.
3. Review the result and adjust prompts, continuity notes, or reference images.
4. Save the plan again.
5. Build the full sequence only after the short test behaves as intended.

For the implementation-level reference, see `docs/llm-guides/SCRIPT_TO_FILM_IMPLEMENTATION.md`.
