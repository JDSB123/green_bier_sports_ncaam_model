#!/usr/bin/env python3
"""
Phase 0: Inventory ingestion endpoints used in-code.

Writes:
  - manifests/ingestion_endpoint_inventory.json

This is intentionally lightweight and conservative:
  - scans only code/script file types (no huge doc crawling)
  - caps stored occurrences per URL to keep output small
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]


URL_RE = re.compile(r"https?://[^\s\"'()<>\]]+")


def _utc_now_z() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _clean_url(raw: str) -> str:
    # Trim trailing punctuation that commonly sticks to URLs in code/docs.
    return raw.rstrip(").,;\"'")


def _classify(url: str) -> str:
    u = url.lower()
    if "site.api.espn.com" in u or "espn.com" in u:
        return "espn"
    if "the-odds-api.com" in u:
        return "the_odds_api"
    if "barttorvik.com" in u:
        return "barttorvik"
    if "api-sports.io" in u:
        return "basketball_api"
    if "microsoft.com" in u or "aka.ms" in u:
        return "microsoft"
    if "github.com" in u:
        return "github"
    return "other"


@dataclass
class Occurrence:
    path: str
    line: int
    excerpt: str


def _iter_code_files(base: Path, exts: set[str]) -> List[Path]:
    out: List[Path] = []
    if not base.exists():
        return out
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate ingestion endpoint inventory JSON"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "manifests" / "ingestion_endpoint_inventory.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--max-occurrences-per-url",
        type=int,
        default=10,
        help="Cap stored occurrences per URL",
    )
    args = parser.parse_args()

    output: Path = args.output
    if not output.is_absolute():
        output = (ROOT / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    exts = {
        ".py",
        ".go",
        ".rs",
        ".ps1",
        ".sh",
        ".dockerfile",
        ".toml",
        ".yml",
        ".yaml",
    }
    # Include Dockerfiles without extension by name:
    dockerfile_names = {"dockerfile"}

    roots = [
        ROOT / "services",
        ROOT / "testing",
        ROOT / "scripts",
        ROOT / "azure",
        ROOT / ".github",
    ]

    url_to_occ: Dict[str, List[Occurrence]] = {}

    files_scanned: int = 0
    for base in roots:
        for p in _iter_code_files(base, exts):
            files_scanned += 1
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for m in URL_RE.finditer(text):
                url = _clean_url(m.group(0))
                if not url:
                    continue

                # Compute line number by counting newlines up to match start.
                start = m.start()
                line_no = text.count("\n", 0, start) + 1
                # Extract containing line for context (bounded).
                line_start = text.rfind("\n", 0, start)
                line_end = text.find("\n", start)
                if line_start == -1:
                    line_start = 0
                else:
                    line_start += 1
                if line_end == -1:
                    line_end = min(len(text), line_start + 240)
                excerpt = text[line_start:line_end].strip()
                if len(excerpt) > 240:
                    excerpt = excerpt[:240] + "…"

                rel = str(p.resolve().relative_to(ROOT))
                occ = Occurrence(path=rel, line=line_no, excerpt=excerpt)

                lst = url_to_occ.setdefault(url, [])
                if len(lst) < int(args.max_occurrences_per_url):
                    lst.append(occ)

        # Also include Dockerfiles (no extension)
        if base.exists():
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if p.name.lower() not in dockerfile_names:
                    continue
                files_scanned += 1
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for m in URL_RE.finditer(text):
                    url = _clean_url(m.group(0))
                    if not url:
                        continue
                    start = m.start()
                    line_no = text.count("\n", 0, start) + 1
                    line_start = text.rfind("\n", 0, start)
                    line_end = text.find("\n", start)
                    if line_start == -1:
                        line_start = 0
                    else:
                        line_start += 1
                    if line_end == -1:
                        line_end = min(len(text), line_start + 240)
                    excerpt = text[line_start:line_end].strip()
                    if len(excerpt) > 240:
                        excerpt = excerpt[:240] + "…"
                    rel = str(p.resolve().relative_to(ROOT))
                    occ = Occurrence(path=rel, line=line_no, excerpt=excerpt)
                    lst = url_to_occ.setdefault(url, [])
                    if len(lst) < int(args.max_occurrences_per_url):
                        lst.append(occ)

    # Build inventory with classification
    inventory = []
    for url, occs in sorted(url_to_occ.items(), key=lambda kv: kv[0].lower()):
        inventory.append(
            {
                "url": url,
                "category": _classify(url),
                "occurrences": [occ.__dict__ for occ in occs],
            }
        )

    payload = {
        "generated_at": _utc_now_z(),
        "files_scanned": files_scanned,
        "roots_scanned": [
            str(p.resolve().relative_to(ROOT))
            for p in roots
            if p.exists()
        ],
        "unique_urls": len(inventory),
        "endpoints": inventory,
    }

    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

