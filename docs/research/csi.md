# Česká školní inspekce (ČŠI) — průzkum zdrojů dat

Datum průzkumu: 2026-09-22. Vše níže ověřeno živými HTTP requesty (curl), pokud
není výslovně označeno jako neověřené.

## 1. opendata.csicr.cz — katalog datasetů

Homepage `https://opendata.csicr.cz/` vypisuje **81 datasetů** (potvrzeno
parsováním HTML — `<a href="/DataSet/Detail/{id}"><h3>Název</h3></a>`).
Rozpad podle typu:

- **1× „Inspekční zprávy“** (id 69) — **jediný dataset navázaný na konkrétní
  školu přes REDIZO** (viz níže, klíčový zdroj).
- **1× „Konkurzy na ředitele škol“** (id 24) — obsahuje pravděpodobně také
  REDIZO/název školy (obsah nekontrolován detailně, jen metadata stránky —
  **neověřeno**, doporučuji zkontrolovat zvlášť, pokud je relevantní).
- **1× „Mezinárodní šetření PIRLS 2016“** (id 68) — mezinárodní žákovské
  šetření, agregovaná/anonymizovaná data, nenavázané na školu.
- **78× ročníkové „Dotazník pro ředitele/učitele MŠ/ZŠ/SŠ“ a „Hospitační
  záznam MŠ/ZŠ/SŠ“** za školní roky 2016/2017 až 2024/2025 (13 datasetů ×
  6 ročníků, různé kombinace) — podle README projektu i podle vzorku staženého
  z detailu datasetu **anonymizované, bez identifikace konkrétní školy**
  (nekontroloval jsem obsah každého z 78 souborů jednotlivě, ale struktura
  detailní stránky a popis odpovídá README poznámce — **z větší části
  neověřeno stažením, jen podle popisků**).

Formáty: každý dataset má obvykle 3 „transformace“ ke stažení — **CSV, JSON,
XML** (stejná data, různý formát), odkazy typu
`https://opendata.csicr.cz/Transformation/Download/{id}`.

### 1.1 Dataset „Inspekční zprávy“ (id 69) — hlavní zdroj

- Detail: `https://opendata.csicr.cz/DataSet/Detail/69`
- Stažení:
  - CSV: `https://opendata.csicr.cz/Transformation/Download/137` (3,76 MB, `text/csv`, jméno souboru `inspekcni_zpravy.csv`)
  - XML: `https://opendata.csicr.cz/Transformation/Download/138` (4,42 MB)
  - JSON: `https://opendata.csicr.cz/Transformation/Download/139` (4,66 MB)
- **14 912 řádků** (1 řádek = 1 inspekční akce u 1 školy, školy s více
  inspekcemi mají víc řádků). Data sahají od 2003 do 2026-06 (nejnovější
  řádky jsou z června 2026), currently udržovaný/aktualizovaný dataset.
- **Sloupce (CSV, UTF-8, řádně quotované, `,` jako oddělovač):**

  | sloupec | popis | příklad |
  |---|---|---|
  | `REDIZO` | REDIZO školy (string, ale číselné) | `600006573` |
  | `Jmeno` | název školy v době inspekce | `Obchodní akademie, Praha 10, Heroldovy sady 1` |
  | `DatumOd` | začátek inspekční činnosti (ISO datetime) | `2017-10-03T00:00:00.0000000` |
  | `DatumDo` | konec inspekční činnosti | `2017-10-06T23:59:59.9990000` |
  | `LinkIZ` | **přímý odkaz na PDF zprávy** | `https://portal.csicr.cz/Files/Get/739cc2311d474c6e9541fb02a8ddf665` |
  | `PortalLink` | odkaz na stránku školy na portal.csicr.cz | `https://portal.csicr.cz/School/600006573` |

  Pozn.: u pár starých/archivních záznamů má `LinkIZ` jiný tvar
  (`.../Files/Get/{GUID}?db=Archive`) a `DatumDo` obsahuje nesmyslné datum
  daleko v budoucnosti (rok 2203, 3000) — zjevně technický artefakt pro
  „stále platné“/archivní záznamy, počítat s tím při parsování dat.

- **Záznam pro pražskou školu (REDIZO 600006573 — Obchodní akademie, Praha 10,
  Heroldovy sady 1)** — nalezen přesně 1 řádek:
  ```
  REDIZO=600006573, Jmeno="Obchodní akademie, Praha 10, Heroldovy sady 1",
  DatumOd=2017-10-03, DatumDo=2017-10-06,
  LinkIZ=https://portal.csicr.cz/Files/Get/739cc2311d474c6e9541fb02a8ddf665,
  PortalLink=https://portal.csicr.cz/School/600006573
  ```
  Tzn. tato konkrétní škola má v datasetu zaznamenánu jen jednu inspekci
  (2017) za celé sledované období — běžné, inspekce se u jedné školy
  neopakují každý rok.

- `LinkIZ` (i `PortalLink`) je **veřejně stažitelný bez přihlášení** —
  ověřeno `curl` (HTTP 200, `Content-Type: application/pdf`).

## 2. Registr inspekčních zpráv na csicr.cz

- URL: `https://www.csicr.cz/cz/Registr-inspekcnich-zprav`
- Je to **klasický ASP.NET/Kentico formulář** (postback), ne REST/JSON API.
  Vyhledávací pole: `jmeno`, `adresa`, `mesto`, `ic`, `identifikator` (REDIZO).
  Filtrování přes `GET ?identifikator=...` **nefunguje** (testováno —
  vrátí nefiltrovanou stránku), formulář zjevně vyžaduje POST/AJAX callback,
  který jsem nerozklíčoval (JS `WebForm_DoCallback`/`PM_Callback` —
  proprietární ASP.NET callback mechanismus, ne standardní JSON XHR).
- **Funguje ale jednoduchý GET vzor pro detail školy**: `?d={interní_id}`,
  např. `https://www.csicr.cz/cz/Registr-inspekcnich-zprav?d=39702` vrátí
  čisté HTML s tabulkou (Počátek/Konec inspekce, odkaz „Zpráva“ na
  `https://portal.csicr.cz/Files/Get/{GUID}` — stejný vzor jako `LinkIZ`
  v opendata CSV). Tohle `{interní_id}` **není REDIZO** a nezjistil jsem
  přímý veřejný převodník REDIZO → `d=`.
- Neregistrovaný dotaz (bez filtru) vrací **975 stránek** (15 škol/stránka
  ⇒ cca 14 600 škol celkem, souhlasí řádově s počtem škol v ČR) — potvrzuje,
  že registr pokrývá všechny typy škol/zařízení, ne jen SŠ.
- **Závěr**: registr na csicr.cz je pro programové stažení horší volba než
  opendata CSV — nemá čistý JSON/GET filtr podle REDIZO a interní ID škol
  neodpovídá REDIZO. Odkazy na PDF zprávy (`portal.csicr.cz/Files/Get/{GUID}`)
  jsou identické s těmi v opendata datasetu, takže **stačí použít opendata
  CSV jako zdroj pravdy** a registr na csicr.cz ignorovat.
- Počet zpráv pro pražské SŠ za posledních ~6 let: **nezjištěno přesně**
  přes registr (chybí filtr podle kraje/typu školy v použitelné podobě).
  Hrubý odhad z opendata CSV (název obsahuje „Praha“, od 2020) = **563
  řádků**, ale to zahrnuje všechny typy škol/zařízení s „Praha“ v názvu
  (MŠ, ZŠ, SVČ...), ne jen SŠ — **jde jen o orientační horní odhad**,
  přesné číslo vyžaduje JOIN s registrem MŠMT (seznam REDIZO pražských SŠ).

## 3. portal.csicr.cz (InspIS PORTÁL)

- Vyhledávací formulář: `https://portal.csicr.cz/Search/School`, POSTuje
  (unobtrusive AJAX, `data-ajax="true"`) na
  `https://portal.csicr.cz/Search/SchoolSearch?Length=6`.
- Formulářová pole zahrnují **`a03REDIZO`** (RED-IZO), `a03ICO`, `a03Name`,
  `a03Street`, `a03City`, `a05ID` (kraj — **Praha = `1`**), `a17UIVCode`
  (typ školy — **střední školy = `C`**), `a09ID` (typ zřizovatele), a
  souřadnice pro vyhledávání v okolí.
- Testovací POST (`a17UIVCode=C&a05ID=1`, tj. SŠ v Praze) vrátil **HTTP 200**
  a fragment HTML s hláškou „Bylo nalezeno **217** škol“ — tzn. **v Praze je
  evidováno 217 středních škol/zařízení tohoto typu na portále ČŠI**
  (řádově odpovídá i jiným zdrojům v README). Ale samotná tabulka výsledků
  se **nenaplnila daty** (0 řádků) — endpoint je zjevně stavový (session
  cookie `CSIPortal_0`/`SERVERID`) a vyžaduje předchozí GET na `/Search/School`
  + správně udržovaný postback stav; naivní přímý POST bez plné inicializace
  session nefunguje spolehlivě pro stažení řádků. Následný pokus o stránkování
  (`GET /Search/SchoolSearch?p=1`) skončil chybou serveru (500, `Int32
  overflow`).
- **Závěr**: portal.csicr.cz **nemá čistý/dokumentovaný JSON endpoint**;
  jde o stavový ASP.NET AJAX formulář, který vrací HTML fragmenty a je
  citlivý na session/postback stav. Pole `a03REDIZO` potvrzuje, že REDIZO je
  interním identifikátorem i zde, ale spolehlivé hromadné strojové
  scrapování by vyžadovalo emulaci prohlížeče (Selenium/Playwright) nebo
  detailnější rozklíčování ASP.NET postback protokolu — **nedoporučuji pro
  tento projekt**, opendata CSV je jednodušší a spolehlivější.
- Stránka jedné školy (`https://portal.csicr.cz/School/{REDIZO}`) funguje
  jako čisté GET (ověřeno pro 600006573) a obsahuje kontakty, mapu, odkazy
  na PDF zprávy (`/Files/Get/{GUID}`) a odkaz na infoabsolvent.cz profil —
  ale opět jen HTML, žádné strukturované JSON.

## 4. robots.txt a licence

- **robots.txt neexistuje na žádné ze tří domén** — `opendata.csicr.cz`,
  `www.csicr.cz` i `portal.csicr.cz` vrací na `/robots.txt` HTTP 404 (žádné
  explicitní omezení pro roboty, ale také žádné explicitní svolení).
- **Licence**: na homepage opendata.csicr.cz ani na detailu datasetu
  „Inspekční zprávy“ jsem **nenašel explicitní licenční doložku** (žádný
  text „licence“/„CC BY“ v HTML). Nezkoušel jsem hlouběji NKOD/data.gov.cz
  katalogový záznam (dotaz na data.gov.cz vracel 400/404 na jednoduché
  testy). **Licence tedy zůstává neověřená** — doporučuji před produkčním
  použitím ověřit explicitně (např. přes datovou schránku/kontaktní
  formulář ČŠI, nebo v NKOD zápisu datové sady), i když jde o veřejnou
  instituci a „otevřená data“ jsou takto sama ČŠI označena.

## 5. Test extrakce PDF zprávy (REDIZO 600006573, Praha 10, Obchodní akademie)

- PDF staženo přímo z `LinkIZ` (bez přihlášení), 280 KB, 8 stran,
  `application/pdf`.
- `pdftotext` **nebyl v prostředí dostupný** (poppler-utils chybí).
  `pypdf` selhal kvůli chybějící/vadné binární závislosti (`_cffi_backend` /
  `cryptography` konflikt v tomto sandboxu — **prostředí-specifický
  problém**, ne problém samotného PDF).
- **`pymupdf` (fitz) fungoval bez problémů** (`pip install pymupdf`) a
  extrahoval **čistý, dobře strukturovaný text** (20 615 znaků, 8 stran).
- Text obsahuje jasně nadepsané sekce (rozpoznatelné regexem/řádkovým
  parserem): `Hodnocení podmínek vzdělávání`, `Hodnocení průběhu
  vzdělávání`, `Hodnocení výsledků vzdělávání`, **`Závěry`** →
  `Hodnocení vývoje`, **`Silné stránky`** (odrážkový seznam), `Příležitosti
  ke zlepšení`, **`Doporučení pro zlepšení činnosti školy`**. Hlavička
  zprávy navíc strojově čitelně obsahuje `Identifikátor` (REDIZO), `IČ`,
  `Sídlo`, `Zřizovatel`, `Termín inspekční činnosti`.
- Formát sekcí (nadpis na vlastním řádku, poté odrážky `- text`) byl u tohoto
  vzorku velmi konzistentní a snadno parsovatelný jednoduchým řádkovým
  skriptem (detekce nadpisu → sběr odrážek do dalšího nadpisu). **Ověřeno jen
  na 1 zprávě** — struktura sekcí (názvy, přítomnost „Silné stránky“ vs. jen
  „Závěry“) se mezi lety/typy inspekcí pravděpodobně mírně liší (starší/nové
  šablony ČŠI), takže parser bude potřeba otestovat na větším vzorku a
  ošetřit varianty.

## Doporučení pro Python import

1. **Zdroj pravdy**: stahovat `https://opendata.csicr.cz/Transformation/Download/137`
   (CSV dataset „Inspekční zprávy“, id 69) pravidelně (je průběžně
   aktualizovaný, obsahuje záznamy až do běžícího školního roku). JSON
   varianta (id 139) je alternativa, pokud je pohodlnější než CSV parsing.
2. **Filtrace na pražské SŠ**: dataset sám neobsahuje kraj ani typ školy —
   je nutné **JOIN podle REDIZO** s MŠMT registrem škol (viz README bod 3,
   dataset `00022985` na data.gov.cz), který kraj i typ školy obsahuje.
   Filtrování podle „Praha“ v názvu (jak jsem to udělal pro rychlý odhad)
   **není spolehlivé** (falešně vynechá školy bez „Praha“ v názvu, zahrne
   MŠ/ZŠ/SVČ s „Praha“ v názvu).
3. **Stahování PDF**: iterovat přes `LinkIZ` z CSV, ukládat PDF lokálně
   (žádné rate-limity nebyly pozorovány, ale doporučuji šetrné tempo a
   `User-Agent`/kontakt v hlavičce jako slušnost vůči veřejné instituci).
4. **Extrakce textu**: použít `pymupdf` (`import fitz` / `pymupdf`), ne
   `pdftotext`/`pypdf` (v tomto sandboxu nefunkční — v jiném prostředí může
   být `pypdf` v pořádku, ale `pymupdf` je ověřeně funkční a dává čistý
   layoutový text).
5. **Parsování závěrů**: jednoduchý stavový řádkový parser hledající nadpisy
   `Závěry`, `Hodnocení vývoje`, `Silné stránky`, `Slabé stránky`/`Příležitosti
   ke zlepšení`, `Doporučení pro zlepšení činnosti školy` a sbírající
   odrážky (`- ...`) do dalšího nadpisu — otestovat na širším vzorku (10–20
   zpráv různých let/typů škol) před nasazením, kvůli variabilitě šablon.
6. **portal.csicr.cz a registr na csicr.cz přeskočit** jako zdroje pro
   automatizaci — nemají spolehlivé strojové rozhraní; PDF odkazy, které by
   odtud šly získat, jsou identické s těmi v opendata CSV, takže žádná
   dodatečná hodnota za cenu výrazně vyšší implementační složitosti
   (session/postback handling).

## Problémy a otevřené otázky

- Licence použití opendata dat ČŠI nebyla explicitně nalezena/ověřena.
- Přesný počet inspekčních zpráv pro pražské SŠ za posledních 6 let
  nebyl spočítán přesně (vyžaduje JOIN s registrem MŠMT) — jen hrubý odhad
  563 (nadhodnocený, zahrnuje i jiné typy škol).
- Dataset „Konkurzy na ředitele škol“ (id 24) nebyl obsahově prozkoumán
  (jen metadata stránky) — může/nemusí být užitečný doplněk, ale nebyl
  ověřen stažením obsahu.
- Struktura sekcí v PDF zprávách ověřena jen na 1 vzorku — riziko variace
  mezi šablonami různých let.
