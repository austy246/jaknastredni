# MŠMT Rejstřík škol a školských zařízení — průzkum (2026-09-22)

Ověřeno živým stažením dat (curl, proxy s CA bundle `/root/.ccr/ca-bundle.crt`) a
SPARQL dotazy na `https://data.gov.cz/sparql`. Pracovní soubory:
`<scratchpad>/msmt/`.

## 1. Dataset na data.gov.cz (NKOD)

- **`data.gov.cz/api/...` REST endpoint neexistuje** ve tvaru, který jsem zkoušel
  (`/api/v2/datasets?...`) — vrací 404/HTML stránku "nenalezeno". Funkční cesta
  je **SPARQL endpoint `https://data.gov.cz/sparql`** (GET s `query=`,
  `Accept: application/sparql-results+json`) — ten funguje spolehlivě.
- Katalog `00022985` (MŠMT) obsahuje **samostatný dataset pro každý kraj** plus
  několik variant pro celou ČR (aktuální, "pro rok 2025", "pro rok 2026",
  historický snapshot "celá ČR (31.12.2024)") a zvlášť
  "Rejstřík školských právnických osob". Relevantní datová sada pro tento
  projekt:
  - **IRI**: `https://data.gov.cz/zdroj/datové-sady/00022985/68f34056b9690cfcaeb637afab35ddff`
  - **Název**: "Rejstřík škol a školských zařízení - Hl. m. Praha"
  - `dcterms:accrualPeriodicity` = **DAILY** (ne jen půlročně/čtvrtletně, jak
    naznačovalo README — soubor se generuje denně; `datumVystupu` uvnitř JSONu
    odpovídá dnešnímu dni stažení).
  - `dcterms:accessRights` = PUBLIC, `dcterms:spatial` = ČR.
  - Popis datasetu (HTML): `https://lkod-ftp.msmt.gov.cz/00022985/88a7c12b-6084-4e47-8b50-46097c6e683f/popis-rejstrik-skol-a-skolskych-zarizeni.html`
    (funguje, 200 OK, 40 KB) — obsahuje popis všech polí.

### Distribuce (ověřeno SPARQL dotazem na `dcat:distribution`)
- **Formát**: `JSON_LD` (`dcterms:format` = EU file-type JSON_LD, `dcat:mediaType`
  = `application/ld+json`). V praxi je to **obyčejný JSON s jednou obálkou
  `@context: "http://msmt.cz/"`** — nejde o plnohodnotný JSON-LD s `@id`/`@type`
  na úrovni záznamů, spíš jen formální označení.
- **`dcat:downloadURL` (= `dcat:accessURL`) pro Prahu**:
  `https://lkod-ftp.msmt.gov.cz/00022985/21e5fd4a-5378-4d64-90e9-759b15d01f28/RSSZ-Hl-m-Praha.jsonld`
- **`dcterms:conformsTo` (JSON schema)**:
  `https://lkod.msmt.gov.cz/schemas/rssz-json-schema.jschema`
- **Licence**: `dcterms:license` odkazuje na specifikaci podmínek užití, která
  přes `skos:narrowMatch` míří na **CC0** (`publications.europa.eu/.../licence/CC0`)
  a explicitně tvrdí: "neobsahuje autorská díla", "není autorskoprávně chráněná
  databáze", "není chráněna zvláštním právem pořizovatele databáze",
  "neobsahuje osobní údaje". Prakticky: **volně použitelná data bez licenčních
  omezení.** (Pozn.: datová sada přesto obsahuje jméno ředitele/ředitelky a
  jeho/její adresu — MŠMT je zjevně považuje za veřejnou funkční informaci, ne
  za osobní údaj ve smyslu GDPR-omezení; při publikaci vlastní databáze na to
  přesto stojí za to dát pozor.)

## 2. Stažení a struktura JSON

Soubor pro Prahu se stáhl bez problémů (HTTP 200, žádný 403 — 403 dává jen
**root** `https://lkod-ftp.msmt.gov.cz/`, přímé URL souborů fungují):

```
curl -L "https://lkod-ftp.msmt.gov.cz/00022985/21e5fd4a-5378-4d64-90e9-759b15d01f28/RSSZ-Hl-m-Praha.jsonld" -o praha.jsonld
```
- **HTTP 200**, `content-type: application/ld+json`, **`content-length: 2 956 551 B` (~2,9 MB)**,
  `last-modified: Mon, 21 Sep 2026 23:17:38 GMT` (aktuální, generováno tuž noc).
- Pro srovnání celoplošný soubor `RSSZ-cela-CR.jsonld`
  (`https://lkod-ftp.msmt.gov.cz/00022985/88a7c12b-6084-4e47-8b50-46097c6e683f/RSSZ-cela-CR.jsonld`)
  má dle HEAD requestu **`content-length: 30 954 928 B` (~29,5 MB)**, stejný
  `last-modified` čas → jde o synchronní denní export.

### Struktura (top-level)
```json
{
  "@context": "http://msmt.cz/",
  "datumVystupu": "2026-09-22",
  "list": [ {právnická osoba…}, … ]   // 1044 záznamů pro Prahu
}
```

`list` = pole **právnických osob** (zřizovatelů/provozovatelů), ne přímo škol.
Každá položka má klíčové entity ve třech úrovních:

1. **Právnická osoba** (top-level záznam v `list`)
   - `redIzo` (resortní IZO **právnické osoby** — pozor, není totéž jako IZO
     jednotlivé školy níže), `ico`, `kraj`, `uplnyNazev`, `zkracenyNazev`,
     `adresa` (ulice/číslo/obec/část obce/číslo obvodu Prahy/PSČ/kodRUIAN/okres/
     uzemiDleORP), `pravniForma` (kód, číselník BBPF), `typZrizovatele` (kód,
     číselník BAZS), `emaily`, `platnostNaDobuNeurcitou` (bool),
     `reditel` {nazevOsoby, reditelJeStatutar, datumVznikuFunkce, adresa},
     `statutarniOrgany`, `zrizovatele` (FO/PO se svými adresami/IČO),
     `skolyAZarizeni` (pole).
2. **Škola/školské zařízení** (`skolyAZarizeni[]`)
   - `izo` (resortní identifikátor **této konkrétní školy/zařízení** — toto je
     ten IZO, který se běžně používá např. u CERMAT dat),
   - `uplnyNazev`, `druh` (kód druhu/typu, **číselník AKDT** — např. `C00` =
     Střední škola, `A00` = mateřská škola (odvozeno z dat), `B00` =
     základní škola (odvozeno), `L11`/`L13` = zřejmě školní jídelna/výdejna,
     `G21`/`G22` = zřejmě školní družina/klub — **tyto odvozené kódy kromě
     C00 nejsou oficiálně ověřené**, číselník AKDT jsem online nenašel
     (zkoušel jsem pár uhodnutelných URL na lkod.msmt.gov.cz, 404); doporučuji
     před finálním filtrováním dohledat oficiální číselník AKDT, např. přes
     rejstriky.msmt.cz nebo přímý dotaz na MŠMT),
   - `jazyk` (kód, číselník NAJS), `kapacity[]` ({mernaJednotka, nejvyssiPovolenyPocet}),
   - `mistaVyuky[]` ({IDmista/izo, typ, adresa}),
   - `obory[]` — obory vzdělání: `kod` (**KKOV formát**, např. `63-41-M/02`,
     `78-42-M/02` — sedí s číselníkem AKSO, který je de facto KKOV),
     `nazev`, `formaVzdelavani` (kód RAFS), `delkaVzdelavani` (kód RADS),
     `jazykOboru` (kód RAJO), `kapacita` (int), `mernaJednotkaKapacit` (BBJK),
     `dobihajiciObor` (bool),
   - `datumZapisu`, `datumZahajeniCinnosti`.
   - **Chybí pole pro zánik/ukončení** (žádné `datumUkonceniCinnosti` v datech
     ani ve schématu) → dataset zřejmě obsahuje **jen aktuálně platné/aktivní**
     záznamy, ne historii zaniklých škol.

### Ukázka záznamu — REDIZO 600006573 (Obchodní akademie, Praha 10, Heroldovy sady 1)
Nalezen přesně podle `redIzo` v Praha souboru:
```json
{
  "redIzo": "600006573",
  "ico": "61385387",
  "uplnyNazev": "Obchodní akademie, Praha 10, Heroldovy sady 1",
  "adresa": {"ulice": "Heroldovy sady", "cisloDomovni": 362, "obec": "Praha",
             "castObce": "Vršovice", "cisloObvoduPrahy": "Praha 10",
             "psc": "101 00", "kodRUIAN": 22658289, "okres": "CZ010A"},
  "reditel": {"nazevOsoby": "Mgr. Richard Žert", "reditelJeStatutar": true,
              "datumVznikuFunkce": "2008-08-19"},
  "zrizovatele": [{"druhOsoby": "PO", "nazevOsoby": "Hlavní město Praha", "ico": "00064581"}],
  "skolyAZarizeni": [{
    "izo": "000638510",
    "uplnyNazev": "Střední škola",
    "druh": "C00",
    "kapacity": [{"mernaJednotka": "01", "nejvyssiPovolenyPocet": 500}],
    "obory": [
      {"kod": "63-41-M/02", "nazev": "Obchodní akademie", "kapacita": 240, "dobihajiciObor": false},
      {"kod": "78-42-M/02", "nazev": "Ekonomické lyceum", "kapacita": 360, "dobihajiciObor": false},
      {"kod": "78-42-M/08", "nazev": "Lyceum (režim pokusného ověřování)", "kapacita": 136, "dobihajiciObor": false}
    ],
    "datumZapisu": "2005-01-01",
    "datumZahajeniCinnosti": "1996-05-16"
  }]
}
```
Potvrzuje shodu se sekundárním zdrojem `prijimacky-onlinekurzy.cz`
(`/skola/600006573/obchodni-akademie-heroldovy-sady-362-praha`) — REDIZO
600006573 je skutečně tato škola.

## 3. Filtrování na Prahu a "střední škola"

- **Praha**: přímočaré — použít krajový soubor `RSSZ-Hl-m-Praha.jsonld`
  (žádné doplňkové filtrování není nutné, celý soubor je jen Praha).
  Pole `adresa.cisloObvoduPrahy` (např. "Praha 10") navíc umožňuje filtrovat
  na konkrétní městskou část.
- **Střední škola**: filtrovat na `skolyAZarizeni[].druh == "C00"`.
- **Počet**: v souboru pro Prahu je **1044 právnických osob** celkem (mateřské
  školy, ZŠ, SŠ, VOŠ, konzervatoře, školní jídelny/družiny/kluby atd.).
  Záznamů s `druh == "C00"` (střední škola) je **přesně 219** (ověřeno
  skriptem, žádné duplicitní IZO, 1:1 mezi právnickou osobou a SŠ facilitou
  v tomto vzorku). Toto číslo zahrnuje všechny právní formy (veřejné,
  soukromé, církevní) a všechny obory (gymnázia, SOŠ, SOU, konzervatoře jsou
  pod jiným kódem `E00` — 35 záznamů — takže nejsou v těch 219 zahrnuty,
  pokud by měly vlastní právnickou osobu).
  Rozložení ostatních kódů `druh` v Praze pro kontext (odvozeno, ne oficiálně
  ověřeno): A00=456 (MŠ), B00=321 (ZŠ), G21=301, L13=271, C00=219 (SŠ),
  G22=118, F10=46, E00=35 (pravděp. konzervatoř/VOŠ), G11=26, H22=20, G40=18,
  K20=18, F20=11, M40=10, L12=10, H21=10, K10=10, D00=8, L15=8, ostatní <5.

## 4. JSON Schema (`lkod.msmt.gov.cz/schemas/rssz-json-schema.jschema`)

Staženo úspěšně (HTTP 200, 14 069 B), JSON Schema draft 2020-12. Hlavní
struktura odpovídá popisu výše:
- root: `{@context (const "http://msmt.cz/"), datumVystupu (date), list[]}`
- `list[].{redIzo, ico, kraj, uplnyNazev, zkracenyNazev, adresa ($ref adresa-json-schema.jschema), pravniForma, typZrizovatele, emaily[], platnostNaDobuNeurcitou, reditel{…}, statutarniOrgany[], zrizovatele[], skolyAZarizeni[]}`
- `skolyAZarizeni[].{izo, uplnyNazev, druh, jazyk, kapacity[]{mernaJednotka,nejvyssiPovolenyPocet}, mistaVyuky[]{izo,typ,adresa}, obory[]{kod,nazev,formaVzdelavani,delkaVzdelavani,jazykOboru,mernaJednotka,kapacita}, datumZapisu, datumZahajeniCinnosti}`
- Schéma **neobsahuje enum/popis hodnot pro kódované sloupce** (`druh`,
  `pravniForma`, `typZrizovatele`, `jazyk`, `kod` u oborů atd.) — jen textový
  popis "Kód druhu/typu (číselník AKDT)" apod. Vlastní číselníky (AKDT, BBPF,
  BAZS, NAJS, BBJK, AKSO, RAFS, RADS, RAJO) jsou zmíněné jménem, ale jejich
  obsah/URL jsem online nedohledal (zkoušené URL vrátily 404) — je třeba je
  buď získat jinde (rejstriky.msmt.cz dokumentace, případně přímý dotaz na
  MŠMT), nebo odvodit hodnoty empiricky z dat (jako u `druh` výše, kde C00 je
  ověřeně "Střední škola").
- Existuje i pomocné schéma `adresa-json-schema.jschema` (referencované přes
  `$ref`), nestahoval jsem ho zvlášť, ale struktura adresy je z dat jasná
  (viz popis výše).

## 5. Alternativy (nezkoušeno stahovat, jen orientačně)

- **rejstriky.msmt.cz/rejskol** a **isv.gov.cz/rssz** — webové UI, limit ~400
  řádků na dotaz (viz README), nemá smysl jako primární zdroj, když je bulk
  JSON-LD dostupný a funkční.
- **khardix/rejskol** (GitHub, archivovaný Python scraper) — řeší právě ten
  limit 400 řádků pro webové UI; pro nás irelevantní, protože bulk export
  funguje přímo.
- Bulk JSON-LD **funguje bez problémů**, takže alternativy nebyly potřeba.

## Doporučení pro import (Python)

1. Stahovat rovnou **krajový soubor pro Prahu** (`RSSZ-Hl-m-Praha.jsonld`,
   ~3 MB) místo celé ČR (~30 MB) — šetří čas/paměť, obsah je identický
   podmnožina.
2. URL zjišťovat dynamicky přes SPARQL dotaz (ne hardcodovat) — `distribuce`
   hash v URL datasetu se může při reorganizaci katalogu změnit, ale přímé
   `downloadURL`/`accessURL` souboru na `lkod-ftp.msmt.gov.cz` je stabilní
   napříč aktualizacemi (soubor se přepisuje na místě, `datumVystupu` uvnitř
   JSONu říká, jak starý je).
   ```python
   import requests
   SPARQL = "https://data.gov.cz/sparql"
   q = """PREFIX dcat: <http://www.w3.org/ns/dcat#>
   SELECT ?url WHERE {
     ?ds a dcat:Dataset ; <http://purl.org/dc/terms/title> "Rejstřík škol a školských zařízení - Hl. m. Praha"@cs ;
         dcat:distribution ?dist .
     ?dist dcat:downloadURL ?url .
   }"""
   r = requests.get(SPARQL, params={"query": q}, headers={"Accept": "application/sparql-results+json"})
   url = r.json()["results"]["bindings"][0]["url"]["value"]
   data = requests.get(url).json()
   ```
3. Parsovat na tři úrovně (právnická osoba → škola/zařízení → obor), ukládat
   do relační DB s klíči `redIzo` (organizace) a `izo` (škola/zařízení,
   běžný cross-reference identifikátor s CERMAT/atlasskolstvi/
   prijimacky-onlinekurzy) a `kod` oboru (KKOV, cross-ref s CERMAT XLSX).
4. Filtr na "střední škola" = `skolyAZarizeni[].druh == "C00"`; než se
   nasadí do produkce, **ověřit kód C00 a případně E00 (konzervatoř) proti
   oficiálnímu číselníku AKDT** — v tomto průzkumu je ověřen jen empiricky
   (jeden vzorek + rozumný odhad), ne z oficiální dokumentace číselníku.
5. Ukládat `datumVystupu` jako verzi/timestamp importu (dataset se mění
   denně) — umožní detekovat, kdy se v registru něco změnilo (nová škola,
   zaniklý obor, změna kapacity), pokud se import bude opakovat.
6. Pro C#/Python projekt: JSON schema (`rssz-json-schema.jschema`, JSON
   Schema draft 2020-12) lze rovnou použít pro codegen modelů (např.
   `datamodel-code-generator` v Pythonu, nebo `NJsonSchema`/`QuickType` pro
   C#) — ušetří ruční psaní tříd.
7. Napojení na CERMAT XLSX a další zdroje: primární spojovací klíč je **IZO**
   školy (`skolyAZarizeni[].izo`), ne `redIzo` právnické osoby — to je nutné
   dodržet, protože jedna právnická osoba může provozovat víc škol/zařízení
   (viz "Vyšší odborná škola grafická a Střední průmyslová škola grafická" —
   jeden `redIzo`, dvě samostatné `skolyAZarizeni` položky s různým `izo`
   a `druh`).

## Problémy / omezení

- `data.gov.cz/api/...` REST rozhraní jsem nenašel funkční — je nutné použít
  SPARQL endpoint.
- Root `lkod-ftp.msmt.gov.cz/` vrací 403 (directory listing zakázán), ale
  přímé URL konkrétních souborů fungují bez autentizace.
- Číselníky (AKDT, AKSO/KKOV, BBPF, BAZS, NAJS, BBJK, RAFS, RADS, RAJO)
  nejsou součástí staženého schématu ani jsem nenašel jejich strojově
  čitelný zdroj online v tomto průzkumu — hodnoty jsem z části odvodil
  empiricky z dat (jen `C00` = Střední škola je jistý, ostatní kódy jsou
  označeny jako neověřené odhady výše). Doporučuji před finálním nasazením
  dohledat oficiální číselníky (např. přes dokumentaci k rejstriky.msmt.cz
  nebo přímý dotaz na MŠMT/NÚKIB opendata kontakt).
- Dataset neobsahuje historii zaniklých škol/oborů (jen aktuální stav) —
  pro sledování změn v čase je nutné buď archivovat vlastní denní snapshoty,
  nebo použít historické varianty datasetu (např. "celá ČR (31.12.2024)"),
  pokud existují i pro kraj Praha (nekontrolováno).
