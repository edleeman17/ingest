import base64
import io
import httpx
import json
import os

import pytesseract
from PIL import Image

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.1.95:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

_SUMMARISE_SYSTEM = (
    "You are a task extraction assistant. Given a message, extract a concise actionable "
    "task summary and relevant tags. Respond ONLY with valid JSON: "
    '{"summary": "one-line action item under 80 chars", "tags": ["tag1", "tag2"]}. '
    "Tags should be 1-3 relevant categories."
)


def ocr_image(image_b64: str) -> str:
    """Extract text from a base64-encoded image using Tesseract."""
    image_bytes = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(img, config="--psm 6")
    return text.strip()


async def summarise(raw_text: str) -> tuple[str, list[str]]:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": f"Message:\n{raw_text}\n\nExtract the task:",
                "system": _SUMMARISE_SYSTEM,
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        result = json.loads(data["response"])
        return result.get("summary", raw_text[:80]), result.get("tags", [])
