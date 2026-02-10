# Terminoloogia

Avalik EN ↔ ET andmevaldkonna mõistete sõnastik, mis builditakse MkDocsiga ja deploy’itakse GitHub Pagesi.

## Kasutamine

- Sirvi vasteid: `docs/index.md` (genereeritud)
- Otsi mõisteid: päise otsing (Material search)
- Ava detailid: `docs/terms/<slug>.md` (genereeritud)

## Kuidas panustada

1. Muuda ainult `data/terms.yml` faili.
2. Käivita generaator:
   - `uv run python scripts/generate_glossary.py`
3. Kontrolli tulemust:
   - `uv run mkdocs serve`
4. Tee PR koos andme- ja genereeritud failimuudatustega.

Täpsed juhised on failis `docs/contributing.md`.

## Kohalik arendus (uv)

1. `uv sync --group dev`
2. `uv run python scripts/generate_glossary.py`
3. `uv run mkdocs serve`

## Arutelu ja vaidlused

Vaidlused terminite üle käivad GitHub Discussionsis kategoorias **Terminid**.
