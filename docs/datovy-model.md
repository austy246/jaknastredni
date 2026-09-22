# Datový model

Cíl: jedna lokální databáze (SQLite), do které se dají opakovaně naimportovat
všechny zdroje z [README](../README.md) a nad kterou půjde stavět srovnání škol.
Schéma je v [`jaknastredni/schema.sql`](../jaknastredni/schema.sql).

## Zásady

- **Klíče přebíráme z rejstříku MŠMT.** REDIZO identifikuje právnickou osobu,
  IZO konkrétní školu, kód KKOV obor. Ostatní zdroje se na ně napojují, nikdy
  nezakládají vlastní školy.
- **SQLite, žádný ORM.** Jeden soubor, přenositelný mezi Pythonem a C#
  (`Microsoft.Data.Sqlite`). Schéma je čisté SQL, dá se použít z obou jazyků.
- **Snapshot vs. časová řada.** Rejstřík je aktuální stav (přepisuje se),
  výsledky CERMAT a inspekce ČŠI jsou události v čase (přidávají se, klíč
  obsahuje rok).
- **Surové kódy číselníků zůstávají v datech.** Oficiální číselníky MŠMT nejsou
  online; tabulka `ciselnik` nese známé hodnoty a příznak `overeno`.
- **Osobní údaje minimalizujeme.** Ukládá se jen jméno ředitele (veřejná
  funkce), ne jeho adresa; u zřizovatelů fyzických osob ne datum narození ani
  adresa.
- **Každý import má záznam** v `import_run` (zdroj, URL, hash souboru, datum
  dat), takže jde dohledat, odkud které řádky pocházejí.
- **Databáze je odvozený artefakt, ne zdroj pravdy.** Sestavuje se vždy znovu
  z `data/raw/` (`jaknastredni.build_db`, čistě offline) — proto se soubor
  `data/jaknastredni.db` neverzuje v gitu, jen syrová data v `data/raw/`.
  Viz README, sekce "Rychlý start" a "Rozhodnutí o vývoji a ukládání dat".

## Přehled entit

```
organizace (REDIZO) ──< zrizovatel
     │
     └──< skola (IZO) ──< skola_kapacita
               │      ──< misto_vyuky
               │      ──< obor (KKOV, forma, délka)
               │
               ├──< prijimaci_rizeni   (CERMAT JPZ 2024+, rok × kolo × KKOV × ročník)   [hotovo]
organizace ────┼──< jpz_skupina        (CERMAT JPZ 2017–2023, rok × skupina oborů)       [hotovo]
               ├──< maturita           (CERMAT MZ 2015+, rok × období × SMO16 × předmět) [hotovo]
               ├──< inspekce           (ČŠI, datum × PDF)                                [hotovo]
               └──< web_profil         (infoabsolvent [hotovo] / Atlas [hotovo], datum scrapování)
```

Plné čáry jsou implementované (importéry MŠMT, CERMAT maturita, CERMAT JPZ
2017–2023 a nový formát 2024+, ČŠI, infoabsolvent.cz a atlasskolstvi.cz).
CERMAT do roku 2023, maturita a ČŠI inspekce nemají IZO, proto se váží na
organizaci (REDIZO), ne na školu; JPZ 2024+ IZO má, ale bez cizího klíče na
`skola(izo)` (viz níže).

## Implementované tabulky (MŠMT)

| Tabulka | Klíč | Obsah |
|---|---|---|
| `organizace` | `redizo` | název, IČO, kraj, právní forma, typ zřizovatele, adresa sídla (vč. obvodu Prahy, RÚIAN), e-maily, ředitel, `aktualizovano` |
| `zrizovatel` | `redizo, poradi` | druh osoby, název, IČO |
| `skola` | `izo` | název, `druh` (AKDT, `C00` = SŠ), jazyk, data zápisu a zahájení |
| `skola_kapacita` | `izo, merna_jednotka` | nejvyšší povolený počet |
| `misto_vyuky` | `izo, id_mista, typ` | adresa místa výuky |
| `obor` | `izo, kod_kkov, forma, delka, jazyk` | název, kapacita, dobíhající |
| `ciselnik` | `ciselnik, kod` | známé významy kódů, `overeno` |
| `import_run` | `id` | evidence běhů importu |

Pohled `v_stredni_skola` spojuje školu s organizací pro `druh IN ('C00','E00')`
a dopočítává kapacitu žáků a počet aktivních oborů.

Stav po importu pražského snapshotu z 22. 9. 2026:

| | počet |
|---|---|
| organizace | 1044 |
| škol a zařízení | 2434 |
| střední školy (`C00`) | 219 |
| aktivní obory na SŠ | 779 (190 různých KKOV) |

## Implementované tabulky (CERMAT, ČŠI, infoabsolvent.cz)

### `maturita` — CERMAT MZ 2015+
Klíč `(redizo, rok, obdobi, smo16, predmet)`; `obdobi` je `j` (jarní) nebo
`jap` (jaro+podzim), `smo16 = 'CELKEM'` pro řádek za celou školu (jinak kód
skupiny oborů SMO16, např. `LYC`, `SEK`), `predmet` je `CELKEM` (souhrn za
celou společnou část MZ, bez skóru/percentilu) nebo `CJ/MA/AJ/NJ/RJ/FJ/SJ`.
Sloupce: přihlášeni, konali, uspěli, neuspěli, nekonali, průměrný % skór,
směrodatná odchylka % skóru, průměrný percentil, podíl úspěšných, čistá
neúspěšnost, podíl volby předmětu (jen u volitelných předmětů, ne ČJ ani
CELKEM). Bez cizího klíče na `organizace` — CERMAT zahrnuje i školy mimo
Prahu a zaniklé školy, které v rejstříku MŠMT nejsou; filtr na Prahu se dělá
JOINem v dotazech (nebo `--jen-praha` při importu). Zdroj:
[`research/cermat.md`](research/cermat.md), oddíly 4, 7, 9, 10.

### `jpz_skupina` — CERMAT JPZ, starý formát 2017–2023
Klíč `(redizo, skupina_oboru, rocnik, rok)`. Sloupce: `prihlaseni_cj,
konali_cj, prumerny_percentil_cj, smerodatna_odchylka_cj` a stejná čtveřice
pro `_ma`. Bez IZO a bez KKOV (jen hrubá "oborová skupina" typu `GY8`, `LYC`,
`4LETÉ OBORY`), metrika úspěšnosti je průměrné percentilové umístění (0–100
percentil), ne bodové skóre. Zdrojový list nemá sloupec typu `TŘÍDĚNÍ` —
školní řádky se poznají jen podle číselného REDIZO v 1. sloupci (krajské a
celorepublikové součty mají tam text nebo prázdno). Rok 2020 má tři sloupce
absence (`OMLUVENI/NEOMLUVENI/VYLOUČENI`) místo jednoho (`NEKONALI`) — do
`jpz_skupina` se nepromítají, mapování je podle jména sloupce, ne pozice.
Bez cizího klíče na `organizace` (stejný důvod jako `maturita`), filtr na
Prahu přes JOIN nebo `--jen-praha`. Naimportováno 21 569 řádků za 2017–2023.
Zdroj: [`research/cermat.md`](research/cermat.md), oddíly 3, 5, 9, 13.

### `inspekce` — seznam inspekčních zpráv
Klíč `(redizo, datum_od)`, oba jsou ISO `YYYY-MM-DD`. Sloupce: `nazev`
(název školy v době inspekce, ne osobní údaj), `datum_do`, `pdf_url` (přímý
odkaz na PDF zprávy), `portal_url` (odkaz na portal.csicr.cz). Bez cizího
klíče na `organizace` — dataset zahrnuje všechny typy škol/zařízení v celé
ČR od roku 2003, i školy mimo Prahu a zaniklé školy, které v rejstříku MŠMT
nejsou; filtr na Prahu se dělá JOINem v dotazech (nebo `--jen-praha` při
importu). PDF zprávy se v tomto importéru nestahují (jen seznam/metadata),
extrakce textu (sekce „Závěry", „Silné stránky" apod.) zůstává budoucí krok
pro užší seznam škol. Zdroj: [`research/csi.md`](research/csi.md).

### `web_profil` — scrapovaný doplňkový profil školy
Klíč `(redizo, zdroj, stazeno)`; `zdroj` je `'infoabsolvent'` nebo `'atlas'`
(dva nezávislé řádky pro stejné REDIZO/den, klíč obsahuje zdroj). Sloupec
`data` je JSON objekt, jehož schéma se mezi zdroji liší (dokumentováno
v modulovém docstringu příslušného importéru) — obecně pole, která rejstřík
MŠMT nemá.

**`zdroj = 'infoabsolvent'`** (`jaknastredni/infoabsolvent.py`): vybavení a
nabídka školy, velikost školy, ubytování/stravování, přístup k PC/internetu
mimo výuku, den otevřených dveří, cizí jazyky (za celou školu), poznámka SŠ,
kontakt (www/e-mail/telefon), odkaz na ČŠI zprávy, a pole `obory[]` — pro
každou kombinaci KKOV × zaměření/ŠVP: délka a forma studia, počet povinných
jazyků a jejich seznam, `loni_prihlaseni`/`loni_plan_prijmout` (pozor:
infoabsolvent zveřejňuje jen loňský PLÁN přijmout, ne skutečný počet
přijatých — na rozdíl od Atlasu), `letos_plan_prijmout`, zda se koná
přijímací zkouška, roční školné, možnost studia pro ZP, podrobnosti
přijímacího řízení (`prijimaci_rizeni`: jednotná/ústní/písemná/talentová/
praktická zkouška, jiná kritéria, termíny) a poznámky k oboru. Adresa,
okres, typ školy a jméno zřizovatele se z infoabsolventu záměrně
nevytahují — jsou redundantní vůči `organizace`/`misto_vyuky`/`zrizovatel`.
Zdroj: [`research/atlas-infoabsolvent.md`](research/atlas-infoabsolvent.md),
oddíl 2. Stav po běhu 22. 9. 2026: 211/211 pražských SŠ, 743 řádků oborů.

**`zdroj = 'atlas'`** (`jaknastredni/atlas.py`): dny otevřených dveří,
doplňující informace (volný text), cizí jazyky, ubytování, stravování, a
pole `obory[]` — pro každý obor: název + KKOV kód, typ ukončení (maturitní
zkouška/výuční list), délka studia, `planovany_pocet_prijmout` (plán
přijmout na příští rok), **`loni_prihlaseni`/`loni_prijati`** (na rozdíl od
infoabsolventu jde o **skutečný** loňský počet přijatých, ne jen plán —
jediné místo v projektu, kde je toto číslo k dispozici zdarma, viz README
bod 4), přijímací zkoušky (předměty), `plp`/`ozp` (bool), a
`doporuceny_prospech` (float) — pole, které žádný jiný ověřený zdroj v
projektu nemá. Adresa, IČ, ředitel/ka, zřizovatel a kontakty se z Atlasu
záměrně nevytahují ze stejného důvodu jako u infoabsolventu. Placená
statistika JPZ/maturit u maturitních oborů (odkaz "Statistika",
`?obor=...`) se nikdy nestahuje ani neparsuje — viz modulový docstring
`atlas.py` a docs/research/atlas-infoabsolvent.md, oddíl 1.4 a 3 (bod 1).
Atlas nemá REDIZO v URL (na rozdíl od infoabsolventu) — čte se z textu
detailu školy, interní ID Atlasu v URL seznamu (`/ss{id}-slug`) se
nepoužívá jako klíč. Zdroj:
[`research/atlas-infoabsolvent.md`](research/atlas-infoabsolvent.md),
oddíl 1. **Implementováno, doposud nespuštěno na produkčních datech.**

Bez cizího klíče na `organizace` u obou zdrojů (stejný důvod jako
`maturita`). Žádné osobní údaje nad rámec toho, co už ukládá MŠMT
(`organizace.reditel_jmeno`), se v žádném z obou zdrojů neukládají.

### `prijimaci_rizeni` — CERMAT JPZ, nový formát 2024+
Klíč `(izo, kod_kkov, rocnik, rok, kolo, zamereni_oboru, forma_vzdelavani,
delka_studia, jazyk_studia)` — plánovaný kratší klíč `(izo, kod_kkov,
rocnik, rok, kolo)` se v reálných datech ukázal jako nejednoznačný (školy
nabízející víc zaměření/forem pod jedním KKOV), proto rozšířeno stejně jako
u tabulky `obor`. Sloupce z `_vysledky.xlsx` spojené s `_kapacity` a
`_prihlasky` přes `ID_SOF` (spolehlivější než navržené `ID_SO`, které je
navíc v letech 2024–2025 u `_kapacity`/`_prihlasky` přejmenované na
`IS_SO`): kapacita, index poptávky, přihlášky celkem a podle priority 1–5, přijatí a
podle priority 1–5, konali ČJ/MA, % skór a percentil (průměr/min/max)
zvlášť za všechny přihlášené a za přijaté, důvody nepřijetí (přijat na
vyšší prioritu / nedostatečná kapacita / nesplnění podmínek / vzdal se
přijetí). Stejně jako `maturita` bez cizího klíče na `skola(izo)` —
CERMAT zahrnuje i školy mimo Prahu a zaniklé; filtr na Prahu přes JOIN
nebo `--jen-praha`. Zdroj: [`research/cermat.md`](research/cermat.md),
oddíly 6, 13.

## Plánované tabulky (návrh)

Všechny tabulky navržené v tomto dokumentu jsou nyní implementované (viz
sekci výše), včetně Atlasu školství jako druhého zdroje (`zdroj = 'atlas'`)
do existující tabulky `web_profil` (`jaknastredni/atlas.py`) — implementován,
doposud nespuštěn na produkčních datech (viz README bod 4). Žádné další
plánované rozšíření datového modelu aktuálně není otevřené.

## Spojování zdrojů

| Zdroj | Klíč | Poznámka |
|---|---|---|
| CERMAT JPZ 2024+ | `izo` + `kkov` | IZO má prefix `izo_`, před spojením odstranit; víc zaměření/forem pod jedním KKOV, viz `prijimaci_rizeni` výše |
| CERMAT JPZ ≤2023 | `redizo` | obor jen jako skupina |
| CERMAT maturita | `redizo` | obor jen jako SMO16 |
| ČŠI | `redizo` | filtr na Prahu přes JOIN s `organizace` |
| infoabsolvent | `redizo` z URL | |
| Atlas školství | `redizo` z detailu | interní ID v URL (`/ss{id}-slug`) není REDIZO, čte se z textu detailu (`atlas.py`) |

## Otevřené body

- Oficiální číselník AKDT: rozhodnout, zda `E00` (35 záznamů v Praze) jsou
  konzervatoře, VOŠ nebo obojí, a jak s nimi nakládat ve výběru.
- Historie: rejstřík nemá zaniklé školy. Pokud bude potřeba, ukládat denní
  snapshoty do `data/raw/msmt/` (importér to už dělá) a porovnávat.
- Geolokace: `kod_ruian` v adrese umožňuje dotáhnout souřadnice z RÚIAN.
