# PURPOSE OF THE FILE -- PII REDACTION: mask private data before it is STORED.
#
# Phase 5a's audit trail stores every question verbatim. A question like
# "why did priya@acme.com log in from 10.0.4.17 with password=Summer2026?"
# would put an email, an IP and a password into a long-lived index that many
# people can read. This module masks those parts:
#
#   "why did [REDACTED_EMAIL] log in from [REDACTED_IP] with password=[REDACTED_SECRET]?"
#
# WHERE it runs (and where it deliberately does not):
#   - audit events (app/audit_ph5.py)  -> redacted before publishing
#   - log lines that echo the question (app/tracing_ph3.py, app/main_ph1.py)
#   - NOT the answer sent back to the analyst: a security copilot that hides
#     the attacker's IP from the person investigating it is useless. Live
#     users are protected by RBAC (Phase 5c); stored copies by this file.
#
# HOW: plain regular expressions, no ML model. Fast (microseconds), no extra
# download, and every rule can be read and tested. The trade-off: regex can't
# spot a bare person's name ("ask Ravi about it") - that needs an NLP model
# such as Microsoft Presidio, a possible later upgrade.
#
# Rule ORDER matters: secrets first (so "token=abc@x.com" is masked as a
# secret, not half-masked as an email), then structured numbers (card,
# Aadhaar) before the looser phone rule that could otherwise eat their digits.

import re
from dataclasses import dataclass, field

from . import config_ph1 as config


def _luhn_ok(digits: str) -> bool:
    """Credit cards end in a checksum digit (the Luhn algorithm). Checking it
    stops random long numbers - order IDs, timestamps - being masked as cards."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

# (label, compiled pattern, which regex group to replace - 0 = whole match)
# Group > 0 is used where we keep a prefix for readability: in
# "password=hunter2" we keep "password=" and mask only "hunter2".
_RULES: list[tuple[str, re.Pattern, int]] = [
    # --- secrets -----------------------------------------------------------
    ("SECRET", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), 0),
    ("SECRET", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),                      # AWS access key id
    ("SECRET", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), 0),            # GitHub token
    ("SECRET", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), 0),                 # OpenAI-style key
    ("SECRET", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), 0),          # Slack token
    ("SECRET", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), 0),  # JWT
    ("SECRET", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{16,})"), 1),
    ("SECRET", re.compile(
        r"(?i)\b(?:password|passwd|pwd|pass|secret|token|api[_-]?key|access[_-]?key)"
        r"\s*[:=]\s*[\"']?([^\s\"',;]*[^\s\"',;?)])"), 1),  # a trailing "?" ends the question, not the password
    # --- contact details ---------------------------------------------------
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), 0),
    # --- government / financial numbers -------------------------------------
    ("CARD", re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), 0),                    # checked by Luhn below
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b"), 0),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), 0),
    ("PHONE", re.compile(r"(?<![\w+])(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}\b"), 0),  # Indian mobile
    ("PHONE", re.compile(r"(?<![\w+])\+\d{1,3}[ -]?\(?\d{1,4}\)?(?:[ -]?\d{2,4}){2,4}\b"), 0),  # +CC intl
    # --- identities on the network -------------------------------------------
    ("USERNAME", re.compile(r"(?i)\b(?:user(?:name)?|login|account)\s*[:=]\s*[\"']?([A-Za-z0-9._\\-]{2,})"), 1),
    ("IP", re.compile(rf"\b{_OCTET}(?:\.{_OCTET}){{3}}\b"), 0),
]


@dataclass
class Redaction:
    text: str
    # e.g. {"EMAIL": 1, "IP": 2} - what was found (never the values themselves),
    # stored on the audit event so you can search "which questions held PII?"
    found: dict[str, int] = field(default_factory=dict)


def redact(text: str | None, *, mask_ips: bool | None = None) -> Redaction:
    """Returns a masked copy of `text` plus counts of what was masked.
    Never raises - redaction failing must not break the request it protects."""
    if not text:
        return Redaction(text or "")
    if mask_ips is None:
        mask_ips = config.PII_REDACT_IPS

    found: dict[str, int] = {}
    out = text
    for label, pattern, group in _RULES:
        if label == "IP" and not mask_ips:
            continue

        def _sub(m: re.Match, label=label, group=group) -> str:
            if label == "CARD" and not _luhn_ok(re.sub(r"\D", "", m.group(0))):
                return m.group(0)  # long number, but not a real card - leave it
            found[label] = found.get(label, 0) + 1
            placeholder = f"[REDACTED_{label}]"
            if group == 0:
                return placeholder
            # keep the "password=" prefix, mask only the captured value
            start, end = m.span(group)
            base = m.start(0)
            whole = m.group(0)
            return whole[: start - base] + placeholder + whole[end - base:]

        try:
            out = pattern.sub(_sub, out)
        except Exception:  # pragma: no cover - defensive, regex sub shouldn't fail
            continue
    return Redaction(out, found)


def redact_text(text: str | None) -> str:
    """Shortcut when only the masked string is needed (log lines)."""
    return redact(text).text
