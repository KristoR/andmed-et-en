"""Parse OAI-PMH Dublin Core XML metadata into structured thesis records."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from lxml import etree

logger = logging.getLogger(__name__)

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

# Characters that appear frequently in Estonian but rarely in English
_ESTONIAN_CHARS = set("õäöüÕÄÖÜ")
_ESTONIAN_CHAR_PATTERN = re.compile(r"[õäöüÕÄÖÜ]")


@dataclass
class ThesisRecord:
    """Parsed thesis metadata."""

    identifier: str
    titles: list[str] = field(default_factory=list)
    title_en: str = ""
    title_et: str = ""
    authors: list[str] = field(default_factory=list)
    abstract_en: str = ""
    abstract_et: str = ""
    subjects: list[str] = field(default_factory=list)
    date: str = ""
    year: str = ""
    thesis_type: str = ""
    url: str = ""
    university: str = ""


def _detect_language(text: str) -> str:
    """Detect whether text is Estonian or English using a simple heuristic.

    Counts Estonian-specific characters (õ, ä, ö, ü). If the density
    exceeds a threshold, classify as Estonian.
    """
    if not text:
        return "unknown"
    estonian_count = len(_ESTONIAN_CHAR_PATTERN.findall(text))
    # If Estonian chars make up > 0.5% of the text, likely Estonian
    if len(text) > 0 and estonian_count / len(text) > 0.005:
        return "et"
    return "en"


def _extract_text(elements: list[etree._Element]) -> list[tuple[str, str]]:
    """Extract text and language from a list of XML elements.

    Returns list of (text, lang) tuples.
    """
    results: list[tuple[str, str]] = []
    for el in elements:
        text = (el.text or "").strip()
        if not text:
            continue
        # Try xml:lang attribute
        lang = el.get("{http://www.w3.org/XML/1998/namespace}lang", "")
        if not lang:
            lang = el.get("lang", "")
        if not lang:
            lang = _detect_language(text)
        results.append((text, lang.lower()))
    return results


def parse_record(record_el: etree._Element, university: str = "") -> ThesisRecord | None:
    """Parse a single OAI-PMH <record> element into a ThesisRecord.

    Returns None if the record is deleted or has no usable metadata.
    """
    # Check for deleted records
    header = record_el.find("oai:header", NS)
    if header is not None and header.get("status") == "deleted":
        return None

    # Get OAI identifier
    identifier_el = header.find("oai:identifier", NS) if header is not None else None
    identifier = identifier_el.text if identifier_el is not None and identifier_el.text else ""

    # Find the Dublin Core metadata
    metadata = record_el.find(".//oai_dc:dc", NS)
    if metadata is None:
        return None

    record = ThesisRecord(identifier=identifier, university=university)

    # Authors (dc:creator) — typically "Last, First" or "First Last"
    for creator_el in metadata.findall("dc:creator", NS):
        if creator_el.text and creator_el.text.strip():
            record.authors.append(creator_el.text.strip())

    # Titles — split by language
    title_pairs = _extract_text(metadata.findall("dc:title", NS))
    for title_text, lang in title_pairs:
        record.titles.append(title_text)
        if lang.startswith("et") and not record.title_et:
            record.title_et = title_text
        elif not record.title_en:
            record.title_en = title_text
    # If only one title and no language detected, assign to both
    if len(record.titles) == 1 and not record.title_en and not record.title_et:
        record.title_en = record.titles[0]

    # Descriptions (abstracts) — split by language
    descriptions = _extract_text(metadata.findall("dc:description", NS))
    en_parts: list[str] = []
    et_parts: list[str] = []
    for text, lang in descriptions:
        # Skip very short descriptions (likely not abstracts)
        if len(text) < 50:
            continue
        if lang.startswith("et"):
            et_parts.append(text)
        else:
            en_parts.append(text)
    record.abstract_en = " ".join(en_parts)
    record.abstract_et = " ".join(et_parts)

    # Subjects (keywords)
    for subj_text, _ in _extract_text(metadata.findall("dc:subject", NS)):
        # Some repos put multiple keywords in one element, comma-separated
        for part in subj_text.split(","):
            part = part.strip()
            if part:
                record.subjects.append(part)

    # Date — take the first one, also extract year
    dates = metadata.findall("dc:date", NS)
    for date_el in dates:
        if date_el.text and date_el.text.strip():
            record.date = date_el.text.strip()
            # Extract 4-digit year
            year_match = re.search(r"\b(19|20)\d{2}\b", record.date)
            if year_match:
                record.year = year_match.group(0)
            break

    # Type
    types = metadata.findall("dc:type", NS)
    for type_el in types:
        if type_el.text and type_el.text.strip():
            type_text = type_el.text.strip().lower()
            if any(kw in type_text for kw in ("thesis", "lõputöö", "magistri", "bakalaure", "doktori")):
                record.thesis_type = type_text
                break

    # URL — look for HTTP(S) identifiers
    for id_el in metadata.findall("dc:identifier", NS):
        if id_el.text and id_el.text.strip().startswith("http"):
            record.url = id_el.text.strip()
            break

    return record


def parse_records(
    record_elements: list[etree._Element],
    university: str = "",
) -> list[ThesisRecord]:
    """Parse a list of OAI-PMH record elements into ThesisRecords.

    Filters out deleted records and records without abstracts.
    """
    records: list[ThesisRecord] = []
    skipped = 0

    for el in record_elements:
        rec = parse_record(el, university=university)
        if rec is None:
            skipped += 1
            continue
        # Only keep records that have at least one abstract
        if not rec.abstract_en and not rec.abstract_et:
            skipped += 1
            continue
        records.append(rec)

    logger.info(
        "Parsed %d records with abstracts (%d skipped) for %s",
        len(records),
        skipped,
        university or "unknown",
    )
    return records
