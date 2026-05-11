from pydantic import BaseModel
from typing import Optional


class IngestRequest(BaseModel):
    source: str
    raw_text: str = ""
    image_data: Optional[str] = None  # base64-encoded image
    image_url: Optional[str] = None
    metadata: Optional[dict] = None


class IngestResponse(BaseModel):
    id: int
    summary: str
    tags: list[str]
    ocr_text: Optional[str] = None
