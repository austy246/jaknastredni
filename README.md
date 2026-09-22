# jaknastredni

Osobní projekt na sběr a porovnání dat o středních školách v Praze — cílem je
mít podklady pro výběr vhodné školy (obor, dosažitelnost podle bodů/PZ,
kvalita, maturitní výsledky, uplatnění absolventů apod.).

## Stav

- Průzkum zdrojů dat je hotový a ověřený stažením (22. 9. 2026), podrobné
  zprávy jsou v [`docs/research/`](docs/research/).
- Datový model je navržený v [`docs/datovy-model.md`](docs/datovy-model.md),
  schéma SQLite v [`jaknastredni/schema.sql`](jaknastredni/schema.sql).
- Importér rejstříku MŠMT funguje, viz níže.
- Importér maturitních výsledků CERMAT (`jaknastredni/cermat_mz.py`) funguje
  pro roky 2015–2026, viz níže.
- Scraper infoabsolvent.cz (`jaknastredni/infoabsolvent.py`) funguje a byl
  spuštěn na všech 211 pražských SŠ, viz níže.

## Rychlý start

```bash
pip install -e ".[dev]"
python -m jaknastredni.msmt --db data/jaknastredni.db                        # stáhne pražský snapshot a naimportuje
python -m jaknastredni.cermat_mz --db data/jaknastredni.db --roky 2015-2026 --obdobi jap  # maturitní výsledky
python -m jaknastredni.infoabsolvent --db data/jaknastredni.db              # scraper infoabsolvent.cz (1 req/s, pár minut)
python -m pytest
```

Výsledkem je `data/jaknastredni.db` s 1044 organizacemi, 2434 školami
a zařízeními a 219 středními školami (`druh = 'C00'`); pohled
`v_stredni_skola` je nejrychlejší cesta k přehledu. Tabulka `maturita`
obsahuje maturitní výsledky po školách za roky 2015–2026. Tabulka
`web_profil` obsahuje scrapovaný profil ze zdroje `infoabsolvent` pro
všech 211 pražských SŠ (naposledy staženo 22. 9. 2026) — 743 řádků oborů
napříč 208 školami (3 školy nemají na infoabsolventu žádnou vzdělávací
nabídku uvedenou). Stažené surové soubory zůstávají v `data/raw/msmt/` a
`data/raw/cermat/` s rokem/datem výstupu v názvu; `web_profil` je čistě
odvozená data přímo v databázi, žádné syrové HTML se needukládá (viz níže
u infoabsolventu).

## Rozhodnutí o vývoji a ukládání dat

- **Vývoj přímo v `main`.** Import CERMAT maturity (viz níže) byl na
  explicitní žádost vlastníka repa vyvíjen a commitnut přímo do větve
  `main`, ne přes samostatnou feature větev a pull request.
- **Stažené soubory i výsledná databáze se verzují v repu.** Na rozdíl od
  původního záměru (`data/` jen lokálně, `.gitignore`d) bylo na explicitní
  žádost rozhodnuto ukládat do gitu i `data/jaknastredni.db` a syrové
  soubory `data/raw/**`. `.gitignore` teď vynechává jen přechodné soubory
  SQLite (`*.db-journal`, `*.db-wal`, `*.db-shm`). Důsledek: repo poroste s
  každým dalším importérem/ročníkem (jen maturitní XLSX 2015–2026 mají
  dohromady cca 50 MB) — pokud to začne vadit, řešením je Git LFS nebo návrat
  k `.gitignore`, ne mazání historie.
- **Tabulka `maturita` nemá cizí klíč na `organizace(redizo)`.** CERMAT
  zahrnuje i školy mimo Prahu a mezitím zaniklé školy, které v rejstříku
  MŠMT nejsou. Filtrování na Prahu se dělá JOINem v dotazech, případně
  přepínačem `--jen-praha` při importu (omezí se na REDIZO, která už jsou
  v `organizace`).
- **Sloupce CERMAT XLSX se mapují podle názvu v hlavičce, ne podle pozice.**
  Napříč roky 2015–2026 se mění počet úvodních ID sloupců (0–2), ale názvy a
  pořadí sloupců od `TŘÍDĚNÍ` dál jsou stabilní — podrobně
  [`docs/research/cermat.md`](docs/research/cermat.md), oddíl 12.
- **Hodnota `"-"` v CERMAT datech = žádný uchazeč, ukládá se jako `NULL`**,
  ne jako 0 (0 by znamenalo "nikdo neuspěl", ne "nikdo se nepřihlásil").
- **Testovací fixtury se generují v testu přes `openpyxl`**, ne jako binární
  `.xlsx` v repu — viz `tests/test_cermat_mz.py`.

## Klíčové identifikátory

Napříč všemi zdroji fungují dva identifikátory z rejstříku MŠMT:

- **REDIZO** (9 číslic) = právnická osoba (organizace). Používá ho CERMAT
  (všechny soubory), ČŠI, Atlas školství, infoabsolvent i agregátory.
- **IZO** = konkrétní škola/zařízení pod danou právnickou osobou. Jedna
  právnická osoba může mít víc škol (např. VOŠ + SPŠ pod jedním REDIZO).
  CERMAT ho uvádí jen v JPZ souborech od 2024 (s textovým prefixem `izo_`).
- **Kód oboru KKOV** (např. `63-41-M/02`) = spojovací klíč na úrovni oboru
  mezi rejstříkem MŠMT, CERMAT JPZ 2024+ a weby škol.

Datový model tedy: právnická osoba (REDIZO) → škola (IZO) → obor (KKOV) →
ročník/rok → metriky.

## Zdroje dat

### 1. MŠMT — Rejstřík škol a školských zařízení (jádro databáze) ✅
Podrobně: [`docs/research/msmt-rejstrik.md`](docs/research/msmt-rejstrik.md)

- **Ověřeno stažením.** Pražský krajový soubor (~2,9 MB JSON) se stahuje
  přímo, bez autentizace:
  `https://lkod-ftp.msmt.gov.cz/00022985/21e5fd4a-5378-4d64-90e9-759b15d01f28/RSSZ-Hl-m-Praha.jsonld`
  (root FTP vrací 403, přímé URL fungují). Celá ČR ~29,5 MB.
- Aktualizace **denně** (pole `datumVystupu`), licence odpovídá CC0.
- Struktura: `list[]` právnické osoby → `skolyAZarizeni[]` (IZO, `druh`,
  kapacity, místa výuky) → `obory[]` (kód KKOV, název, forma, délka,
  kapacita, dobíhající).
- Filtr na střední školy: `druh == "C00"` → **219 SŠ v Praze** (z 1044
  právnických osob). Konzervatoře mají pravděpodobně kód `E00` (35 záznamů,
  neověřeno proti oficiálnímu číselníku).
- JSON schema: `https://lkod.msmt.gov.cz/schemas/rssz-json-schema.jschema`
  (draft 2020-12, použitelné pro codegen modelů v C#/Pythonu).
- Metadata datasetu jdou dotazovat přes SPARQL `https://data.gov.cz/sparql`
  (REST API katalogu jsem nenašel).
- Problémy: číselníky kódů (AKDT, BBPF, BAZS…) nejsou v schématu ani online
  dohledány; dataset obsahuje jen aktuální stav (bez historie zaniklých škol).

### 2. CERMAT — data.cermat.cz (JPZ + maturita po školách) ✅
Podrobně: [`docs/research/cermat.md`](docs/research/cermat.md)

- **Ověřeno stažením** 8 souborů. Žádný robots.txt (404).
- **JPZ po školách/oborech**, adresář `/files/files/JPZ/agregovana_data_skoly/`:
  - **2017–2023**: `JPZ{rok}_skoly-skolobory_vysledky.xlsx`, jeden soubor na
    rok. Jen REDIZO (bez IZO), obor jen jako hrubá skupina (GY8, GY4, LYC,
    4LETÉ OBORY…), metrika = průměrné percentilové umístění ČJ/MA.
  - **2024–2026**: `PZ{rok}_kolo{1,2}_skolobory_{kapacity,prihlasky,vysledky}.xlsx`,
    tři soubory na kolo. IZO + REDIZO + **KKOV kód oboru**, kapacita, index
    poptávky, přihlášky podle priorit 1–5, přijatí, % skór a percentil
    (průměr/min/max) zvlášť pro přihlášené a přijaté, důvody nepřijetí.
    91 sloupců, list `vysvetlivky` = datový slovník.
  - **Zlom formátu mezi 2023 a 2024** — import potřebuje dva parsery.
- **Maturita po školách**, adresář `/files/files/MZ/agregovana_data_skoly/`:
  `MZ{rok}j_SC_skolobory.xlsx` (jaro) a `MZ{rok}jap_SC_skolobory.xlsx`
  (jaro+podzim) pro **2015–2026**. REDIZO ano, IZO/KKOV ne (jen skupina
  SMO16). Za každý předmět: přihlášeni/konali/uspěli/neuspěli, průměrný %
  skór, percentil, čistá neúspěšnost. Formát napříč lety stabilní.
- Společné pasti: hlavička je na 2. řádku (1. řádek je sloučený titulek);
  listy míchají řádky škol, krajů a celku — filtrovat podle číselného REDIZO
  (JPZ) nebo sloupce `TŘÍDĚNÍ` (maturita).
- Bodové hranice pro přijetí CERMAT nezveřejňuje (stanovuje škola). Od 2024
  jde ale odvodit min. % skór přijatých uchazečů z `_vysledky.xlsx`.
- vysledky.cermat.cz = starý ASP.NET portál s embedovaným Power BI; žádné
  JSON API nenalezeno, pro import nepoužívat.
- Navíc existují soubory uchazečů (`PZ{rok}_kolo{k}_uchazeci_prihlasky_vysledky.xlsx`,
  2024–2026) a položková data po úlohách — nezkoumáno.

### 3. Česká školní inspekce (ČŠI) ✅
Podrobně: [`docs/research/csi.md`](docs/research/csi.md)

- Z 81 datasetů na opendata.csicr.cz je na konkrétní školu navázaný jediný:
  **„Inspekční zprávy"** (dataset 69). CSV:
  `https://opendata.csicr.cz/Transformation/Download/137` (3,8 MB, 14 912
  řádků, 2003–2026, i JSON/XML varianta).
- Sloupce: `REDIZO, Jmeno, DatumOd, DatumDo, LinkIZ` (přímý odkaz na PDF
  zprávy, veřejně stažitelný), `PortalLink`.
- Dataset nemá kraj ani typ školy → filtr na pražské SŠ jen JOINem s
  rejstříkem MŠMT přes REDIZO.
- PDF zprávy jsou textově extrahovatelné (ověřeno pymupdf); mají sekce
  „Závěry" → „Silné stránky", „Příležitosti ke zlepšení", „Doporučení" jako
  odrážkové seznamy — parsovatelné, ale ověřeno jen na jedné zprávě.
- Registr na csicr.cz a portal.csicr.cz jsou stavové ASP.NET formuláře bez
  použitelného API; nic navíc oproti CSV. Portál potvrdil **217 SŠ v Praze**.
- Licence otevřených dat nebyla explicitně nalezena.

### 4. Atlas školství (Scio) — atlasskolstvi.cz ✅
Podrobně: [`docs/research/atlas-infoabsolvent.md`](docs/research/atlas-infoabsolvent.md)

- robots.txt povoluje vše kromě `/admin/`. Server-rendered HTML, bez API a
  sitemapy.
- Seznam: `https://www.atlasskolstvi.cz/stredni-skoly?region=hlm-praha`,
  stránkování `?p=N`, **214 škol**, 11 stran. URL detailu `/ss{interníID}-slug`
  (ID není REDIZO).
- Detail (zdarma): adresa, kontakty, ředitel, IČ, **REDIZO** (čitelný text),
  zřizovatel, dny otevřených dveří, jazyky, ubytování/stravování, tabulka
  oborů s KKOV, plán přijmout, **loňský počet přihlášených/přijatých**,
  předměty přijímaček, PLP, OZP, doporučený prospěch. Tabulka má `data-name`
  atributy → snadný parser.
- Placené (1 kredit = 1 obor u 1 školy na 12 měsíců): historické výsledky
  JPZ a maturit u maturitních oborů. U učňovských oborů zdarma. Cena kreditu
  vyžaduje účet (nezjištěno). VOP definují službu „pro osobní potřebu" se
  zákazem poskytování třetím osobám — placenou část neautomatizovat.
  Vzhledem k tomu, že totéž je zdarma v CERMAT XLSX, není důvod platit.

### 5. infoabsolvent.cz (NPI ČR) ✅
Podrobně: [`docs/research/atlas-infoabsolvent.md`](docs/research/atlas-infoabsolvent.md)

- robots.txt zakazuje jen porovnávání oborů a export do Wordu (a celý web
  pro `meta-externalagent`). Server-rendered ASP.NET MVC, bez API.
- Seznam: `https://www.infoabsolvent.cz/Skoly/Seznam/SOS?Kraj=CZ011`
  (parametr vždy nastavit explicitně), **211 škol na jedné stránce**.
  URL detailu `/Skoly/Skola/{REDIZO}/{slug}/SOS` — **REDIZO přímo v URL**.
- Detail: nejpodrobnější tabulka oborů ze všech webů (KKOV, ŠVP, forma,
  jazyky, loni přihlášení/plán, letos plán, školné, přijímací řízení po
  složkách vč. „jiná kritéria", termíny, podpora ZP), vybavení, velikost
  školy, odkaz na ČŠI zprávy. Karty oborů (`/Obory/KartaOboru/{kód}`) mají
  uplatnění absolventů a navazující povolání (obecně za obor, ne za školu).
- Žádná stránka s podmínkami užití nenalezena; kontakt `infoabsolvent@npi.cz`.
- **Scraper implementován a spuštěn** (`jaknastredni/infoabsolvent.py` →
  tabulka `web_profil`, zdroj `infoabsolvent`, JSON blob v poli `data`).
  Robots.txt znovu ověřen před spuštěním (22. 9. 2026) — beze změny oproti
  průzkumu výše. Všech **211/211** pražských SŠ staženo a naparsováno bez
  chyby, celkem 743 řádků oborů (208/211 škol má na infoabsolventu
  vyplněnou vzdělávací nabídku, 3 nemají žádnou — ověřeno, není to chyba
  parseru). Sloupec „LONI: přihlášení/plán přijmout" na stránce je
  **loňský počet přihlášených a loňský PLÁN přijmout, ne skutečný počet
  přijatých** — infoabsolvent.cz skutečný počet přijatých neuvádí (na
  rozdíl od Atlasu, viz bod 4); ukládá se tedy jako `loni_prihlaseni` a
  `loni_plan_prijmout`. Parser používá `BeautifulSoup` s vestavěným
  `html.parser` (`beautifulsoup4` přidáno jako hlavní závislost, lxml
  nepotřeba). Žádné syrové HTML se neukládá do `data/raw/` — výstupem je
  přímo řádek v `web_profil`.

### 6. prijimacky-onlinekurzy.cz (agregátor, jen inspirace) ✅
Podrobně: [`docs/research/prijimacky-onlinekurzy.md`](docs/research/prijimacky-onlinekurzy.md)

- robots.txt povoluje `/mesto/*` i `/skola/*`; 185 škol v Praze, `?page=1..10`,
  server-rendered HTML bez datového API. REDIZO v URL detailu potvrzeno.
- Detail: per obor tabulka 2024/2025/2026 + „odhad 2027" s řádky kapacita,
  přihlášeno, přijato, šance („každý N-tý"), průměr bodů, minimum bodů; plus
  proprietární „skóre obtížnosti" a žebříčky zájmu za 30 dní. Parametr
  `rocnik=` data nemění (jen marketingový formulář).
- Kapacita, přihlášeno, přijato, průměr a KKOV jdou reprodukovat z CERMAT
  2024+ a rejstříku MŠMT. Skóre obtížnosti, žebříčky a predikce jsou
  proprietární — nekopírovat, nahradit vlastní průhlednou metrikou.
- UX nápady: karta školy s mini-metrikami per obor, tabulka let vedle sebe,
  filtr kraj → městská část → typ školy (GY4/GY6/GY8/LYC/SOS/SOU), REDIZO
  v URL, srovnávací pohled.

### 7. prihlaskynastredni.cz / DIPSY
Přihlašovací portál, **není datový zdroj** — žádný veřejný export ani API.
(Neověřováno znovu; soubory uchazečů z DIPSY publikuje CERMAT, viz bod 2.)

### 8. ČSÚ
Souhrnné statistiky na úrovni krajů, ne škol. Nerelevantní pro jádro
databáze.

### 9. Mediální žebříčky
Dílčí články (Seznam Zprávy, Deníky) řadící školy podle maturit vycházejí
ze stejných CERMAT/MŠMT souborů jako bod 2 — vlastní žebříček si lze
spočítat přímo ze zdroje. EDUin k nim publikuje kritické komentáře.

### 10. Další nalezené zdroje
Podrobně: [`docs/research/dalsi-zdroje.md`](docs/research/dalsi-zdroje.md)

- **GitHub `tangero/stredniskoly`** (web prijimackynaskolu.cz, Patrick
  Zandl) — živě udržovaný projekt kombinující CERMAT přijímačky 2023–2026,
  rejstřík MŠMT, profily škol z ČŠI InspIS portálu a MHD dostupnost. Soubor
  `data/inspis_school_profiles.json` (4,3 MB, 1180 škol klíčovaných REDIZO,
  školné, zaměření, počty žáků) je hotový scraper portal.csicr.cz. Repo
  nemá soubor LICENSE — před převzetím dat ověřit u autora. Nejužitečnější
  jako referenční implementace a zdroj mapování oborů.
- **Wikidata P6370 (REDIZO)** — 7062 položek v ČR, ověřeno SPARQL; hodí se
  pro napojení na Wikipedii a souřadnice, pokrytí neúplné.
- **OpenStreetMap `ref:redizo`** — jen 213 použití v celé ČR, nepoužitelné
  jako primární zdroj.
- **Negativní zjištění**: magistrát hl. m. Prahy nemá v NKOD žádný dataset
  o školách (ověřeno SPARQL); opendata.praha.eu (nyní lkod.cz) má 10
  datasetů v tématu Vzdělávání, ale jsou to JS SPA stránky, konkrétní
  názvy neověřeny. Dlouhodobý záměr vzdělávání HMP a výroční zprávy jsou
  jen PDF se souhrnnými statistikami.
- `FilipSivak/cermat-data` — jednorázový snapshot z roku 2020, zastaralé.

## Kontrolní součty: kolik je v Praze středních škol

| Zdroj | Počet | Poznámka |
|---|---|---|
| MŠMT rejstřík, `druh == C00` | 219 | + 35 záznamů `E00` (pravděp. konzervatoře/VOŠ) |
| ČŠI portál, typ C, kraj Praha | 217 | |
| Atlas školství | 214 | |
| infoabsolvent.cz | 211 | seznam SOS zahrnuje i gymnázia a konzervatoře |
| prijimacky-onlinekurzy.cz | 185 | jen školy s JPZ daty |

Rozdíly jsou malé a vysvětlitelné (dobíhající školy, konzervatoře, školy bez
JPZ). Rejstřík MŠMT je referenční množina.

## Doporučený postup

1. ~~**Import rejstříku MŠMT**~~ hotovo (`jaknastredni/msmt.py`), zbývá
   ověřit číselník druhů (`C00` vs. `E00`).
2. **Import CERMAT XLSX**:
   - ~~maturita 2015–2026 (jeden parser)~~ hotovo
     (`jaknastredni/cermat_mz.py`, tabulka `maturita`).
   - JPZ 2024–2026 (nový formát, 3 soubory × 2 kola × rok) — další v pořadí,
     tabulka `prijimaci_rizeni`, klíč IZO + KKOV (prefix `izo_` odstranit).
   - JPZ 2017–2023 (starý formát, jen pro trendy na úrovni skupiny oborů,
     klíč REDIZO).
3. **Import ČŠI CSV** → seznam inspekcí per REDIZO; PDF stahovat jen pro
   školy na užším seznamu a extrahovat sekci „Závěry".
4. ~~**Scraper infoabsolvent.cz** (211 detailů, 1 req/s) pro přijímací
   kritéria, školné, jazyky, vybavení~~ hotovo (`jaknastredni/infoabsolvent.py`,
   tabulka `web_profil`, zdroj `infoabsolvent`) — volitelně ještě Atlas
   školství pro doporučený prospěch a jako druhý zdroj pro křížovou kontrolu
   (zůstává neudělané, viz "Otevřené otázky" níže). Vždy REDIZO z
   detailu/URL infoabsolventu, ne z interního ID Atlasu.
5. Prezentace: inspirovat se agregátorem (bod 6), ale metriky počítat
   z oficiálních dat s uvedeným vzorcem.

## Otevřené otázky

- Oficiální číselník druhů škol (AKDT) pro spolehlivý filtr SŠ/konzervatoř.
- Licence otevřených dat ČŠI a podmínky užití infoabsolvent.cz.
- Konzistence hlaviček CERMAT souborů v neověřených letech (JPZ 2024–2025,
  MZ 2018–2025) — ověřit před ostrým importem.
- Struktura sekcí v ČŠI PDF napříč šablonami různých let.
