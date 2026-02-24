"""OAI-PMH harvester for Estonian university thesis repositories."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests
from lxml import etree

logger = logging.getLogger(__name__)

OAI_DC_PREFIX = "oai_dc"

# Namespaces used in OAI-PMH responses
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

# CS / data science keywords for filtering sets
CS_DATA_KEYWORDS = [
    "informaatika",
    "informatics",
    "computer science",
    "arvutiteadus",
    "data science",
    "andmeteadus",
    "tarkvaratehnika",
    "software engineering",
    "infotehnoloogia",
    "information technology",
    "matemaatika",
    "mathematics",
    "statistika",
    "statistics",
    "küberneetika",
    "cybernetics",
    "tehisintellekt",
    "artificial intelligence",
    "masinõpe",
    "machine learning",
]


@dataclass
class UniversityConfig:
    """Configuration for a single university's OAI-PMH endpoint."""

    key: str
    name: str
    base_url: str
    sets: list[str] = field(default_factory=list)


UNIVERSITIES: dict[str, UniversityConfig] = {
    "ut": UniversityConfig(
        key="ut",
        name="University of Tartu",
        base_url="https://dspace.ut.ee/oai/request",
    ),
    "taltech": UniversityConfig(
        key="taltech",
        name="TalTech",
        base_url="https://digikogu.taltech.ee/oai/request",
    ),
    "tlu": UniversityConfig(
        key="tlu",
        name="Tallinn University",
        base_url="https://www.etera.ee/oai",
    ),
}

REQUEST_DELAY_SECONDS = 2.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0


def _oai_request(
    base_url: str,
    params: dict[str, str],
    *,
    timeout: float = 30.0,
) -> etree._Element:
    """Make an OAI-PMH request with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(base_url, params=params, timeout=timeout)
            resp.raise_for_status()
            return etree.fromstring(resp.content)
        except (requests.RequestException, etree.XMLSyntaxError) as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = RETRY_BACKOFF_BASE ** (attempt + 1)
            logger.warning(
                "OAI request failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                MAX_RETRIES,
                wait,
                exc,
            )
            time.sleep(wait)
    raise RuntimeError("Unreachable")


def discover_sets(base_url: str, verbose: bool = False) -> list[tuple[str, str]]:
    """Discover OAI-PMH sets and filter for CS/data science ones.

    Returns list of (setSpec, setName) tuples.
    """
    logger.info("Discovering sets at %s", base_url)
    root = _oai_request(base_url, {"verb": "ListSets"})

    all_sets: list[tuple[str, str]] = []
    for set_elem in root.findall(".//oai:set", NS):
        spec_el = set_elem.find("oai:setSpec", NS)
        name_el = set_elem.find("oai:setName", NS)
        if spec_el is not None and spec_el.text:
            spec = spec_el.text
            name = name_el.text if name_el is not None and name_el.text else spec
            all_sets.append((spec, name))

    # Handle resumption tokens for large set lists
    while True:
        token_el = root.find(".//oai:resumptionToken", NS)
        if token_el is None or not token_el.text:
            break
        time.sleep(REQUEST_DELAY_SECONDS)
        root = _oai_request(base_url, {"verb": "ListSets", "resumptionToken": token_el.text})
        for set_elem in root.findall(".//oai:set", NS):
            spec_el = set_elem.find("oai:setSpec", NS)
            name_el = set_elem.find("oai:setName", NS)
            if spec_el is not None and spec_el.text:
                spec = spec_el.text
                name = name_el.text if name_el is not None and name_el.text else spec
                all_sets.append((spec, name))

    if verbose:
        logger.info("Found %d total sets", len(all_sets))

    # Filter for CS / data science related sets
    matched: list[tuple[str, str]] = []
    for spec, name in all_sets:
        name_lower = name.lower()
        if any(kw in name_lower for kw in CS_DATA_KEYWORDS):
            matched.append((spec, name))
            if verbose:
                logger.info("  Matched set: %s — %s", spec, name)

    logger.info("Matched %d CS/data science sets out of %d total", len(matched), len(all_sets))
    return matched


def harvest_records(
    base_url: str,
    sets: list[str] | None = None,
    from_date: str | None = None,
    until_date: str | None = None,
    verbose: bool = False,
) -> list[etree._Element]:
    """Harvest OAI-PMH records, optionally filtering by set and date range.

    Returns list of <record> XML elements.
    """
    all_records: list[etree._Element] = []

    # If no sets specified, harvest without set filter
    set_specs = sets if sets else [None]

    for set_spec in set_specs:
        params: dict[str, str] = {
            "verb": "ListRecords",
            "metadataPrefix": OAI_DC_PREFIX,
        }
        if set_spec:
            params["set"] = set_spec
        if from_date:
            params["from"] = from_date
        if until_date:
            params["until"] = until_date

        if verbose:
            logger.info(
                "Harvesting records: set=%s, from=%s, until=%s",
                set_spec or "(all)",
                from_date or "(any)",
                until_date or "(any)",
            )

        try:
            root = _oai_request(base_url, params)
        except requests.HTTPError as exc:
            # Some repos return errors for empty result sets
            if exc.response is not None and exc.response.status_code in (404, 422):
                logger.warning("No records found for set %s, skipping", set_spec)
                continue
            raise

        # Check for OAI-PMH error (e.g. noRecordsMatch)
        error_el = root.find(".//oai:error", NS)
        if error_el is not None:
            code = error_el.get("code", "")
            if code == "noRecordsMatch":
                logger.info("No records match for set %s", set_spec or "(all)")
                continue
            logger.warning("OAI-PMH error: %s — %s", code, error_el.text)
            continue

        records = root.findall(".//oai:record", NS)
        all_records.extend(records)

        # Handle resumption tokens (pagination)
        page = 1
        while True:
            token_el = root.find(".//oai:resumptionToken", NS)
            if token_el is None or not token_el.text:
                break
            page += 1
            if verbose:
                logger.info("  Fetching page %d (token: %s...)", page, token_el.text[:30])
            time.sleep(REQUEST_DELAY_SECONDS)
            root = _oai_request(
                base_url,
                {"verb": "ListRecords", "resumptionToken": token_el.text},
            )
            records = root.findall(".//oai:record", NS)
            all_records.extend(records)

        if verbose:
            logger.info("  Collected %d records so far", len(all_records))
        time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Total records harvested: %d", len(all_records))
    return all_records
