"""Command-line entry point for the standalone Civitai concept researcher."""

from __future__ import annotations

import argparse
import json
import sys

from .researcher import CivitaiAPIError, research_concept


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Find public Civitai generation recipes for a concept; output is review-only JSON."
    )
    parser.add_argument("--concept", required=True, help="Pose, camera, body-mechanics, or other concept query.")
    parser.add_argument("--base-model", default="Pony", help="Base model filter, normally Pony or Anima; use Any for no local filter.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum review candidates (1–20).")
    parser.add_argument("--max-pages", type=int, default=1, help="Public API result pages to inspect (1–3).")
    parser.add_argument("--include-nsfw", action="store_true", help="Do not apply the helper's safe-only filter.")
    arguments = parser.parse_args(argv)
    try:
        result = research_concept(
            arguments.concept,
            arguments.base_model,
            arguments.limit,
            safe_only=not arguments.include_nsfw,
            max_pages=arguments.max_pages,
        )
    except (ValueError, CivitaiAPIError) as exc:
        print(f"Civitai concept research failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
