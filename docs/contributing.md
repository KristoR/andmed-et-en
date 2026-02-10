# Panustamine

## Kuidas lisada või muuta terminit

1. Ava `data/terms.yml`.
2. Lisa või muuda kirjet.
3. Kohustuslikud väljad:
   - `en`
   - `et`
4. Valikulised väljad:
   - `alt.et` (list)
   - `alt.en` (list)
   - `definition`
   - `references` (`[{title, url}]`)
   - `example`

Pärast muudatust käivita:

- `uv run python scripts/generate_glossary.py`
- `uv run mkdocs serve`

## Vaidlused ja GitHub Discussions

Kui termini tõlge on vaieldav, ava GitHub Discussionsis kategoorias **Terminid** uus teema:

- pealkiri: `Term: <EN> / <ET>`
- kirjelda, miks pakud muudatust
- lisa viited

Konsensuse korral uuenda `data/terms.yml`:

- eelistatud vaste `et` väljal
- alternatiivid `alt.et` või `alt.en` väljadel
