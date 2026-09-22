# Průzkum: prijimacky-onlinekurzy.cz (agregátor škol) — 22. 9. 2026

Zdroj dat: přímé HTTP requesty (curl, UA `research-bot/1.0`, ~1 req/s, celkem
cca 12 requestů). Vše ověřeno na živých odpovědích, stažené soubory jsou v
`<scratchpad>/agregator/`.

## 1. robots.txt a podmínky užití

**robots.txt** (`https://prijimacky-onlinekurzy.cz/robots.txt`, HTTP 200):
- `User-agent: *` — obecně povoleno crawlování.
- Disallow pouze pro: `/admin/`, `/shop/*` (checkout, login, platby),
  `/ajax_*`, interní API endpointy (`/api_compare_school.php`,
  `/ajax_get_token.php` apod.), `/app/`, `/s/`, `/api/pvk/`.
- **Stránky `/mesto/...`, `/skola/...`, `/skoly`, `/kraj/...` NEJSOU
  zakázané** — robots.txt jejich čtení nijak neomezuje.
- Sitemap: `https://prijimacky-onlinekurzy.cz/sitemap.php` (obsahuje statické
  stránky, cca 557 kB) a `video-sitemap.php`.

**Podmínky užití**: samostatná stránka "podmínky užití" nenalezena (404 na
uhodnutých URL `/podminky-uziti`, `/terms`). Nalezené dokumenty:
- `/obchodni-podminky.php` (HTTP 200) — Všeobecné obchodní podmínky. Čl. 8
  ("Ochrana autorských práv a licence"): *"Veškerý Digitální obsah je
  autorským dílem Poskytovatele... Uživatel není oprávněn Digitální obsah ani
  jeho části jakkoliv šířit, kopírovat, sdílet s třetími osobami..."* —
  **týká se ale výslovně placeného kurzového obsahu (kurzy, materiály,
  uživatelský účet)**, ne obecně veřejně dostupných stránek databáze škol.
  Žádná explicitní klauzule k opakovanému scrapování/reuse dat ze stránek
  `/skola/*` a `/mesto/*` nebyla nalezena.
- `/ochrana-osobnich-udaju` (HTTP 200) — GDPR/zpracování osobních údajů,
  nerelevantní k datům o školách.

**Závěr k legalitě**: robots.txt technicky nebrání čtení veřejných stránek
`/skola/*` a `/mesto/*` v přiměřeném tempu. Obchodní podmínky ale obsahují
obecnou autorskoprávní doložku k "Digitálnímu obsahu" webu — **hromadné
stažení a republikování jejich odvozených dat (skóre obtížnosti, žebříčky
"nejžádanější obory") by mohlo být sporné**; doporučuji používat web jen jako
**inspiraci pro UX a jako vodítko k tomu, odkud brát validovaná primární data
(CERMAT XLSX)**, ne kopírovat jejich vlastní odvozené metriky 1:1. Toto
hodnocení je moje interpretace, ne právní stanovisko.

## 2. Stránka `/mesto/praha` — seznam škol

- HTTP 200, čistě server-rendered HTML (žádné `__NEXT_DATA__`, žádné
  `window.__...` JSON blob s daty, jen jeden `application/ld+json` blok s
  `Organization` schema — bez dat o školách).
- Text na stránce: **"185 škol"** celkem pro Prahu.
- **Stránkování**: klasické `?page=N` odkazy `page=2` … `page=10` (tj. ~19–20
  škol na stránku, 10 stránek).
- Filtrační UI (kraj/typ školy/vyhledávání) na této konkrétní stránce v HTML
  nebylo nalezeno; ale společná stránka `/skoly` (obecný seznam, ne
  city-specific) má formulář s poli:
  - `kraj` (select: 14 krajů, hodnota "Hlavní město Praha" apod.)
  - `typ_skoly` (select: `GY4`, `GY6`, `GY8`, `LYC`, `NAS`, `SOS`, `SOU` —
    zjevně kódy: gymnázium 4/6/8-leté, lyceum, nástavbové studium, SOŠ, SOU)
  - `mesto`, `search` (textové)
- V breadcrumbech na detailu školy se objevuje i URL vzor
  `/mesto/praha?district=10` (filtr na městskou část/Prahu 10) — nepřímo
  potvrzeno, ale samotný filtr jsem na stránce `/mesto/praha` nedohledal
  (možná JS-generovaný nebo dostupný jen přes odkaz z jiné stránky).

**Struktura "karty" školy v seznamu** (jedna `<div>` na školu):
- Název školy (`<h2>`)
- Adresa (ulice, město, PSČ) + odkaz na web školy
- Pro každý obor školy blok se 4 metrikami: **Přihlášeno**, **Přijato**,
  **Minimum** (bodů), **Průměr** (bodů) — tj. pole jsou agregovaná per obor,
  ne jen za celou školu
- Tlačítko "Zobrazit detail školy" s odkazem `/skola/{REDIZO}/{slug}`

**REDIZO v URL**: **ano, potvrzeno** — odkazy mají tvar `/skola/600004708/...`,
`/skola/600006573/...` atd. Číslo je devítimístné REDIZO (shoduje se s formátem
REDIZO z MŠMT rejstříku, viz README bod 3). To je důležité — umožňuje to
snadné párování jejich záznamů s oficiálním rejstříkem/CERMAT daty přes
REDIZO jako klíč.

## 3. Detail školy — příklad Obchodní akademie, Heroldovy sady (REDIZO 600006573)

URL vzor: `/skola/{REDIZO}/{slug}?rocnik={5|7|9}`.

**Hlavička**: název, adresa (ulice, město, PSČ), web školy, e-mail, telefon.
Rychlá navigace na obory přes anchor odkazy (`#ekonomicke-lyceum` atd.).

**Per obor blok** (opakuje se pro každý obor školy, id `data-obor="..."`):
- Název oboru + **kód oboru RVP** (např. `78-42-M/02` — přesně formát kódu
  oboru vzdělání používaný CERMATem/MŠMT)
- Proprietární badge typu *"1. nejžádanější 4letý obor v Praze (za 30 dní)"*
  — odvozeno z vlastní návštěvnosti/zájmu na webu, ne z oficiálních dat
- **"Skóre obtížnosti"** 0–100 (např. 65/100) — vlastní proprietární index,
  v JSON-LD popsáno jako *"Interní skóre obtížnosti pro tento obor je
  65/100"*
- **Tabulka let**: sloupce **2024, 2025, 2026** (skutečná data) + **"ODHAD
  2027"** (predikce). Řádky (metriky) pro každý rok:
  1. Kapacita oboru
  2. Přihlášeno celkem
  3. Přijato celkem
  4. **Šance (každý kolikátý?)** — odvozený poměr přihlášeno/přijato,
     vyjádřený jako "je přijat každý N-tý"
  5. Průměr bodů přijatých
  6. Minimum k přijetí (bodů)
- Info text u tabulky: *"Body představují výsledek ze státní části JPZ
  (CERMAT testy)... Data nezahrnují školní část zkoušek (vysvědčení,
  soutěže atp.)"* — tedy **explicitně přiznávají, že vychází z CERMAT JPZ
  výsledků**, ale bodové hranice pro přijetí (min/průměr) jsou stanovené
  školou, ne CERMATem (jak už uvádí README bod 1).

**Parametr `rocnik=5/7/9`**: ověřeno přímým porovnáním HTML pro `rocnik=9` a
`rocnik=5` u stejné školy — **veškerá číselná data v tabulkách (76 číselných
hodnot) byla identická**. Rozdíl je pouze v personalizovaném textu/CTA formuláře
"LEAD CAPTURE: Zaslání orientačního testu pro ročník" (marketingový lead-gen
formulář, přizpůsobený textem podle toho, v jaké třídě dítě je — typicky 5.
třída = přihlášky na 6leté gymnázium, 7. třída = 4leté gymnázium/8leté
gymnázium podle kontextu, 9. třída = běžné SŠ přihlášky). **Parametr tedy
neovlivňuje zobrazená statistická data**, jen marketing.

**XHR/JSON API**: **žádné nenalezeno**. Stránka je čistě server-side
renderovaná (žádný `__NEXT_DATA__`, žádný fetch dat o škole přes JS). Jediné
dva `fetch()` volání v HTML detailu:
- `POST /ajax_set_grade.php` — zjevně ukládá zvolený ročník (personalizace)
- `POST /ajax_capture_school_lead.php` — odesílá lead formulář (e-mail apod.)
Oba jsou v `robots.txt` implicitně kryté vzorem `Disallow: /ajax_*` (resp.
konkrétní `/ajax_get_token.php` aj.) — nejde o veřejné datové API, nejsou
určené k dotazování zvenčí.

**JSON-LD structured data** (`application/ld+json`) na detailu obsahuje:
- `BreadcrumbList` (cesta Domů → Seznam škol → kraj → město/district → škola)
- `EducationalOrganization` s `hasCourse[]` — pro každý obor název +
  `description` text obsahující "Interní skóre obtížnosti pro tento obor je
  X/100" (jediné strojově snadno parsovatelné pole ze skóre obtížnosti;
  samotná tabulka bodů/přijetí v JSON-LD není).

## 4. Reprodukovatelnost metrik z oficiálních CERMAT XLSX (README bod 1)

| Metrika na agregátoru | Reprodukovatelné z CERMAT XLSX? |
|---|---|
| Přihlášeno celkem (per obor/rok) | **Ano** — přímo v CERMAT XLSX (počty přihlášených) |
| Přijato celkem (per obor/rok) | **Ano** — přímo v CERMAT XLSX |
| Průměr bodů přijatých | **Ano** — CERMAT publikuje průměrné % skóre; nutno ověřit přesnou definici (může jít o vlastní přepočet z % na "body") |
| Minimum k přijetí (bodů) | **Pravděpodobně ne přímo** — README bod 1 výslovně uvádí, že CERMAT centrálně nezveřejňuje bodové hranice pro přijetí (ty si stanovuje škola). Agregátor to pravděpodobně dopočítává z min. skóre přijatého uchazeče v CERMAT datech (odvozeno, ne oficiální hranice) — **neověřeno**, jde o mou domněnku |
| Kapacita oboru | **Ne z CERMATu** — kapacita je v MŠMT rejstříku škol (README bod 3), ne v CERMAT výsledkových XLSX |
| Kód oboru RVP | **Ano** — je v MŠMT rejstříku i v CERMAT datech |
| "Šance (každý kolikátý?)" | **Ano, lehce dopočitatelné** — jednoduchý odvozený poměr přihlášeno/přijato, žádná externí data navíc |
| "Skóre obtížnosti" 0–100 | **Ne, proprietární** — vlastní index (pravděpodobně kombinace poměru přihlášeno/přijato, min. bodů a/nebo návštěvnosti webu); metodika nikde nezveřejněna |
| Žebříček "nejžádanější obor (30 dní)" | **Ne, proprietární** — založeno na vlastní webové návštěvnosti/zájmu uživatelů agregátoru, nelze reprodukovat z veřejných dat |
| "ODHAD 2027" (predikce) | **Ne přímo** — vlastní predikční model nad historickými řadami; dalo by se nahradit vlastní jednoduchou extrapolací, ale metodika není veřejná |

**Shrnutí**: přibližně 70 % zobrazených čísel (přihlášeno/přijato/průměr
bodů/kapacita/kód oboru) je reprodukovatelných kombinací CERMAT XLSX +
MŠMT rejstříku (přes REDIZO jako společný klíč). Zbytek (skóre obtížnosti,
žebříčky zájmu, predikce) je proprietární a nedá se z veřejných zdrojů
ověřit ani legálně převzít — u vlastního projektu je lepší tyto koncepty
znovu odvodit z vlastní, průhledné metodiky, ne kopírovat jejich čísla.

## 5. UX nápady pro vlastní prezentaci

- **Karta školy s obory jako sub-bloky** — přehledné 4 metriky
  (přihlášeno/přijato/min/průměr) v mini-gridu per obor, funguje dobře i na
  mobilu.
- **Tabulka let vedle sebe (2024/2025/2026 + odhad)** — okamžitě vidět trend
  náročnosti bez nutnosti klikat na graf.
- **Filtry**: kraj → město/městská část (district), typ školy (gymnázium
  4/6/8leté, lyceum, SOŠ, SOU), fulltext search podle názvu/adresy.
- **Odvozená metrika "šance" (kolikátý je přijat)** je intuitivnější pro
  laika než syrová procenta — stojí za zvážení jako vlastní, transparentně
  spočítaná metrika (s uvedením vzorce).
- **REDIZO v URL detailu** — dobrý vzor pro vlastní routing/identifikátory,
  usnadní propojení s CERMAT/MŠMT daty a deep-linkování.
- **Breadcrumb hierarchie kraj → město/městská část → škola** — vhodné i pro
  filtrování/URL strukturu vlastní databáze pražských škol po městských
  částech.
- Co **nekopírovat**: proprietární "skóre obtížnosti" a žebříčky "nejžádanější
  za 30 dní" (založené na jejich vlastní návštěvnosti) — pro vlastní projekt
  by šlo nahradit něčím ověřitelným, např. meziroční trend poměru
  přihlášeno/kapacita z CERMAT dat.
- Zvážit srovnávací (compare) view víc oborů/škol vedle sebe — na agregátoru
  jsem explicitní "porovnávač" UI nenašel (jen skrytý/blokovaný endpoint
  `/api_compare_school.php` v robots.txt, což naznačuje, že podobnou funkci
  mají, ale renderuje se jinak nebo je za placenou zdí — **neověřeno přímo**).

## Poznámka k metodě

Nebyl proveden žádný pokus o obejití `Disallow` pravidel ani o volání
zakázaných AJAX/API endpointů. Všechna tvrzení o obsahu stránek jsou založena
na přímo stažených HTML odpovědích (uložené soubory v pracovním adresáři).
Věci označené jako "neověřeno" nebo "moje domněnka" nejsou potvrzeny přímým
pozorováním a je třeba je brát jako hypotézu.
