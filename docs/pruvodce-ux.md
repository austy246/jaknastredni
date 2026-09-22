# Průvodce výběrem školy — návrh UX

Návrh interakce, kterou uchazeč (respektive jeho rodič) projde, aby se ze
**623 denních nabídek pražských středních škol** dostal na pět, které mu
dávají smysl. Implementace návrhu: [`jaknastredni/pruvodce.py`](../jaknastredni/pruvodce.py)
(výpočetní jádro + interaktivní CLI) a [`jaknastredni/oblasti.py`](../jaknastredni/oblasti.py)
(překlad kódů KKOV do lidské řeči).

## Pro koho a proti čemu

Uživatel je žák 9. (nebo 5./7.) třídy a jeho rodič, někdy v září až lednu.
Zná dvě tři školy „od známých", má mlhavou představu o oboru a zásadně mu
chybí odpověď na otázku **„kam mám reálnou šanci se dostat?"**. Existující
weby (Atlas školství, infoabsolvent, agregátory — viz README, zdroje 4–6)
mu dají buď encyklopedický seznam bez pořadí, nebo neprůhledné „skóre
obtížnosti" bez vzorce. Průvodce má být tím třetím: **řadí, a u každého
čísla řekne, odkud je a co neumí**.

## Tři principy, ze kterých návrh vychází

**1. Jednotka není škola, ale nabídka (škola × obor).** Přihláška se podává
na obor, kapacita i hranice přijetí jsou oborové. Kdybychom řadili školy,
průměrovali bychom gymnázium s učňovským oborem na téže adrese. Pětice na
konci je tedy pět nabídek — a nejvýš jedna od každé školy (viz `vyber_top`),
protože dvě varianty IT oboru na jedné průmyslovce jsou pro uchazeče jedna
volba, ne dvě.

**2. Přihlášky jsou tři a pořadí se nevyplatí taktizovat.** Od roku 2024
rozhoduje o umístění centrální algoritmus podle priorit uchazeče — dát si
na první místo sen nikdy neuškodí šanci na druhou a třetí volbu. UX z toho
plyne: nestačí „top 5", je potřeba **návrh tří přihlášek rozložených podle
rizika** (sen / realistická / jistota). Kdo si podá tři sny, jde do 2. kola.
Proto `portfolio()` a proto je v textu výsledku ta věta o pořadí napsaná
natvrdo — je to nejčastější a nejdražší omyl rodičů.

**3. Průhlednost místo přesnosti.** Data umí spočítat hodně, ale ne to
hlavní (jestli tam bude dítě šťastné). Každá karta proto nese `duvody`
(proč se objevila) i `varovani` (co data neříkají) a šance je vždy doplněná
o zdroj odhadu. Raději „90 %, odhadnuto z poměru přihlášek ku kapacitě"
než holé „90 %".

## Průchod otázkami

Devět otázek, z toho **povinná jediná** (první). Každá další jen zužuje;
kdo nic nevyplní, dostane pětici škol s nejlepšími maturitními výsledky,
kam se dá dostat. Pořadí je od nejvíc rozhodujícího filtru k nejjemnějšímu,
aby se dalo kdykoli odejít s rozumným výsledkem.

| # | Otázka | Typ | Co dělá | Z čeho v datech |
|---|---|---|---|---|
| 1 | Ze které třídy se hlásíš? (5./7./9.) | výběr, povinné | tvrdý filtr | poslední dvojčíslí KKOV (`K/81`, `K/61`, ostatní) |
| 2 | Jaký typ vzdělání? (gymnázium, lyceum, SOŠ, obor s výučním listem) | víc možností | tvrdý filtr | písmeno KKOV (`K`/`M`/`L`/`H`/`E`) |
| 3 | Které oblasti tě baví? (11 oblastí) | víc možností | tvrdý filtr + skóre `zajem` | první dvojčíslí KKOV → `oblasti.OBLASTI` |
| 4 | Kde by to mělo být? (Praha 1–10) | víc možností | skóre `blizkost` | `organizace.obvod_prahy` + `misto_vyuky` |
| 5 | Očekávaný % skór z přijímaček (ČJ, MA) | 2× číslo 0–100 | šance na přijetí | `prijimaci_rizeni.skor_prijati_min_cjma` |
| 6 | Průměr na vysvědčení | číslo 1–5 | skóre `dosazitelnost` | `doporuceny_prospech` (Atlas školství) |
| 7 | Kolik můžete dát za školné? | výběr | tvrdý filtr + skóre `cena` | `web_profil` → `skolne_rocne` |
| 8 | Co je pro tebe nejdůležitější? (max 3) | víc možností | mění váhy složek | — |
| 9 | Chceš mít jistotu konkrétního jazyka? | výběr | tvrdý filtr | `web_profil` → `vyucovane_jazyky` |

(Desátá možnost — školy zřízené pro žáky se zdravotním postižením —
není otázka ve formuláři, ale přepínač `Profil.specialni_potreby`;
viz „Co se do výsledku nedostane vůbec".)

Proč zrovna takhle:

- **Otázka 1 je první a povinná**, protože jediná dělí nabídku na tři skoro
  nepřekrývající se světy (41 osmiletých, 17 šestiletých, 565 čtyřletých
  nabídek). Bez ní nejde ukázat ani rozumný výchozí seznam.
- **Otázka 3 se ptá na oblasti, ne na obory.** Skupin oborů je v pražské
  nabídce 27 a jejich oficiální názvy („Obecně odborná příprava") uchazeči
  nic neříkají. `oblasti.py` je mapuje na 11 srozumitelných oblastí, které
  se **smějí překrývat** — elektrotechnika (26) patří pod „IT" i pod
  „Techniku", polygrafie (34) pod „Řemesla" i „Média". Filtr má radši
  nabídnout víc než obor schovat.
- **Otázky 5 a 6 jsou dvě, ne jedna.** Na skór z přijímaček nanečisto
  odpoví jen část uchazečů (a v září skoro nikdo), průměr na vysvědčení zná
  každý. Otázka 5 je přesnější a pohání odhad šance; otázka 6 je záchytná a
  promítá se do skóre `dosazitelnost` (školy dávají body za prospěch).
  Ani jedna není povinná — bez nich se šance odhaduje jen z poměru
  přihlášek ku kapacitě a průvodce to u výsledku napíše.
- **Otázka 8 nemění, co se zobrazí, ale v jakém pořadí.** Zvolená priorita
  zdvojnásobí váhu své složky skóre (`_vahy_profilu`). Víc než tři priority
  = žádná priorita, proto tvrdý limit tři.
- **Otázka 4 nefiltruje, jen váží.** Kdo zaškrtne Prahu 6, ale hledá
  bezplatný IT obor, žádný tam nenajde — místo prázdného výsledku dostane
  okolí a poznámku „v Praze 6 nic takového není". Sousedství obvodů je
  hrubá náhrada dojezdové doby MHD (viz „Co návrh zatím neumí").

### Co se do výsledku nedostane vůbec

Šest pražských organizací jsou školy **zřízené pro žáky se zdravotním
postižením** (podle názvu: „pro sluchově postižené", „pro zrakově
postižené", „škola speciální") a do toho praktické školy (typ `C`).
Pro uchazeče bez doporučení školského poradenského zařízení to není volba
a v pětici zabírají místo — bez `Profil.specialni_potreby` se proto
nenabízejí. Rejstřík MŠMT žádný příznak „speciální škola" nemá (rozlišuje
jen `druh`), takže je to **heuristika podle názvu** (`VZOR_SKOLY_PRO_ZP`);
na pražských datech sedí přesně (6 z 238 organizací, ručně zkontrolováno),
ale při rozšíření mimo Prahu je potřeba ji ověřit znovu.

### Na co se záměrně neptáme

- **Na kraj.** Databáze je pražská (README, kontrolní součty).
- **Na formu studia.** Žák ZŠ jde do denního studia; dálkové a nástavbové
  obory průvodce vyřazuje rovnou (`oblasti.TYPY_MIMO_ZS`).
- **Na „jak dobrá má být škola".** Nikdo neřekne „chci průměrnou školu".
  Kvalita se do pořadí promítá vždy, jen s vyšší vahou, když si ji uchazeč
  zvolí jako prioritu.
- **Na konkrétní školy, které už zná.** Zajímavá funkce („máme tyhle tři,
  co dál?"), ale je to jiná úloha než průvodce — spíš srovnávací pohled,
  viz „Další kroky".

## Skóre shody

Vážený průměr šesti složek, každá normalizovaná na 0–1, výsledek na 0–100.
Váhy jsou v `SLOZKY_SKORE`, zvolená priorita svou složku zdvojnásobí:

| Složka | Váha | Co měří |
|---|---|---|
| `zajem` | 3,0 | jak přesně obor sedí do zvolených oblastí |
| `dosazitelnost` | 2,5 | reálnost přijetí (šance + doporučený prospěch) |
| `kvalita` | 1,5 | maturitní výsledky školy, úspěšnost, posun žáků |
| `blizkost` | 1,5 | zvolený obvod (1,0) / sousední (0,6) / jinde (0,2) |
| `cena` | 1,0 | školné proti zadanému stropu |
| `prostredi` | 1,0 | velikost školy, jazyky, vybavení — jen podle priorit |

Dvě rozhodnutí, která nejsou samozřejmá:

- **`dosazitelnost` není „čím jistější, tím lepší".** Nad 40 % šance dává
  plný bod a dál už neroste. Cílem je vyhodit z pětice školy, kam uchazeč
  nemá reálnou šanci — ne tlačit ho do nejpodprůměrnější školy, kam ho
  určitě vezmou. Rozložení rizika je práce `portfolio()`, ne řazení.
- **`kvalita` se normalizuje proti tomu, co zrovna prošlo filtrem**, ne
  proti celé Praze. Percentily maturit se mezi gymnázii a učňovskými obory
  liší o desítky bodů; absolutní práh by u odborných oborů celou složku
  fakticky vypnul (všichni by měli nulu).

Chybějící data dávají 0,5 (neutrál), ne nulu — škola nemá být potrestaná za
to, že ji CERMAT nevykázal. Místo toho se to napíše do `varovani`.

## Šance na přijetí

Nejdůležitější a nejnebezpečnější číslo v celém průvodci. Počítá se ve
třech úrovních podle toho, co o nabídce víme (`sance_prijeti`):

**1. Známá hranice přijetí** (467 z 803 pražských nabídek 2026). CERMAT od
roku 2024 zveřejňuje minimální % skór přijatého uchazeče
(`skor_prijati_min_cjma`, škála 0–200 = součet % skóru z ČJ a MA).
Očekávaná hranice pro příští rok je vážený průměr let 2024–2026 (nejnovější
rok váží 3×) a šance je normální rozdělení kolem ní:

```
šance = Φ((očekávaný skór uchazeče − očekávaná hranice) / σ)
```

`σ` **není odhad od stolu** — vychází z naměřeného meziročního rozptylu
hranic: na 598 dvojicích škola×obor (2024→2025 a 2025→2026) je směrodatná
odchylka meziroční změny 20,4 bodu, medián |změny| 12 bodů, p90 32 bodů.
Odtud `SIGMA_ZAKLAD = 18`, u škol s rozkolísanou hranicí až 32, u nabídek
s jediným rokem dat 24. Uchazeč přesně na loňské hranici tak dostane zhruba
50 %, ne 100 % — což je přesně ta zpráva, kterou potřebuje slyšet.

**2. Jen poměr přihlášek ku kapacitě** (`index_poptavky`). Hrubý odhad
z pásem (≤ 0,9 → 92 %; ≤ 1,2 → 80 %; ≤ 2 → 60 %; ≤ 4 → 35 %; víc → 18 %),
posunutý podle toho, jak silný uchazeč je proti průměru. Používá se tam,
kde škola hranici nevykázala. Pozor: `index_poptavky < 1` **neznamená**, že
vezmou všechny — v roce 2026 bylo takových nabídek 81 a jen v 15 z nich se
počet přijatých rovnal počtu přihlášených (zbytek uchazečů se dostal na
školu s vyšší prioritou).

**3. Nic z toho** — typicky učňovské obory bez jednotné zkoušky. Šance je
`None` a karta ukáže „data chybí", ne vymyšlené procento. Až bude
v databázi Atlas školství (loňský **skutečný** počet přijatých, ne jen
plán), pokryje i tuhle skupinu — kód už s tím počítá (`loni_prijati`).

Odhad se vždy ořízne na 3–97 %. Stoprocentní jistota neexistuje, protože
škola si k JPZ přidává vlastní kritéria (prospěch, pohovor, talentovka),
která v datech nejsou — a pokud je přidává, je to napsané ve `varovani`.

## Karta výsledku

Pořadí informací na kartě odpovídá tomu, v jakém pořadí se rodič ptá:

1. **Název školy, obor, kód KKOV, typ** — co to vlastně je.
2. **Adresa, městská část, web.**
3. **Shoda X/100 a šance na přijetí Y % (+ odkud odhad je).**
4. **Hranice přijetí po letech** — tři čísla vedle sebe řeknou o stabilitě
   školy víc než jeden průměr.
5. **Přijímačky posledního roku:** přihlášek / míst / přijatých, plus
   letošní plán školy.
6. **`+` důvody** — obor sedí do zvolené oblasti, školné, maturitní
   úspěšnost, posun žáků, velikost školy.
7. **`!` varování** — rozkolísaná hranice, vlastní kritéria školy,
   talentová zkouška (jiný termín přihlášky!), chybějící data, stará
   inspekční zpráva.
8. **Den otevřených dveří a odkaz na inspekční zprávy ČŠI** — jediné dvě
   akce, které může uživatel hned udělat.

Pod pěticí je **návrh tří přihlášek** s rolemi sen (šance 10–45 %),
realistická (45–82 %) a jistota (82 % a výš). V každém pásmu se vybírá
nabídka s **nejvyšší shodou**, ne s nejvyšší šancí, a nikdy dvakrát táž
škola (dedupe podle REDIZO) — tři přihlášky na jednu školu nejsou rozložené
riziko, protože dva obory téže školy padnou obvykle společně. Když pásmo zůstane
prázdné, řekne se proč — „nic, kam by tě vzali skoro jistě, přidej záložní
obor, jinak hrozí 2. kolo" je užitečnější než prázdné místo.

## Metrika „posun" (přidaná hodnota školy)

Maturitní výsledky měří hlavně to, jaké žáky škola přijala — gymnázium
s hranicí 160 bodů bude mít lepší maturity než učňovský obor bez ohledu na
to, jak učí. Proto se počítá i **posun**: průměrný percentil školy u
maturity v roce Y minus průměrný percentil téže školy u přijímaček v roce
Y−4, tedy zhruba tentýž ročník na vstupu a na výstupu (`jpz_skupina`
2017–2023 × `maturita` 2015+, 514 z 623 nabídek má výsledek).

Je to **hrubý ukazatel**, ne oficiální „přidaná hodnota":

- obě čísla jsou za celou školu (CERMAT u maturity neuvádí IZO ani KKOV),
  takže se míchají obory,
- kohorta není táž (odchody, opakování, přestupy, víceletá gymnázia),
- percentily z JPZ a z maturity mají jinou referenční populaci.

Proto se posun nikdy neukazuje jako hlavní číslo, jen jako jeden ze tří
vstupů do složky `kvalita` a jako řádek `+` na kartě s uvedenými roky.

## Oblasti zájmu

Mapování 27 skupin KKOV → 11 oblastí je v `oblasti.OBLASTI` a bylo
odvozeno z reálných názvů oborů v pražském snapshotu, ne z teorie. Skupiny
se záměrně opakují ve víc oblastech:

| Oblast | Skupiny KKOV |
|---|---|
| Všeobecné vzdělání (gymnázium, lyceum) | 79, 78 |
| IT, počítače, elektronika | 18, 26 |
| Technika, strojírenství, doprava | 23, 26, 28, 37, 39 |
| Stavebnictví a řemesla | 36, 33, 31, 32, 34, 21 |
| Ekonomika, obchod, podnikání | 63, 64, 66, 37 |
| Právo, veřejná správa, bezpečnost | 68 |
| Zdravotnictví a péče o člověka | 53, 43, 69, 74 |
| Pedagogika a sociální práce | 75, 61 |
| Umění, design, média | 82, 72, 34 |
| Gastronomie, hotelnictví, cestovní ruch | 65, 29 |
| Příroda, zemědělství, ekologie | 16, 41, 43, 28 |

## Co návrh zatím neumí

- **Dojezdovou dobu MHD.** Nejžádanější údaj, který nemáme — místo něj je
  sousednost obvodů (`oblasti.SOUSEDNI_OBVODY`), což u Prahy 4 vs. Prahy 9
  hodně zkresluje. Řeší to import GTFS z Golemia/PID (README, zdroj 12);
  až bude, nahradí `_skore_blizkost` skutečný dojezd ze zadané adresy.
- **Atmosféru školy, kvalitu učitelů, šikanu.** Nejbližší zástupný údaj jsou
  závěry inspekčních zpráv ČŠI — PDF jsou strojově čitelná a mají sekce
  „Silné stránky" / „Příležitosti ke zlepšení" (README, zdroj 3). Zatím se
  odkazuje jen na portál.
- **Poměr žák/učitel a velikost tříd.** Statistické výkazy MŠMT/ÚIV
  (README, zdroj 11) — neověřeno stažením.
- **Uplatnění absolventů konkrétní školy.** Infoabsolvent má karty oborů
  obecně, ne po školách.
- **Změny pro příští ročník.** Škola může obor zrušit, otevřít nový nebo
  změnit kritéria; průvodce pracuje s loňskými čísly a říká to.

## Druhý zdroj: Atlas školství

`_doplnit_web_profil()` čte **všechny** zdroje v tabulce `web_profil`
v pořadí `PORADI_ZDROJU` (`infoabsolvent`, pak `atlas`); pozdější zdroj jen
doplňuje, co chybí, nikdy nepřepisuje. Pořadí určuje `ORDER BY` v SQL, ne
náhodné pořadí řádků.

Atlas (`jaknastredni/atlas.py`, 215 pražských škol, 738 oborů) přináší tři
pole, která infoabsolvent nemá vůbec:

| Pole | Pokrytí | K čemu je v průvodci |
|---|---|---|
| `doporuceny_prospech` | 72 z 623 nabídek | otázka 6 — složka `dosazitelnost` a text na kartě |
| `loni_prijati` | 552 z 623 | **skutečně** přijatí, ne plán (3. úroveň odhadu šance) |
| `plp` | 570 z 623 (333× ano) | povinná lékařská prohlídka — konkrétní úkol pro rodiče |

**Názvy klíčů se mezi scrapery liší** a záměrně se nesjednocují: každý
scraper pojmenovává pole podle svého webu, aby šla dohledat ke zdroji.
Aliasy řeší až `_prvni()` v průvodci — `den_otevrenych_dveri` vs.
`dny_otevrenych_dveri`, `letos_plan_prijmout` vs. `planovany_pocet_prijmout`.
Atlas navíc u oboru **neuvádí formu studia** (nemá pro ni sloupec), takže
filtr na denní formu jeho řádky propouští; spojovacím klíčem je KKOV.

### Co Atlas na odhadu šance nezměnil

`loni_prijati` mělo podle původního návrhu pokrýt učňovské obory bez JPZ,
kde odhad šance chyběl. V praxi se to neprojeví: **44 nabídek nemá data
o přijímacím řízení** a ani jedna z nich nemá oborový řádek v Atlasu ani
v infoabsolventu (škola se páruje přes REDIZO, ale ten konkrétní obor
v jejich tabulce oborů není). Zbylé obory bez jednotné zkoušky mají v CERMAT
řádek s kapacitou a přihláškami, takže na ně sahá už 2. úroveň odhadu
(`index_poptavky`). `loni_prijati` tedy dnes slouží hlavně jako druhý zdroj
čísel na kartě a jako pojistka, kdyby CERMAT řádek chyběl.

Otevřená možnost do budoucna: u nabídek **bez zveřejněné hranice** (46 %)
je přihlášky/**přijatí** přesnější signál poptávky než dnešní
přihlášky/**kapacita** — kapacita nemusí být naplněná. Obě čísla má přitom
CERMAT sám, takže na to Atlas není potřeba; je to změna modelu, ne
propojení zdroje, proto zůstává jako návrh.

## Webový prototyp

`web/index.html` je klikací verze návrhu — jedna statická stránka bez
serveru, všech devět otázek pod sebou a **výsledek se překresluje při každé
změně** (včetně počtu vyhovujících nabídek v hlavičce, takže je vidět, jak
se trychtýř zužuje). Data a konstanty si bere z `web/data.js`, který
generuje:

```bash
python -m jaknastredni.export_web --db data/jaknastredni.db -o web/data.js
```

`web/data.js` se **neverzuje** (odvozený artefakt, stejně jako databáze —
viz README, „Rozhodnutí o vývoji a ukládání dat"); stránka se otevře i
přímo z disku, proto je to `window.JNS_DATA = {…}`, ne čistý JSON.

Zdrojem pravdy o hodnocení zůstává `pruvodce.py`. Export proto do dat
přibaluje i **všechny konstanty** (váhy složek, σ, pásma portfolia, oblasti
zájmu, typy vzdělání) a JavaScript je čte odtamtud — změna váhy v Pythonu
se po přegenerování projeví i ve webu. Duplikovaný zůstává jen tvar vzorce
(~150 řádků v `index.html`); při změně logiky hodnocení je potřeba upravit
obojí.

Dvě věci, které prototyp ukazuje a CLI ne:

- **Osa 0–200 bodů** pod každou kartou: hranice přijetí za jednotlivé roky
  jako svislé značky a skór uchazeče červeně. Tři čísla v řadě vedle sebe
  řeknou o stabilitě školy víc než průměr a je hned vidět, jestli uchazeč
  stojí nad hranicí, nebo v pásmu, kde o tom rozhodne vlastní kritérium
  školy.
- **Pás šance** s rozmytým koncem — vizuální připomínka, že je to odhad
  s nejistotou, ne naměřená hodnota.

## Další kroky

1. **Plnohodnotné webové UI.** Prototyp je jednostránkový a ukazuje všechny
   otázky naráz; ostrá verze by měla mít průchod po krocích s možností
   kdykoli přeskočit a sdílitelný odkaz na výsledek. `--json` výstup CLI je
   přesně to, co takový frontend potřebuje.
2. **Srovnávací pohled** pro 2–3 vybrané školy vedle sebe (tabulka let,
   hranice, maturity) — to, co si uživatel stejně dělá ručně v Excelu.
3. **Dojezd MHD** (GTFS) — největší jednotlivé zlepšení kvality výsledku.
4. **Závěry inspekčních zpráv** — extrakce sekcí ze ČŠI PDF pro školy
   v užším výběru, ne pro všech 219.
5. **Kalibrace na skutečnosti.** Až budou známé výsledky 2027, porovnat
   odhad šance s tím, jak to dopadlo, a případně upravit `σ`.
