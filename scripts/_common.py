"""
Shared helpers for the design-system-assets scripts.

Stdlib-only on purpose: the skill ships zero install dependencies. If you
add anything here, keep it that way.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_json_file(path: str | Path, label: str = "file", exit_code: int = 1) -> Any:
    """
    Read and parse a JSON file with friendly, single-line errors.

    On missing path / unreadable file / malformed JSON, prints to stderr and
    exits with `exit_code`. Used at CLI boundaries so a bad input file
    surfaces a useful message instead of a stack trace.
    """
    p = Path(path)
    if not p.exists():
        print(f"ERROR: {label} not found: {p}", file=sys.stderr)
        sys.exit(exit_code)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: {label} is not valid JSON ({p}): {e}", file=sys.stderr)
        sys.exit(exit_code)
    except OSError as e:
        print(f"ERROR: cannot read {label} ({p}): {e}", file=sys.stderr)
        sys.exit(exit_code)


def post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 120,
    provider_name: str = "API",
) -> dict[str, Any]:
    """
    POST a JSON body and return the parsed JSON response.

    Wraps HTTPError / URLError into a single RuntimeError carrying the
    provider name and a truncated response body — that's the pattern every
    API-calling script in this repo was duplicating.
    """
    payload_bytes = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=payload_bytes,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{provider_name} returned {e.code}: {err_body[:500]}"
        ) from e
    except URLError as e:
        raise RuntimeError(f"Network error calling {provider_name}: {e}") from e


def get_bytes(url: str, timeout: int = 60) -> bytes:
    """GET raw bytes (for image URL fetches). Same error wrapping as post_json."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            return resp.read()
    except HTTPError as e:
        raise RuntimeError(f"GET {url} returned {e.code}") from e
    except URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e
