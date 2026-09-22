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

## Přehled entit

```
organizace (REDIZO) ──< zrizovatel
     │
     └──< skola (IZO) ──< skola_kapacita
               │      ──< misto_vyuky
               │      ──< obor (KKOV, forma, délka)
               │
               ├──< prijimaci_rizeni   (CERMAT JPZ 2024+, rok × kolo × KKOV × ročník)   [plán]
               ├──< jpz_skupina        (CERMAT JPZ 2017–2023, rok × skupina oborů)       [plán]
organizace ────┼──< maturita           (CERMAT MZ 2015+, rok × období × SMO16 × předmět) [hotovo]
               ├──< inspekce           (ČŠI, datum × PDF)                                [plán]
               └──< web_profil         (infoabsolvent / Atlas, datum scrapování)         [plán]
```

Plné čáry jsou implementované (importéry MŠMT a CERMAT maturita), hranaté
závorky označují tabulky navržené pro další importéry. CERMAT do roku 2023 a
maturita nemají IZO, proto se váží na organizaci (REDIZO), ne na školu.

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

## Implementované tabulky (CERMAT maturita)

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

## Plánované tabulky (návrh)

### `prijimaci_rizeni` — CERMAT JPZ, nový formát 2024+
Klíč `(izo, kod_kkov, rocnik, rok, kolo)`. Sloupce z `_vysledky.xlsx`
spojené s `_kapacity` a `_prihlasky` přes `ID_SO`: kapacita, index poptávky,
přihlášky celkem a podle priority 1–5, přijatí, konali ČJ/MA, % skór a
percentil (průměr/min/max) zvlášť za všechny a za přijaté, důvody nepřijetí.
Zdroj: [`research/cermat.md`](research/cermat.md), oddíl 6.

### `jpz_skupina` — CERMAT JPZ, starý formát 2017–2023
Klíč `(redizo, skupina_oboru, rocnik, rok)`. Přihlášeni, konali, průměrné
percentilové umístění a směrodatná odchylka za ČJ a MA. Bez IZO a KKOV, jen
pro dlouhé trendy.

### `inspekce` — ČŠI
Klíč `(redizo, datum_od)`. `datum_do`, `pdf_url`, `portal_url`, později
extrahovaný text sekcí `silne_stranky`, `prilezitosti`, `doporuceni`.
Zdroj: dataset 69 na opendata.csicr.cz.

### `web_profil` — scrapované doplňky
Klíč `(redizo, zdroj, stazeno)`. JSON s poli, která rejstřík nemá: přijímací
kritéria, školné, dny otevřených dveří, jazyky, vybavení, loňský poměr
přihlášení/přijatí. Zdroj infoabsolvent.cz, případně Atlas školství.

## Spojování zdrojů

| Zdroj | Klíč | Poznámka |
|---|---|---|
| CERMAT JPZ 2024+ | `izo` + `kkov` | IZO má prefix `izo_`, před spojením odstranit |
| CERMAT JPZ ≤2023 | `redizo` | obor jen jako skupina |
| CERMAT maturita | `redizo` | obor jen jako SMO16 |
| ČŠI | `redizo` | filtr na Prahu přes JOIN s `organizace` |
| infoabsolvent | `redizo` z URL | |
| Atlas školství | `redizo` z detailu | interní ID v URL není REDIZO |

## Otevřené body

- Oficiální číselník AKDT: rozhodnout, zda `E00` (35 záznamů v Praze) jsou
  konzervatoře, VOŠ nebo obojí, a jak s nimi nakládat ve výběru.
- Historie: rejstřík nemá zaniklé školy. Pokud bude potřeba, ukládat denní
  snapshoty do `data/raw/msmt/` (importér to už dělá) a porovnávat.
- Geolokace: `kod_ruian` v adrese umožňuje dotáhnout souřadnice z RÚIAN.
