"""
Browse router — handles URL fetch, DNS lookup, and proxying page content.
"""

import re
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from urllib.parse import urlparse, urljoin, quote
import httpx
from bs4 import BeautifulSoup

from backend.models import BrowseRequest, BrowseResponse, ProtocolStep
from backend.services.dns_service import resolve_a_record
from backend.services.http_service import fetch_with_steps

router = APIRouter()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _normalize_url(url: str) -> str:
    """Add https:// if scheme is missing."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


@router.post("/api/browse", response_model=BrowseResponse)
async def browse(request: BrowseRequest):
    url = _normalize_url(request.url)
    parsed = urlparse(url)
    hostname = parsed.netloc or parsed.path

    all_steps: list[ProtocolStep] = []

    # ── Phase 1: DNS
    dns_steps, resolved_ip = resolve_a_record(hostname, step_offset=0)
    # Renumber starting from 1
    for i, s in enumerate(dns_steps):
        s.id = i + 1
    all_steps.extend(dns_steps)

    # ── Phase 2: HTTP (TCP + TLS + request + response)
    http_steps, status_code, response_headers, body_preview = await fetch_with_steps(
        url,
        step_offset=len(all_steps),
        resolved_ip=resolved_ip or hostname,
    )
    all_steps.extend(http_steps)

    proxy_url = f"/proxy?url={quote(url, safe='')}"

    return BrowseResponse(
        steps=all_steps,
        proxy_url=proxy_url,
        success=status_code in range(200, 400),
        error=None if status_code in range(200, 400) else f"HTTP {status_code}",
    )


@router.get("/proxy", response_class=HTMLResponse)
async def proxy_page(url: str):
    """
    Fetches a remote URL and returns its HTML content rewritten for iframe display.
    Injects a banner showing the URL being proxied.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": USER_AGENT},
            verify=True,
        ) as client:
            response = await client.get(url)

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "html" not in content_type:
            # Non-HTML resource — show a friendly info page
            return HTMLResponse(content=_non_html_page(url, content_type), status_code=200)

        html = response.text
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Rewrite relative links to absolute so they load within the proxy
        soup = BeautifulSoup(html, "lxml")

        # Inject <base> tag
        if not soup.find("base"):
            base_tag = soup.new_tag("base", href=base_url + "/")
            if soup.head:
                soup.head.insert(0, base_tag)
            else:
                head = soup.new_tag("head")
                head.append(base_tag)
                if soup.html:
                    soup.html.insert(0, head)

        # Inject banner
        banner_html = f"""
        <div id="npv-proxy-banner" style="
            position:fixed;top:0;left:0;right:0;z-index:999999;
            background:linear-gradient(90deg,#00d4ff,#7b2ff7);
            color:#fff;font-family:Inter,sans-serif;font-size:13px;
            padding:6px 16px;display:flex;align-items:center;gap:8px;
            box-shadow:0 2px 12px rgba(0,212,255,.3);
        ">
            <span style="font-size:16px;">🌐</span>
            <strong>Protocol Visualizer Proxy</strong>
            <span style="opacity:.7;">→</span>
            <code style="background:rgba(255,255,255,.15);padding:2px 6px;border-radius:4px;">{url}</code>
        </div>
        <div style="height:38px;"></div>
        """
        
        interceptor_script = """
        <script>
        document.addEventListener('click', function(e) {
            let target = e.target.closest('a');
            if (target && target.href && !target.href.startsWith('javascript:')) {
                e.preventDefault();
                window.parent.postMessage({ type: 'NPV_NAVIGATE', url: target.href }, '*');
            }
        });
        document.addEventListener('submit', function(e) {
            e.preventDefault();
            let form = e.target;
            let targetUrl = form.action || window.location.href;
            window.parent.postMessage({ type: 'NPV_NAVIGATE', url: targetUrl }, '*');
        });
        </script>
        """

        if soup.body:
            soup.body.insert(0, BeautifulSoup(banner_html, "html.parser"))
            soup.body.append(BeautifulSoup(interceptor_script, "html.parser"))

        return HTMLResponse(content=str(soup), status_code=200)

    except Exception as e:
        return HTMLResponse(content=_error_page(url, str(e)), status_code=200)


def _non_html_page(url: str, content_type: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><title>Non-HTML Resource</title>
<style>body{{background:#0d1117;color:#e6edf3;font-family:Inter,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;
max-width:480px;text-align:center;}}
code{{background:#21262d;padding:4px 8px;border-radius:4px;color:#79c0ff;}}
</style></head>
<body><div class="card">
<div style="font-size:48px;margin-bottom:16px;">📄</div>
<h2>Non-HTML Resource</h2>
<p>This URL returns a <code>{content_type}</code> file, not an HTML page.</p>
<p style="color:#8b949e;font-size:14px;">The protocol steps have been captured in the right panel.</p>
<a href="{url}" target="_blank" style="color:#00d4ff;">Open directly ↗</a>
</div></body></html>"""


def _error_page(url: str, error: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><title>Page Blocked</title>
<style>body{{background:#0d1117;color:#e6edf3;font-family:Inter,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.card{{background:#161b22;border:1px solid #f85149;border-radius:12px;padding:32px;
max-width:480px;text-align:center;}}
code{{background:#21262d;padding:4px 8px;border-radius:4px;color:#ff7b72;font-size:12px;}}
</style></head>
<body><div class="card">
<div style="font-size:48px;margin-bottom:16px;">🚫</div>
<h2>Page Cannot Be Proxied</h2>
<p>This site uses security headers (X-Frame-Options / CSP) that prevent embedding.</p>
<p><strong>The DNS and HTTP protocol steps are still accurate</strong> in the right panel.</p>
<code>{error[:120]}</code><br><br>
<a href="{url}" target="_blank" style="color:#00d4ff;">Open in new tab ↗</a>
</div></body></html>"""
