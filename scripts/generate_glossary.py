from __future__ import annotations

import re
import unicodedata
import urllib.parse
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT_DIR / "data" / "terms.yml"
DOCS_DIR = ROOT_DIR / "docs"
TERMS_DIR = DOCS_DIR / "terms"
INDEX_FILE = DOCS_DIR / "index.md"

REPO_URL = "https://github.com/KristoR/andmed-et-en"
DISCUSSION_NEW_URL = f"{REPO_URL}/discussions/new?category=terminid"
CONTRIBUTING_URL = "contributing.md"

ESTONIAN_MAP = str.maketrans(
    {
        "õ": "o",
        "Õ": "o",
        "ä": "a",
        "Ä": "a",
        "ö": "o",
        "Ö": "o",
        "ü": "u",
        "Ü": "u",
    }
)


def normalize_text(value: str) -> str:
    value = value.translate(ESTONIAN_MAP)
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def slugify(value: str) -> str:
    value = normalize_text(value.strip().lower())
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "term"


def write_if_changed(path: Path, content: str) -> None:
    normalized = content.rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return
    path.write_text(normalized, encoding="utf-8")


def to_list_of_strings(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("alt.* must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def load_terms(path: Path) -> list[dict[str, object]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("data/terms.yml must contain a YAML list")

    terms: list[dict[str, object]] = []
    seen_en: set[str] = set()
    seen_slugs: set[str] = set()

    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entry #{index} must be an object")

        en = str(item.get("en", "")).strip()
        et = str(item.get("et", "")).strip()
        if not en or not et:
            raise ValueError(f"Entry #{index} must contain non-empty 'en' and 'et'")

        en_key = en.casefold()
        if en_key in seen_en:
            raise ValueError(f"Duplicate 'en' value detected: {en}")
        seen_en.add(en_key)

        slug = slugify(en)
        if slug in seen_slugs:
            raise ValueError(f"Duplicate slug detected for EN term: {en}")
        seen_slugs.add(slug)

        alt_obj = item.get("alt") or {}
        if alt_obj and not isinstance(alt_obj, dict):
            raise ValueError(f"Entry #{index} has invalid 'alt' value")

        alt_et = to_list_of_strings(alt_obj.get("et") if isinstance(alt_obj, dict) else None)
        alt_en = to_list_of_strings(alt_obj.get("en") if isinstance(alt_obj, dict) else None)

        definition = str(item.get("definition", "")).strip()
        example = str(item.get("example", "")).strip()

        references_raw = item.get("references") or []
        if not isinstance(references_raw, list):
            raise ValueError(f"Entry #{index} has invalid 'references' value")

        references: list[dict[str, str]] = []
        for ref_index, ref in enumerate(references_raw, start=1):
            if not isinstance(ref, dict):
                raise ValueError(f"Entry #{index} reference #{ref_index} must be an object")
            title = str(ref.get("title", "")).strip()
            url = str(ref.get("url", "")).strip()
            if not title or not url:
                raise ValueError(
                    f"Entry #{index} reference #{ref_index} must contain non-empty title and url"
                )
            references.append({"title": title, "url": url})

        # Parse thesis references (lõputööd)
        theses_raw = item.get("theses") or []
        if not isinstance(theses_raw, list):
            raise ValueError(f"Entry #{index} has invalid 'theses' value")

        theses: list[dict[str, str]] = []
        for t_index, thesis in enumerate(theses_raw, start=1):
            if not isinstance(thesis, dict):
                raise ValueError(f"Entry #{index} thesis #{t_index} must be an object")
            theses.append({
                "author": str(thesis.get("author", "")).strip(),
                "title_et": str(thesis.get("title_et", "")).strip(),
                "title_en": str(thesis.get("title_en", "")).strip(),
                "year": str(thesis.get("year", "")).strip(),
                "url": str(thesis.get("url", "")).strip(),
            })

        terms.append(
            {
                "en": en,
                "et": et,
                "slug": slug,
                "alt_et": alt_et,
                "alt_en": alt_en,
                "definition": definition,
                "references": references,
                "example": example,
                "theses": theses,
            }
        )

    return terms


def sort_key(value: str) -> str:
    return normalize_text(value).casefold()


def first_letter(value: str) -> str:
    normalized = normalize_text(value).strip()
    if not normalized:
        return "#"
    ch = normalized[0].upper()
    return ch if ch.isalpha() else "#"


def letter_anchor(prefix: str, letter: str) -> str:
    if letter == "#":
        return f"{prefix}-0-9"
    return f"{prefix}-{slugify(letter)}"


def render_letter_section(
    left_field: str,
    right_field: str,
    anchor_prefix: str,
    terms: list[dict[str, object]],
    indent: str = "",
) -> list[str]:
    """Render alphabetical letter-grouped list of terms."""
    sorted_terms = sorted(terms, key=lambda term: sort_key(str(term[left_field])))

    by_letter: dict[str, list[dict[str, object]]] = {}
    for term in sorted_terms:
        letter = first_letter(str(term[left_field]))
        by_letter.setdefault(letter, []).append(term)

    letters = sorted(by_letter.keys(), key=lambda x: (x == "#", x))

    lines: list[str] = []

    if letters:
        jump_links = [f"[{letter}](#{letter_anchor(anchor_prefix, letter)})" for letter in letters]
        lines.append(indent + " | ".join(jump_links))
        lines.append("")

    for letter in letters:
        lines.append(f"{indent}### {letter} {{#{letter_anchor(anchor_prefix, letter)}}}")
        lines.append("")
        for term in by_letter[letter]:
            left = str(term[left_field])
            right = str(term[right_field])
            link = f"terms/{term['slug']}.md"
            lines.append(f"{indent}- [{left}]({link}) — [{right}]({link})")
        lines.append("")

    return lines


def _discussion_url_for_term(en: str, et: str) -> str:
    """Build a pre-filled GitHub Discussion URL for a specific term."""
    title = f"Term: {en} / {et}"
    body = (
        f"## Termin\n\n"
        f"- **EN**: {en}\n"
        f"- **ET**: {et}\n\n"
        f"## Ettepanek\n\n"
        f"Kirjelda siia oma ettepanekut (uus tõlge, alternatiiv, definitsioon, parandus jne).\n\n"
        f"## Viited\n\n"
        f"Lisa viited, mis toetavad ettepanekut.\n"
    )
    params = urllib.parse.urlencode({"category": "terminid", "title": title, "body": body})
    return f"{REPO_URL}/discussions/new?{params}"


def render_term_page(term: dict[str, object]) -> str:
    en = str(term["en"])
    et = str(term["et"])
    alt_et = term["alt_et"]
    alt_en = term["alt_en"]
    definition = str(term["definition"])
    references = term["references"]
    example = str(term["example"])
    theses = term["theses"]

    discussion_url = _discussion_url_for_term(en, et)

    lines = [
        "<!-- AUTOGENERATED FILE. Muuda data/terms.yml faili. -->",
        "",
        f"# {et} — {en}",
        "",
        "## EN",
        "",
        en,
        "",
        "## EE",
        "",
        et,
        "",
        "## Alternatiivid",
        "",
    ]

    if alt_et or alt_en:
        if alt_et:
            lines.append(f"- EE: {', '.join(alt_et)}")
        if alt_en:
            lines.append(f"- EN: {', '.join(alt_en)}")
    else:
        lines.append("- Puudub")
    lines.append("")

    lines.extend(["## Definitsioon", ""])
    lines.append(definition if definition else "Puudub")
    lines.append("")

    lines.extend(["## Viited", ""])
    if references:
        for ref in references:
            lines.append(f"- [{ref['title']}]({ref['url']})")
    else:
        lines.append("- Puudub")
    lines.append("")

    lines.extend(["## Näide", ""])
    lines.append(example if example else "Puudub")
    lines.append("")

    # Thesis references section
    if theses:
        lines.extend(["## Lõputööd", ""])
        lines.append("Terminit on kasutatud järgmistes lõputöödes:")
        lines.append("")
        for thesis in theses:
            author = thesis.get("author", "")
            title_et = thesis.get("title_et", "")
            title_en = thesis.get("title_en", "")
            year = thesis.get("year", "")
            url = thesis.get("url", "")

            parts: list[str] = []
            if author:
                parts.append(f"**{author}**")
            if title_et and url:
                parts.append(f"[{title_et}]({url})")
            elif title_et:
                parts.append(f"*{title_et}*")
            if title_en:
                parts.append(f"({title_en})")
            if year:
                parts.append(f"({year})")

            lines.append(f"- {' '.join(parts) if parts else 'Puudub'}")
        lines.append("")

    # Suggest change link at the bottom
    lines.extend(
        [
            "---",
            "",
            f"[Soovita muudatust]({discussion_url}){{ .md-button .md-button--primary }}",
            "",
        ]
    )

    return "\n".join(lines)


def render_index(terms: list[dict[str, object]]) -> str:
    lines = [
        "<!-- AUTOGENERATED FILE. Muuda data/terms.yml faili. -->",
        "",
        "# EN ↔ ET andmevaldkonna sõnastik",
        "",
        f"Põhileht kuvab ainult vasteid. Detailid on iga termini alamlehel. **{len(terms)} terminit.**",
        "",
        f"[Soovita uut terminit]({DISCUSSION_NEW_URL}){{ .md-button }}",
        "",
        # Tab: EN → ET (default)
        '=== "EN → ET"',
        "",
    ]

    en_lines = render_letter_section("en", "et", "en", terms, indent="    ")
    lines.extend(en_lines)

    # Tab: ET → EN
    lines.append('=== "ET → EN"')
    lines.append("")

    et_lines = render_letter_section("et", "en", "et", terms, indent="    ")
    lines.extend(et_lines)

    # Tab: Kõik (both on one page)
    lines.append('=== "Kõik"')
    lines.append("")

    all_lines = render_letter_section("en", "et", "all", terms, indent="    ")
    lines.extend(all_lines)

    return "\n".join(lines)


def generate() -> None:
    terms = load_terms(DATA_FILE)

    TERMS_DIR.mkdir(parents=True, exist_ok=True)
    generated_paths: set[Path] = set()

    for term in terms:
        term_path = TERMS_DIR / f"{term['slug']}.md"
        write_if_changed(term_path, render_term_page(term))
        generated_paths.add(term_path)

    for existing in TERMS_DIR.glob("*.md"):
        if existing not in generated_paths:
            existing.unlink()

    write_if_changed(INDEX_FILE, render_index(terms))


def main() -> None:
    generate()
    print(f"Generated {INDEX_FILE.relative_to(ROOT_DIR)} and {len(list(TERMS_DIR.glob('*.md')))} term pages.")


if __name__ == "__main__":
    main()
