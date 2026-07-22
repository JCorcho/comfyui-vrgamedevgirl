# Scene-video handoff validation

## Why this guard exists

The ComfyUI video writer can leave an MP4 open briefly while it writes the
trailer (`moov` atom). A previous run can also leave a same-named file in the
permanent `rendered_scene_videos` folder. If the runner chooses either file
before the new scratch render is complete, thumbnailing, duration measurement,
or stitching fails with an FFmpeg error even though the new render itself
succeeded.

## Runtime flow

1. The workflow writes the scene into the per-run scratch folder.
2. `find_scene_video_output` considers candidate files, but keeps only files
   that exist, are non-empty, satisfy the run-time/scene filters, and pass an
   FFprobe video-stream probe. Invalid or truncated MP4s are ignored.
3. `collect_scene_video` waits for a stable source, probes it again, copies it
   with the existing retry/atomic-replace logic, waits for the destination to
   settle, and probes the destination before creating a thumbnail.
4. Only the validated destination is handed to timeline measurement and native
   audio stitching.

The probe intentionally requires a readable video stream rather than requiring
an audio stream. Music-video and video-only workflows remain compatible; the
Script-to-Film path separately requests embedded native audio and validates it
during the final FFprobe smoke check.

## Reproduce the check

Use the local routes with a project folder and scene number:

```text
POST /vrgdg/workflow_runner/find_scene_video_output
{
  "project_folder": "<project>",
  "video_mode": "script_to_film",
  "scene_number": 1,
  "min_mtime": <render-start-unix-time>
}
```

Pass the returned `video_path` to:

```text
POST /vrgdg/workflow_runner/collect_scene_video
{
  "project_folder": "<project>",
  "video_mode": "script_to_film",
  "scene_number": 1,
  "source_path": "<returned-video-path>"
}
```

Then probe the collected MP4 with the configured `ffprobe.exe` (the runner uses
the FFmpeg installation on `PATH` when its sibling binary is not bundled) and verify that it
contains a readable video stream before calling Script-to-Film duration reflow
or stitching. A valid handoff must never produce `moov atom not found`.

## Verification performed

The live smoke path rendered a real Pony keyframe, queued a real LTX 2.3 FP8
native-audio clip, collected it, measured and reflowed its duration, and
stitched the final MP4. The scratch clip, collected clip, and final clip all
passed FFprobe; the final clip contained H.264 video plus AAC audio.
