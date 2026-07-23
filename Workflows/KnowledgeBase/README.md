# Concept / Pose Knowledge Base Test Workflows

Open these five GUI-format workflows from the **VRGDG Concept Recipe Tests**
subfolder in ComfyUI's Workflows sidebar. Deploy the files to
`ComfyUI/user/default/workflows/VRGDG Concept Recipe Tests/`:

1. **Search and Review** — research only; writes nothing.
2. **Approve and Save** — paste a reviewed Civitai `candidate_id` and set
   your own score before queueing. Its placeholder intentionally prevents an
   accidental save.
3. **Browse Local Recipes** — list, view, and Best Match with no writes.
4. **Manual Add or Edit Test Recipe** — creates/updates only
   `manual_test_pose_01`, a disposable recipe.
5. **Delete Manual Test Recipe** — deletes only that disposable test recipe.

They contain no generation nodes, queues, model loads, or Music Video routing.
