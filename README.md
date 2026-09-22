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
- Importér seznamu inspekčních zpráv ČŠI (`jaknastredni/csi.py`) funguje,
  viz níže.
- Importér JPZ starého formátu CERMAT (`jaknastredni/cermat_jpz_old.py`)
  funguje pro roky 2017–2023, viz níže.
- Scraper infoabsolvent.cz (`jaknastredni/infoabsolvent.py`) funguje a byl
  spuštěn na všech 211 pražských SŠ, viz níže.
- Importér výsledků JPZ CERMAT, nový formát (`jaknastredni/cermat_jpz.py`)
  funguje pro roky 2024–2026 (obě kola), viz níže.
- Scraper Atlas školství (`jaknastredni/atlas.py`) funguje a byl spuštěn na
  všech 215 pražských SŠ nabízených Atlasem (druhý zdroj do `web_profil`,
  `zdroj = 'atlas'`), viz níže.
- Proces stažení dat a sestavení databáze je rozdělený na dva kroky
  (`jaknastredni.fetch_all` a `jaknastredni.build_db`), viz "Rychlý start".
- Nad hotovou databází běží **průvodce výběrem školy**
  (`jaknastredni/pruvodce.py`) — z odpovědí uchazeče vybere 5 nejlepších
  nabídek a návrh tří přihlášek, viz níže a [`docs/pruvodce-ux.md`](docs/pruvodce-ux.md).
  Klikací prototyp průvodce je `web/index.html`.

## Rychlý start

Proces je rozdělený na dva kroky: **fetch** (stáhne syrová data ze všech
zdrojů do `data/raw/`, síťově náročné a pomalé kvůli rate limitu
infoabsolventu) a **build** (sestaví/aktualizuje databázi čistě z toho, co
už je v `data/raw/`, žádná síť, cca 1 minuta). Syrová data se commitují do
repa, výsledná databáze ne (viz "Rozhodnutí" níže) — proto build stačí
spustit po každém `git clone`/deploy, fetch jen když je potřeba zdrojová
data obnovit/rozšířit o nový ročník.

```bash
pip install -e ".[dev]"
python -m jaknastredni.fetch_all -v        # stáhne vše ze všech zdrojů do data/raw/ (~7–8 minut)
python -m jaknastredni.build_db  -v        # sestaví data/jaknastredni.db jen z data/raw/ (~1 minuta, offline)
python -m pytest
```

Nad hotovou databází se pak dá spustit průvodce výběrem školy:

```bash
python -m jaknastredni.pruvodce --db data/jaknastredni.db              # interaktivní dotazník
python -m jaknastredni.pruvodce --profil profil.json --json            # neinteraktivně, JSON výstup
```

Jednotlivé importéry jdou pořád spustit i samostatně (stáhnou i naimportují
najednou, přes síť) — užitečné pro doplnění jen jednoho zdroje/ročníku:

```bash
python -m jaknastredni.msmt --db data/jaknastredni.db                        # stáhne pražský snapshot a naimportuje
python -m jaknastredni.cermat_mz --db data/jaknastredni.db --roky 2015-2026 --obdobi jap  # maturitní výsledky
python -m jaknastredni.csi --db data/jaknastredni.db                        # seznam inspekcí ČŠI
python -m jaknastredni.cermat_jpz_old --db data/jaknastredni.db --roky 2017-2023          # JPZ starý formát
python -m jaknastredni.infoabsolvent --db data/jaknastredni.db              # scraper infoabsolvent.cz (1 req/s, pár minut)
python -m jaknastredni.cermat_jpz --db data/jaknastredni.db --roky 2024-2026            # výsledky přijímaček (JPZ)
python -m jaknastredni.atlas --db data/jaknastredni.db                      # scraper atlasskolstvi.cz (1 req/s, pár minut)
```

Výsledkem je `data/jaknastredni.db` s 1044 organizacemi, 2434 školami
a zařízeními a 219 středními školami (`druh = 'C00'`); pohled
`v_stredni_skola` je nejrychlejší cesta k přehledu. Tabulka `maturita`
obsahuje maturitní výsledky po školách za roky 2015–2026, tabulka
`jpz_skupina` výsledky JPZ po školách a oborových skupinách za roky
2017–2023 (21 569 řádků) a tabulka `prijimaci_rizeni` výsledky JPZ po
škole × oboru za roky 2024–2026 (27 289 řádků, obě kola). Tabulka
`inspekce` obsahuje 14 912 záznamů o inspekcích ČŠI za roky 2003–2026 (350
z nich se týká pražských středních škol, 217 různých REDIZO — souhlasí
s kontrolním součtem portálu ČŠI, viz níže). Tabulka `web_profil` obsahuje
scrapovaný profil ze zdroje `infoabsolvent` pro všech 211 pražských SŠ
(naposledy staženo 22. 9. 2026) — 743 řádků oborů napříč 208 školami
(3 školy nemají na infoabsolventu žádnou vzdělávací nabídku uvedenou).
Stažené surové soubory zůstávají v `data/raw/msmt/`, `data/raw/cermat/`
a `data/raw/csi/` s rokem/datem výstupu v názvu; `web_profil` je čistě
odvozená data přímo v databázi, žádné syrové HTML se needukládá (viz níže
u infoabsolventu). Druhý zdroj do `web_profil`, `atlas` (Atlas školství,
`jaknastredni/atlas.py`), byl spuštěn na všech **215/215** pražských SŠ
nabízených Atlasem (naposledy staženo 22. 9. 2026) — 738 řádků oborů, z toho
703 (95 %) má i skutečný loňský počet přijatých (na rozdíl od infoabsolventu,
který má jen loňský plán) a 86 řádků doporučený průměrný prospěch. Stejně
jako u infoabsolventu se syrové HTML ukládá do `data/raw/atlas/`
(`{atlas_id}.html` + `_manifest.json`), ne přímo redizo — to se dozví až
import z detailu stránky, viz bod 4 níže.

## Rozhodnutí o vývoji a ukládání dat

- **Vývoj přímo v `main`.** Import CERMAT maturity (viz níže) byl na
  explicitní žádost vlastníka repa vyvíjen a commitnut přímo do větve
  `main`, ne přes samostatnou feature větev a pull request.
- **Syrová stažená data se verzují v repu, výsledná databáze ne.** Zpočátku
  se do gitu ukládalo obojí (`data/jaknastredni.db` i `data/raw/**`), ale
  databáze je čistě odvozená (100% reprodukovatelná z `data/raw/` skriptem
  `jaknastredni.build_db`, viz "Rychlý start") a jako binární SQLite soubor
  se v gitu nedá rozumně diffovat — každá i jednořádková změna znovu
  commitne celý soubor (desítky MB) a repo neúměrně roste. `data/raw/**`
  naopak diffovat nepotřebujeme (nemění se, jen přibývá) a chceme ho mít
  verzované pro reprodukovatelnost/audit. `.gitignore` proto ignoruje
  `*.db` (a přechodné soubory SQLite `*.db-journal`/`*.db-wal`/`*.db-shm`),
  ale ne `data/raw/`. Historie z doby, kdy se databáze do repa ukládala,
  zatím zůstává beze změny (nebyla přepsána) — pokud by časem vadila
  velikost `.git`, řešením je `git filter-repo`, ne postupné mazání.
- **Proces je rozdělený na fetch (`jaknastredni/fetch_all.py`) a build
  (`jaknastredni/build_db.py`).** Cílem je, aby build šel spouštět v CI/CD
  při nasazení čistě offline (`git clone` + `build_db` => hotová databáze),
  bez závislosti na dostupnosti/rychlosti/rate limitům zdrojových webů.
  Podmínkou bylo, aby úplně každý zdroj uměl uložit syrová data lokálně a
  naimportovat je později bez sítě — to platilo už pro CERMAT/MŠMT/ČŠI
  (mají vlastní `download()`/`parse()`), ale ne pro scraper
  infoabsolvent.cz, který dřív stahoval a rovnou parsoval HTML v jednom
  kroku. Doplněno:
  `infoabsolvent.fetch_raw()` teď ukládá HTML každé školy do
  `data/raw/infoabsolvent/{redizo}.html` a `_manifest.json` (seznam škol +
  datum stažení + URL), `infoabsolvent.import_from_local()` z nich importuje
  offline. `build_db.py` najde nejnovější soubor podle jména (MŠMT
  snapshot, ČŠI CSV) nebo podle vzoru názvu (CERMAT XLSX podle roku/období/
  kola) a použije jeho `parse()`/`import_rows()` — nikdy nestahuje nic
  sám. `fetch_all.py` má pevné roky pro JPZ starý formát (2017–2023, formát
  zmrzlý) a plovoucí horní hranici (aktuální rok) pro maturitu a JPZ nový
  formát; chybějící/ještě nepublikovaný soubor jen zaloguje a pokračuje dál.
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
  `.xlsx` v repu — viz `tests/test_cermat_mz.py`, `tests/test_cermat_jpz.py`.
- **Importér JPZ 2017–2023** (`jaknastredni/cermat_jpz_old.py`) byl na
  explicitní žádost vlastníka repa vyvíjen na samostatné větvi (ne přímo v
  `main`). Tabulka `jpz_skupina` stejně jako `maturita` nemá cizí klíč na
  `organizace(redizo)` (stejný důvod: školy mimo Prahu, zaniklé školy),
  filtr `--jen-praha` funguje stejně. Tento zdroj nemá sloupec typu
  `TŘÍDĚNÍ` — školní řádky se poznají jen podle číselného REDIZO v 1.
  sloupci (krajské/celkové řádky mají text nebo prázdno). Rok 2020 má navíc
  tři sloupce absence (`OMLUVENI/NEOMLUVENI/VYLOUČENI`) místo jednoho
  (`NEKONALI`) — parser tyto sloupce nemapuje (schéma je nepotřebuje), takže
  rozdíl je neškodný; podrobně
  [`docs/research/cermat.md`](docs/research/cermat.md), oddíl 13.
- **Tabulka `prijimaci_rizeni` (JPZ) má rozšířený primární klíč.** Plán v
  `docs/datovy-model.md` počítal s klíčem `(izo, kod_kkov, rocnik, rok,
  kolo)`, ale v reálných datech není jednoznačný (školy s víc zaměřeními
  pod jedním KKOV) — klíč je rozšířený o `zamereni_oboru`,
  `forma_vzdelavani`, `delka_studia`, `jazyk_studia`, viz
  `docs/research/cermat.md`, oddíl 14, a `jaknastredni/schema.sql`. Tři
  zdrojové soubory (`vysledky`/`prihlasky`/`kapacity`) se spojují přes
  `ID_SOF` (ověřeno jako spolehlivější než navržené `ID_SO`, které je navíc
  v letech 2024–2025 v `prihlasky`/`kapacity` přejmenované na `IS_SO`).

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
- **Scraper implementován a spuštěn** (`jaknastredni/atlas.py` → tabulka
  `web_profil`, zdroj `atlas`, JSON blob v poli `data`, stejná architektura
  fetch/import jako u infoabsolventu — viz bod 5 níže). Stahuje jen
  bezplatná pole (dny otevřených dveří, doplňující informace, cizí jazyky,
  ubytování/stravování a tabulku oborů s KKOV, plánovaným počtem
  přijímaných, **loňským skutečným počtem přihlášených/přijatých** — na
  rozdíl od infoabsolventu, který uvádí jen loňský PLÁN přijmout, ne kolik
  jich bylo skutečně přijato — přijímacími zkouškami, PLP, OZP, ročním
  školným a doporučeným průměrným prospěchem, což je pole, které žádný jiný
  ověřený zdroj v tomto projektu nemá). Placený odkaz "Statistika"
  (historické výsledky JPZ/maturit u maturitních oborů) se záměrně
  nestahuje ani nenásleduje — viz bod 1.4 a 3 v research dokumentu výše
  (VOP definují službu jako "pro osobní potřebu" se zákazem poskytování
  třetí osobě, a totéž je zdarma v CERMAT). REDIZO se na rozdíl od URL
  seznamu (interní ID Atlasu, `/ss{id}-slug`) čte až z textu detailu školy.
  Živé stažení (22. 9. 2026) potvrdilo **215/215** škol z Atlasova seznamu
  pro Prahu úspěšně staženo a naimportováno (0 chybí HTML, 0 bez REDIZO) —
  o jednu víc než textový součet "Nalezeno 214 škol" v research dokumentu
  (drobný rozdíl proti dřívějšímu průzkumu, neřešeno dál). Smoke test proti
  živému webu zároveň odhalil, že první verze parseru (psaná jen podle
  textového popisu struktury bez živého ověření) měla víc chybných
  selektorů — `data-maxpages` je na vnořeném elementu, obor je rozložený do
  dvou `<tr>` (hlavní řádek + řádek se školným/prospěchem), název oboru a
  kód KKOV jsou oddělené elementy a číselné hodnoty používají pevnou mezeru
  jako oddělovač tisíců — parser i testy byly opraveny podle skutečného HTML.

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

### 11. Statistické výkazy MŠMT/ÚIV (výkonové ukazatele školství)
**Zvažováno, neověřeno.** `data.uiv.cz` / `stistko.msmt.cz` by měly
publikovat po školách počty žáků, tříd a pedagogů ze statistických výkazů
(řada S), tedy dopočitatelný **poměr žák/učitel a průměrnou velikost
třídy** — metriku kvality, kterou žádný z výše ověřených zdrojů nemá.
Potřeba ověřit dostupnost, formát a granularitu (škola vs. IZO) stažením,
jako u ostatních zdrojů.

### 12. PID / Golemio GTFS (dopravní dostupnost MHD)
**Zvažováno, neověřeno.** Alternativa k převzetí statického
`transit_graph.json` z `tangero/stredniskoly` (bod 10, neověřená licence)
— aktuální a udržovaná otevřená data Pražské integrované dopravy (GTFS
přes Golemio/PID) by šla použít pro vlastní dopočet reálné dojezdové doby
MHD ze zadané adresy do každé školy, bez závislosti na cizím scraperu.
Potřeba ověřit endpoint, licenci a formát (GTFS/GTFS-RT) a rozsah práce na
routing výpočtu.

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

## Průvodce výběrem školy

Podrobný návrh UX (proč které otázky, jak se počítá skóre a šance, co se
zobrazuje na kartě): [`docs/pruvodce-ux.md`](docs/pruvodce-ux.md).
Implementace: [`jaknastredni/pruvodce.py`](jaknastredni/pruvodce.py) +
[`jaknastredni/oblasti.py`](jaknastredni/oblasti.py).

Průvodce nic nestahuje a do databáze nezapisuje — jen ji čte. Základní
jednotkou je **nabídka = škola × obor** (623 denních nabídek pražských SŠ),
protože přihláška se podává na obor a všechna čísla (kapacita, poměr
přihlášek, hranice přijetí) jsou oborová.

Devět otázek (povinná jen první — ze které třídy se uchazeč hlásí), z nich
tvrdé filtry (třída, typ vzdělání, oblast zájmu, školné, jazyk) a průhledné
vážené skóre shody ze šesti složek (`zajem`, `dosazitelnost`, `kvalita`,
`blizkost`, `cena`, `prostredi`). Výstup:

- **5 nejlepších nabídek**, nejvýš jedna od každé školy, každá s důvody
  (`+`) i varováními (`!`);
- **návrh tří přihlášek** rozložený podle rizika (sen / realistická /
  jistota) — od roku 2024 se podávají tři přihlášky a pořadí priorit se
  nevyplatí taktizovat, což průvodce uživateli říká natvrdo.

Klikací prototyp je `web/index.html` (statická stránka, žádný server) —
data si bere z `web/data.js`, který se generuje z databáze:

```bash
python -m jaknastredni.export_web --db data/jaknastredni.db -o web/data.js
```

Soubor `web/data.js` se neverzuje (odvozený artefakt, stejně jako databáze).
Zdrojem pravdy o hodnocení zůstává `pruvodce.py` — export do dat přibaluje
i jeho konstanty, takže je web čte a nemá je opsané u sebe.

Průvodce čte **všechny** zdroje v tabulce `web_profil` (infoabsolvent, pak
Atlas školství); pozdější zdroj jen doplňuje, co chybí. Z Atlasu přibyl
doporučený prospěch (72 nabídek), skutečný počet loni přijatých (552) a
povinná lékařská prohlídka (570). Názvy klíčů se mezi scrapery liší
záměrně — aliasy řeší `_prvni()` v `pruvodce.py`, ne přejmenování ve
scraperech.

**Šance na přijetí** se u 550 z 623 nabídek **neodhaduje, ale měří**: ze
souborů uchazečů CERMAT (tabulka `prijimacky_pasmo`, importér
`jaknastredni.cermat_uchazeci`) se spočítá skutečný podíl přijatých v okolí
uchazečova bodového pásma — „ze 115 lidí s podobným skórem se jich dostalo
39". Odhad z minimálního skóru přijatého (`skor_prijati_min_cjma`) zůstává
jako záloha a jako kotva smršťování, protože je to ocasová hodnota a vychází
systematicky optimisticky — proti naměřeným datům až o 40 procentních bodů.
Naměřené podíly se vyhlazují isotonickou regresí (PAVA), aby šance nikdy
neklesla s rostoucími body; o použití naměřených dat se rozhoduje jednou za
nabídku, ne podle skóre, jinak vznikne útes na přepnutí metody. Obojí hlídá
test napříč všemi nabídkami. Žádné neprůhledné „skóre obtížnosti" jako
u agregátorů (zdroj 6) — vzorec je v dokumentaci i v kódu.

**Známky ze základky** ve veřejných datech nejsou: soubory uchazečů CERMAT
(156 210 řádků za rok 2026) neobsahují ani základní školu, ani prospěch,
a žádný jiný dataset základku na výsledky přijímaček neváže.

## Doporučený postup

1. ~~**Import rejstříku MŠMT**~~ hotovo (`jaknastredni/msmt.py`), zbývá
   ověřit číselník druhů (`C00` vs. `E00`).
2. **Import CERMAT XLSX**:
   - ~~maturita 2015–2026 (jeden parser)~~ hotovo
     (`jaknastredni/cermat_mz.py`, tabulka `maturita`).
   - ~~JPZ 2024–2026 (nový formát, 3 soubory × 2 kola × rok)~~ hotovo
     (`jaknastredni/cermat_jpz.py`, tabulka `prijimaci_rizeni`, klíč IZO +
     KKOV + zaměření/forma/délka/jazyk, prefix `izo_` odstraněn).
   - ~~JPZ 2017–2023 (starý formát, jen pro trendy na úrovni skupiny oborů,
     klíč REDIZO)~~ hotovo (`jaknastredni/cermat_jpz_old.py`, tabulka
     `jpz_skupina`).
3. ~~**Import ČŠI CSV**~~ hotovo (`jaknastredni/csi.py`, tabulka `inspekce`,
   14 912 řádků, 2003–2026) → seznam inspekcí per REDIZO; PDF stahovat jen
   pro školy na užším seznamu a extrahovat sekci „Závěry" zůstává budoucí
   krok (mimo rozsah tohoto importéru).
4. ~~**Scraper infoabsolvent.cz** (211 detailů, 1 req/s) pro přijímací
   kritéria, školné, jazyky, vybavení~~ hotovo (`jaknastredni/infoabsolvent.py`,
   tabulka `web_profil`, zdroj `infoabsolvent`). ~~**Scraper Atlas
   školství** pro doporučený prospěch, skutečný loňský počet přijatých a
   jako druhý zdroj pro křížovou kontrolu~~ hotovo (`jaknastredni/atlas.py`,
   tabulka `web_profil`, zdroj `atlas`, 215/215 škol, viz bod 4 v "Zdroje
   dat" výše). Vždy REDIZO z detailu/URL infoabsolventu, resp. z textu
   detailu Atlasu, ne z interního ID Atlasu v URL seznamu.
5. Prezentace: inspirovat se agregátorem (bod 6), ale metriky počítat
   z oficiálních dat s uvedeným vzorcem.

## Otevřené otázky

- Oficiální číselník druhů škol (AKDT) pro spolehlivý filtr SŠ/konzervatoř.
- Licence otevřených dat ČŠI a podmínky užití infoabsolvent.cz.
- ~~Konzistence hlaviček CERMAT souborů v neověřených letech (JPZ 2024–2025,
  MZ 2018–2025) — ověřit před ostrým importem.~~ Ověřeno živě 22. 9. 2026:
  všech 24 souborů MZ (2015–2026) a všech 6 kombinací rok×kolo JPZ nového
  formátu (2024–2026) se naparsovalo bez chyby se shodnými počty řádků jako
  v `data/raw/` (žádný soubor se od stažení nezměnil, ověřeno SHA-256/
  bytovou shodou). Jediná zjištěná odchylka: `PZ2025_kolo2_..._prihlasky.xlsx`
  má prázdné `ID_SOF` ve všech řádcích (datová chyba CERMAT, ne formátová
  změna) — neškodné, `_vysledky.xlsx` je nadmnožina, viz
  `docs/research/cermat.md`.
- Struktura sekcí v ČŠI PDF napříč šablonami různých let.
- Body 11 a 12 (výkonové ukazatele MŠMT/ÚIV, PID/Golemio GTFS) jsou zatím
  jen nápady bez ověření stažením — než se implementují, potřebují stejný
  research postup jako zdroje 1–6.
