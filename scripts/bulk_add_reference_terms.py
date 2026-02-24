"""Bulk-add reference terms to data/terms.yml.

One-time script to populate the glossary with the curated reference terms
as minimal entries (en + et). These can be enriched later with definitions,
references, and examples.

Usage:
    uv run python scripts/bulk_add_reference_terms.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from thesis.reference_terms import get_all_terms

ROOT_DIR = Path(__file__).resolve().parents[1]
TERMS_FILE = ROOT_DIR / "data" / "terms.yml"


def load_existing_en_terms(path: Path) -> set[str]:
    """Return set of existing EN terms (lowercased) to avoid duplicates."""
    if not path.exists():
        return set()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw or not isinstance(raw, list):
        return set()
    terms: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            en = str(item.get("en", "")).strip().lower()
            if en:
                terms.add(en)
    return terms


def main() -> None:
    existing = load_existing_en_terms(TERMS_FILE)
    print(f"Existing terms in glossary: {len(existing)}")

    # Load current terms.yml content
    if TERMS_FILE.exists():
        current_entries = yaml.safe_load(TERMS_FILE.read_text(encoding="utf-8")) or []
    else:
        current_entries = []

    added = 0
    skipped = 0

    for ref in get_all_terms():
        if ref.en.lower() in existing:
            skipped += 1
            continue

        # Use first ET hint as the primary translation
        if not ref.et_hints:
            skipped += 1
            continue

        et_primary = ref.et_hints[0]
        et_alternatives = ref.et_hints[1:] if len(ref.et_hints) > 1 else []

        entry: dict = {
            "en": ref.en,
            "et": et_primary,
        }

        # Add alternatives if any
        if et_alternatives:
            entry["alt"] = {"et": et_alternatives, "en": []}
        else:
            entry["alt"] = {"et": [], "en": []}

        current_entries.append(entry)
        existing.add(ref.en.lower())
        added += 1

    # Write back
    TERMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TERMS_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(
            current_entries,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    print(f"Added {added} new terms, skipped {skipped} (already exist or no ET hint)")
    print(f"Total terms now: {len(current_entries)}")


if __name__ == "__main__":
    main()
