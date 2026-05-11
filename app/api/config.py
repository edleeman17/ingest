import os
import yaml
from pathlib import Path

_PATH = Path("/app/config.yml")
_DEFAULTS: dict = {
    "features": {
        "llm": True,
        "ocr": True,
        "web_ingest": False,
    }
}


def _load() -> dict:
    if not _PATH.exists():
        cfg = {"features": dict(_DEFAULTS["features"])}
    else:
        with open(_PATH) as f:
            data = yaml.safe_load(f) or {}
        cfg = {"features": dict(_DEFAULTS["features"])}
        cfg["features"].update(data.get("features", {}))

    # Auto-disable llm if OLLAMA_HOST not configured
    if not os.getenv("OLLAMA_HOST", "").strip():
        cfg["features"]["llm"] = False

    return cfg


_config = _load()


def feature(name: str) -> bool:
    return bool(_config["features"].get(name, _DEFAULTS["features"].get(name, False)))
