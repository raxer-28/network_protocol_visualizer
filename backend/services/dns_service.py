"""
DNS resolution service — performs real DNS lookups using dnspython
and returns structured ProtocolStep objects capturing the full query/response.
"""

import time
import socket
from typing import Optional
import dns.resolver
import dns.message
import dns.query
import dns.rdatatype
import dns.name

from backend.models import ProtocolStep, HighlightField


def resolve_a_record(hostname: str, step_offset: int = 0) -> tuple[list[ProtocolStep], Optional[str]]:
    """
    Perform a real DNS A record lookup for the given hostname.
    Returns (steps, resolved_ip).
    """
    steps: list[ProtocolStep] = []
    resolved_ip: Optional[str] = None
    t0 = time.time()

    # Step 1 — client sends DNS query
    query_detail = (
        f";; QUESTION SECTION:\n"
        f";{hostname}.   IN  A\n\n"
        f";; Query type: A (IPv4 Address)\n"
        f";; Recursion desired: yes\n"
        f";; Using system resolver (recursive)"
    )
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="DNS",
        direction="client→server",
        label=f"DNS Query — A record for {hostname}",
        detail=query_detail,
        highlight_fields=[
            HighlightField(key="Type", value="A"),
            HighlightField(key="Name", value=hostname),
            HighlightField(key="Flags", value="RD (Recursion Desired)"),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
    ))

    # Step 2 — perform actual resolution
    try:
        t_query = time.time()
        resolver = dns.resolver.Resolver()
        answer = resolver.resolve(hostname, "A")
        elapsed_ms = round((time.time() - t_query) * 1000, 2)

        ips = [str(r) for r in answer]
        resolved_ip = ips[0] if ips else None
        ttl = answer.rrset.ttl if answer.rrset else "N/A"

        response_detail = (
            f";; ANSWER SECTION:\n"
            + "\n".join(f"{hostname}.  {ttl}  IN  A  {ip}" for ip in ips)
            + f"\n\n;; Query time: {elapsed_ms} ms\n"
            f";; Authoritative: no (recursive resolver)\n"
            f";; Records returned: {len(ips)}"
        )

        steps.append(ProtocolStep(
            id=step_offset + 2,
            phase="DNS",
            direction="server→client",
            label=f"DNS Response — {hostname} → {resolved_ip}",
            detail=response_detail,
            highlight_fields=[
                HighlightField(key="IP Address", value=resolved_ip or ""),
                HighlightField(key="TTL", value=str(ttl) + "s"),
                HighlightField(key="Records", value=str(len(ips))),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
        ))

    except dns.resolver.NXDOMAIN:
        steps.append(ProtocolStep(
            id=step_offset + 2,
            phase="DNS",
            direction="server→client",
            label=f"DNS Error — NXDOMAIN (host not found)",
            detail=f";; ERROR: {hostname} does not exist (NXDOMAIN)\n;; Rcode: 3",
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=True,
        ))
    except Exception as e:
        # Fallback: try socket
        try:
            resolved_ip = socket.gethostbyname(hostname)
            steps.append(ProtocolStep(
                id=step_offset + 2,
                phase="DNS",
                direction="server→client",
                label=f"DNS Response — {hostname} → {resolved_ip}",
                detail=(
                    f";; ANSWER SECTION (via system resolver):\n"
                    f"{hostname}.  300  IN  A  {resolved_ip}\n\n"
                    f";; Note: Resolved using socket.gethostbyname() fallback"
                ),
                highlight_fields=[
                    HighlightField(key="IP Address", value=resolved_ip),
                    HighlightField(key="Method", value="System resolver"),
                ],
                timestamp_ms=round((time.time() - t0) * 1000, 2),
            ))
        except Exception as e2:
            steps.append(ProtocolStep(
                id=step_offset + 2,
                phase="DNS",
                direction="server→client",
                label="DNS Error — Resolution failed",
                detail=f";; ERROR: {str(e2)}",
                timestamp_ms=round((time.time() - t0) * 1000, 2),
                is_error=True,
            ))

    return steps, resolved_ip


def resolve_mx_record(domain: str, step_offset: int = 0) -> tuple[list[ProtocolStep], Optional[str]]:
    """
    Perform a real DNS MX record lookup for the given email domain.
    Returns (steps, primary_mx_host).
    """
    steps: list[ProtocolStep] = []
    mx_host: Optional[str] = None
    t0 = time.time()

    # Step 1 — client sends MX query
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="DNS",
        direction="client→server",
        label=f"DNS Query — MX record for {domain}",
        detail=(
            f";; QUESTION SECTION:\n"
            f";{domain}.   IN  MX\n\n"
            f";; Query type: MX (Mail Exchange)\n"
            f";; Purpose: Find mail server for recipient domain\n"
            f";; Recursion desired: yes"
        ),
        highlight_fields=[
            HighlightField(key="Type", value="MX"),
            HighlightField(key="Domain", value=domain),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
    ))

    # Step 2 — actual resolution
    try:
        t_query = time.time()
        resolver = dns.resolver.Resolver()
        answer = resolver.resolve(domain, "MX")
        elapsed_ms = round((time.time() - t_query) * 1000, 2)

        records = sorted(answer, key=lambda r: r.preference)
        mx_host = str(records[0].exchange).rstrip(".") if records else None
        ttl = answer.rrset.ttl if answer.rrset else "N/A"

        response_detail = (
            f";; ANSWER SECTION:\n"
            + "\n".join(
                f"{domain}.  {ttl}  IN  MX  {r.preference} {r.exchange}"
                for r in records
            )
            + f"\n\n;; Query time: {elapsed_ms} ms\n"
            f";; Primary MX: {mx_host} (lowest priority = {records[0].preference})"
        )

        steps.append(ProtocolStep(
            id=step_offset + 2,
            phase="DNS",
            direction="server→client",
            label=f"DNS Response — MX → {mx_host}",
            detail=response_detail,
            highlight_fields=[
                HighlightField(key="Primary MX", value=mx_host or ""),
                HighlightField(key="Priority", value=str(records[0].preference)),
                HighlightField(key="TTL", value=str(ttl) + "s"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
        ))

    except Exception as e:
        # Simulate Gmail MX as fallback
        mx_host = "smtp.gmail.com"
        steps.append(ProtocolStep(
            id=step_offset + 2,
            phase="DNS",
            direction="server→client",
            label=f"DNS Response — MX (simulated)",
            detail=(
                f";; ANSWER SECTION (simulated - resolver error: {str(e)}):\n"
                f"{domain}.  300  IN  MX  10 smtp.gmail.com.\n\n"
                f";; Note: Using simulated MX record"
            ),
            highlight_fields=[
                HighlightField(key="Primary MX", value="smtp.gmail.com"),
                HighlightField(key="Priority", value="10"),
            ],
            timestamp_ms=round((time.time() - t0) * 1000, 2),
        ))

    return steps, mx_host
