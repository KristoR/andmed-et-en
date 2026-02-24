"""Fetch theses from Estonian universities and discover missing glossary terms.

Usage:
    uv run python scripts/fetch_theses.py [OPTIONS]

Examples:
    # Small test run (one university, recent theses)
    uv run python scripts/fetch_theses.py --universities ut --from-date 2024-01-01 --verbose

    # Full historical run
    uv run python scripts/fetch_theses.py --full --from-date 2015-01-01

    # Monthly incremental run (uses saved state)
    uv run python scripts/fetch_theses.py
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path

import yaml

# Add parent directory to path so thesis package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from thesis.harvester import UNIVERSITIES, discover_sets, harvest_records
from thesis.parser import parse_records
from thesis.reporter import generate_candidate_yaml, print_summary
from thesis.term_extractor import extract_terms

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
TERMS_FILE = DATA_DIR / "terms.yml"
STATE_FILE = DATA_DIR / "harvest_state.json"
DEFAULT_OUTPUT = DATA_DIR / "candidate_terms.yml"

DEFAULT_FROM_DATE = "2015-01-01"


def load_existing_terms(path: Path) -> set[str]:
    """Load existing glossary terms and return a set of EN terms (lowercased)."""
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
            # Also add alternatives
            alt = item.get("alt")
            if isinstance(alt, dict):
                for alt_en in alt.get("en", []) or []:
                    alt_str = str(alt_en).strip().lower()
                    if alt_str:
                        terms.add(alt_str)
    return terms


def load_state(path: Path) -> dict:
    """Load harvest state from JSON file."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    """Save harvest state to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Estonian university theses and discover missing glossary terms.",
    )
    parser.add_argument(
        "--from-date",
        help=f"Start date YYYY-MM-DD (default: from state or {DEFAULT_FROM_DATE})",
    )
    parser.add_argument(
        "--until-date",
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore saved state, do full run from --from-date",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output candidate terms file (default: {DEFAULT_OUTPUT.relative_to(ROOT_DIR)})",
    )
    parser.add_argument(
        "--universities",
        help="Comma-separated: ut,taltech,tlu (default: all)",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=3,
        help="Minimum thesis mentions for NLP-discovered terms (default: 3)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Determine which universities to harvest
    if args.universities:
        uni_keys = [k.strip().lower() for k in args.universities.split(",")]
        for k in uni_keys:
            if k not in UNIVERSITIES:
                parser.error(f"Unknown university: {k}. Available: {', '.join(UNIVERSITIES)}")
    else:
        uni_keys = list(UNIVERSITIES.keys())

    # Load state
    state = load_state(STATE_FILE)
    if args.full:
        state = {}

    # Determine date range
    until_date = args.until_date or datetime.date.today().isoformat()

    # Load existing glossary terms
    existing_terms = load_existing_terms(TERMS_FILE)
    logging.info("Loaded %d existing glossary terms", len(existing_terms))

    # Harvest and parse records from each university
    all_records = []
    thesis_counts: dict[str, int] = {}

    for uni_key in uni_keys:
        uni = UNIVERSITIES[uni_key]
        logging.info("=" * 40)
        logging.info("Processing %s (%s)", uni.name, uni.base_url)
        logging.info("=" * 40)

        # Determine from_date for this university
        uni_state = state.get("universities", {}).get(uni_key, {})
        if args.from_date:
            from_date = args.from_date
        elif uni_state.get("last_harvest_date"):
            from_date = uni_state["last_harvest_date"]
        else:
            from_date = DEFAULT_FROM_DATE

        # Discover CS/data science sets
        cached_sets = uni_state.get("sets")
        if cached_sets and not args.full:
            set_specs = cached_sets
            logging.info("Using %d cached sets for %s", len(set_specs), uni.name)
        else:
            try:
                matched_sets = discover_sets(uni.base_url, verbose=args.verbose)
                set_specs = [spec for spec, _ in matched_sets]
            except Exception as exc:
                logging.error("Failed to discover sets for %s: %s", uni.name, exc)
                set_specs = []

        if not set_specs:
            logging.warning(
                "No CS/data science sets found for %s. "
                "Trying harvest without set filter...",
                uni.name,
            )

        # Harvest records
        try:
            raw_records = harvest_records(
                uni.base_url,
                sets=set_specs if set_specs else None,
                from_date=from_date,
                until_date=until_date,
                verbose=args.verbose,
            )
        except Exception as exc:
            logging.error("Failed to harvest records from %s: %s", uni.name, exc)
            raw_records = []

        # Parse records
        records = parse_records(raw_records, university=uni_key)
        all_records.extend(records)
        thesis_counts[uni_key] = len(records)
        logging.info("Got %d thesis records with abstracts from %s", len(records), uni.name)

        # Update state for this university
        if "universities" not in state:
            state["universities"] = {}
        state["universities"][uni_key] = {
            "last_harvest_date": until_date,
            "sets": set_specs,
            "total_records_harvested": len(raw_records),
        }

    if not all_records:
        logging.warning("No thesis records found. Check connectivity and set filters.")
        save_state(STATE_FILE, state)
        return

    # Extract terms
    logging.info("Extracting terms from %d thesis records...", len(all_records))
    missing_terms, confirmed_terms, nlp_novel_terms = extract_terms(
        all_records,
        existing_terms,
        min_frequency=args.min_frequency,
    )

    # Generate report
    generate_candidate_yaml(missing_terms, nlp_novel_terms, args.output)

    # Print summary
    from_date_display = args.from_date or DEFAULT_FROM_DATE
    print_summary(
        missing_terms,
        confirmed_terms,
        nlp_novel_terms,
        thesis_counts,
        from_date=from_date_display,
        until_date=until_date,
    )

    # Save state
    state["last_run"] = datetime.datetime.now().isoformat()
    save_state(STATE_FILE, state)
    logging.info("State saved to %s", STATE_FILE.relative_to(ROOT_DIR))
    logging.info("Candidate terms saved to %s", args.output.relative_to(ROOT_DIR))


if __name__ == "__main__":
    main()
