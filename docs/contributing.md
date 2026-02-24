# Panustamine

## Kuidas lisada uus termin

### Variant 1: GitHub Discussion (lihtsaim)

Ava uus arutelu eeltäidetud vormiga:

[Soovita uut terminit](https://github.com/KristoR/andmed-et-en/discussions/new?category=terminid){ .md-button .md-button--primary }

Täida väljad ja kirjelda oma ettepanekut. Toimetaja lisab termini pärast arutelu.

### Variant 2: Pull Request (tehniline)

1. Muuda ainult faili `data/terms.yml`.
2. Lisa uus kirje:

    ```yaml
    - en: "ingliskeelne termin"
      et: "eestikeelne termin"
      alt:
        et: ["alternatiiv1"]
        en: []
      definition: "Lühike definitsioon."
      references:
        - title: "Viite pealkiri"
          url: "https://..."
      example: "Näidislause termini kasutamisega."
      theses:
        - author: "Perekonnanimi"
          title_et: "Lõputöö pealkiri eesti keeles"
          title_en: "Thesis title in English"
          year: "2024"
          url: "https://dspace.ut.ee/..."
    ```

3. Kohustuslikud väljad: `en`, `et`
4. Valikulised väljad: `alt`, `definition`, `references`, `example`, `theses`
5. Käivita generaator ja kontrolli tulemust:

    ```bash
    uv run python scripts/generate_glossary.py
    uv run mkdocs serve
    ```

6. Tee PR koos andme- ja genereeritud failimuudatustega.

## Kuidas muuta olemasolevat terminit

1. Leia termin failis `data/terms.yml`.
2. Muuda soovitud väljasid (tõlge, definitsioon, alternatiivid, viited, näide).
3. Käivita generaator ja tee PR.

Või ava termini lehel link **"Soovita muudatust"** — see avab eeltäidetud GitHub Discussioni.

## Väljad

| Väli | Kohustuslik | Kirjeldus |
|------|:-----------:|-----------|
| `en` | Jah | Ingliskeelne termin |
| `et` | Jah | Eestikeelne eelistatud vaste |
| `alt.et` | Ei | Eestikeelsed alternatiivid (list) |
| `alt.en` | Ei | Ingliskeelsed alternatiivid (list) |
| `definition` | Ei | Lühike definitsioon |
| `references` | Ei | Viited: `[{title, url}]` |
| `example` | Ei | Näidislause |
| `theses` | Ei | Lõputööviited: `[{author, title_et, title_en, year, url}]` |

## Automaatne terminite avastamine

Repo sisaldab automaatset torustikku, mis otsib Eesti ülikoolide lõputöödest andmevaldkonna termineid:

```bash
# Käivita lõputööde otsimine
uv run python scripts/fetch_theses.py --verbose

# Edenda kandidaatterminid sõnastikku
uv run python scripts/promote_candidates.py
```

See torustik käivitub automaatselt iga kuu GitHub Actionsis ja loob PR-i uute kandidaatterminitega.

## Vaidlused ja GitHub Discussions {#vaidlused-ja-github-discussions}

Kui termini tõlge on vaieldav, ava [GitHub Discussionsis](https://github.com/KristoR/andmed-et-en/discussions/new?category=terminid) kategoorias **Terminid** uus teema:

- pealkiri: `Term: <EN> / <ET>`
- kirjelda, miks pakud muudatust
- lisa viited

Konsensuse korral uuenda `data/terms.yml`:

- eelistatud vaste `et` väljal
- alternatiivid `alt.et` või `alt.en` väljadel
