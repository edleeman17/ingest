import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
from pydantic import BaseModel

from shared.models import IngestRequest, IngestResponse
from api.db import init_db, insert_item
from api.ollama import ocr_image, summarise
from api.config import feature
from api.items import list_items, set_done, set_group, set_positions, list_sources, list_groups, create_group, rename_group, delete_group, enrich_item

logger = logging.getLogger(__name__)
STATIC_DIR = Path("/static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Ingest",
    description="Capture actionable messages from anywhere into a LAN-hosted todo list.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── PWA shell ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=FileResponse, include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")

@app.get("/sw.js", include_in_schema=False)
async def sw():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


# ── Items ─────────────────────────────────────────────────────────────────────
@app.get("/api/items", tags=["items"], summary="List items")
async def get_items(
    done: Optional[int] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Return paginated items. `done=0` for todo, `done=1` for completed."""
    items, total = await list_items(done=done, source=source, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}

@app.get("/api/sources", tags=["items"], summary="List distinct sources")
async def get_sources():
    return await list_sources()


class PatchItem(BaseModel):
    done: Optional[bool] = None
    group_id: Optional[int] = None
    ungroup: bool = False

@app.patch("/api/items/{item_id}", tags=["items"], summary="Update item")
async def patch_item(item_id: int, body: PatchItem):
    """Mark done/undone, assign to group, or remove from group."""
    if body.done is not None:
        await set_done(item_id, body.done)
    if body.ungroup:
        await set_group(item_id, None)
    elif body.group_id is not None:
        await set_group(item_id, body.group_id)
    return {"ok": True}


# ── Groups ────────────────────────────────────────────────────────────────────
@app.get("/api/groups", tags=["groups"], summary="List groups with their items")
async def get_groups():
    return await list_groups()


class GroupBody(BaseModel):
    name: str

@app.post("/api/groups", tags=["groups"], summary="Create group")
async def post_group(body: GroupBody):
    gid = await create_group(body.name)
    return {"id": gid, "name": body.name}

@app.patch("/api/groups/{group_id}", tags=["groups"], summary="Rename group")
async def patch_group(group_id: int, body: GroupBody):
    await rename_group(group_id, body.name)
    return {"ok": True}

@app.delete("/api/groups/{group_id}", tags=["groups"], summary="Delete group (items become ungrouped)")
async def del_group(group_id: int):
    await delete_group(group_id)
    return {"ok": True}


class ReorderBody(BaseModel):
    item_ids: list[int]

@app.post("/api/groups/{group_id}/reorder", tags=["groups"], summary="Reorder items within group")
async def reorder_group(group_id: int, body: ReorderBody):
    """Pass all item IDs in the desired order."""
    await set_positions(group_id, body.item_ids)
    return {"ok": True}


# ── Ingest ────────────────────────────────────────────────────────────────────
async def _enrich(item_id: int, raw_text: str, image_data):
    text = raw_text
    if image_data and feature("ocr"):
        try:
            loop = asyncio.get_event_loop()
            ocr_text = await loop.run_in_executor(None, ocr_image, image_data)
            text = (text + "\n\n[Image text: " + ocr_text + "]") if text else ocr_text
        except Exception:
            logger.exception("OCR failed")
    if feature("llm"):
        try:
            summary, tags = await summarise(text)
        except Exception:
            logger.exception("summarise failed")
            summary, tags = text[:120], []
    else:
        summary, tags = text[:120], []
    await enrich_item(item_id, summary, tags)


@app.post("/ingest", response_model=IngestResponse, tags=["ingest"], summary="Ingest a new item")
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """Saves immediately and returns. OCR and LLM summarisation run in the background."""
    raw_text = (req.raw_text or "").strip()
    if not raw_text and not req.image_data:
        raise HTTPException(status_code=400, detail="No text or image content provided")
    item_id = await insert_item(req.source, raw_text, raw_text[:120], [])
    background_tasks.add_task(_enrich, item_id, raw_text, req.image_data)
    return IngestResponse(id=item_id, summary=raw_text[:120], tags=[], ocr_text=None)



# ── Misc ──────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health():
    enabled = {name: feature(name) for name in ("llm", "ocr")}
    return {"status": "ok", "features": enabled}

@app.get("/shortcuts", response_class=HTMLResponse, include_in_schema=False)
async def shortcuts_page():
    return """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Install Shortcuts</title><style>body{font-family:sans-serif;padding:2em;max-width:400px;margin:auto}
a{display:block;padding:1em;margin:1em 0;background:#007aff;color:white;text-decoration:none;border-radius:12px;text-align:center}</style></head>
<body><h2>Ingest</h2>
<a href="/shortcuts/text">Install: Ingest Text</a>
<a href="/shortcuts/screenshot">Install: Ingest Screenshot</a></body></html>"""

@app.get("/shortcuts/text", include_in_schema=False)
async def shortcut_text():
    return Response((STATIC_DIR/"Ingest Text.shortcut").read_bytes(), media_type="application/x-apple-aspen-shortcut")

@app.get("/shortcuts/screenshot", include_in_schema=False)
async def shortcut_screenshot():
    return Response((STATIC_DIR/"Ingest Screenshot.shortcut").read_bytes(), media_type="application/x-apple-aspen-shortcut")

@app.get("/ca", include_in_schema=False)
async def root_ca():
    p = STATIC_DIR / "rootCA.crt"
    if not p.exists():
        raise HTTPException(404, "No CA cert configured")
    return Response(p.read_bytes(), media_type="application/x-x509-ca-cert")


@app.get("/api/config", tags=["meta"], summary="Active feature flags")
async def get_config():
    """Returns which features are enabled. Safe to expose on LAN."""
    return {"features": {name: feature(name) for name in ("llm", "ocr", "web_ingest")}}
