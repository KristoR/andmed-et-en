"""Dual-strategy term extraction from thesis abstracts."""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from .parser import ThesisRecord
from .reference_terms import ReferenceTerm, get_all_terms, get_et_hints_map

logger = logging.getLogger(__name__)

# Words that are too generic to be useful as standalone NLP-discovered terms
STOPWORDS_EN = {
    "the", "a", "an", "this", "that", "these", "those", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "over", "then", "than", "but", "and", "or", "not",
    "no", "nor", "so", "too", "very", "just", "also", "more", "most", "much",
    "many", "such", "own", "same", "other", "each", "every", "both", "few",
    "all", "any", "some", "which", "who", "whom", "what", "where", "when",
    "how", "why", "it", "its", "we", "our", "they", "their", "them",
    "he", "she", "his", "her", "him", "i", "me", "my", "you", "your",
    "one", "two", "three", "first", "second", "third", "new", "used",
    "based", "using", "use", "used", "different", "well", "however",
    "proposed", "paper", "work", "study", "results", "approach", "method",
    "research", "thesis", "chapter", "section", "figure", "table",
    "present", "show", "provide", "main", "order", "case", "number",
    "given", "part", "found", "made", "several", "important",
}

# Generic noun phrases to filter out from NLP extraction
GENERIC_PHRASES = {
    "this thesis", "this work", "this paper", "this study", "this research",
    "the results", "the method", "the approach", "the system", "the model",
    "the data", "the process", "the problem", "the author", "the user",
    "previous work", "related work", "future work", "main goal",
    "master thesis", "bachelor thesis", "doctoral thesis",
}


@dataclass
class TermMatch:
    """A term found in thesis abstracts."""

    en: str
    et_hints: list[str] = field(default_factory=list)
    source: str = ""  # "curated", "nlp", or "both"
    confidence: str = ""  # "high", "medium"
    frequency: int = 0
    thesis_refs: list[dict[str, str]] = field(default_factory=list)
    category: str = ""


def _build_regex_pattern(term: str) -> re.Pattern[str]:
    """Build a word-boundary-aware regex pattern for a term."""
    escaped = re.escape(term)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def extract_curated_terms(
    records: list[ThesisRecord],
    reference_terms: list[ReferenceTerm] | None = None,
) -> dict[str, TermMatch]:
    """Match curated reference terms against thesis abstracts.

    Returns a dict of en_term (lowercased) → TermMatch.
    """
    if reference_terms is None:
        reference_terms = get_all_terms()

    # Pre-compile regex patterns for each term
    en_patterns: list[tuple[ReferenceTerm, re.Pattern[str]]] = []
    for ref in reference_terms:
        en_patterns.append((ref, _build_regex_pattern(ref.en)))

    # Also compile patterns for ET hints
    et_hint_patterns: list[tuple[ReferenceTerm, str, re.Pattern[str]]] = []
    for ref in reference_terms:
        for hint in ref.et_hints:
            if len(hint) >= 3:  # Skip very short hints
                et_hint_patterns.append((ref, hint, _build_regex_pattern(hint)))

    results: dict[str, TermMatch] = {}

    for record in records:
        found_in_record: set[str] = set()

        # Search English abstracts
        text_en = record.abstract_en
        if text_en:
            for ref, pattern in en_patterns:
                if pattern.search(text_en):
                    key = ref.en.lower()
                    found_in_record.add(key)

        # Search Estonian abstracts
        text_et = record.abstract_et
        if text_et:
            for ref, hint, pattern in et_hint_patterns:
                if pattern.search(text_et):
                    key = ref.en.lower()
                    found_in_record.add(key)

        # Also search subjects/keywords
        for subject in record.subjects:
            subject_lower = subject.lower()
            for ref, pattern in en_patterns:
                if pattern.search(subject_lower):
                    found_in_record.add(ref.en.lower())

        # Update results
        for key in found_in_record:
            if key not in results:
                ref_term = next((r for r in reference_terms if r.en.lower() == key), None)
                results[key] = TermMatch(
                    en=ref_term.en if ref_term else key,
                    et_hints=ref_term.et_hints if ref_term else [],
                    source="curated",
                    confidence="high",
                    category=ref_term.category if ref_term else "",
                )
            results[key].frequency += 1
            # Keep up to 3 sample thesis references
            if len(results[key].thesis_refs) < 3:
                title = record.titles[0] if record.titles else "(untitled)"
                results[key].thesis_refs.append({
                    "title": title,
                    "url": record.url,
                    "university": record.university,
                })

    logger.info("Curated matching found %d unique terms across %d records", len(results), len(records))
    return results


def extract_nlp_terms(
    records: list[ThesisRecord],
    min_frequency: int = 3,
) -> dict[str, TermMatch]:
    """Extract noun phrases from English abstracts using spaCy.

    Also extracts n-grams from Estonian abstracts.
    Returns dict of phrase (lowercased) → TermMatch for phrases appearing
    in at least min_frequency theses.
    """
    try:
        import spacy
    except ImportError:
        logger.warning("spaCy not installed, skipping NLP extraction")
        return {}

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.warning(
            "spaCy model en_core_web_sm not found. "
            "Run: uv run python -m spacy download en_core_web_sm"
        )
        return {}

    # Count how many theses each phrase appears in
    phrase_thesis_count: Counter[str] = Counter()
    phrase_thesis_refs: dict[str, list[dict[str, str]]] = {}

    for record in records:
        found_phrases: set[str] = set()

        # English NLP extraction
        if record.abstract_en:
            doc = nlp(record.abstract_en)
            for chunk in doc.noun_chunks:
                phrase = chunk.text.strip().lower()
                # Filter: 2-4 words, not purely stopwords, not generic
                words = phrase.split()
                if len(words) < 2 or len(words) > 4:
                    continue
                if phrase in GENERIC_PHRASES:
                    continue
                # At least one content word (not a stopword)
                content_words = [w for w in words if w not in STOPWORDS_EN]
                if not content_words:
                    continue
                # Skip if starts/ends with a stopword-only prefix
                if words[0] in {"the", "a", "an", "this", "that", "these", "those"}:
                    phrase = " ".join(words[1:])
                    if len(phrase.split()) < 2:
                        continue
                found_phrases.add(phrase)

        # Estonian n-gram extraction (simple approach since no spaCy model)
        if record.abstract_et:
            et_words = re.findall(r"[a-zõäöüšž]+", record.abstract_et.lower())
            for n in (2, 3):
                for i in range(len(et_words) - n + 1):
                    ngram = " ".join(et_words[i : i + n])
                    # Basic filtering: each word at least 3 chars
                    parts = ngram.split()
                    if all(len(p) >= 3 for p in parts):
                        found_phrases.add(ngram)

        # Update counts
        for phrase in found_phrases:
            phrase_thesis_count[phrase] += 1
            if phrase not in phrase_thesis_refs:
                phrase_thesis_refs[phrase] = []
            if len(phrase_thesis_refs[phrase]) < 3:
                title = record.titles[0] if record.titles else "(untitled)"
                phrase_thesis_refs[phrase].append({
                    "title": title,
                    "url": record.url,
                    "university": record.university,
                })

    # Filter by minimum frequency
    results: dict[str, TermMatch] = {}
    for phrase, count in phrase_thesis_count.items():
        if count >= min_frequency:
            results[phrase] = TermMatch(
                en=phrase,
                source="nlp",
                confidence="medium",
                frequency=count,
                thesis_refs=phrase_thesis_refs.get(phrase, []),
            )

    logger.info(
        "NLP extraction found %d phrases with frequency >= %d",
        len(results),
        min_frequency,
    )
    return results


def extract_terms(
    records: list[ThesisRecord],
    existing_terms: set[str],
    min_frequency: int = 3,
) -> tuple[list[TermMatch], list[TermMatch], list[TermMatch]]:
    """Run both extraction strategies and compare against existing glossary.

    Args:
        records: Parsed thesis records.
        existing_terms: Set of existing EN terms (lowercased) from terms.yml.
        min_frequency: Minimum thesis mentions for NLP-discovered terms.

    Returns:
        Tuple of (missing_terms, confirmed_terms, nlp_novel_terms):
        - missing_terms: Curated terms found in theses but not in glossary.
        - confirmed_terms: Curated terms found in theses that ARE in glossary.
        - nlp_novel_terms: NLP-discovered terms not in curated list or glossary.
    """
    # Strategy A: Curated list matching
    curated_results = extract_curated_terms(records)

    # Strategy B: NLP extraction
    nlp_results = extract_nlp_terms(records, min_frequency=min_frequency)

    # Separate curated results into missing vs confirmed
    missing_terms: list[TermMatch] = []
    confirmed_terms: list[TermMatch] = []

    for key, match in curated_results.items():
        if key in existing_terms:
            confirmed_terms.append(match)
        else:
            missing_terms.append(match)

    # Find NLP terms not already covered by curated list or glossary
    curated_keys = set(curated_results.keys())
    et_hints_map = get_et_hints_map()

    nlp_novel: list[TermMatch] = []
    for key, match in nlp_results.items():
        # Skip if already found by curated matching
        if key in curated_keys:
            continue
        # Skip if it's an ET hint for a known term
        if key in et_hints_map:
            continue
        # Skip if already in glossary
        if key in existing_terms:
            continue
        nlp_novel.append(match)

    # Sort by frequency (descending)
    missing_terms.sort(key=lambda m: m.frequency, reverse=True)
    confirmed_terms.sort(key=lambda m: m.frequency, reverse=True)
    nlp_novel.sort(key=lambda m: m.frequency, reverse=True)

    logger.info(
        "Term extraction summary: %d missing, %d confirmed, %d novel NLP terms",
        len(missing_terms),
        len(confirmed_terms),
        len(nlp_novel),
    )

    return missing_terms, confirmed_terms, nlp_novel
