# AGENTS.md

## Eesmärk
Avalik EN ↔ ET andmevaldkonna mõistete sõnastik, mis on:
- otsitav igalt lehelt (otsing päises)
- sirvitav põhilehel (ainult EE↔EN vasted, tähestiku kaupa, hüpped tähtedele)
- iga termini kohta on alamleht (tähendus, alternatiivid, viited, näide)
- koostöine (PR-id + arutelud)

## Põhinõuded
1) Otsing (EN ja ET) peab töötama igal lehel päises.
2) Põhileht (index) on “telefoniraamat” stiilis:
   - ainult EE ↔ EN vasted
   - tähestikuline sirvimine + hüpe vastava tähe juurde
   - kaks sortimisvaadet:
     - ET → EN
     - EN → ET
3) Alamlehed per termin:
   - EN
   - EE
   - Alternatiivid
   - Definitsioon
   - Viited
   - Näide
4) Arutelu vaidluste korral toimub GitHub Discussions all.

## Tehniline teostus (soovituslik)
### Stack
- MkDocs + Material for MkDocs (GitHub Pages)
- Python skript terminite genereerimiseks YAML-ist

### Repostruktuur
- data/terms.yml
  - Single source of truth (käsitsi muudetakse ainult seda faili)
- scripts/generate_glossary.py
  - Genereerib docs/index.md ja docs/terms/*.md
- docs/
  - MkDocs sisu
- mkdocs.yml
  - Material teema + search plugin
- .github/workflows/deploy.yml
  - Genereerimine + build + deploy GitHub Pages

## Andmevorming
Fail: data/terms.yml

Minimaalne kirje (kohustuslikud väljad):
- en: "<english term>"
- et: "<estonian preferred term>"

Valikulised väljad:
- alt:
    et: [ ... ]
    en: [ ... ]
- definition: "<short definition>"
- references:
    - title: "<source name>"
      url: "<source link>"
- example: "<example sentence or SQL snippet>"

Näidis (ilma koodibloki süntaksita, et vältida markdowni rikkumist):

    - en: "data warehouse"
      et: "andmeladu"
      alt:
        et: ["andmeait"]
        en: []
      definition: "Struktureeritud andmete keskne hoidla analüüsi jaoks."
      references:
        - title: "Sõnaveeb"
          url: "https://sonaveeb.ee/..."
      example: "Näide: dim-fact mudeliga andmeladu toetab agregatsioone."

Reeglid:
- en ja et peavad olema olemas.
- alt / definition / references / example on valikulised.
- Üks kirje = üks mõiste (mitte lihtsalt sõna).

## Slug reeglid (termini URL / faili nimi)
- Slug genereeritakse deterministlikult en väärtusest:
  - lowercase
  - tühikud -> "-"
  - eemaldada või asendada erimärgid
  - normaliseerida õ/ä/ö/ü (nt "ä" -> "a", "õ" -> "o")
- Faili asukoht: docs/terms/<slug>.md

## Genereeritavad lehed
### 1) Põhileht: docs/index.md
- Sisaldab kahte osa:
  - ET → EN
  - EN → ET
- Mõlemas osas:
  - hüpperiba tähtedele (A, B, C, ...)
  - iga tähe all read kujul:
    - "ET — EN" (ET linkib termini lehele)
    - või "EN — ET" (EN linkib termini lehele)
- Indexis näidatakse ainult vasteid, mitte definitsioone ega viiteid.

Märkus:
- Võib teha ka kaks lehte (index-et.md ja index-en.md), aga alguses on lihtne hoida ühes indexis.

### 2) Termini alamleht: docs/terms/<slug>.md
Standardiseeritud struktuur:
- Pealkiri: "EE — EN"
- Sektsioonid:
  - EN
  - EE
  - Alternatiivid (kui olemas)
  - Definitsioon (kui olemas)
  - Viited (kui olemas)
  - Näide (kui olemas)
  - Arutelu (link repo Discussions'ile või otsingule)

## Arutelu ja vaidluste protsess
Arutelu ei käi “hääletamisega” YAML failis. See käib GitHub Discussions all.

Soovituslik mudel:
1) Repo settings: enable Discussions.
2) Lisa kategooria: "Terminid".
3) Vaidluse korral avada Discussion pealkirjaga:
   - "Term: <EN> / <ET>"
4) Kui konsensus tekib:
   - uuendada data/terms.yml (preferred et)
   - vajadusel lisada alternatiivid alt.et / alt.en
5) Kui konsensust ei teki:
   - termin võib olla endiselt olemas, aga alternatiivide kaudu kajastatud
   - (valikuline) lisa hiljem status väli, nt draft/approved

## Panustamine (PR flow)
- Muudatused tehakse PR-iga:
  - lisa / muuda kirje data/terms.yml
  - generator tekitab docs/index.md ja docs/terms/*.md
- Mitte-tehniline panus:
  - avada GitHub Discussion või Issue (kui soovitakse “todo” stiilis)
  - toimetaja teeb PR-i

## Kohalik arendus
1) Loo virtuaalkeskkond
2) Paigalda sõltuvused:
   - pip install -r requirements.txt
3) Genereeri lehed:
   - python scripts/generate_glossary.py
4) Käivita dev server:
   - mkdocs serve
  
## Git kehtestamise (_commit_) reeglid

- Ära lisa kehtestamise kirjeldusse seansi URL-e (nt `https://claude.ai/...`)
- Ära lisa `Co-Authored-By` ega muid AI atributsiooni ridu
- Kasuta _Conventional Commits_ formaati: `tüüp: lühikirjeldus`
- Pealkiri max 72 tähemärki
- Kui muudatus on mittetriviaalne, lisa lühike selgitav lõik: mis muutus ja miks
- Ära loo uut haru automaatselt, kui kasutaja pole seda selgesõnaliselt palunud

## Deploy (GitHub Pages)
GitHub Actions peab:
- installima dependencies (mkdocs, mkdocs-material, pyyaml)
- käivitama generatori
- ehitama mkdocs build
- deploy’ima GitHub Pages’i

## PR checklist
- [ ] data/terms.yml on korrektne YAML ja läbiloetav
- [ ] en/et on olemas (kohustuslik)
- [ ] genereerimine käib veatult (docs/index.md ja docs/terms/* uuenevad)
- [ ] duplikaadid kontrollitud (vähemalt en unikaalne; ideaalis ka et)
- [ ] viited (kui lisatud) on toimivad lingid
- [ ] termin on leitav otsingust (MkDocs search)
