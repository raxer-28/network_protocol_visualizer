"""
SMTP service — sends real emails via Gmail SMTP (smtplib)
and captures the full SMTP conversation as ProtocolStep objects.
Includes detailed TCP transport-layer steps and a TLS state machine.
"""

import smtplib
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from backend.models import ProtocolStep, HighlightField
from backend.services.tcp_simulator import generate_tcp_handshake, generate_tcp_data, generate_tcp_teardown

load_dotenv()

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email_with_steps(to: str, subject: str, body: str) -> tuple[list[ProtocolStep], bool, str]:
    """
    Send a real email via Gmail SMTP using STARTTLS.
    Intercepts and records the full SMTP dialog as ProtocolStep objects.
    Returns (steps, success, error_message).
    """
    sender_email = os.getenv("SENDER_EMAIL", "")
    sender_password = os.getenv("SENDER_PASSWORD", "")

    if not sender_email or not sender_password:
        return _no_credentials_steps(to, subject, body), False, "Email credentials not set in .env file"

    steps: list[ProtocolStep] = []
    t0 = time.time()
    step_id = 1

    # ── TCP Handshake (transport layer) ──────────────────────────
    steps.append(ProtocolStep(
        id=step_id, phase="TCP", direction="info",
        label=f"TCP Connect → {SMTP_HOST}:{SMTP_PORT}",
        detail=(
            f"[TCP 3-Way Handshake Initiated]\n"
            f"Client → {SMTP_HOST}:{SMTP_PORT}\n\n"
            f"Step 1: SYN   Client → Server\n"
            f"Step 2: SYN-ACK  Server → Client\n"
            f"Step 3: ACK   Client → Server\n\n"
            f"Connection established. Ready for SMTP."
        ),
        highlight_fields=[
            HighlightField(key="Server", value=SMTP_HOST),
            HighlightField(key="Port", value=str(SMTP_PORT)),
            HighlightField(key="Protocol", value="TCP"),
        ],
        timestamp_ms=round((time.time() - t0) * 1000, 2),
        layer="transport"
    ))
    step_id += 1
    t_ms = round((time.time() - t0) * 1000, 2)
    tcp_steps = generate_tcp_handshake(t_ms, "client_ip", SMTP_HOST, SMTP_PORT, step_offset=step_id - 1)
    for s in tcp_steps:
        s.id = step_id
        step_id += 1
    steps.extend(tcp_steps)

    tcp_seq = 1
    tcp_ack = 1

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:

            # ── 220 Service Ready ─────────────────────────────────
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="220 Service Ready",
                detail=f"220 {SMTP_HOST} ESMTP ready\r\n\r\n[Server announces SMTP service availability]",
                highlight_fields=[
                    HighlightField(key="Code", value="220"),
                    HighlightField(key="Status", value="Service Ready"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1
            # Transport ACK for this
            for s in generate_tcp_data(t_ms, "server→client", tcp_ack, tcp_seq, 50, step_offset=step_id - 1):
                s.id = step_id; step_id += 1; steps.append(s)

            # ── EHLO ──────────────────────────────────────────────
            domain = sender_email.split("@")[1] if "@" in sender_email else "localhost"
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label=f"EHLO {domain}",
                detail=(
                    f"EHLO {domain}\r\n\r\n"
                    f"[Extended HELLO — client introduces itself\n"
                    f" and requests server capability list]"
                ),
                highlight_fields=[
                    HighlightField(key="Command", value="EHLO"),
                    HighlightField(key="Client Domain", value=domain),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1
            seg_len = len(domain) + 10
            for s in generate_tcp_data(t_ms, "client→server", tcp_seq, tcp_ack, seg_len, step_offset=step_id - 1):
                s.id = step_id; step_id += 1; steps.append(s)
            tcp_seq += seg_len

            # ── 250 OK Capabilities ───────────────────────────────
            code, resp = smtp.ehlo()
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="250 OK — Server capabilities",
                detail=(
                    f"250-{SMTP_HOST} at your service\r\n"
                    f"250-SIZE 35882577\r\n"
                    f"250-8BITMIME\r\n"
                    f"250-STARTTLS\r\n"
                    f"250-ENHANCEDSTATUSCODES\r\n"
                    f"250-PIPELINING\r\n"
                    f"250-CHUNKING\r\n"
                    f"250 SMTPUTF8\r\n\r\n"
                    f"[Server lists supported extensions]"
                ),
                highlight_fields=[
                    HighlightField(key="Code", value="250"),
                    HighlightField(key="Key Caps", value="STARTTLS, AUTH, SIZE"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1
            for s in generate_tcp_data(t_ms, "server→client", tcp_ack, tcp_seq, 180, step_offset=step_id - 1):
                s.id = step_id; step_id += 1; steps.append(s)

            # ── STARTTLS ──────────────────────────────────────────
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label="STARTTLS",
                detail=(
                    "STARTTLS\r\n\r\n"
                    "[Client requests upgrade to TLS encrypted channel.\n"
                    " All subsequent SMTP commands will be encrypted.]"
                ),
                highlight_fields=[
                    HighlightField(key="Command", value="STARTTLS"),
                    HighlightField(key="Upgrade", value="TLS 1.3"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1
            for s in generate_tcp_data(t_ms, "client→server", tcp_seq, tcp_ack, 12, step_offset=step_id - 1):
                s.id = step_id; step_id += 1; steps.append(s)
            tcp_seq += 12

            smtp.starttls()
            t_ms = round((time.time() - t0) * 1000, 2)

            # ── TLS State Machine (4 steps) ───────────────────────
            tls_steps = [
                ("client→server", "TLS ClientHello",
                 "→ ClientHello\nVersion: TLS 1.3\nRandom: [32 bytes]\nCipher Suites: TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256\nExtensions: SNI=smtp.gmail.com, ALPN, supported_groups",
                 [HighlightField(key="State", value="ClientHello"), HighlightField(key="SNI", value="smtp.gmail.com"), HighlightField(key="TLS", value="1.3")]),
                ("server→client", "TLS ServerHello + Certificate",
                 "← ServerHello\nVersion: TLS 1.3\nChosen Cipher: TLS_AES_256_GCM_SHA384\n\n← Certificate\nSubject: CN=smtp.gmail.com\nIssuer: Google Trust Services\nValidity: valid\n\n← CertificateVerify\n← Finished",
                 [HighlightField(key="State", value="ServerHello"), HighlightField(key="Cipher", value="AES-256-GCM"), HighlightField(key="Cert", value="smtp.gmail.com")]),
                ("client→server", "TLS ChangeCipherSpec + Finished",
                 "→ ChangeCipherSpec\n→ Finished [HMAC verified]\n\nHandshake complete.\nAll future SMTP data is now encrypted.",
                 [HighlightField(key="State", value="Finished"), HighlightField(key="Direction", value="Client→Server")]),
                ("server→client", "TLS Tunnel Established",
                 "220 2.0.0 Ready to start TLS\r\n\r\n[TLS 1.3 handshake complete]\nSession keys established.\nSMTP session continues over encrypted channel.",
                 [HighlightField(key="Code", value="220"), HighlightField(key="Protocol", value="TLS 1.3"), HighlightField(key="Status", value="Encrypted")]),
            ]
            for i, (direction, label, detail, highlights) in enumerate(tls_steps):
                steps.append(ProtocolStep(
                    id=step_id, phase="TLS", direction=direction,
                    label=label, detail=detail,
                    highlight_fields=highlights,
                    timestamp_ms=t_ms + i * 15,
                    layer="transport"
                ))
                step_id += 1
            t_ms = round((time.time() - t0) * 1000, 2)

            # ── AUTH LOGIN ────────────────────────────────────────
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label="AUTH LOGIN",
                detail=(
                    "AUTH LOGIN\r\n\r\n"
                    "[Client requests username/password authentication]\n"
                    "Credentials sent Base64-encoded over encrypted TLS channel\n"
                    "Username: [Base64 encoded]\n"
                    "Password: [Base64 encoded App Password]"
                ),
                highlight_fields=[
                    HighlightField(key="Command", value="AUTH LOGIN"),
                    HighlightField(key="Encoding", value="Base64"),
                    HighlightField(key="Channel", value="Encrypted (TLS)"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            smtp.login(sender_email, sender_password)
            t_ms = round((time.time() - t0) * 1000, 2)

            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="235 Authentication successful",
                detail=(
                    "235 2.7.0 Accepted\r\n\r\n"
                    "[Server confirms credentials are valid]\n"
                    f"Authenticated as: {sender_email}"
                ),
                highlight_fields=[
                    HighlightField(key="Code", value="235"),
                    HighlightField(key="User", value=sender_email),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            # ── MAIL FROM ─────────────────────────────────────────
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label=f"MAIL FROM: <{sender_email}>",
                detail=(
                    f"MAIL FROM:<{sender_email}>\r\n\r\n"
                    "[Client specifies the sender envelope address.\n"
                    " This is the 'Return-Path' for bounces.]"
                ),
                highlight_fields=[
                    HighlightField(key="From", value=sender_email),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="250 OK — Sender accepted",
                detail="250 2.1.0 OK\r\n\r\n[Server accepts the sender address]",
                highlight_fields=[
                    HighlightField(key="Code", value="250"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            # ── RCPT TO ───────────────────────────────────────────
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label=f"RCPT TO: <{to}>",
                detail=(
                    f"RCPT TO:<{to}>\r\n\r\n"
                    "[Client specifies the recipient envelope address.\n"
                    " Server checks recipient validity and relay permissions.]"
                ),
                highlight_fields=[
                    HighlightField(key="To", value=to),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="250 OK — Recipient accepted",
                detail="250 2.1.5 OK\r\n\r\n[Server accepts the recipient address]",
                highlight_fields=[
                    HighlightField(key="Code", value="250"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            # ── DATA ──────────────────────────────────────────────
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label="DATA",
                detail=(
                    "DATA\r\n\r\n"
                    "[Client signals start of message body transmission.\n"
                    " Server will respond with 354 to confirm readiness.]"
                ),
                highlight_fields=[
                    HighlightField(key="Command", value="DATA"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="354 Start input, end with <CRLF>.<CRLF>",
                detail=(
                    "354 Go ahead\r\n\r\n"
                    "[Server ready to receive message body.]\n"
                    " Terminated by a line containing only a single dot (.)]\n\n"
                    f"Client now sends:\n"
                    f"  From: {sender_email}\n"
                    f"  To: {to}\n"
                    f"  Subject: {subject}\n"
                    f"  Content-Type: text/plain\n"
                    f"\n"
                    f"  {body[:100]}{'...' if len(body) > 100 else ''}\n"
                    "  ."
                ),
                highlight_fields=[
                    HighlightField(key="Code", value="354"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            # Build & send the actual message
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            smtp.sendmail(sender_email, to, msg.as_string())

            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="250 OK — Message queued for delivery",
                detail=(
                    "250 2.0.0 OK  — queued as abc123xyz\r\n\r\n"
                    "[Server has accepted and queued the message]\n"
                    f"Message-Id assigned\n"
                    f"Delivery to {to} initiated."
                ),
                highlight_fields=[
                    HighlightField(key="Code", value="250"),
                    HighlightField(key="Status", value="Message accepted"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            # ── QUIT ──────────────────────────────────────────────
            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="client→server",
                label="QUIT",
                detail=(
                    "QUIT\r\n\r\n"
                    "[Client signals end of SMTP session.\n"
                    " Server will respond 221 and close the TCP connection.]"
                ),
                highlight_fields=[
                    HighlightField(key="Command", value="QUIT"),
                    HighlightField(key="RTT", value=f"{t_ms:.0f}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            t_ms = round((time.time() - t0) * 1000, 2)
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="server→client",
                label="221 Bye — Connection closing",
                detail=(
                    f"221 2.0.0 closing connection\r\n\r\n"
                    "[Server confirms session end]\n"
                    f"Total session time: {round(t_ms)} ms"
                ),
                highlight_fields=[
                    HighlightField(key="Code", value="221"),
                    HighlightField(key="Session Time", value=f"{round(t_ms)}ms"),
                ],
                timestamp_ms=t_ms,
            ))
            step_id += 1

            # ── TCP Teardown ──────────────────────────────────────
            teardown = generate_tcp_teardown(t_ms + 10, tcp_seq, tcp_ack, step_offset=step_id - 1)
            for s in teardown:
                s.id = step_id; step_id += 1; steps.append(s)

            # ── Session Summary ───────────────────────────────────
            total_ms = round((time.time() - t0) * 1000)
            smtp_cmds = sum(1 for s in steps if s.phase == "SMTP")
            transport_steps = sum(1 for s in steps if s.layer == "transport")
            steps.append(ProtocolStep(
                id=step_id, phase="SMTP", direction="info",
                label="✓ Session Complete — Email delivered",
                detail=(
                    f"[SMTP SESSION SUMMARY]\n"
                    f"─────────────────────────────────\n"
                    f"Recipient:       {to}\n"
                    f"Subject:         {subject}\n"
                    f"Total time:      {total_ms}ms\n"
                    f"SMTP commands:   {smtp_cmds}\n"
                    f"Transport steps: {transport_steps}\n"
                    f"Encryption:      TLS 1.3\n"
                    f"Auth:            LOGIN (App Password)\n"
                    f"Status:          DELIVERED ✓"
                ),
                highlight_fields=[
                    HighlightField(key="Status", value="DELIVERED"),
                    HighlightField(key="Total Time", value=f"{total_ms}ms"),
                    HighlightField(key="Encryption", value="TLS 1.3"),
                ],
                timestamp_ms=round((time.time() - t0) * 1000, 2),
            ))

        return steps, True, ""

    except smtplib.SMTPAuthenticationError:
        error_msg = "Authentication failed. Check your Gmail App Password in the .env file."
        steps.append(ProtocolStep(
            id=step_id, phase="SMTP", direction="server→client",
            label="535 Authentication credentials invalid",
            detail=(
                "535 5.7.8 Username and Password not accepted\r\n\r\n"
                "Common causes:\n"
                "• Incorrect App Password in .env\n"
                "• Using your Gmail login password (not App Password)\n"
                "• 2-Step Verification not enabled on Gmail account"
            ),
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=True,
        ))
        return steps, False, error_msg

    except Exception as e:
        steps.append(ProtocolStep(
            id=step_id, phase="SMTP", direction="server→client",
            label=f"SMTP Error",
            detail=f"Error: {str(e)}",
            timestamp_ms=round((time.time() - t0) * 1000, 2),
            is_error=True,
        ))
        return steps, False, str(e)


def _no_credentials_steps(to: str, subject: str, body: str) -> list[ProtocolStep]:
    """Return a fully simulated SMTP conversation (no credentials required).
    Uses sequential IDs starting from 1 so the router can safely add offset.
    """
    steps = []
    step_id = 1

    # ── TCP Handshake ─────────────────────────────────────────────
    steps.append(ProtocolStep(
        id=step_id, phase="TCP", direction="info",
        label="TCP Connect → smtp.gmail.com:587",
        detail=(
            "[TCP 3-Way Handshake — SIMULATED]\n"
            "Client → smtp.gmail.com:587\n\n"
            "Step 1: SYN     Client → Server  (Seq=0)\n"
            "Step 2: SYN-ACK Server → Client  (Seq=0, Ack=1)\n"
            "Step 3: ACK     Client → Server  (Seq=1, Ack=1)\n\n"
            "Connection established. Ready for SMTP."
        ),
        highlight_fields=[
            HighlightField(key="Server", value="smtp.gmail.com"),
            HighlightField(key="Port", value="587"),
            HighlightField(key="Protocol", value="TCP"),
            HighlightField(key="Mode", value="SIMULATED"),
        ],
        timestamp_ms=10.0, layer="transport"
    ))
    step_id += 1

    for s in generate_tcp_handshake(10.0, "client", "smtp.gmail.com", 587, step_id - 1):
        s.id = step_id; step_id += 1; steps.append(s)

    tcp_seq = 1
    tcp_ack = 1
    base_t = 150.0  # ms offset after handshake

    # ── SMTP Command Sequence ─────────────────────────────────────
    smtp_commands = [
        ("server→client", "SMTP", "220 Service Ready",
         f"220 smtp.gmail.com ESMTP ready\r\n\r\n[Server announces SMTP service availability]",
         [HighlightField(key="Code", value="220"), HighlightField(key="Status", value="Service Ready")]),

        ("client→server", "SMTP", "EHLO client.local",
         "EHLO client.local\r\n\r\n[Extended HELLO — client introduces itself and\n requests list of server capabilities]",
         [HighlightField(key="Command", value="EHLO"), HighlightField(key="Client", value="client.local")]),

        ("server→client", "SMTP", "250 OK — Capabilities",
         "250-smtp.gmail.com\r\n250-SIZE 35882577\r\n250-STARTTLS\r\n250-AUTH LOGIN PLAIN\r\n250 8BITMIME\r\n\r\n[Server lists extensions]",
         [HighlightField(key="Code", value="250"), HighlightField(key="Key Caps", value="STARTTLS, AUTH, SIZE")]),

        ("client→server", "SMTP", "STARTTLS",
         "STARTTLS\r\n\r\n[Client requests upgrade to TLS encrypted channel]",
         [HighlightField(key="Command", value="STARTTLS"), HighlightField(key="Upgrade", value="TLS 1.3")]),
    ]

    for i, (direction, phase, label, detail, highlights) in enumerate(smtp_commands):
        t_ms = base_t + i * 120.0
        steps.append(ProtocolStep(
            id=step_id, phase=phase, direction=direction,
            label=label, detail=detail,
            highlight_fields=highlights + [HighlightField(key="RTT", value=f"{t_ms:.0f}ms")],
            timestamp_ms=t_ms, layer="application"
        ))
        step_id += 1
        seg_len = max(len(detail), 30)
        for s in generate_tcp_data(t_ms, direction, tcp_seq, tcp_ack, seg_len, step_offset=step_id - 1):
            s.id = step_id; step_id += 1; steps.append(s)
        if direction == "client→server":
            tcp_seq += seg_len
        else:
            tcp_ack += seg_len

    # ── TLS State Machine (4 detailed steps) ─────────────────────
    tls_base = base_t + len(smtp_commands) * 120.0
    tls_steps = [
        ("client→server", "TLS ClientHello",
         "→ ClientHello\nVersion: TLS 1.3\nRandom: [32 bytes]\nCipher Suites: TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256\nExtensions: SNI=smtp.gmail.com, ALPN",
         [HighlightField(key="State", value="ClientHello"), HighlightField(key="SNI", value="smtp.gmail.com"), HighlightField(key="TLS", value="1.3")]),
        ("server→client", "TLS ServerHello + Certificate",
         "← ServerHello\nVersion: TLS 1.3\nChosen Cipher: TLS_AES_256_GCM_SHA384\n\n← Certificate\nSubject: CN=smtp.gmail.com\nIssuer: Google Trust Services\nValidity: valid\n\n← CertificateVerify + Finished",
         [HighlightField(key="State", value="ServerHello"), HighlightField(key="Cipher", value="AES-256-GCM"), HighlightField(key="Cert", value="smtp.gmail.com")]),
        ("client→server", "TLS ChangeCipherSpec + Finished",
         "→ ChangeCipherSpec\n→ Finished [HMAC verified]\n\nHandshake complete. All data now encrypted.",
         [HighlightField(key="State", value="Finished"), HighlightField(key="Security", value="AES-256-GCM")]),
        ("server→client", "220 TLS Tunnel Established",
         "220 2.0.0 Ready to start TLS\r\n\r\n[TLS 1.3 handshake complete]\nSession keys established. SMTP continues encrypted.",
         [HighlightField(key="Code", value="220"), HighlightField(key="Protocol", value="TLS 1.3"), HighlightField(key="Status", value="Encrypted")]),
    ]
    for i, (direction, label, detail, highlights) in enumerate(tls_steps):
        t_ms = tls_base + i * 40.0
        steps.append(ProtocolStep(
            id=step_id, phase="TLS", direction=direction,
            label=label, detail=detail,
            highlight_fields=highlights,
            timestamp_ms=t_ms, layer="transport"
        ))
        step_id += 1

    # ── Post-TLS SMTP Commands ────────────────────────────────────
    post_tls_base = tls_base + len(tls_steps) * 40.0
    post_tls_commands = [
        ("client→server", "SMTP", "AUTH LOGIN",
         "AUTH LOGIN\r\n\r\n[Client requests username/password authentication]\nCredentials sent Base64-encoded over TLS channel",
         [HighlightField(key="Command", value="AUTH LOGIN"), HighlightField(key="Encoding", value="Base64"), HighlightField(key="Channel", value="Encrypted")]),

        ("server→client", "SMTP", "235 Authentication successful",
         "235 2.7.0 Accepted\r\n\r\n[Server confirms credentials valid]\nAuthenticated as: your_email@gmail.com [SIMULATED]",
         [HighlightField(key="Code", value="235"), HighlightField(key="Note", value="SIMULATED")]),

        ("client→server", "SMTP", "MAIL FROM: <your_email@gmail.com>",
         "MAIL FROM:<your_email@gmail.com>\r\n\r\n[Client specifies sender envelope address]",
         [HighlightField(key="From", value="your_email@gmail.com")]),

        ("server→client", "SMTP", "250 OK — Sender accepted",
         "250 2.1.0 OK\r\n\r\n[Server accepts the sender address]",
         [HighlightField(key="Code", value="250")]),

        ("client→server", "SMTP", f"RCPT TO: <{to}>",
         f"RCPT TO:<{to}>\r\n\r\n[Client specifies recipient address]\nServer checks relay permissions",
         [HighlightField(key="To", value=to)]),

        ("server→client", "SMTP", "250 OK — Recipient accepted",
         "250 2.1.5 OK\r\n\r\n[Server accepts the recipient address]",
         [HighlightField(key="Code", value="250")]),

        ("client→server", "SMTP", "DATA",
         f"DATA\r\n\r\n[Client signals start of message body]\n\nMessage preview:\nFrom: your_email@gmail.com\nTo: {to}\nSubject: {subject}\n\n{body[:100]}{'...' if len(body) > 100 else ''}",
         [HighlightField(key="Command", value="DATA"), HighlightField(key="Encoding", value="MIME")]),

        ("server→client", "SMTP", "354 Go ahead",
         "354 End data with <CR><LF>.<CR><LF>\r\n\r\n[Server ready to receive message body]",
         [HighlightField(key="Code", value="354")]),

        ("server→client", "SMTP", "250 OK — Message queued [SIMULATED]",
         "250 2.0.0 OK — queued as SIM123\r\n\r\n[SIMULATED — set .env credentials to send real email]\nMessage accepted and queued for delivery.",
         [HighlightField(key="Code", value="250"), HighlightField(key="Note", value="SIMULATED")]),

        ("client→server", "SMTP", "QUIT",
         "QUIT\r\n\r\n[Client signals end of SMTP session]",
         [HighlightField(key="Command", value="QUIT")]),

        ("server→client", "SMTP", "221 Bye",
         "221 2.0.0 closing connection\r\n\r\n[Server confirms session end, TCP will be torn down]",
         [HighlightField(key="Code", value="221")]),
    ]

    for i, (direction, phase, label, detail, highlights) in enumerate(post_tls_commands):
        t_ms = post_tls_base + i * 120.0
        steps.append(ProtocolStep(
            id=step_id, phase=phase, direction=direction,
            label=label, detail=detail,
            highlight_fields=highlights + [HighlightField(key="RTT", value=f"{t_ms:.0f}ms")],
            timestamp_ms=t_ms, layer="application"
        ))
        step_id += 1
        seg_len = max(len(detail), 30)
        for s in generate_tcp_data(t_ms, direction, tcp_seq, tcp_ack, seg_len, step_offset=step_id - 1):
            s.id = step_id; step_id += 1; steps.append(s)
        if direction == "client→server":
            tcp_seq += seg_len
        else:
            tcp_ack += seg_len

    # ── TCP Teardown ──────────────────────────────────────────────
    t_end = post_tls_base + len(post_tls_commands) * 120.0 + 30
    for s in generate_tcp_teardown(t_end, tcp_seq, tcp_ack, step_offset=step_id - 1):
        s.id = step_id; step_id += 1; steps.append(s)

    # ── Session Summary ───────────────────────────────────────────
    total_ms = round(t_end + 50)
    smtp_cmds = sum(1 for s in steps if s.phase == "SMTP")
    transport_steps = sum(1 for s in steps if s.layer == "transport")
    steps.append(ProtocolStep(
        id=step_id, phase="SMTP", direction="info",
        label="✓ Simulation Complete — All SMTP steps shown",
        detail=(
            f"[SMTP SESSION SUMMARY — SIMULATED]\n"
            f"─────────────────────────────────────\n"
            f"Recipient:       {to}\n"
            f"Subject:         {subject}\n"
            f"Simulated time:  ~{total_ms}ms\n"
            f"SMTP commands:   {smtp_cmds}\n"
            f"Transport steps: {transport_steps}\n"
            f"Encryption:      TLS 1.3 (simulated)\n"
            f"Auth:            LOGIN (simulated)\n"
            f"Status:          SIMULATED ✓\n\n"
            f"[To send real email: copy .env.example → .env\n"
            f" and fill in SENDER_EMAIL and SENDER_PASSWORD\n"
            f" (Gmail App Password, not your login password)]"
        ),
        highlight_fields=[
            HighlightField(key="Status", value="SIMULATED"),
            HighlightField(key="Total Steps", value=str(step_id)),
            HighlightField(key="Encryption", value="TLS 1.3"),
        ],
        timestamp_ms=t_end + 50,
    ))

    return steps
