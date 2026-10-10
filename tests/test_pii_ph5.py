# Phase 5b tests - run with: python -m pytest -q
# No Elasticsearch, Redis, Redpanda or Ollama needed: pure-Python checks.

import pytest

from app.pii_ph5 import redact


@pytest.mark.parametrize(
    "text, label",
    [
        ("contact priya.k@acme.com now", "EMAIL"),
        ("call +91 98765 43210", "PHONE"),
        ("call 9876543210", "PHONE"),
        ("aadhaar 2345 6789 0123", "AADHAAR"),
        ("PAN ABCDE1234F", "PAN"),
        ("card 4111 1111 1111 1111", "CARD"),            # Luhn-valid test card
        ("key AKIAIOSFODNN7EXAMPLE leaked", "SECRET"),
        ("password=Summer2026!", "SECRET"),
        ("Authorization: Bearer abcdefghijklmnop1234", "SECRET"),
        ("login from 10.0.4.17", "IP"),
        ("username: rkumar failed", "USERNAME"),
    ],
)
def test_each_kind_is_masked(text, label):
    r = redact(text)
    assert f"[REDACTED_{label}]" in r.text
    assert r.found.get(label) == 1


def test_value_is_gone_but_prefix_kept():
    r = redact("why did password=hunter2 fail?")
    assert "hunter2" not in r.text
    assert "password=[REDACTED_SECRET]" in r.text


def test_mixed_question():
    q = "why did priya@acme.com log in from 10.0.4.17 with password=Summer2026?"
    r = redact(q)
    assert r.text == (
        "why did [REDACTED_EMAIL] log in from [REDACTED_IP] "
        "with password=[REDACTED_SECRET]?"
    )
    assert r.found == {"EMAIL": 1, "IP": 1, "SECRET": 1}


@pytest.mark.parametrize(
    "text",
    [
        "What is the ransomware runbook?",
        "incident 2026-0142 on 2026-10-04 at 14:32",
        "order number 1234567890123",         # 13 digits, fails Luhn -> not a card
        "version 1.2.3 released",               # not an IP (only 3 parts)
        "port 8080 and 9200",
    ],
)
def test_clean_text_untouched(text):
    r = redact(text)
    assert r.text == text
    assert r.found == {}


def test_ips_can_be_kept():
    r = redact("login from 10.0.4.17", mask_ips=False)
    assert r.text == "login from 10.0.4.17"


def test_empty_and_none():
    assert redact("").text == ""
    assert redact(None).text == ""
