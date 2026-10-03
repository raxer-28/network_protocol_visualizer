"""
Pydantic models for the Network Protocol Visualizer API.
"""

from pydantic import BaseModel
from typing import Optional


class HighlightField(BaseModel):
    """A key-value pair to highlight within a protocol step's detail text."""
    key: str
    value: str


class ProtocolStep(BaseModel):
    """Represents one message or event in a protocol exchange."""
    id: int
    phase: str                          # "DNS" | "TCP" | "TLS" | "HTTP" | "SMTP"
    direction: str                      # "client→server" | "server→client" | "info"
    label: str                          # Short label, e.g. "DNS Query (A)"
    detail: str                         # Full raw message / command text
    highlight_fields: list[HighlightField] = []  # Key fields to highlight
    timestamp_ms: float                 # Relative ms from start of exchange
    is_error: bool = False
    layer: str = "application"          # "application" | "transport"


class BrowseRequest(BaseModel):
    url: str


class BrowseResponse(BaseModel):
    steps: list[ProtocolStep]
    proxy_url: str
    success: bool
    error: Optional[str] = None


class MailRequest(BaseModel):
    to: str
    subject: str
    body: str
    simulate: bool = False


class MailResponse(BaseModel):
    steps: list[ProtocolStep]
    success: bool
    error: Optional[str] = None


class StreamRequest(BaseModel):
    url: str


class StreamResponse(BaseModel):
    steps: list[ProtocolStep]
    stream_url: str
    is_hls: bool = False
    success: bool
    error: Optional[str] = None


class StreamChunkRequest(BaseModel):
    url: str
    chunk_index: int
    time_sec: float = 0.0
    is_seek: bool = False
    is_hls: bool = False


class StreamChunkResponse(BaseModel):
    steps: list[ProtocolStep]
    success: bool
    error: Optional[str] = None
