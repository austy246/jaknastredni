# jaknastredni

Osobní projekt na sběr a porovnání dat o středních školách v Praze — cílem je
mít podklady pro výběr vhodné školy (obor, dosažitelnost podle bodů/PZ,
kvalita, maturitní výsledky, uplatnění absolventů apod.).

## Stav

Projekt teprve začíná. Tento dokument shrnuje průzkum dostupných zdrojů dat
(září 2026) — co lze reálně stáhnout/scrapovat a v jakém formátu — jako
podklad pro návrh datového modelu a scraperů.

## Zdroje dat

### 1. CERMAT — data.cermat.cz / vysledky.cermat.cz
Nejlepší kvantitativní zdroj pro **jednotnou přijímací zkoušku (JPZ)**.

- Hlavní portál: https://data.cermat.cz/ (sekce "Jednotná přijímací zkouška",
  "Maturitní zkouška", aktuality)
- Ke stažení jsou **XLSX soubory** s výsledky za školu/obor: REDIZO, obor,
  délka studia, počty přihlášených/přijatých, průměrné/min/max % skóre
  (matematika, čeština), percentily. Zveřejňují se po 1. i dalších kolech
  (např. "Výsledky 2. kola přijímacích zkoušek 2026").
- Bodové hranice pro přijetí CERMAT centrálně nezveřejňuje — ty si stanovuje
  každá škola sama.
- Agregované výsledky (JPZ i maturita) jsou navíc v Power BI dashboardu na
  https://vysledky.cermat.cz/data/PrehledVysledkuJPZ.aspx a
  https://vysledky.cermat.cz/data/default.aspx (bez zdokumentovaného API,
  export jen přes UI dashboardu).
- Žádné oficiální REST/JSON API, žádný záznam v katalogu otevřených dat
  (data.gov.cz / NKOD). Před hromadným stahováním zkontrolovat robots.txt.

### 2. prihlaskynastredni.cz / DIPSY (dipsy.gov.cz)
Centralizovaný přihlašovací systém od 2024/2025 (provozuje CERMAT).
Veřejné stránky jsou informační ("jak podat přihlášku"), samotný DIPSY je
přihlašovací portál pro uchazeče/školy. **Není datový zdroj** — žádný veřejný
bulkový export ani API nenalezen.

### 3. MŠMT — Rejstřík škol a školských zařízení
Oficiální registr všech škol.

- Webové UI: rejstriky.msmt.cz/rejskol/, isv.gov.cz/rssz/ — vyhledávání,
  detail školy (název, adresa, IČO, REDIZO/IZO, zřizovatel, kapacita, obory
  vzdělání s kódy). Limit ~400 řádků na dotaz ve webovém UI.
- **Hromadná otevřená data**: dataset na data.gov.cz (NKOD, id `00022985`),
  pravidelné celoplošné snapshoty (leden/březen/červen/září/říjen/prosinec)
  na lkod-ftp.msmt.gov.cz ve formátu **JSON-LD** (schema
  lkod.msmt.gov.cz/schemas/rssz-json-schema.jschema). Bez osobních údajů,
  volná licence. Nejlepší zdroj pro základní fakta o všech školách — filtrovat
  na kraj Praha.
- Existující (archivovaný, neudržovaný) scraper jako referenční pomůcka:
  https://github.com/khardix/rejskol (Python, řeší limit 400 řádků).

### 4. Česká školní inspekce (ČŠI)
- Inspekční zprávy (PDF, po školách): csicr.cz — "Registr inspekčních zpráv".
- Vyhledávač pro rodiče: **portal.csicr.cz** ("InspIS PORTÁL") — vyhledávání
  podle typu školy/regionu/obce, kontakty, odkazy na inspekční zprávy dané
  školy. Jen web, bez datového exportu.
- **Otevřená data**: opendata.csicr.cz — 81 datasetů (CSV/JSON/XML), ale
  dotazníky/pozorování jsou anonymizované (bez identifikace školy), jen
  metadata inspekčních zpráv jsou navázaná na konkrétní školu. Žádné strojově
  čitelné hodnocení kvality na úrovni školy.

### 5. ČSÚ (Český statistický úřad)
Souhrnné statistiky (počty žáků, kraje) na csu.gov.cz a
statistikaamy.csu.gov.cz, doplňkově vzdelavanivdatech.cz. **Ne na úrovni
jednotlivé školy.**

### 6. Atlas školství (Scio) — atlasskolstvi.cz
- Seznam pražských SŠ: atlasskolstvi.cz/stredni-skoly?region=hlm-praha —
  strukturované stránky po školách, pravděpodobně scrapovatelné jako HTML.
- Hlubší statistiky (atlasskolstvi.cz/statisticke-informace-oboru,
  /vysledky-prijimacek): trendy přihlášek/kapacit, bodové hranice potřebné k
  přijetí, maturitní výsledky (průměry, percentily) — u maturitních
  (gymnázia, SOŠ) oborů **placené (přihlášení + kredit)**; u učňovských oborů
  volně dostupné. Bez API — před scrapováním ověřit robots.txt/podmínky užití.

### 7. infoabsolvent.cz (NPI ČR)
Katalog škol a oborů s filtrem na kraj (Praha), cca 35 polí na školu a 40 na
obor (kontakty, vybavení, přijímačky, jazyky, uplatnění absolventů na trhu
práce). Zdroj dat: rejstřík škol + přímé podklady od škol. Jen webové
stránky/detaily, bez API nebo hromadného exportu.

### 8. Inspirace UX/prezentace — prijimacky-onlinekurzy.cz
Nezávislý agregátor (ne primární zdroj dat, ale dobrá inspirace pro
prezentaci): https://prijimacky-onlinekurzy.cz/mesto/praha

- Přehled škol v Praze (185 škol, stránkováno), pro každou obor, počet
  přihlášených/přijatých, minimální a průměrné bodové skóre — data prý
  odvozená z CERMAT výsledků ("Data: CERMAT & živý zájem").
- Detail školy na URL vzoru `/skola/{REDIZO}/{slug}?rocnik=9`, např.
  `/skola/600006573/obchodni-akademie-heroldovy-sady-362-praha?rocnik=9` —
  potvrzuje, že REDIZO je klíčový identifikátor napříč zdroji.
- Žebříčky "nejžádanějších" škol podle zájmu za posledních 30 dní (vlastní
  proprietární metrika, ne oficiální data).
- Žádné stažitelné datové sady ani API nenalezeno — jen webové stránky.

### 9. Mediální žebříčky
Nenalezen jednotný aktuální "žebříček pražských středních škol" (iDNES/HN/
Deník N). Existují dílčí články (Seznam Zprávy, regionální Deníky) řadící
školy podle maturitních výsledků z čeština, vycházející patrně z MŠMT
souhrnných výsledků jarních maturit (msmt.gov.cz). EDUin (eduin.cz) k těmto
žebříčkům publikuje kritické komentáře. Žádný z článků neodkazuje na
stažitelný dataset.

## Shrnutí a doporučený přístup

Žádný zdroj nenabízí čisté veřejné API. Realisticky nejlepší kombinace:

1. **MŠMT Rejstřík škol (JSON-LD, data.gov.cz)** — základní fakta o všech
   školách v Praze (název, adresa, obory, kapacity, IZO/REDIZO) → jádro
   databáze.
2. **CERMAT XLSX výsledky JPZ** — pro obory s jednotnou přijímací zkouškou:
   počty přihlášených/přijatých, skóre po školách/letech.
3. **infoabsolvent.cz / atlasskolstvi.cz** — scraping HTML pro doplňkové
   údaje (uplatnění absolventů, bodové hranice u placených částí Atlasu jen
   pokud má smysl platit).
4. **ČŠI inspekční zprávy (PDF)** — volitelně, pro kvalitativní posouzení
   konkrétních škol na užším finálním seznamu (ne pro plošné stažení).

Další krok: navrhnout datový model (škola → obor → ročník → výsledky) a začít
prvním scraperem/importem z MŠMT registru, protože je to jediný zdroj s
oficiálním hromadným strojově čitelným exportem.
