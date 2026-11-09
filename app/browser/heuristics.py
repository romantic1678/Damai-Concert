"""Page heuristics — detect likely human-verification needs. Never solves them."""

from __future__ import annotations

import re

# Keywords that suggest the user must intervene (captcha / queue / verify).
_TAKEOVER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"验证码"),
    re.compile(r"滑块"),
    re.compile(r"排队"),
    re.compile(r"人机验证"),
    re.compile(r"安全验证"),
    re.compile(r"captcha", re.I),
    re.compile(r"recaptcha", re.I),
)


def needs_human_verification(title: str, body_text: str) -> str | None:
    """Return a short reason if page likely needs human verification, else None."""
    blob = f"{title}\n{body_text}"
    for pattern in _TAKEOVER_PATTERNS:
        if pattern.search(blob):
            return f"detected:{pattern.pattern}"
    return None


def looks_blank(title: str, body_text: str) -> bool:
    return not (title or "").strip() and len((body_text or "").strip()) < 20


def looks_http_error_page(title: str, body_text: str) -> bool:
    blob = f"{title}\n{body_text}".lower()
    return any(
        token in blob
        for token in ("500", "502", "503", "internal server error", "bad gateway", "页面异常")
    )
