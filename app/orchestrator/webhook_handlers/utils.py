"""Shared utilities for Help Scout webhook event handlers."""

import re
from typing import Any, Dict


def extract_thread_body(thread_data: Dict[str, Any]) -> str:
    """Extract plain text from a Help Scout thread (strip HTML)."""
    body = thread_data.get("body") or ""
    if isinstance(body, str):
        body = re.sub(r"<[^>]+>", "", body)
    return (body or "").strip()
