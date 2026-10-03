"""
Stream router — resolves video URLs and delivers live chunk protocol steps.
"""

from fastapi import APIRouter
from backend.models import (
    StreamRequest,
    StreamResponse,
    StreamChunkRequest,
    StreamChunkResponse,
)
from backend.services.stream_service import build_stream_steps, build_stream_chunk_steps

router = APIRouter()

SAMPLE_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"


@router.post("/api/stream", response_model=StreamResponse)
async def stream(request: StreamRequest):
    url = request.url.strip() if request.url else SAMPLE_URL
    if not url.startswith(("http://", "https://")):
        url = SAMPLE_URL

    steps, stream_url, is_hls = await build_stream_steps(url)

    # Renumber initial setup steps sequentially
    for i, s in enumerate(steps):
        s.id = i + 1

    return StreamResponse(
        steps=steps,
        stream_url=stream_url,
        is_hls=is_hls,
        success=True,
    )


@router.post("/api/stream/chunk", response_model=StreamChunkResponse)
async def stream_chunk(request: StreamChunkRequest):
    steps = build_stream_chunk_steps(
        url=request.url,
        chunk_index=request.chunk_index,
        time_sec=request.time_sec,
        is_seek=request.is_seek,
        is_hls=request.is_hls,
    )
    return StreamChunkResponse(steps=steps, success=True)
