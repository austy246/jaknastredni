# Doplňkový průzkum zdrojů dat o středních školách v Praze

Navazuje na `/home/user/jaknastredni/README.md` (9 už prozkoumaných zdrojů). Cílem
bylo najít a **ověřit** (skutečně načtenou stránkou/souborem) další zdroje.
Vše níže bylo ověřeno živě (curl/WebFetch/WebSearch) 22. 9. 2026, pokud není
uvedeno jinak jako "neověřeno".


> **Poznámka koordinátora:** tvrzení v sekci C, že maturitní XLSX po školách neexistují, je nesprávné. Souběžný průzkum CERMAT je reálně stáhl z `/maturitni-zkouska/agregovana-data.html` (soubory `MZ{rok}j_SC_skolobory.xlsx`, 2015–2026), viz [`cermat.md`](cermat.md).

---

## A. Nejvýznamnější nový nález: `tangero/stredniskoly` / prijimackynaskolu.cz

**Vysoká užitečnost — pravděpodobně nejlepší jednotlivý doplňkový zdroj.**

- Repo: https://github.com/tangero/stredniskoly (ověřeno – README, `raw.githubusercontent.com` soubory)
- Veřejný web: **https://www.prijimackynaskolu.cz/** (ověřeno WebFetch) — provozuje
  Patrick Zandl ve spolupráci s Hlídačem státu, kontakt eda@prijimackynaskolu.cz
  (dle WebSearch výsledků, neověřeno přímo stránkou "O projektu").
- Repozitář **kombinuje přesně to, co potřebujeme**: CERMAT výsledky přijímaček
  (2023–2026), MŠMT rejstřík škol, ČŠI InspIS profily škol, dopravní
  dostupnost MHD a manuální mapování oborů. Web nabízí simulátor "kam se s
  danými body dostanu" a sekci dostupnosti MHD do školy.
- **Klíčový podnález** — soubor
  `data/inspis_school_profiles.json` (ověřeno staženo, 4,3 MB):
  strukturovaná data **po škole, klíčovaná REDIZO**, čerpaná z
  portal.csicr.cz (InspIS PORTÁL) — přesně ten zdroj, který README v bodě 4
  označuje za "jen web, bez datového exportu". Obsahuje pro 1180 škol pole
  jako `redizo`, `rocni_skolne`, `zamereni`, `aktualni_pocet_zaku`,
  `nejvyssi_povoleny_pocet_zaku` a desítky dalších (dle statistik v souboru:
  548 441 řádků zdrojového CSV, pokrytí 100 % škol). Je to tedy hotový
  **scraper ČŠI InspIS Portálu** s výstupem ve strojově čitelném JSON.
- Další soubory v `data/`: `school_locations.json` (geolokace),
  `transit_graph.json` (MHD dostupnost), `csi_manifest.json`,
  `csi_diff_latest.json`, `obory_matching.json` (mapování oborů KKOV),
  `msmt_rejstrik/` (podsložka s daty z rejstříku).
- Formát: JSON/CSV. Licence repozitáře: v repu jsem nenašel explicitní
  soubor `LICENSE` (404) — **licence needefinována/neověřena**, nutno
  ověřit před re-use nebo kontaktovat autora.
- Doporučení: prostudovat celý obsah `data/` adresáře (nemám plný přístup
  bez `add_repo`/GitHub API v této session) — pravděpodobně obsahuje víc
  užitečného než co jsem stihl ověřit.

## B. `FilipSivak/cermat-data` (GitHub)

**Nízká–střední užitečnost (zastaralé, ale historicky zajímavé).**

- https://github.com/FilipSivak/cermat-data (ověřeno, README staženo)
- Neoficiální kompilace dat z `vysledky.cermat.cz/data` (starý agregovaný
  dashboard), MIT-duchá licence (autor píše "neoficiální", žádost o
  zodpovědné zacházení).
- Ke stažení: jeden statický snapshot `maturita_19-07-2020.xlsx` (release
  1.0.0, ověřeno URL existuje) — **data z roku 2020**, tedy zastaralá vůči
  nověji ověřeným oficiálním XLSX z data.cermat.cz (viz níže).
- Python skript `download.py` na opakovatelné stažení z starého UI.

## C. CERMAT — upřesnění a ověření struktury XLSX (rozšiřuje bod 1 README)

**Vysoká užitečnost — potvrzuje a upřesňuje již nalezený zdroj.**

- Skutečná (aktuální) cesta k souborům JPZ (přijímačky), ověřeno staženo a
  otevřeno v Pythonu (openpyxl):
  `https://data.cermat.cz/data-a-analyticke-vystupy-jednotna-prijimaci-zkouska/agregovana-data-jpz.html`
  → přímé XLSX, např.
  `https://data.cermat.cz/files/files/JPZ/agregovana_data_skoly/PZ2025_kolo1_skolobory_vysledky.xlsx`
  (staženo, 3,6 MB), s obdobou pro roky **2022–2026**, kola 1 a 2, a
  samostatné soubory `_kapacity`, `_prihlasky`, `_vysledky`.
- **Ověřená granularita**: řádek = škola × obor × ročník. Sloupce mj.:
  `IZO`, `REDIZO`, `NÁZEV ŠKOLY`, adresa, `KRAJ`, `ZŘIZOVATEL`, `KKOV`
  (kód oboru), `KAPACITA`, `PŘIHLÁŠKY CELKEM`, `PŘIJATÍ` (i podle priority
  1–5), `ČJ`/`MA`/`ČJ+MA — % SKÓR — PRŮMĚR/MIN/MAX` a totéž pro
  `PERCENTIL`, zvlášť za všechny uchazeče a zvlášť za přijaté, plus důvody
  nepřijetí. Toto je nejbohatší jediný soubor v celém průzkumu.
- Stránka `aktuality/vysledky-skol-u-prijimacich-zkousek-2025-ke-stazeni.html`
  (ověřeno, HTTP 200) potvrzuje popis obsahu a odkazuje na tutéž sekci.
- Pro **maturitu** jsem obdobnou stránku s XLSX po školách (na úrovni
  škola/obor/předmět) **nenašel** — aktuální článek
  `aktuality/vysledky-maturitnich-didaktickych-testu-2026.html` (ověřeno,
  HTTP 200) odkazuje jen na interaktivní vizualizaci
  `/maturitni-zkouska/vizualizace-dat.html` (Power BI, bez staženého XLSX
  v HTML). To odpovídá tomu, co už README uvádí (Power BI bez
  dokumentovaného API/exportu) — nic nového jsem zde neobjevil, jen
  potvrzuji, že rozdíl JPZ (má XLSX) vs. MZ (jen dashboard) přetrvává i
  v roce 2026.

## D. data.gov.cz / NKOD — ověřeno přes SPARQL endpoint

**Nízká přidaná hodnota nad rámec README bodu 3, ale užitečné jako negativní zjištění.**

SPARQL endpoint `https://data.gov.cz/sparql` funguje a je dotazovatelný
(na rozdíl od HTML vyhledávání, které je SPA a curl nevrací výsledky).
Ověřené dotazy:

- Datasety s "maturit" nebo "přijímac" v názvu: kromě již známého
  registru škol (00022985) našel jen **krajské** datasety —
  Královéhradecký kraj ("Přijímací řízení na střední školy", "Počet žáků
  dle oborů..."), Karlovarský kraj ("Záměr počtu přijímaných uchazečů..."),
  Olomoucký kraj ("Dostupnost středních škol..."), obec Děčín. **Žádný
  není od hl. m. Prahy.**
- Dotaz na datasety s vydavatelem IČO hl. m. Prahy (00064581) v NKOD:
  vrátil **jediný** dataset — "Veřejné osvětlení MHMP" (veřejné osvětlení,
  nic se školstvím). To znamená, že magistrát Prahy **nemá v celostátním
  katalogu NKOD zaregistrovaný žádný dataset o školách** — případná data
  o školách na opendata.praha.eu (viz níže) tedy buď nejsou harmonizována
  do NKOD, nebo neexistují.
- "Úspěšnost žáků základních škol v přijímacím řízení na střední školy" je
  v NKOD veden jen jako **podnět na otevření dat** (`podněty-na-data-k-otevření/4`),
  ne jako existující dataset — potvrzuje, že tahle konkrétní agregace
  oficiálně neexistuje.
- **Praktické doporučení**: pro budoucí scraping/monitoring datasetů použít
  přímo SPARQL endpoint `data.gov.cz/sparql` (rychlé, strojově čitelné),
  místo HTML vyhledávání (JS SPA, curl nefunguje).

## E. opendata.praha.eu / Golemio

**Nízká–střední, neúplně ověřeno.**

- opendata.praha.eu nyní běží na platformě `lkod.cz/catalog/praha`
  (ověřeno přesměrování 301). Katalog má 23 organizací, 407 datových sad,
  z toho téma "Vzdělávání, kultura a sport" má **10 datových sad** (ověřeno
  z JSON-LD/textu stránky), ale vyhledávací UI je Next.js SPA a přes curl
  nejde vylistovat konkrétní tituly bez spuštění JS — **nepodařilo se mi
  ověřit konkrétní názvy/URL** těchto 10 datasetů. Z dřívějšího webového
  vyhledávání vyplývá, že existují datasety jednotlivých městských částí
  (např. Praha 8) s počty tříd/žáků na **základních** školách a MŠ — SŠ
  patrně nejsou v gesci městských částí, takže pravděpodobnost SŠ datasetu
  na této úrovni je nízká (**neověřeno jistě**).
- Golemio (golemio.cz / Operátor ICT) je obecná datová platforma města,
  žádný konkrétní SŠ dataset jsem v ní nenašel a nepotvrdil.
- **Doporučení**: pro definitivní ověření je třeba načíst
  `lkod.cz/catalog/praha/datasets` s JS renderem (Playwright) nebo použít
  DCAT distribuci katalogu Prahy přímo přes SPARQL/CKAN API, což se v
  rámci tohoto průzkumu nepodařilo (žádosti vracely jen skeleton HTML).

## F. Magistrát Prahy — koncepční/výroční dokumenty (PDF, ne strukturovaná data)

**Nízká pro datový model, ale užitečné jako kontext/kvalitativní zdroj.**

- **Dlouhodobý záměr vzdělávání a rozvoje vzdělávací soustavy hl. m. Prahy**
  — ověřené PDF odkazy (nalezeny WebSearch, formát/URL vypadá důvěryhodně,
  obsah stránek jsem needitovanou verzi nefetchoval celou):
  - 2020–2024: `https://www.edu.cz/wp-content/uploads/2021/02/DZ_hl.m.Praha_2020_2024.pdf`
  - 2024–2028: `https://edu.gov.cz/wp-content/uploads/2024/07/09_Praha_DZ-HMP-2024-2028.pdf`
  - Rozcestník verzí 2008–2028: `https://www.prahaskolska.eu/mhmp-post/dlouhodoby-zamer-vzdelavani-a-rozvoje-vzdelavaci-soustavy-hl-m-prahy/`
- **Výroční zprávy o stavu a rozvoji vzdělávací soustavy HMP** — archiv od
  školního roku 2000/2001 na portálu `skoly.praha.eu` (dle WebSearch
  výsledků; přímý odkaz na jeden ročník jsem ověřil: 2018/2019 na
  `https://skoly.praha.eu/files/=86399/vyrocni_zprava_o_stavu_a_rozvoji_vzdelavaci_soustavy_HMP_2018_2019.pdf`
  — **URL nalezeno vyhledáváním, samotné stažení/otevření PDF jsem
  neprovedl**, takže obsah (zda má tabulky po školách) je **neověřený**).
  Portál `skoly.praha.eu` teď přesměrovává na `praha.eu/skolstvi-v-praze`
  (ověřeno 302), který dál odkazuje na `prahaskolska.eu` — struktura webu
  se zjevně mění, staré odkazy mohou přestat fungovat.
- Obě sady dokumentů jsou **PDF, ne tabulková/strojová data** — typicky
  souhrnné statistiky (počty škol, žáků, kapacit, demografické prognózy),
  ne nutně rozpad po jednotlivých školách. Nutno ručně prolistovat, než se
  investuje do parsování.

## G. Wikidata — REDIZO jako identifikátor (P6370)

**Střední užitečnost — funguje jako case-insensitive křížový klíč, ale nízké pokrytí.**

- Vlastnost `P6370` (REDIZO ID) na Wikidatech — ověřeno WebFetch stránky
  vlastnosti: 9místné číslo, zdroj dat rejstriky.msmt.cz, formátovací URL
  na `portal.csicr.cz/School/$1`.
- Ověřeno SPARQL dotazem na `query.wikidata.org/sparql`:
  **7062 položek** na celém Wikidatech má vyplněné P6370 (běžel dotaz,
  vrátil HTTP 200, přesné číslo). Dotaz omezený jen na položky ležící v
  Praze (přes P131*) se **timeoutoval** (HTTP 504) — počet pražských SŠ s
  REDIZO na Wikidatech **neověřen**, nutno dotaz rozdělit/optimalizovat.
- Využitelnost: umožňuje párovat Wikidata Q-ID (a tedy Wikipedia články,
  souřadnice, commonscat) se REDIZO, ale pokrytí je neúplné (ne každá SŠ
  má Wikidata položku) a je třeba počítat s ručním doplňováním.

## H. OpenStreetMap — tag `ref:redizo`

**Nízká užitečnost — řídké pokrytí, ale ověřeno.**

- Ověřeno přes Taginfo API (`taginfo.openstreetmap.org/api/4/...`):
  tag `ref:redizo` má celkem **213 použití** (194 distinct hodnot) napříč
  celou OSM databází (nody/ways/relace), tag `redizo` (bez namespace) jen
  7 použití. Vzhledem k tomu, že v ČR je řádově tisíce škol, je pokrytí v
  OSM **výrazně neúplné** — nespoléhat se na OSM jako primární zdroj
  REDIZO, ale dá se použít jako doplněk ke geolokaci/adrese budov, které
  REDIZO mají vyplněné.

## I. seznamskol.eu, vysokeskoly.cz, stredniskoly.cz, infoabsolvent.cz

**Nízká přidaná hodnota — nic nového oproti README.**

- `seznamskol.eu` — popisuje se jako "největší databáze škol v ČR", má
  stránky jednotlivých škol (ověřeno existenci konkrétní stránky školy
  přes WebSearch výsledek), ale žádné API jsem nenašel ani nepotvrdil.
- `vysokeskoly.cz` má katalog, ale primárně pro VŠ, ne SŠ — nerelevantní.
- Toto jsou v zásadě analogie k již popsanému `atlasskolstvi.cz` a
  `infoabsolvent.cz` v README (webové katalogy bez API) — nepřidávám je
  jako samostatné plnohodnotné zdroje, jen zmiňuji pro úplnost, že
  existují a při scrapingu je třeba dát přednost tomu, který má
  nejstrukturovanější HTML.

## J. GitHub — další relevantní nálezy (mimo A a B)

- `tangero/stredniskoly` repozitář má i aktivní issue/PR historii
  zmiňující "cermat-maturita 2026" data pull requesty (např. PR #92,
  Issue #89) — naznačuje, že si projekt sám automatizovaně stahuje a
  aktualizuje CERMAT maturitní data (github-actions bot), což je další
  nepřímý důkaz, že jde o živě udržovaný projekt (ověřeno z výsledků
  vyhledávání, ne přímým čtením PR obsahu).
- Žádný jiný samostatný GitHub projekt specificky pro "pražské střední
  školy" nebyl nalezen.

---

## Souhrnná tabulka hodnocení

| Zdroj | Formát | Identifikátory | Licence | Užitečnost |
|---|---|---|---|---|
| tangero/stredniskoly (+ prijimackynaskolu.cz) | JSON/CSV/web | REDIZO/IZO | needefinována (ověřit) | **vysoká** |
| CERMAT JPZ XLSX (upřesnění) | XLSX | REDIZO/IZO/KKOV | neuvedena na webu | **vysoká** (již v README, zde upřesněno) |
| FilipSivak/cermat-data | XLSX | — | MIT-like | nízká–střední (zastaralé) |
| data.gov.cz SPARQL (negativní zjištění o Praze) | RDF/SPARQL | — | otevřená data | nízká (ale metodicky užitečné pro další scraping) |
| opendata.praha.eu / Golemio (SŠ dataset) | neověřeno | — | — | neověřeno / pravděpodobně nízká |
| Dlouhodobý záměr + výroční zprávy HMP | PDF | — | veřejný dokument | nízká–střední (kontext, ne tabulková data) |
| Wikidata P6370 | RDF/SPARQL | REDIZO, Q-ID | CC0 | střední (nízké pokrytí) |
| OSM `ref:redizo` | OSM tag | REDIZO | ODbL | nízká (213 použití v celé ČR) |
| seznamskol.eu a další katalogy | HTML | — | — | nízká (duplicitní s already-known) |

## Doporučení pro README

1. Přidat sekci o `tangero/stredniskoly` / prijimackynaskolu.cz jako
   potenciálně nejužitečnější doplňkový zdroj — zejména kvůli hotovému
   scraperu ČŠI InspIS Portálu (`inspis_school_profiles.json`), který řeší
   mezeru popsanou v README bodě 4 ("žádné strojově čitelné hodnocení
   kvality na úrovni školy"). Než ho použít, ověřit licenci/podmínky u
   autora.
2. V bodě 1 README doplnit přesné aktuální URL a ověřenou strukturu sloupců
   XLSX (viz sekce C výše) — stará URL s číselným prefixem
   (`85-aktuality/303-...`) v CERMAT redesignu webu přestala fungovat,
   aktuální vzor cesty je bez číselného prefixu.
3. Zaznamenat negativní zjištění, že magistrát Prahy nemá v NKOD
   zaregistrovaný žádný dataset o školách (ověřeno SPARQL) — šetří to čas
   při budoucím hledání.
4. Zmínit Wikidata P6370 a OSM `ref:redizo` jako slabé, ale existující
   doplňkové zdroje REDIZO↔geolokace/Q-ID.
