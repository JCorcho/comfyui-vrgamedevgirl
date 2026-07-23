# Concept / Pose Knowledge Base Test Workflows

Open these six GUI-format workflows from the **VRGDG Concept Recipe Tests**
subfolder in ComfyUI's Workflows sidebar. Deploy the files to
`ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/`:

1. **Search and Review** — research only; writes nothing.
2. **Approve and Save** — after searching, click **Prepare save #** on the
   result you reviewed, set your own score, then queue the explicit save. Its
   placeholder intentionally prevents an accidental save.
3. **Browse Local Recipes** — list, view, and Best Match with no writes.
4. **Manual Add or Edit Test Recipe** — creates/updates only
   `manual_test_pose_01`, a disposable recipe.
5. **Delete Manual Test Recipe** — deletes only that disposable test recipe.
6. **Script-to-Film Concept Intelligence** — tests the Film Planner's local
   suggestion, explicit apply, and review-only research nodes.

They contain no generation nodes, queues, model loads, or Music Video routing.

In **Search and Review**, run the Search node first. It adds an **Open image #**
button for every candidate, plus **Review result #** buttons that fill the
connected Review node. You may also enter the displayed result number (for
example `2`) in Candidate ID; it is accepted as a one-based selection number.

In **Approve and Save**, the same Search node displays **Prepare save #**
buttons because its output is connected to a Save node. That button fills the
exact candidate ID but does **not** save anything; set the concept information
and quality score, then queue the canvas to approve the recipe. Result numbers
such as `3` are accepted in the Save node too.
