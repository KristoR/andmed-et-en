from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT_DIR / "data" / "terms.yml"
DOCS_DIR = ROOT_DIR / "docs"
TERMS_DIR = DOCS_DIR / "terms"
INDEX_FILE = DOCS_DIR / "index.md"
CONTRIBUTING_DISCUSSION_LINK = "../contributing.md#vaidlused-ja-github-discussions"

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


def render_index_section(
    title: str,
    left_field: str,
    right_field: str,
    anchor_prefix: str,
    terms: list[dict[str, object]],
) -> list[str]:
    sorted_terms = sorted(terms, key=lambda term: sort_key(str(term[left_field])))

    by_letter: dict[str, list[dict[str, object]]] = {}
    for term in sorted_terms:
        letter = first_letter(str(term[left_field]))
        by_letter.setdefault(letter, []).append(term)

    letters = sorted(by_letter.keys(), key=lambda x: (x == "#", x))

    lines = [f"## {title}", ""]

    if letters:
        jump_links = [f"[{letter}](#{letter_anchor(anchor_prefix, letter)})" for letter in letters]
        lines.append(" | ".join(jump_links))
        lines.append("")

    for letter in letters:
        lines.append(f"### {letter} {{#{letter_anchor(anchor_prefix, letter)}}}")
        lines.append("")
        for term in by_letter[letter]:
            left = str(term[left_field])
            right = str(term[right_field])
            link = f"terms/{term['slug']}.md"
            lines.append(f"- [{left}]({link}) — [{right}]({link})")
        lines.append("")

    return lines


def render_term_page(term: dict[str, object]) -> str:
    en = str(term["en"])
    et = str(term["et"])
    alt_et = term["alt_et"]
    alt_en = term["alt_en"]
    definition = str(term["definition"])
    references = term["references"]
    example = str(term["example"])

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

    lines.extend(
        [
            "## Arutelu",
            "",
            f"- Ava vaidluse korral teema [GitHub Discussionsis]({CONTRIBUTING_DISCUSSION_LINK}).",
            f"- Soovituslik pealkiri: `Term: {en} / {et}`",
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
        "Põhileht kuvab ainult vasteid. Detailid on iga termini alamlehel.",
        "",
    ]

    lines.extend(render_index_section("ET → EN", "et", "en", "et", terms))
    lines.extend(render_index_section("EN → ET", "en", "et", "en", terms))

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
