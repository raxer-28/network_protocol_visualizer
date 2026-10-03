"""
HTTP service — performs real HTTP requests using httpx and captures
full request/response headers as ProtocolStep objects.
"""

import time
import httpx
from urllib.parse import urlparse
from backend.models import ProtocolStep, HighlightField
from backend.services.tcp_simulator import generate_tcp_handshake, generate_tcp_data, generate_tcp_teardown


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


async def fetch_with_steps(
    url: str,
    step_offset: int = 0,
    resolved_ip: str = "resolved via DNS",
) -> tuple[list[ProtocolStep], int, dict, str]:
    """
    Perform a real async HTTP GET request.
    Returns (steps, status_code, response_headers, body_preview).
    """
    steps: list[ProtocolStep] = []
    t0 = time.time()
    parsed = urlparse(url)
    hostname = parsed.netloc or parsed.path
    scheme = parsed.scheme.upper()
    is_https = parsed.scheme == "https"

    # ── Step: TCP Connection
    tcp_detail = (
        f"[TCP 3-Way Handshake]\n"
        f"Client IP : (your machine)\n"
        f"Server IP : {resolved_ip}\n"
        f"Port      : {443 if is_https else 80}\n\n"
        f"1. Client → Server  SYN\n"
        f"2. Server → Client  SYN-ACK\n"
        f"3. Client → Server  ACK\n"
        f"   Connection established."
    )
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="TCP",
        direction="info",
        label=f"TCP Handshake — Port {443 if is_https else 80}",
        detail=tcp_detail,
        highlight_fields=[
            HighlightField(key="Server", value=resolved_ip),
            HighlightField(key="Port", value=str(443 if is_https else 80)),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
        layer="application"
    ))
    t_ms = round((time.time() - t0) * 1000, 2)
    steps.extend(generate_tcp_handshake(t_ms, "client_ip", resolved_ip, 443 if is_https else 80, step_offset=step_offset+1))

    step_num = step_offset + 5
    tcp_seq = 1
    tcp_ack = 1

    if is_https:
        tls_detail = (
            f"[TLS 1.3 Handshake]\n\n"
            f"→ ClientHello\n"
            f"   Supported cipher suites: TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384\n"
            f"   SNI (Server Name Indication): {hostname}\n\n"
            f"← ServerHello\n"
            f"   Selected cipher: TLS_AES_128_GCM_SHA256\n"
            f"← Certificate  (server identity proof)\n"
            f"← CertificateVerify\n"
            f"← Finished\n\n"
            f"→ Finished\n"
            f"   Handshake complete — channel encrypted."
        )
        steps.append(ProtocolStep(
            id=step_num,
            phase="TLS",
            direction="info",
            label="TLS 1.3 Handshake",
            detail=tls_detail,
            highlight_fields=[
                HighlightField(key="Protocol", value="TLS 1.3"),
                HighlightField(key="SNI", value=hostname),
                HighlightField(key="Cipher", value="TLS_AES_128_GCM_SHA256"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            layer="application"
        ))
        t_ms = round((time.time() - t0) * 1000, 2)
        # TLS is transported via TCP data segments
        steps.extend(generate_tcp_data(t_ms, "client→server", tcp_seq, tcp_ack, 512, "PSH, ACK", step_offset=step_num))
        tcp_seq += 512
        step_num += 3

    # ── Step: HTTP Request
    request_headers = {
        "Host": hostname,
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    req_detail = (
        f"GET {parsed.path or '/'} HTTP/1.1\r\n"
        + "\r\n".join(f"{k}: {v}" for k, v in request_headers.items())
        + "\r\n\r\n"
        + "(no body — GET request)"
    )
    steps.append(ProtocolStep(
        id=step_num,
        phase="HTTP",
        direction="client→server",
        label=f"HTTP GET {parsed.path or '/'}",
        detail=req_detail,
        highlight_fields=[
            HighlightField(key="Method", value="GET"),
            HighlightField(key="Path", value=parsed.path or "/"),
            HighlightField(key="Host", value=hostname),
            HighlightField(key="Version", value="HTTP/1.1"),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
        layer="application"
    ))
    
    t_ms = round((time.time() - t0) * 1000, 2)
    req_len = len(req_detail)
    steps.extend(generate_tcp_data(t_ms, "client→server", tcp_seq, tcp_ack, req_len, "PSH, ACK", step_offset=step_num))
    tcp_seq += req_len
    step_num += 3

    # ── Actual HTTP request
    status_code = 200
    response_headers: dict = {}
    body_preview = ""

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": USER_AGENT},
            verify=True,
        ) as client:
            t_req = time.time()
            response = await client.get(url)
            elapsed_ms = round((time.time() - t_req) * 1000, 2)

        status_code = response.status_code
        response_headers = dict(response.headers)
        content_type = response_headers.get("content-type", "")
        content_length = response_headers.get("content-length", "N/A")
        transfer_encoding = response_headers.get("transfer-encoding", "")

        # Body preview (first 200 chars of text content)
        if "text" in content_type or "html" in content_type:
            body_preview = response.text[:200].strip().replace("\n", " ")
        else:
            body_preview = f"[Binary content — {content_type}]"

        status_text = {
            200: "OK", 201: "Created", 204: "No Content",
            301: "Moved Permanently", 302: "Found", 304: "Not Modified",
            400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
            404: "Not Found", 500: "Internal Server Error",
        }.get(status_code, "Unknown")

        resp_detail = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            + "\r\n".join(f"{k}: {v}" for k, v in list(response_headers.items())[:15])
            + f"\r\n\r\n"
            + f"[Response time: {elapsed_ms} ms]\n\n"
            + f"Body preview:\n{body_preview[:300]}"
        )

        steps.append(ProtocolStep(
            id=step_num,
            phase="HTTP",
            direction="server→client",
            label=f"HTTP Response — {status_code} {status_text}",
            detail=resp_detail,
            highlight_fields=[
                HighlightField(key="Status", value=f"{status_code} {status_text}"),
                HighlightField(key="Content-Type", value=content_type),
                HighlightField(key="Content-Length", value=content_length),
                HighlightField(key="Response Time", value=f"{elapsed_ms} ms"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=is_err,
            layer="application"
        ))
        
        t_ms = round((time.time() - t0) * 1000, 2)
        resp_len = 2048 if content_length == "N/A" else max(int(content_length), 2048)
        steps.extend(generate_tcp_data(t_ms, "server→client", tcp_ack, tcp_seq, resp_len, "PSH, ACK", step_offset=step_num))
        tcp_ack += resp_len
        step_num += 3
        
        # TCP Teardown
        t_ms += 15
        steps.extend(generate_tcp_teardown(t_ms, tcp_seq, tcp_ack, step_offset=step_num))
        step_num += 4

    except httpx.ConnectError as e:
        steps.append(ProtocolStep(
            id=step_num,
            phase="HTTP",
            direction="server→client",
            label="HTTP Error — Connection refused",
            detail=f"HTTP/1.1 000 Connection Error\r\n\r\nError: {str(e)}",
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=True,
        ))
        status_code = 0
    except httpx.TimeoutException:
        steps.append(ProtocolStep(
            id=step_num,
            phase="HTTP",
            direction="server→client",
            label="HTTP Error — Request timed out",
            detail="HTTP/1.1 408 Request Timeout\r\n\r\nThe server did not respond within 10 seconds.",
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=True,
        ))
        status_code = 408
    except Exception as e:
        steps.append(ProtocolStep(
            id=step_num,
            phase="HTTP",
            direction="server→client",
            label="HTTP Error",
            detail=f"Error: {str(e)}",
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=True,
        ))
        status_code = 0

    return steps, status_code, response_headers, body_preview
