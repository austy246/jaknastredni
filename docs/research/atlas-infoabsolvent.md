# Průzkum: atlasskolstvi.cz a infoabsolvent.cz jako zdroje pro databázi pražských SŠ

Datum průzkumu: 2026-09-22. Vše níže ověřeno živým stažením HTML (uloženo v
`scratchpad/atlas/` a `scratchpad/infoabsolvent/`), pokud není řečeno jinak.

---

## 1. atlasskolstvi.cz (Scio / P.F. art, spol. s r. o.)

### 1.1 robots.txt a podmínky užití
- `https://www.atlasskolstvi.cz/robots.txt` (HTTP 200):
  ```
  User-agent: *
  Disallow: /admin/
  ```
  Žádné jiné omezení cesty pro roboty. Žádný `Crawl-delay`.
- `sitemap.xml` na standardní cestě **neexistuje** (HTTP 404 → vrací se HTML
  stránka "Stránka nenalezena").
- Dedikované obchodní podmínky pro placenou část ("Statistické informace"):
  `https://www.atlasskolstvi.cz/vseobecne-obchodni-podminky-staticke-informace`.
  Klíčové citace:
  - Čl. 1.10: *"Službou se rozumí úplatné zpřístupnění obsahu dat o
    základních, středních, vyšších odborných a vysokých školách v ČR v
    jednotlivých detailech uživatelům **pro jejich osobní potřebu**
    prostřednictvím internetu..."*
  - Čl. 3.1: *"…poskytovatel zavazuje zpřístupnit uživateli… Službu v
    digitální podobě **k užívání pro vlastní potřebu**..."*
  - Čl. 4.2: *"Za jeden kredit je zpřístupněna Služba… tj. **jeden detail
    oboru ke škole vybrané uživatelem**."*
  - Opakovaně (čl. 6.8, 9.9, 10.18 – v kontextu odstoupení od smlouvy):
    *"...zdrží se užívání Služby, **včetně jejího poskytování třetí
    osobě**."*
  - Žádná explicitní klauzule o zákazu automatizovaného stahování/scrapingu/
    data miningu jsem v textu nenašel (hledáno: "automat", "robot",
    "scrap", "crawl", "software", "databáz", "kopírov" – jen jedna
    nesouvisející zmínka o "strojově čitelném formátu" v kontextu GDPR
    práva na přenositelnost údajů).
  - **Interpretace (moje, ne citace)**: smluvní vztah je nastaven jako
    prodej digitálního obsahu "pro osobní potřebu" jednotlivci, ne jako
    B2B datový feed. Automatizované hromadné stahování placených
    statistických detailů je v napětí s duchem podmínek (osobní potřeba,
    zákaz poskytování třetí osobě), i když chybí výslovný "no scraping"
    odstavec. U **bezplatné** části webu (základní údaje o škole, seznam
    oborů, kontakty) obecné "Obchodní podmínky" (`/obchodni-podminky`) ani
    robots.txt scraping výslovně nezakazují.
  - Obecné "Obchodní podmínky" (`/obchodni-podminky`) se týkají hlavně
    inzerce a tištěných publikací, ne přístupu k datům.

### 1.2 Seznam pražských SŠ
- URL: `https://www.atlasskolstvi.cz/stredni-skoly?region=hlm-praha`
- Stránkování: `?p=2&region=hlm-praha`, `?p=3&region=hlm-praha`, … V HTML je
  `<div class="pagination"><div data-maxpages="11" data-nextpage="2">`.
- Celkem **214 škol** v Praze (text na stránce: *"Nalezeno 214 škol"*),
  cca 20 na stránku (viděno 20 `<li>` v `<ul class="schoollist cols1">`) →
  11 stránek.
- Stránka navíc uvádí rozpad podle městských částí (Praha 1: 29, Praha 2:
  18, Praha 3: 14, …) – lze použít jako kontrolní součet.
- Selektory (jednoduchý HTML, žádný JS render nutný):
  - `ul.schoollist > li > a[href^="/ss"]` – odkaz na detail
  - uvnitř `a`: `h2` = název školy, `article` = adresa (ulice, čp/or.č.,
    část obce, PSČ, "Praha N")
  - `img[alt="Logo školy …"]` – logo (nepovinné)
  - ID školy je v URL: vzor `/ss{ID}-{slug}`, např.
    `/ss16-stredni-prumyslova-skola-strojnicka-...` (ID `16` = interní ID
    Atlasu, **není** REDIZO/IZO/IČO).
- Žádné REDIZO/IZO/IČO v seznamu – ty jsou až na detailu školy.

### 1.3 Detail školy
Stažené vzorky: `ss16` (Střední průmyslová škola strojnická, Praha 1) a
`ss183` (Obchodní akademie, Praha 10, Heroldovy sady 1).

Dostupná pole (vše bez přihlášení, bez paywallu):
- Název, celá adresa, e-mail, telefon (i s poznámkou u koho), fax,
  webová stránka, jméno ředitele/ředitelky, IČ, **Redizo** (potvrzeno v
  obou vzorcích: `<strong>Redizo:</strong> 600004686` resp. `600006573`),
  zřizovatel (Kraj/…).
- Dny otevřených dveří (text s termíny).
- "Doplňující informace" – volný text o přijímání, zaměření oborů.
- Cizí jazyky (zkratky AJ/NJ/ŠJ…), ubytování, stravování (cena/měsíc).
- Tabulka **"Obory a zaměření"** – pro každý obor:
  - název oboru + kód KKOV (`18-20-M/01` apod.)
  - typ ukončení (maturitní zkouška/výuční list) a délka studia
  - "Přijmou 2026/27" (plánovaný počet přijímaných)
  - "Přihl./přij. 2025/26" (X/Y – počet přihlášených/přijatých loni,
    **toto číslo je volně dostupné i u maturitních oborů**, jen odkaz
    "Statistika" vedle je placený)
  - přijímací zkoušky (předměty ČJ/M apod.)
  - PLP (povinná lékařská prohlídka) ano/ne
  - OZP (přijímání žáků se změněnou pracovní schopností) ano/ne
  - doporučený průměrný prospěch
  - odkaz "Statistika" → `?obor={ID}&forma=...&typ=...&delka_studia=...` –
    vede na **placenou** stránku s historickými statistikami přijímaček a
    maturit (viz 1.4).
- Dlouhý popisný text o škole (marketingový, z pera školy).
- Selektory jsou stabilní HTML (žádné SPA/JS-rendered), tabulka oborů má
  `data-name="..."` atributy usnadňující mapování sloupců
  (`data-name="Obor, zaměření, kód oboru KKOV"`,
  `data-name="Přijmou 2026/27"`, `data-name="Přihl./přij. 2025/26"`,
  `data-name="Přijímací zkoušky"`, `data-name="PLP"`, `data-name="OZP"`,
  `data-name="Doporučený prospěch"`).

**REDIZO je na detailu vždy přítomné a čitelné** → přímý klíč pro
propojení s MŠMT rejstříkem / CERMAT výsledky.

### 1.4 Co je placené vs. zdarma, ceny
- Zdarma: základní údaje o škole (adresa, kontakty, IČ, REDIZO), seznam
  oborů s kódy KKOV, plánované počty přijímaných, **loňský poměr
  přihlášení/přijatí**, info o přijímacích zkouškách (předměty, PLP, OZP),
  doporučený prospěch, popisný text, u **učňovských oborů** i historické
  počty přihlášených/přijatých (potvrzeno textem na
  `/vysledky-prijimacek`: *"Informace o počtech přihlášených a přijatých
  uchazečů u učebních oborů jsou zobrazeny bez uplatnění kreditů"*).
- Placené (u **maturitních** oborů – gymnázia, SOŠ): stránka
  "Detail oboru se statistickými informacemi" obsahující výsledky
  jednotné přijímací zkoušky a maturit v minulých letech. Citace ze
  stažené stránky (`?obor=3716&forma=2&...`):
  *"Nákupem za 1 kredit získáte přístup ke statistickým informacím o
  jednom vybraném oboru u jedné školy po dobu 12 měsíců od zakoupení."*
  Vyžaduje registraci/přihlášení (`href="/prihlaseni?returnUrl=/nakup-kreditu"`).
- Konkrétní ceníková stránka `nakup-kreditu` vrací HTTP 302 → přesměruje
  na přihlášení, **cenu kreditu jsem tedy nezjistil** (vyžaduje účet) –
  needěláno, mimo rozsah bez placené registrace. **Neověřeno.**
- Souhrnná stránka `/vysledky-prijimacek` (zdarma čitelná) dobře
  vysvětluje metodiku: data jsou po 1. kole přijímacího řízení, zdroj
  CERMAT případně škola, mohou se mírně lišit od finálních čísel.

### 1.5 JSON/XHR endpointy
- `sitemap.xml` neexistuje (404).
- V HTML detailu školy a stránky s obory jsem nenašel žádné volání na
  `/api/...` ani jiný JSON endpoint – stránky jsou čistě server-rendered
  HTML (klasický web, ne SPA). Odkaz "Statistika" u oboru je normální
  `<a href="?obor=...">` (query-string parametry na téže URL školy), ne
  AJAX/JSON.
- Žádné explicitní REST API nenalezeno.

---

## 2. infoabsolvent.cz (NPI ČR / Trexima)

### 2.1 robots.txt a podmínky užití
- `https://www.infoabsolvent.cz/robots.txt` (HTTP 200):
  ```
  User-agent: *
  Disallow: /Obory/PorovnaniOboru
  Disallow: /Skoly/KartaSkolyPorovnavaneObory/
  Disallow: /Tools/SaveAsWord

  User-agent: meta-externalagent
  Disallow: /
  ```
  Konkrétní disallow cesty se netýkají seznamu ani detailu škol/oborů
  (`/Skoly/Seznam/...`, `/Skoly/Skola/...`, `/Obory/KartaOboru/...` **nejsou**
  zakázané). Explicitně zablokovaný je jen Meta's crawler (`meta-externalagent`)
  úplně.
- `sitemap.xml` neexistuje (HTTP 302 → přesměrování na
  `/Error/PageNotFound/`).
- **Nenašel jsem žádnou dedikovanou stránku "Podmínky užití" / "Obchodní
  podmínky" / copyright doložku** – ani v hlavičce/patičce homepage, ani
  přes odkaz "O projektu" (ten vede na obecný redakční článek o kariérovém
  poradenství, ne na právní text). Hledáno klíčovými slovy
  "podmínky", "autorská", "copyright", "©", "cookie" v patičce – nic
  relevantního nalezeno kromě odkazu na cookie-lištu (JS skript
  `ccbundle-isa.min.js`, ale bez samostatné textové stránky s podmínkami
  v prvním patru navigace). **Neověřeno vyčerpávajícím způsobem** – je
  možné, že stránka existuje na neodkazovaném URL; další pátrání by
  vyžadovalo fulltextové hledání na webu nebo Google.
- Závěr: jediné formální omezení je robots.txt (viz výše); žádný právní
  text výslovně řešící (ne)povolenost scrapingu nebyl nalezen.

### 2.2 Seznam pražských SŠ
- Seznam škol podle typu, např. `https://www.infoabsolvent.cz/Skoly/Seznam/SOS`
  (kód "SOS" v cestě odpovídá kategorii "střední odborné školy" v širším
  smyslu – zahrnuje i gymnázia a konzervatoře, viz vzorek).
- Filtr na kraj Praha přes query parametry:
  `https://www.infoabsolvent.cz/Skoly/Seznam/SOS?PosTab=Reg&Vzd=20&NastavKraj=True&Kraj=CZ011`
  (`CZ011` = kód kraje Hlavní město Praha, CZ-NUTS).
- Bez explicitního filtru vrátila stránka **rovnou 211 škol** – shoduje se
  přesně s číslem u filtrovacího checkboxu *"Hlavní město Praha (211)"*.
  Vypadá to, že výchozí zobrazení bylo už na Prahu předfiltrované
  (pravděpodobně podle geolokace/IP proxy nebo defaultního cookie
  `Obec=500054`, což je kód obce Praha viditelný v odkazech na homepage).
  Explicitním parametrem `Kraj=CZ011` dostanu stejných 211 výsledků
  spolehlivě, **doporučuji vždy parametr explicitně nastavit**, nespoléhat
  na default.
- Žádné viditelné stránkování v HTML (`grep` na "pagination"/"Stranka="
  nic nenašel) – všech 211 škol je na jedné stránce.
- Selektory: odkazy `a[href^="/Skoly/Skola/"]`, vzor URL:
  `/Skoly/Skola/{REDIZO}/{slug}/SOS` – **REDIZO je přímo součástí URL**
  (např. `/Skoly/Skola/600004686/Stredni-prumyslova-skola-strojnicka-skola-/SOS`).
  Název školy je v textu odkazu/slugu (diakritika odstraněná), přesný
  název je pak na detailu.
- Existují i jiné seznamy podle typu školy (`/Skoly/Seznam/...` s jinými
  kódy) – neprozkoumáno vyčerpávajícím způsobem, ale `SOS` pokrývá
  gymnázia, SOŠ i konzervatoře (viz vzorek obsahující "Gymnázium
  Hudební škola…", "Pražská konzervatoř…", "Obchodní akademie…").

### 2.3 Detail školy
Vzorky: REDIZO `600004686` (SPŠ strojnická, Betlémská) a REDIZO `600004520`
(Obchodní akademie Dusní).

Dostupná pole (vše bez přihlášení, bez paywallu):
- Název, adresa, okres, typ školy (veřejná/soukromá/církevní),
  vybavení školy a nabídka (studovna, fitcentrum, bezbariérovost…),
  velikost školy (pásmo počtu žáků), ubytování, stravování,
  přístup k PC/internetu mimo vyučování, den otevřených dveří,
  cizí jazyky, poznámka SŠ (volný text, např. podpora žáků se SPU),
  odkaz na inspekční zprávy ČŠI, kontakt (www, e-mail, telefon), mapa.
- **REDIZO**: není v čitelném textu na stránce, ale je v hidden form
  poli a shoduje se s URL: `<input id="redIzo" name="redIzo" type="hidden" value="600004686" />`.
- Tabulka "Vzdělávací nabídka školy pro školní rok 2026/2027" – pro
  každý obor (mnohem podrobnější než Atlas):
  - kód KKOV, název oboru, zaměření/ŠVP
  - délka studia, forma studia (denní/večerní/dálková/distanční/kombinovaná)
  - počet povinných cizích jazyků, vyučované jazyky
  - "LONI: přihlášení/plán přijmout" a "LETOS: plán přijmout" (čísla)
  - zda se koná přijímací zkouška, roční školné, možnost studia pro ZP
    (a jaké postižení – zrakové/sluchové/tělesné…)
  - detail přijímacího řízení: jednotná příjímací zkouška (předměty),
    ústní/písemná/talentová/praktická zkouška ano/ne, "jiná kritéria
    přijímání" (např. body za prospěch), termín podání přihlášek,
    termín jednotné zkoušky
  - poznámky k oboru
  - odkaz na samostatnou "kartu oboru" `/Obory/KartaOboru/{kód}/{slug}`
    s obecnými (ne školně-specifickými) daty o oboru: charakteristika,
    profil absolventa, učební plán, **"Uplatnění absolventů v oboru"**
    (volný text), navazující povolání (seznam), a sekce
    "Informace o trhu práce" / "Nezaměstnanost absolventů podle oborů
    vzdělání" (patrně odkazuje na agregovaná data NPI/MPSV, obsah
    tohoto panelu nebyl v ukázce plně stažen – **neověřeno do detailu**).
- Odhad počtu polí odpovídá README (cca 35 na školu, cca 40 na obor) –
  potvrzeno jako řádově správné.
- HTML je klasický server-rendered ASP.NET (vidět `__doPostBack`,
  ASP.NET MVC ajax update atributy `ajax-mode="replace"` pro
  "Porovnat obory" – to je HTML replace, ne JSON).

### 2.4 Export/sitemap/XHR endpoint
- Sitemap neexistuje.
- Žádný JSON/REST endpoint nalezen; interakce (filtrování, "porovnat
  obory") probíhá přes ASP.NET MVC AJAX s **HTML fragmenty** (atribut
  `ajax-update="#porovnavaneObory"`), ne JSON.
- robots.txt explicitně zakazuje `/Tools/SaveAsWord` (export do Wordu) a
  `/Obory/PorovnaniOboru`, `/Skoly/KartaSkolyPorovnavaneObory/` – tyto
  cesty by scraper měl obcházet i kdyby k nim šlo přistoupit.
- Žádná data ke stažení hromadně (CSV/XLSX) nenalezena.

---

## 3. Shrnutí – vhodnost pro scraper a pracnost

| | atlasskolstvi.cz | infoabsolvent.cz |
|---|---|---|
| robots.txt | povoluje vše kromě `/admin/` | povoluje seznam/detail škol i oborů, zakazuje jen pár nástrojových cest a Meta crawler |
| Explicitní "no scraping" klauzule | ne (jen "osobní potřeba" u placené služby) | žádná nalezená stránka s podmínkami |
| Seznam Praha | 214 škol, stránkováno po ~20 (`?p=N&region=hlm-praha`) | 211 škol, 1 stránka (`?Kraj=CZ011`) |
| REDIZO v detailu | ano, čitelný text | ano, v URL + hidden poli |
| Placený obsah | jen historické výsledky JPZ/maturit u maturitních oborů (1 kredit/obor/škola, cena neznámá bez účtu) | žádný nalezený |
| Formát | statický server-rendered HTML, stabilní `data-name` atributy | statický server-rendered ASP.NET MVC HTML |
| API/JSON | žádné | žádné |

**Odhad pracnosti Python scraperu** (orientační, bez placené části):
- Atlas – seznam + detail (bez placených statistik): jednoduchý
  `requests` + `BeautifulSoup`/`lxml`, cca 1 den práce (11 stránek seznamu
  + 214 detailů, rate-limit 1 req/s ≈ 4 minuty čistého stahování,
  parsování je přímočaré díky `data-name` atributům).
- infoabsolvent – seznam škol + detail školy: podobně cca 1 den
  (211 škol, jedna stránka seznamu, detail o něco složitější kvůli
  hnízděné tabulce oborů a HTML entitám v UTF-8/Windows-1250 mixu –
  ověřit encoding).
- infoabsolvent – karty oborů (obecná data, uplatnění, navazující
  povolání): další 0,5–1 den, pokud je to žádoucí (obory se opakují
  napříč školami, stačí stáhnout jednou za unikátní kód KKOV).
- Atlas placené statistiky JPZ/maturit: vyžaduje registraci a nákup
  kreditů; do doby zjištění ceny a zvážení právního rizika (viz
  "osobní potřeba"/zákaz poskytování třetí osobě) **nedoporučuji
  automatizovat** – spíš ruční nákup pro užší finální seznam škol, jak
  navrhuje README bod 4 analogicky pro ČŠI.

### Problémy / rizika
1. U atlasskolstvi.cz je smluvní rámec pro placenou část nastaven jako
   B2C "pro osobní potřebu" s zákazem poskytování třetí osobě – hromadné
   stažení placených statistik by narušovalo účel smlouvy, i když chybí
   výslovná anti-scraping klauzule. Bezplatná část (adresa, obory, kódy
   KKOV, REDIZO, počty přihlášených/přijatých u učňovských oborů) je bez
   patrného omezení.
2. U infoabsolvent.cz chybí jakýkoli nalezený právní text k použití dat –
   je tedy nejasné, zda/jak provozovatel (NPI ČR) scraping omezuje mimo
   robots.txt. Doporučuji před produkčním nasazením zkusit ještě
   kontaktovat provozovatele (e-maily `infoabsolvent@npi.cz`,
   `ckp@npi.cz` nalezené v patičce) nebo důkladněji prohledat web (mimo
   rozsah tohoto průzkumu).
3. Kódování/HTML entity: oba weby vrací HTML s číselnými entitami
   (`&#xE9;` apod.) místo UTF-8 znaků přímo v textu – běžný parser
   (BeautifulSoup s `html.parser`/`lxml`) si s tím poradí automaticky,
   jen je třeba na to pamatovat při psaní testů.
4. Interní ID Atlasu (`ss16`) není REDIZO – nutno vždy číst REDIZO
   z detailu, ne odvozovat z URL seznamu.
5. infoabsolvent "Kraj Praha default" chování (211 = stejné jako
   explicitní filtr) je zatím ověřeno jen jednou sadou requestů z tohoto
   prostředí – pro produkci vždy nastavovat `Kraj=CZ011` explicitně, ne
   spoléhat na výchozí chování serveru.
