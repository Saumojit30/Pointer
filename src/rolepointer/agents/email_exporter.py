"""
RolePointer — RFC 5322 EML Generator & Mailto Deep Link Dispatcher
Enables 1-click desktop/mobile client handoff with pre-filled subject, headers, and pitch.
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Optional
from loguru import logger

OUTPUT_DIR = Path("generated_pdfs").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_eml_file(
    company: str,
    role_title: str,
    pitch_body: str,
    candidate_name: str = "Alex Morgan",
    candidate_email: str = "alex.morgan@example.com",
    recipient_email: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> str:
    """
    Generates a standard RFC 5322 compliant .eml file.
    Can be directly opened in Outlook, Apple Mail, Thunderbird, or uploaded to email clients.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    to_addr = recipient_email or f"careers@{company.lower().replace(' ', '')}.com"
    subject = f"Application: {role_title} — {candidate_name} ({company})"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{candidate_name} <{candidate_email}>"
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="rolepointer.local")
    msg["User-Agent"] = "RolePointer-Executive-Carrier/1.0"
    msg.set_content(pitch_body, subtype="plain", charset="utf-8")

    clean_comp = "".join(c for c in company if c.isalnum() or c in ("-", "_")).lower()
    clean_role = "".join(c for c in role_title if c.isalnum() or c in ("-", "_")).lower()
    filename = f"pitch_{clean_comp}_{clean_role}.eml"
    filepath = output_dir / filename

    with open(filepath, "wb") as f:
        f.write(msg.as_bytes())

    logger.info(f"[EmailExporter] Generated RFC 5322 EML file: {filename}")
    return filename


def generate_mailto_url(
    company: str,
    role_title: str,
    pitch_body: str,
    candidate_name: str = "Alex Morgan",
    recipient_email: Optional[str] = None,
) -> str:
    """
    Generates a URL-safe mailto: link for instantaneous browser-to-client handoff.
    """
    to_addr = recipient_email or f"careers@{company.lower().replace(' ', '')}.com"
    subject = f"Application: {role_title} — {candidate_name} ({company})"
    
    # URL encode parameters
    params = {
        "subject": subject,
        "body": pitch_body,
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"mailto:{to_addr}?{query}"
