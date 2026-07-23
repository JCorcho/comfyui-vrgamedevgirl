"""Windows-friendly launcher for the standalone Civitai concept researcher.

It keeps the helper runnable with ComfyUI's embedded Python, whose isolated
configuration does not automatically place the current directory on sys.path.
"""

import os
import sys


_TOOLS_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

from civitai_concept_researcher.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
