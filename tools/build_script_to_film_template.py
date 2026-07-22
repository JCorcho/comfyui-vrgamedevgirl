"""Build the isolated Script-to-Film native-audio API template.

This is a deterministic, source-controlled transformation of the maintained
two-pass I2V graph.  It deliberately leaves the Music Video source graph alone.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "Workflows" / "UsedForUIDoNotTouch"
SOURCE = WORKFLOWS / "Singlei2vForUI_API.json"
TARGET = WORKFLOWS / "ScriptToFilm_T2AV_CharacterRef_API.json"


def _ref_nodes(value):
    """Yield prompt-node ids referenced by Comfy API input values."""
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
            yield value[0]
        else:
            for item in value:
                yield from _ref_nodes(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _ref_nodes(item)


def _reachable_graph(graph, output_id):
    required = set()
    pending = [output_id]
    while pending:
        node_id = pending.pop()
        if node_id in required:
            continue
        node = graph.get(node_id)
        if node is None:
            raise RuntimeError(f"Required node {node_id!r} is missing from the source workflow.")
        required.add(node_id)
        pending.extend(_ref_nodes(node.get("inputs", {})))
    return {node_id: graph[node_id] for node_id in sorted(required)}


def _node(class_type, title, inputs):
    return {"class_type": class_type, "inputs": inputs, "_meta": {"title": title}}


def build_template():
    graph = json.loads(SOURCE.read_text(encoding="utf-8"))

    # Replace the music-specific image-folder and audio/SRT chain with exactly two
    # film inputs: an optional keyframe/reference image and a planned valid frame
    # count.  LTXVEmptyLatentAudio becomes the source of native LTX audio.
    graph["film:frames"] = _node("PrimitiveInt", "Film planned frames ((frames - 1) % 8 = 0)", {"value": 97})
    graph["film:character_reference"] = _node("LoadImage", "Film/T2AV Character Reference or Pony Keyframe", {"image": "example.png"})
    graph["film:output_prefix"] = _node("PrimitiveString", "Film output prefix", {"value": "script_to_film/script_to_film"})

    graph["218:200"]["inputs"]["value"] = ["film:frames", 0]
    graph["218:279"]["inputs"]["input"] = ["film:character_reference", 0]
    graph["218:280"]["inputs"]["image"] = ["film:character_reference", 0]
    graph["219:221"]["inputs"]["image"] = ["film:character_reference", 0]
    graph["218:199"]["inputs"]["audio_latent"] = ["218:182", 0]

    # The native generated audio must be muxed directly. No source audio, SRT
    # timing, image trimming, crop, or music-video mux path remains reachable.
    graph["273"]["inputs"]["frame_rate"] = ["736:424", 0]
    graph["273"]["inputs"]["filename_prefix"] = ["film:output_prefix", 0]
    graph["273"]["inputs"]["images"] = ["936", 0]
    graph["273"]["inputs"]["audio"] = ["236:197", 0]
    graph["273"]["inputs"]["trim_to_audio"] = False
    graph["273"]["_meta"]["title"] = "Film native-audio video combine"
    graph["218:182"]["_meta"]["title"] = "Film empty native audio latent"
    graph["236:197"]["_meta"]["title"] = "Film LTX native audio decode"
    graph["218:222"]["_meta"]["title"] = "Film pass 1 reference conditioning (bypass for pure T2AV)"
    graph["219:221"]["_meta"]["title"] = "Film pass 2 reference conditioning (bypass for pure T2AV)"

    # Keep only the graph reachable from the final Film mux.  This prunes every
    # source-audio / SRT / crop / music-video image-folder dependency by topology
    # rather than relying on a brittle list of node ids.
    graph = _reachable_graph(graph, "273")
    expected = {"film:frames", "film:character_reference", "film:output_prefix", "218:182", "236:197", "273"}
    missing = expected.difference(graph)
    if missing:
        raise RuntimeError(f"Film template pruning removed required nodes: {sorted(missing)}")
    banned = {"VHS_LoadAudio", "VRGDG_AudioCrop", "VRGDG_LoadAudioSplit_SRTOnly", "LTXVAudioVAEEncode", "VRGDG_TrimImageBatch_SRTOnly", "IndexedImageFromFolder_ForRemakeMode"}
    retained_banned = sorted(node_id for node_id, node in graph.items() if node.get("class_type") in banned)
    if retained_banned:
        raise RuntimeError(f"Film template retained Music Video nodes: {retained_banned}")

    TARGET.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return graph


if __name__ == "__main__":
    built = build_template()
    print(f"Wrote {TARGET} with {len(built)} reachable nodes.")
