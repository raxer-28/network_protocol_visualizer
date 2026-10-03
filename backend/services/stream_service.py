"""
Stream service — performs real HTTP requests to resolve a video URL,
detects HLS (.m3u8) vs direct .mp4, returns initial setup steps (DNS/TCP/TLS/HEAD),
and generates real-time HTTP chunk / byte-range steps dynamically during video playback.
"""

import time
import httpx
from urllib.parse import urlparse
from backend.models import ProtocolStep, HighlightField
from backend.services.dns_service import resolve_a_record
from backend.services.tcp_simulator import generate_tcp_handshake, generate_tcp_data, generate_tcp_teardown, generate_udp_datagrams


SAMPLE_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"


async def build_stream_steps(url: str) -> tuple[list[ProtocolStep], str, bool]:
    """
    Given a video URL, performs real DNS + HTTP handshake requests and returns:
    (initial_steps, stream_url_for_video_element, is_hls)
    """
    steps: list[ProtocolStep] = []
    t0 = time.time()
    step_id = 1

    if not url or not url.startswith(("http://", "https://")):
        url = SAMPLE_URL

    parsed = urlparse(url)
    hostname = parsed.netloc
    is_https = parsed.scheme == "https"
    is_hls = url.endswith(".m3u8") or "m3u8" in url

    # ── Phase 1: DNS lookup
    dns_steps, resolved_ip = resolve_a_record(hostname, step_offset=0)
    for s in dns_steps:
        s.id = step_id
        s.timestamp_ms = round((time.time() - t0) * 1000, 2)
        steps.append(s)
        step_id += 1

    # ── Phase 2: TCP connection
    steps.append(ProtocolStep(
        id=step_id, phase="TCP", direction="info",
        label=f"TCP Handshake -> {hostname}:{443 if is_https else 80}",
        detail=(
            f"[TCP 3-Way Handshake]\n"
            f"Client -> {resolved_ip or hostname}:{443 if is_https else 80}\n\n"
            f"SYN ->\n<- SYN-ACK\nACK ->\n\nSocket connected."
        ),
        highlight_fields=[
            HighlightField(key="Server IP", value=resolved_ip or hostname),
            HighlightField(key="Port", value=str(443 if is_https else 80)),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
        layer="application"
    ))
    t_ms = round((time.time() - t0) * 1000, 2)
    steps.extend(generate_tcp_handshake(t_ms, "client_ip", resolved_ip or hostname, 443 if is_https else 80, step_offset=step_id))
    step_id += 4
    tcp_seq = 1
    tcp_ack = 1

    if is_https:
        steps.append(ProtocolStep(
            id=step_id, phase="TLS", direction="info",
            label="TLS 1.3 Handshake (Secure Tunnel)",
            detail=(
                f"-> ClientHello (SNI: {hostname})\n"
                f"<- ServerHello\n<- Certificate\n<- Finished\n-> Finished\n\n"
                "Encrypted channel established via TLS 1.3."
            ),
            highlight_fields=[
                HighlightField(key="SNI", value=hostname),
                HighlightField(key="Protocol", value="TLS 1.3"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            layer="application"
        ))
        t_ms = round((time.time() - t0) * 1000, 2)
        steps.extend(generate_tcp_data(t_ms, "client→server", tcp_seq, tcp_ack, 512, "PSH, ACK", step_offset=step_id))
        tcp_seq += 512
        step_id += 3

    # ── Phase 3: HEAD request to probe content type and byte-range support
    content_type = "video/mp4"
    content_length = "unknown"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
            head_resp = await client.head(url)
            content_type = head_resp.headers.get("content-type", "video/mp4")
            content_length = head_resp.headers.get("content-length", "unknown")
            is_hls = "mpegurl" in content_type or is_hls
    except Exception:
        pass

    steps.append(ProtocolStep(
        id=step_id, phase="HTTP", direction="client→server",
        label=f"HTTP HEAD {parsed.path or '/'} (probe format)",
        detail=(
            f"HEAD {parsed.path or '/'} HTTP/1.1\r\n"
            f"Host: {hostname}\r\n"
            f"User-Agent: Mozilla/5.0 (NetworkProtocolVisualizer/1.0)\r\n"
            f"Accept: */*\r\n\r\n"
            f"[Client probes server to check byte-range support and MIME type]"
        ),
        highlight_fields=[
            HighlightField(key="Method", value="HEAD"),
            HighlightField(key="Path", value=parsed.path or "/"),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
    ))
    step_id += 1

    steps.append(ProtocolStep(
        id=step_id, phase="HTTP", direction="server→client",
        label=f"200 OK — Content-Type: {content_type}",
        detail=(
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {content_length}\r\n"
            f"Accept-Ranges: bytes\r\n"
            f"Cache-Control: public, max-age=3600\r\n\r\n"
            f"[Server supports partial byte ranges. Stream primed for live chunks]"
        ),
        highlight_fields=[
            HighlightField(key="Content-Type", value=content_type),
            HighlightField(key="Content-Length", value=str(content_length)),
            HighlightField(key="Accept-Ranges", value="bytes"),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
    ))
    step_id += 1

    if is_hls:
        # If HLS, fetch manifest step so client has playlist
        steps.append(ProtocolStep(
            id=step_id, phase="HTTP", direction="client→server",
            label="HTTP GET — HLS Master Playlist (.m3u8)",
            detail=(
                f"GET {parsed.path} HTTP/1.1\r\n"
                f"Host: {hostname}\r\n"
                f"Accept: application/vnd.apple.mpegurl\r\n\r\n"
                f"[Client requests playlist to enumerate available bitrates]"
            ),
            highlight_fields=[
                HighlightField(key="Method", value="GET"),
                HighlightField(key="Type", value="HLS Playlist"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
        ))
        step_id += 1

        steps.append(ProtocolStep(
            id=step_id, phase="HTTP", direction="server→client",
            label="200 OK — Master Playlist Loaded",
            detail=(
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/vnd.apple.mpegurl\r\n\r\n"
                f"#EXTM3U\n#EXT-X-VERSION:3\n"
                f"#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1920x1080\n"
                f"#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=1280x720\n\n"
                f"[Ready for adaptive chunk delivery on playback]"
            ),
            highlight_fields=[
                HighlightField(key="Status", value="200 OK"),
                HighlightField(key="Stream Type", value="HLS Live"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
        ))
        step_id += 1

    return steps, url, is_hls


def build_stream_chunk_steps(
    url: str,
    chunk_index: int,
    time_sec: float = 0.0,
    is_seek: bool = False,
    is_hls: bool = False,
) -> list[ProtocolStep]:
    """
    Generates a realistic client-request & server-response step pair for a video
    byte range or segment chunk in real time during video playback.
    """
    parsed = urlparse(url if url else SAMPLE_URL)
    hostname = parsed.netloc or "commondatastorage.googleapis.com"
    path = parsed.path or "/sample/BigBuckBunny.mp4"

    chunk_kb = 512
    chunk_bytes = chunk_kb * 1024
    total_bytes = 158_008_374

    # Calculate byte offsets based on time_sec or chunk_index
    if is_seek:
        start_byte = int(time_sec * 1_200_000)
        end_byte = start_byte + chunk_bytes
        label_req = f"HTTP GET — Seek Range [{format_seconds(time_sec)}]"
        label_res = f"206 Partial Content — Seek Buffer ({chunk_kb}KB)"
        note = f"[User seeked to {format_seconds(time_sec)} -> fetching new playback buffer]"
    elif is_hls:
        seg_num = max(1, chunk_index)
        t_start = (seg_num - 1) * 2
        t_end = seg_num * 2
        label_req = f"HTTP GET — Segment {seg_num:03d}.ts [{t_start}s-{t_end}s]"
        label_res = f"200 OK — Segment {seg_num:03d} Delivered ({chunk_kb}KB)"
        note = f"[HLS segment #{seg_num} delivered for playback timeline]"
        start_byte = (seg_num - 1) * chunk_bytes
        end_byte = seg_num * chunk_bytes
    else:
        start_byte = (chunk_index - 1) * chunk_bytes
        end_byte = start_byte + chunk_bytes
        label_req = f"HTTP GET — Range chunk #{chunk_index} [{format_seconds(time_sec)}]"
        label_res = f"206 Partial Content — Chunk #{chunk_index} ({chunk_kb}KB)"
        note = f"[Real-time buffer chunk #{chunk_index} received at {format_seconds(time_sec)}]"

    req_step = ProtocolStep(
        id=1,
        phase="HTTP",
        direction="client→server",
        label=label_req,
        detail=(
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {hostname}\r\n"
            f"Range: bytes={start_byte:,}-{end_byte:,}\r\n"
            f"User-Agent: Mozilla/5.0 (StreamPlayer/2.0)\r\n"
            f"Accept: video/*\r\n\r\n"
            f"{note}"
        ),
        highlight_fields=[
            HighlightField(key="Method", value="GET"),
            HighlightField(key="Range", value=f"bytes={start_byte:,}-{end_byte:,}"),
            HighlightField(key="Playback Time", value=format_seconds(time_sec)),
        ],
        timestamp_ms=round(time_sec * 1000, 2),
        layer="application"
    )

    res_step = ProtocolStep(
        id=2,
        phase="HTTP",
        direction="server→client",
        label=label_res,
        detail=(
            f"HTTP/1.1 206 Partial Content\r\n"
            f"Content-Type: video/mp4\r\n"
            f"Content-Range: bytes {start_byte:,}-{end_byte:,}/{total_bytes:,}\r\n"
            f"Content-Length: {chunk_bytes:,}\r\n"
            f"X-Cache: HIT\r\n\r\n"
            f"[{chunk_kb}KB binary video data streamed to browser media buffer]"
        ),
        highlight_fields=[
            HighlightField(key="Status", value="206 Partial Content"),
            HighlightField(key="Chunk Size", value=f"{chunk_kb} KB"),
            HighlightField(key="Buffered To", value=format_seconds(time_sec + 2)),
        ],
        timestamp_ms=round(time_sec * 1000 + 45, 2),
        layer="application"
    )
    
    # Simulate UDP datagrams for streaming instead of TCP
    udp_steps_req = generate_udp_datagrams(round(time_sec * 1000, 2), "client→server", 45000, 443, 250, step_offset=2)
    udp_steps_res = generate_udp_datagrams(round(time_sec * 1000 + 45, 2), "server→client", 443, 45000, chunk_bytes, step_offset=2+len(udp_steps_req))

    return [req_step, res_step] + udp_steps_req + udp_steps_res


def format_seconds(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"
