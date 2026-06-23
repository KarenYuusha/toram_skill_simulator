from __future__ import annotations

import base64
from functools import lru_cache

from toram_utils.paths import ROOT


@lru_cache(maxsize=None)
def icon_data_uri(path_text: str) -> str | None:
    path = ROOT / path_text
    if not path.exists():
        return None
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
