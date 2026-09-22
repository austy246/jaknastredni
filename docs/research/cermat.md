# CERMAT – průzkum zdrojů dat (data.cermat.cz, vysledky.cermat.cz)

Ověřeno: 2026-09-22. Vše níže je ověřeno skutečným stažením/otevřením souborů, pokud není uvedeno jinak.

## 1. robots.txt

`https://data.cermat.cz/robots.txt` → **HTTP 404** (nginx). Soubor neexistuje, není tedy žádné explicitní omezení crawlování přes robots.txt. (Neznamená to svolení k čemukoliv – jen že soubor chybí.)

## 2. Struktura webu data.cermat.cz

Hlavní menu:
- `/data-a-analyticke-vystupy-jednotna-prijimaci-zkouska.html` (JPZ = jednotná přijímací zkouška)
  - `/.../agregovana-data-jpz.html` – **odkazy na souhrnné xlsx po školách/oborech** (nejdůležitější zdroj)
  - `/.../agregovana-data-jpz/regionalni-a-oborove-agregace.html` – kraj/typ školy agregace
  - `/.../datove-soubory.html` – položková data (per úloha, ne per škola) + soubory "Uchazeci" (přihlášky/výsledky uchazečů, 2024–2026)
  - `/.../analyticke-vystupy.html`, `/.../vizualizace-dat.html`, `/.../prijimacky-nanecisto.html`
- `/maturitni-zkouska.html`
  - `/maturitni-zkouska/agregovana-data.html` – **souhrnné xlsx po školách (skolobory)** pro maturitu
  - `/maturitni-zkouska/datove-soubory.html` – položková data po předmětech (ne po školách)
  - `/maturitni-zkouska/analyticke-vystupy.html`, `/maturitni-zkouska/vizualizace-dat.html`
- `/aktuality.html` – aktuality (odkazy na výsledky 2. kola PZ 2026, podzimní maturita 2026 atd., neobsahují přímé datové soubory, jen novinky)

## 3. Seznam stažitelných souborů „po školách" – JPZ (jednotná přijímací zkouška)

Zdroj: `/data-a-analyticke-vystupy-jednotna-prijimaci-zkouska/agregovana-data-jpz.html`, adresář `/files/files/JPZ/agregovana_data_skoly/`

| Rok | Kolo | Soubor | Formát/schéma |
|---|---|---|---|
| 2017–2023 | souhrn (řádný+náhradní termín) | `JPZ{rok}_skoly-skolobory_vysledky.xlsx` | „starý" formát (viz níže) |
| 2024 | kolo 1, kolo 2 | `PZ2024_kolo{1,2}_skolobory_{kapacity,prihlasky,vysledky}.xlsx` | „nový" formát |
| 2025 | kolo 1, kolo 2 | `PZ2025_kolo{1,2}_skolobory_{kapacity,prihlasky,vysledky}.xlsx` | nový formát |
| 2026 | kolo 1, kolo 2 | `PZ2026_kolo{1,2}_skolobory_{kapacity,prihlasky,vysledky}.xlsx` | nový formát (2026 kolo 2 zatím říjen/listopad – odkaz existuje, obsah neověřen zda je již naplněný) |

Dodatečně regionální/oborové agregace (kraj × typ školy, ne po jednotlivých školách):
`/files/files/JPZ/regionalni_oborove_agregace/PZ2024-2026_agregace_typskoly_region_{kapacity,prihlasky}.xlsx`

Dále existují **položková data po úlohách** (ne po školách, ale po žácích/úlohách) v `/files/JPZ-polozkova-data/{rok}/Polozkova_data/JPZ{rok}_{CJL4,CJL6,CJL8,MA4,MA6,MA8}_polozkova_data.xlsx` pro roky 2017–2026 (4/6/8 = délka oboru), a **soubory uchazečů** `PZ{2024,2025,2026}_kolo{1,2}_uchazeci_prihlasky_vysledky.xlsx` (jednotlivé přihlášky, patrně anonymizované – obsah nebyl stahován, mimo rozsah úkolu "po školách").

## 4. Seznam stažitelných souborů „po školách" – maturita

Zdroj: `/maturitni-zkouska/agregovana-data.html`, adresář `/files/files/MZ/agregovana_data_skoly/`

Pro každý rok **2015–2026** dva soubory:
- `MZ{rok}j_SC_skolobory.xlsx` – jarní zkušební období
- `MZ{rok}jap_SC_skolobory.xlsx` – jaro + podzim (souhrn)

Formát je napříč lety 2015–2026 **strukturálně velmi stabilní** (viz níže), na rozdíl od JPZ.

## 5. Struktura souborů – JPZ „starý formát" (2017–2023)

Ověřeno na `JPZ2017_skoly-skolobory_vysledky.xlsx` (2 listy: hlavní list + `ciselniky`) a `JPZ2020`, `JPZ2023`.

- List obsahuje ~3300–3400 řádků, ~22–24 sloupců.
- Řádek 0 = titulek (sloučené buňky ČJ/MA), **skutečná hlavička je na řádku 1 (index 1)**:
  `REDIZO / KRAJ / OBOROVÁ SKUPINA | OBOROVÁ SKUPINA | ROČNÍK | NÁZEV ŠKOLY | ADRESA ŠKOLY | KRAJ (KÓD) | KRAJ (NÁZEV) | ZŘIZOVATEL | PŘIHLÁŠENI | KONALI | NEKONALI (2017/2023) / OMLUVENI,NEOMLUVENI,VYLOUČENI (2020) | PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ | SMĚRODATNÁ ODCHYLKA … | (totéž pro MATEMATIKU)`
- **Důležitá zvláštnost**: v prvním sloupci jsou namíchané tři typy řádků – (a) celorepublikové součty za obor. skupinu, (b) krajské součty, (c) řádky **jednotlivých škol**. Pouze u školních řádků je v 1. sloupci REDIZO (číslo), u krajských/celkových řádků je tam text kraje/„CELKEM". U krajských řádků chybí REDIZO úplně a KRAJ (KÓD/NÁZEV) je vyplněný, u školních řádků bývá KRAJ (KÓD/NÁZEV) naopak prázdný (info je jen v adrese) – **je nutné filtrovat podle toho, zda je hodnota v 1. sloupci číselná (REDIZO)**.
- Kód oboru je jen zkratka „oborové skupiny": `GY8, GY6, GY4, 4LETÉ OBORY, LYC, SEK, NAS...` – **není to KKOV kód**, jen hrubá kategorie.
- **Žádné IZO.**
- Metrika úspěšnosti = „průměrné percentilové umístění" a směrodatná odchylka (0–100 percentil), **ne bodové skóre a ne % skór**.
- List `ciselniky` (v 2017/2020) obsahuje legendu oborových skupin a zřizovatelů, ale ne mapování na REDIZO.
- Příklad řádku pro Obchodní akademii (REDIZO 600006573, Praha), obor „4LETÉ OBORY": `(600006573, '4LETÉ OBORY', 9, 'Obchodní akademie', 'Heroldovy sady 362, Praha, psč 10 100', 'CZ010', 'Hlavní město Praha', 7, 232, 232, 0, 66.4, 22.6, 232, 232, 0, 66, 21.4)` – sloupce: REDIZO, obor.skup., ročník, zřizovatel(kód 7=veřejná), přihl./konali/nekonali ČJ, průměr. percentil ČJ, sm.odch. ČJ, přihl./konali/nekonali MA, průměr. percentil MA, sm.odch. MA.
- Menší nekonzistence v letech: 2020 má 3 sloupce pro absence (OMLUVENI/NEOMLUVENI/VYLOUČENI) místo jednoho (NEKONALI) v 2017/2023, počet listů se liší (2017/2020 mají navíc `ciselniky`, 2023 má jen jeden list `List1`).

## 6. Struktura souborů – JPZ „nový formát" (2024–2026, `PZ{rok}_kolo{k}_skolobory_vysledky.xlsx`)

Ověřeno na `PZ2026_kolo1_skolobory_vysledky.xlsx` (listy: `pz2026_kolo1`, `vysvetlivky`; **6369 řádků, 91 sloupců**).

Toto je **zásadně přepracovaná, mnohem granulárnější struktura** oproti 2017–2023: jeden řádek = jedna kombinace škola × obor (KKOV) × ročník, ne agregace za celou oborovou skupinu.

Klíčové sloupce (výběr): `ID_SOF, ID_SO (interní UUID), ROK, KOLO, IZO, REDIZO, NÁZEV ŠKOLY, ULICE, OBEC, PSČ, KRAJ, KRAJ-NÁZEV, OKRES, OKRES-NÁZEV, ORP, ORP-NÁZEV, ZŘIZOVATEL, ZŘIZOVATEL-NÁZEV, ROČNÍK, MATURITNÍ STATUS, POVINNOST JPZ, TYP ŠKOLY, TYP ŠKOLY-NÁZEV, SKUPINA OBORŮ (16), KKOV, OBOR-NÁZEV, ZAMĚŘENÍ OBORU, FORMA VZDĚLÁVÁNÍ, DÉLKA STUDIA, ZKRÁCENÉ STUDIUM, JAZYK STUDIA, KAPACITA, INDEX POPTÁVKY (PŘIHLÁŠKY/KAPACITA), PŘIHLÁŠKY CELKEM, PŘIJATÍ, PŘIHLÁŠKY/PŘIJATÍ - PRIORITA 1..5, ČJ+MA/ČJ/MA - KONALI, % SKÓR (průměr/min/max), PERCENTIL (průměr/min/max) — vše zvlášť pro všechny uchazeče i jen pro PŘIJATÉ, NEPŘIJATI - PŘIJAT NA VYŠŠÍ PRIORITU / NEDOSTATEČNÁ KAPACITA / NESPLNĚNÍ PODMÍNEK / VZDAL SE PŘIJETÍ`.

- **Má IZO i REDIZO** (IZO ve formátu `izo_000638510` – textový prefix!, REDIZO jako číslo).
- **Má skutečný kód oboru KKOV** (např. `63-41-M/02`), ne jen hrubou skupinu.
- List `vysvetlivky` obsahuje datový slovník (popis každého sloupce).
- Soubory `..._prihlasky.xlsx` (39 sloupců, bez skóre, jen přihlášky po prioritách) a `..._kapacity.xlsx` (32 sloupců, jen kapacita) mají shodnou levou část sloupců (identifikace školy/oboru) jako `_vysledky.xlsx`, jen s jinou pravou částí – **lze spojovat přes ID_SO / (REDIZO+KKOV+ROČNÍK)**.
- Příklad – Obchodní akademie Heroldovy sady (REDIZO 600006573), obor SEK 63-41-M/02: kapacita 30, přihlášky 282, přijato 30, index poptávky 9,4.
- Struktura vypadá stejná pro 2024, 2025, 2026 (název listu obsahuje rok a kolo, jinak sloupce shodné) – **ověřeno jen vizuálně porovnáním hlaviček 2026 vs. popisem výše; přesné porovnání 2024/2025 hlaviček nebylo provedeno, doporučuji ověřit před importem**.

**Zlom mezi formáty nastává mezi rokem 2023 a 2024** – jde o dvě zcela odlišná schémata, import musí mít dvě větve/mapovací vrstvy.

## 7. Struktura souborů – maturita (`MZ{rok}{j|jap}_SC_skolobory.xlsx`)

Ověřeno na `MZ2017j_SC_skolobory.xlsx` a `MZ2026j_SC_skolobory.xlsx` (oba: 2 listy – rok/„vysvetlivky"; ~3700 řádků, 96–98 sloupců).

- Hlavička (řádek 1, resp. 2 kvůli mergnutému titulku): `TŘÍDĚNÍ, ROK, REDIZO, NÁZEV ŠKOLY, ADRESA ŠKOLY, TYP ŠKOLY, TYP ŠKOLY-NÁZEV, SMO16, SMO16-NÁZEV, KRAJ, KRAJ-NÁZEV`, poté bloky po předmětech: **SPOLEČNÁ ČÁST MZ CELKEM, ČESKÝ JAZYK, MATEMATIKA, ANGLIČTINA, NĚMČINA, RUŠTINA, FRANCOUZŠTINA, ŠPANĚLŠTINA** (v 2026 souboru identické předměty), pro každý blok: `PŘIHLÁŠENI, KONALI, USPĚLI, NEUSPĚLI, NEKONALI, PRŮMĚRNÝ % SKÓR, SMĚRODATNÁ ODCHYLKA % SKÓRU, PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ, PODÍL ÚSPĚŠNÝCH (%), ČISTÁ NEÚSPĚŠNOST (%), (u volitelných předmětů navíc) PODÍL VOLBY PŘEDMĚTU (%)`.
- **Má REDIZO**, ale **nemá IZO ani kód oboru/KKOV** – agregace je jen na úrovni škola × SMO16 (skupina oborů, 16 kategorií, textový kód typu „LYC", „GY8" apod.), ne na úrovni jednotlivého oboru vzdělání.
- Řádky opět míchají typy: celorepublikové „total"/„CELKEM" řádky, krajské řádky (`redizo='x'`), řádky za celou školu (`..._CELKEM`, REDIZO vyplněno, SMO16=„CELKEM") a řádky škola × SMO16 (`redizo_smo16_...`). **Sloupec 1 („TŘÍDĚNÍ"/„entita_id_row") určuje typ řádku** – nutné filtrovat na `TŘÍDĚNÍ IN ('redizo','redizo_smo16')` pro školní data.
- **Drobný rozdíl 2017 vs. 2026**: soubor 2026 má navíc 2 sloupce na začátku (`entita_id_row`, `id_row` – nové ID sloupce), 2017 je nemá; jinak je pozice a název sloupců od REDIZO dál prakticky identická (jen 96 vs. 98 sloupců celkem kvůli těm 2 navíc). Formát maturity je tedy **napříč roky 2015–2026 velmi stabilní** – žádoucí pro snadný import jedním parserem.
- Příklad – Obchodní akademie Heroldovy sady (REDIZO 600006573), řádek CELKEM 2026: přihlášeno 116, konalo 113, uspělo 111, neuspělo 2, nekonalo 3, úspěšnost 95,7 %.

## 8. vysledky.cermat.cz – Power BI a API

- Web `vysledky.cermat.cz` je **starý ASP.NET WebForms portál** (ViewState, `ScriptResource.axd`), ne moderní SPA. Menu: Úvodní stránka, Agregovaná data, Maturitní zkouška, Jednotná přijímací zkouška, Grafické interpretace, Položková data, Číselníky.
- Na stránce `data/PrehledVysledkuJPZ.aspx` (Agregovaná data → JPZ) je odkaz **„Výsledková data za jednotlivé školy"** vedoucí na embedded Power BI report:
  `https://app.powerbi.com/view?r=eyJrIjoiODZlOTNkZWYtYWFlMC00NTdlLWE5YzYtN2ExYTFkODQ2NWRkIiwidCI6Ijc4ODJmYzNiLTRhOTAtNDk4Ny05MmQ4LTNlMzFiODE4ZTZjNSIsImMiOjh9`
- To je **veřejné „view" embed** Power BI (ne API) – **žádný přímý JSON/XHR datový endpoint nebyl na statických HTML stránkách nalezen** (nekontroloval jsem network trace v prohlížeči/JS runtime, jen statický HTML/zdrojový kód stránek – to je omezení tohoto průzkumu). Power BI „view" reporty typicky natahují data přes interní, měnící se a autorizované Power BI Query API (ne stabilní veřejné REST rozhraní), export je možný jen ručně přes UI (Power BI umí export do CSV/Excel z reportu, ale je to manuální krok, ne skriptovatelný endpoint bez reverse-engineeringu tokenů).
- **Doporučení**: pro automatizovaný import nepoužívat Power BI dashboard, ale přímo XLSX soubory z data.cermat.cz (sekce 5–7 výše) – jsou stabilnější, verzované podle roku/kola a bez nutnosti autentizace.
- Jinde na webu (`graf/Default.aspx`, `statistika/Default.aspx`) nebyly nalezeny žádné další zmínky Power BI ani jiné XHR/JSON API.

## 9. Souhrn konzistence struktury napříč lety

| Zdroj | Roky | Konzistence |
|---|---|---|
| JPZ skoly-skolobory (starý) | 2017–2023 | Stabilní jádro, drobné odchylky (počet sloupců pro absence: NEKONALI vs. OMLUVENI/NEOMLUVENI/VYLOUČENI v 2020; počet/název listů) |
| JPZ skolobory (nový, kolo1/kolo2 × kapacity/prihlasky/vysledky) | 2024–2026 | Vypadá stabilní, ale **jiné schéma než 2017–2023** (zlom v roce 2024) |
| Maturita SC_skolobory | 2015–2026 | Velmi stabilní (jen +2 ID sloupce od nějakého roku), stejné předměty a metriky |

## 10. Doporučení pro import v Pythonu

1. Používat `openpyxl` (ideálně `read_only=True` kvůli velikosti – soubory 0,4–4 MB, resp. region. agregace až 18 MB) nebo `pandas.read_excel(engine="openpyxl")`.
2. Hlavička je typicky na **2. řádku listu** (řádek 0 = sloučený titulek) – při čtení přeskočit řádek 0, nebo `header=1` v pandas.
3. Pro JPZ 2017–2023: filtrovat řádky, kde 1. sloupec je číselné REDIZO (školní řádky), ignorovat krajské/celkové součty.
4. Pro JPZ 2024–2026: filtrovat na sloupec REDIZO (číslo) a případně KOLO (1/2), spojovat `vysledky`/`prihlasky`/`kapacity` přes `ID_SO` nebo `(REDIZO, KKOV, ROČNÍK)`.
5. Pro maturitu: filtrovat `TŘÍDĚNÍ`/`entita_id_row` na hodnoty `redizo` (škola celkem) a `redizo_smo16` (škola × skupina oborů), ignorovat `total`/kraj.
6. IZO ve „vysledky" 2024–2026 má textový prefix `izo_...` – při propojování s jinými zdroji (např. rejstřík škol MŠMT) je nutné prefix odstranit/normalizovat.
7. Držet dvě samostatné parsovací třídy/mapování: JPZ-starý (≤2023) vs. JPZ-nový (≥2024); maturitní parser lze mít jeden pro všechny roky.
8. Před ostrým importem doporučuji stáhnout a porovnat hlavičky i pro PZ2024 a PZ2025 (v tomto průzkumu ověřen jen PZ2026) a pro maturitní roky 2018–2025 (ověřeny jen 2017 a 2026), aby se odhalily případné mezilehlé drobné změny.

## 11. Problémy / omezení tohoto průzkumu

- Nebyl ověřen skutečný obsah 2. kola PZ 2026 (odkaz existuje, ale sezóna 2026 probíhá – soubor může být částečně prázdný/neaktuální k 22.9.2026).
- Nebyly stahovány ani kontrolovány soubory „uchazeci_prihlasky_vysledky" (jednotlivé přihlášky uchazečů) ani položková data po úlohách – mimo scope „po školách", ale mohou být zajímavé pro budoucí rozšíření.
- Power BI dashboard nebyl analyzován v prohlížeči/přes network trace (jen statický HTML), takže existence případného skrytého JSON API nebyla zcela vyloučena, jen nebyla nalezena v dostupném statickém kódu.
- Hlavičky souborů MZ za roky 2018–2025 a JPZ nový formát za roky 2024–2025 byly doověřeny dodatečně, viz oddíl 12 (MZ) — JPZ 2024–2025 zůstává neověřené.

## 12. Porovnání hlaviček MZ 2015–2026 (ověřeno před importem importéru `cermat_mz.py`)

Staženo a porovnáno všech **24 souborů** `MZ{rok}{j,jap}_SC_skolobory.xlsx` pro
roky 2015–2026 (oba soubory za každý rok). Hlavička je vždy na **řádku 2**
(řádek 1 je sloučený titulek), datová oblast začíná řádkem 3. Zjištění:

- **Sloupce od `TŘÍDĚNÍ` dál (fixní identifikační sloupce i všechny bloky
  předmětů) mají naprosto stejný název a pořadí ve všech 24 souborech.**
  Bloky předmětů jsou vždy v pořadí `SPOLEČNÁ ČÁST MZ CELKEM` (9 sloupců,
  bez skóru/percentilu, jen počty a dvě míry neúspěšnosti navíc – „hrubá
  neúspěšnost" a „neúčast"), `ČESKÝ JAZYK` (10 sloupců, bez podílu volby
  předmětu – ČJ je povinný), `MATEMATIKA, ANGLIČTINA, NĚMČINA, RUŠTINA,
  FRANCOUZŠTINA, ŠPANĚLŠTINA` (po 11 sloupcích, včetně podílu volby
  předmětu – volí se mezi MA a cizím jazykem). Celkem 11 fixních + 85
  předmětových = 96 sloupců od `TŘÍDĚNÍ`.
- **Liší se jen počet a pojmenování 0–2 úvodních ID sloupců před `TŘÍDĚNÍ`**:
  - `j` soubory **2015–2017**: žádné úvodní sloupce, `TŘÍDĚNÍ` je sloupec A
    (96 sloupců celkem).
  - `j` soubory **2018–2026**: dva úvodní sloupce `entita_id_row, id_row`
    (98 sloupců).
  - `jap` soubory **2015–2024**: dva úvodní sloupce, ale **nepojmenované** –
    1. sloupec má prázdnou hlavičku (`None`), 2. sloupec se jmenuje `entita`
    (98 sloupců).
  - `jap` soubory **2025–2026**: stejné dva sloupce, nově pojmenované
    `entita_id_row, id_row` (98 sloupců) – sjednoceno s `j`.
  - Žádný jiný rozdíl (počet listů, typy řádků, hodnoty ve sloupci
    `TŘÍDĚNÍ`) mezi roky nalezen nebyl.
- **Důsledek pro parser**: mapovat sloupce podle jména hledáním `TŘÍDĚNÍ`,
  `ROK`, `REDIZO`, `SMO16` a `KRAJ - NÁZEV` v hlavičce (řádek 2) a bloky
  předmětů počítat pozičně od prvního sloupce za `KRAJ - NÁZEV` v pevně
  daných šířkách (9/10/11×6) – funguje shodně pro všech 24 souborů bez
  ohledu na úvodní ID sloupce. Přesně to dělá `jaknastredni/cermat_mz.py`.
- **REDIZO** je v části souborů uloženo jako číslo (např. `2026 jap`), v
  jiných jako text (`2017 j`) – nutné normalizovat na 9místný textový řetězec
  se zleva doplněnými nulami.
- **Chybějící hodnoty** (typicky cizí jazyky, které na dané škole nikdo
  nepsal) nejsou `None`/prázdné buňky, ale doslovný řetězec `"-"` – parser ho
  převádí na `NULL`.
- Ověřeno na referenční škole REDIZO 600006573 (Obchodní akademie, Heroldovy
  sady): řádek CELKEM/CELKEM v `MZ2026j_SC_skolobory.xlsx` dává přihlášeno
  116, konalo 113, uspělo 111, neuspělo 2, nekonalo 3 – shoduje se s
  příkladem v oddílu 7.

Maturitní soubory jsou napříč 2015–2026 bezpečně importovatelné jedním
parserem; JPZ nový formát (2024–2025) zůstává neověřený a je otevřenou
otázkou pro příští importér (JPZ 2024+).

## 13. Porovnání hlaviček JPZ starý formát 2017–2023 (ověřeno před importem importéru `cermat_jpz_old.py`)

Staženo a porovnáno všech **7 souborů** `JPZ{rok}_skoly-skolobory_vysledky.xlsx`
pro roky 2017–2023. Zjištění:

- **Počet a název listů se mezi roky liší** — `main` list (`ciselniky`, pokud
  je přítomen, se ignoruje):
  - 2017–2020: dva listy, hlavní `JPZ{rok}_red` + `ciselniky`.
  - 2021: dva listy, hlavní `JPZ2021` (bez přípony `_red`) + `ciselniky`.
  - 2022: jeden list, `JPZ2022-radny a nahradni termin` (žádný `ciselniky`).
  - 2023: jeden list, `List1` (žádný `ciselniky`).
  - **Důsledek pro parser**: název hlavního listu nejde odvodit z roku ani
    z pevného vzoru — bere se jediný list, jehož název (case-insensitive)
    není `"ciselniky"`.
- **Hlavička je vždy na 2. řádku** (1. řádek je sloučený titulek
  `JPZ {rok} - VÝSLEDKY ŠKOL A OBOROVÝCH SKUPIN...`), stejně jako u maturity.
- **Fixní úvodní sloupce (0–7) mají shodný název a pořadí ve všech 7
  souborech**: `REDIZO / KRAJ / OBOROVÁ SKUPINA, OBOROVÁ SKUPINA, ROČNÍK,
  NÁZEV ŠKOLY, ADRESA ŠKOLY, KRAJ (KÓD), KRAJ (NÁZEV), ZŘIZOVATEL`. Za nimi
  následují dva shodně strukturované bloky `ČESKÝ JAZYK` a `MATEMATIKA`
  (2022/2023 mají v titulku `MATEMATIKA*` s poznámkou o ukrajinských
  uchazečích — sloupce samotné jsou beze změny).
- **Potvrzený rozdíl v absenčních sloupcích** (mezi `KONALI` a `PRŮMĚRNÉ
  PERCENTILOVÉ UMÍSTĚNÍ` v každém předmětovém bloku):
  - 2017, 2018, 2019, 2021, 2022, 2023: jeden sloupec `NEKONALI`.
  - **2020**: tři sloupce `OMLUVENI, NEOMLUVENI, VYLOUČENI` místo jednoho
    `NEKONALI` (posouvá zbytek hlavičky o +2 sloupce oproti ostatním rokům).
  - Cílový datový model (`jpz_skupina`) tyto sloupce vůbec nepotřebuje (žádné
    pole "nekonali"), takže se prostě nemapují — parser hledá jen jména
    `PŘIHLÁŠENI`, `KONALI`, `PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ`, `SMĚRODATNÁ
    ODCHYLKA (PERCENTIL. UMÍSTĚNÍ)` (každé z nich se v hlavičce vyskytuje
    přesně 2×, poprvé v bloku ČJ, podruhé v bloku MA) a je mu jedno, co přesně
    je mezi `KONALI` a `PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ`.
  - Přesně tohle dělá `jaknastredni/cermat_jpz_old.py` (funkce `_find_pair`).
- **Počet datových řádků na list**: 3421 (2017) až 2056 (2021, hlubší pokles
  patrně souvislost s covidovým ročníkem/změnou organizace přijímaček), po
  filtru na číselné REDIZO klesá na 3364/3286/3218/3211/1997/3235/3258
  školních řádků. Žádné duplicitní klíče `(redizo, oborová skupina, ročník)`
  uvnitř jednoho ročníku nebyly nalezeny (ověřeno skriptem nad všemi
  staženými soubory).
- **Žádný sloupec typu `TŘÍDĚNÍ`** (na rozdíl od maturity) — školní řádky se
  poznají výhradně podle toho, že 1. sloupec (`REDIZO / KRAJ / OBOROVÁ
  SKUPINA`) obsahuje číslo. Krajské řádky mají v 1. sloupci buď text názvu
  kraje (2017–2021), nebo `None` (2022, 2023 — kraj řádky mají prázdný 1.
  sloupec, ale vyplněné `KRAJ (KÓD)`/`KRAJ (NÁZEV)`), celorepublikové řádky
  mají text typu `"GYMNÁZIUM 8LETÉ CELKEM"`. Regexem `\d+(\.0)?` na
  `str(hodnota).strip()` (a explicitním vyloučením `bool`, protože Python
  `True`/`False` je `isinstance(..., int)`) se filtrují spolehlivě všechny
  roky.
- **REDIZO přichází jako `int`/`float` ve všech 7 souborech** (na rozdíl od
  maturity, kde je to místy text) — normalizace na 9místný text se zleva
  doplněnými nulami je ale stejná.
- **`ZŘIZOVATEL` je v roce 2022 uložen jako text `'7'`, jinde jako číslo `7`**
  — nepodstatné, sloupec se do `jpz_skupina` vůbec neukládá (schéma podle
  `datovy-model.md` ho nepotřebuje).
- **Ověřeno na referenční škole REDIZO 600006573** (Obchodní akademie,
  Heroldovy sady), skupina `4LETÉ OBORY`, ročník 9: `PŘIHLÁŠENI/KONALI` ČJ
  232/232, průměrný percentil ČJ 66,4, průměrný percentil MA 66,0 v roce
  2017 — hodnoty se shodují s příkladem v oddílu 5 a se skutečným importem
  do `jpz_skupina`. Trend 2017→2023 pro tuto školu (skupina `4LETÉ OBORY`):
  přihlášeno 232→468, průměrný percentil ČJ 66,4→68,9, MA 66,0→70,6 —
  hodnoty rostou plynule bez viditelných skoků na hranici 2019/2020, což
  potvrzuje, že se rozdílný počet/název absenčních sloupců v 2020 promítl do
  parsování korektně (jinak by dávkové posunutí sloupců u 2020 způsobilo
  zjevně nesmyslné hodnoty).

Soubory JPZ 2017–2023 jsou tedy bezpečně importovatelné jedním parserem,
mapujícím sloupce podle jména (ne podle pozice), stejně jako maturita.
JPZ nový formát (2024–2026) zůstává neověřený, viz oddíl 6, a je otevřenou
otázkou pro příští importér (JPZ 2024+, tabulka `prijimaci_rizeni`).

## Přílohy
Soubory JPZ nového formátu (oddíl 6) zůstaly jen ve scratchpadu průzkumu,
mimo repo:
- `<scratchpad>/cermat/files/PZ2026_kolo1_skolobory_{vysledky,prihlasky,kapacity}.xlsx`
- `<scratchpad>/cermat/files/PZ2024-2026_agregace_typskoly_region_prihlasky.xlsx`

Soubory maturity `MZ{rok}{j,jap}_SC_skolobory.xlsx` (2015–2026, 24 souborů) a
JPZ starého formátu `JPZ{rok}_skoly-skolobory_vysledky.xlsx` (2017–2023, 7
souborů) jsou naimportované a uložené v repu v `data/raw/cermat/`
(rozhodnutí uložit i syrová data do repa, ne jen do `.gitignore`d `data/`,
viz README, sekce „Rozhodnutí o ukládání dat").
