"""
Mail router — sends real emails via SMTP and returns protocol steps.
"""

from fastapi import APIRouter
from backend.models import MailRequest, MailResponse
from backend.services.smtp_service import send_email_with_steps, _no_credentials_steps
from backend.services.dns_service import resolve_mx_record

router = APIRouter()


@router.post("/api/mail", response_model=MailResponse)
async def send_mail(request: MailRequest):
    # Extract recipient domain for MX lookup
    recipient_domain = request.to.split("@")[-1] if "@" in request.to else "gmail.com"

    all_steps = []

    # ── Phase 1: DNS MX lookup
    mx_steps, mx_host = resolve_mx_record(recipient_domain, step_offset=0)
    for i, s in enumerate(mx_steps):
        s.id = i + 1
    all_steps.extend(mx_steps)

    # ── Phase 2: SMTP send
    if request.simulate:
        smtp_steps = _no_credentials_steps(request.to, request.subject, request.body)
        success = True
        error = None
    else:
        smtp_steps, success, error = send_email_with_steps(
            to=request.to,
            subject=request.subject,
            body=request.body,
        )
    # Renumber smtp steps continuing from dns steps
    offset = len(all_steps)
    for s in smtp_steps:
        s.id = s.id + offset
    all_steps.extend(smtp_steps)

    return MailResponse(
        steps=all_steps,
        success=success,
        error=error or None,
    )
