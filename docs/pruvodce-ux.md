# Průvodce výběrem školy — návrh UX

Návrh interakce, kterou uchazeč (respektive jeho rodič) projde, aby se ze
**702 denních nabídek pražských středních škol** dostal na pět, které mu
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

**1. Jednotka není škola, ale nabídka (škola × obor × zaměření).** Přihláška se podává
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

Patnáct otázek a jedna doplňující (5b), z toho **povinná jediná** (první). Každá další jen zužuje;
kdo nic nevyplní, dostane pětici škol s nejlepšími maturitními výsledky,
kam se dá dostat. Pořadí je od nejvíc rozhodujícího filtru k nejjemnějšímu,
aby se dalo kdykoli odejít s rozumným výsledkem.

| # | Otázka | Typ | Co dělá | Z čeho v datech |
|---|---|---|---|---|
| 1 | Ze které třídy se hlásíš? (5./7./9.) | výběr, povinné | tvrdý filtr | poslední dvojčíslí KKOV (`K/81`, `K/61`, ostatní) |
| 2 | Co chceš dělat, až školu dodělᚠ| výběr | skóre `typ` | — |
| 3 | Víš už, čemu se chceš věnovat? | výběr | skóre `typ` | — |
| 4 | Kolik chceš praxe? | výběr | skóre `typ` | — |
| 5 | Které oblasti tě baví? (12 oblastí) | víc možností | tvrdý filtr + skóre `zajem` | první dvojčíslí KKOV → `oblasti.OBLASTI` |
| 5b | A co konkrétně z toho? | víc možností | skóre `zajem` | názvy ŠVP a popisy škol → `oblasti.ZAMERENI` |
| 6 | Kde bydlíš? (Praha 1–22) | víc možností | skóre `blizkost` | `obvod_prahy` + `misto_vyuky`, přes `MC_NA_OBVOD` |
| 7 | Body z přijímaček nanečisto (ČJ, MA) | 2× číslo 0–50 | šance na přijetí | `prijimacky_pasmo` |
| 8 | Průměr na vysvědčení | číslo 1–5 | skóre `dosazitelnost` | `doporuceny_prospech` (Atlas školství) |
| 9 | Kolik můžete dát za školné? | výběr | tvrdý filtr + skóre `cena` | `web_profil` → `skolne_rocne` |
| 10 | Co je pro tebe nejdůležitější? (max 3) | víc možností | mění váhy složek | — |
| 11 | Chceš mít jistotu konkrétního jazyka? | výběr | skóre `jazyk` | `web_profil` → `vyucovane_jazyky` |
| 12 | Děláš sport/umění závodně? | výběr | tvrdý filtr | `talentova_zkouska` |
| 13 | Připravuješ se už teď? | výběr | návrh posuvníku | — |
| 14 | Kolik hodin týdně reálně máš? | výběr | návrh posuvníku | — |
| 15 | Chodíš na kurz nebo doučování? | výběr | návrh posuvníku | — |

Školy zřízené pro žáky se zdravotním postižením nejsou otázka ve formuláři,
ale přepínač `Profil.specialni_potreby` (viz „Co se do výsledku nedostane
vůbec"). **Kdy jsou přijímačky se taky neptáme — spočítá se to**: termíny ze
scrapu (`prihlasky_do`, `termin_jpz`) se posunou na nejbližší budoucí výskyt
a nad výsledkem se ukáže, kolik zbývá týdnů. Ta tvrdší deadline není zkouška,
ale **termín přihlášky** — trojice škol musí být hotová o dva měsíce dřív.

Proč zrovna takhle:

- **Otázka 1 je první a povinná**, protože jediná dělí nabídku na tři skoro
  nepřekrývající se světy (41 osmiletých, 17 šestiletých, 565 čtyřletých
  nabídek). Bez ní nejde ukázat ani rozumný výchozí seznam.
- **Na typ vzdělání se průvodce neptá, odvozuje ho** (otázky 2–4). Čtrnáctiletý
  netuší, jestli chce „lyceum" nebo „čtyřletý maturitní obor" — a kdyby to
  věděl, nepotřebuje průvodce. Ptáme se proto na tři věci, na které odpovědět
  umí (co po škole, jak moc má jasno, kolik praxe), a typ z nich spočítáme
  (`oblasti.OSOBNOSTNI_OTAZKY`, `preference_typu`). Není to filtr, ale váha:
  ostatní typy zůstávají ve výsledku, jen níž. Odvozený typ se pak ukáže nad
  výsledkem jako **zjištění** („podle odpovědí ti sedí lyceum, SOŠ,
  gymnázium"), ne jako něco, co musel uchazeč vyplnit.
- **Otázka 6 se ptá na městskou část, ne na správní obvod.** Data MŠMT mají
  jen obvody Praha 1–10, ale nikdo neřekne „bydlím ve správním obvodu Praha
  4" — řekne „v Praze 12". `oblasti.MC_NA_OBVOD` to přeloží (Modřany a Kamýk
  jsou v rejstříku pod Prahou 4, ověřeno v datech).
- **Otázka 7 se ptá na body z 50, ne na procenta.** Uchazeč dostane
  z přijímaček nanečisto „19 bodů z češtiny", ne „38 %". Převod na % skór,
  se kterým pracuje CERMAT, dělá formulář.
- **Otázka 5 se ptá na oblasti, ne na obory.** Skupin oborů je v pražské
  nabídce 27 a jejich oficiální názvy („Obecně odborná příprava") uchazeči
  nic neříkají. `oblasti.py` je mapuje na 11 srozumitelných oblastí, které
  se **smějí překrývat** — elektrotechnika (26) patří pod „IT" i pod
  „Techniku", polygrafie (34) pod „Řemesla" i „Média". Filtr má radši
  nabídnout víc než obor schovat.
- **Otázky 7 a 8 jsou dvě, ne jedna.** Na skór z přijímaček nanečisto
  odpoví jen část uchazečů (a v září skoro nikdo), průměr na vysvědčení zná
  každý. Otázka 7 je přesnější a pohání odhad šance; otázka 8 je záchytná a
  promítá se do skóre `dosazitelnost` (školy dávají body za prospěch).
  Ani jedna není povinná — bez nich se šance odhaduje jen z poměru
  přihlášek ku kapacitě a průvodce to u výsledku napíše.
- **Otázka 10 nemění, co se zobrazí, ale v jakém pořadí.** Zvolená priorita
  zdvojnásobí váhu své složky skóre (`_vahy_profilu`). Víc než tři priority
  = žádná priorita, proto tvrdý limit tři.
- **Otázka 6 nefiltruje, jen váží.** Kdo zaškrtne Prahu 6, ale hledá
  bezplatný IT obor, žádný tam nenajde — místo prázdného výsledku dostane
  okolí a poznámku „v Praze 6 nic takového není". Sousedství obvodů je
  hrubá náhrada dojezdové doby MHD (viz „Co návrh zatím neumí").

- **Otázky 13–15 se neptají na odhodlání.** „Jak moc se budeš připravovat?"
  odpoví každý „hodně" a odpověď nemá informační hodnotu. Ptáme se na
  chování, které už běží, a na čas, který reálně je. Z odpovědí vyjde
  **návrh polohy posuvníku** (0–10 bodů na předmět), ne předpověď —
  a průvodce to o sobě říká nahlas: žádná veřejná data nevážou hodiny
  přípravy na body, soubory uchazečů CERMAT obsahují výsledek, ne přípravu.
  Jakýkoli převod „3× týdně = +15 bodů" by byl vymyšlený, tedy přesně to,
  co u agregátorů kritizujeme (README, zdroj 6).
- **Jazyk (otázka 11) váží, nefiltruje.** Jako tvrdý filtr vyhazoval třetinu
  nabídky (138 → 90) a měnil 3 z 5 škol v pětici — na otázku, která vypadá
  jako detail na konci formuláře, moc. Kdo na jazyku trvá, zapne
  `Profil.jazyk_povinny`.

### Jak se pozná, co která otázka dělá

Měřeno na reálném profilu (9. třída, IT + humanitní, Praha 12, 108/200 b.,
prospěch 1,4, do 30 tis., priorita kvalita) — mění se vždy jedna odpověď:

| Otázka | Změna | Nabídek (ze 138) | Vymění v pětici |
|---|---|---|---|
| 1. třída | 5. místo 9. | 25 | 5/5 |
| 2.–4. osobnostní | „rovnou pracovat" místo „na vysokou" | 138 | typy `[M,M,M,M,G4]` → `[H,H,M,L0,H]` |
| 5. oblasti | jen IT / nevyplněno | 42 / 369 | 2/5 |
| 6. bydliště | Praha 6 místo 12 | 138 | 3/5 |
| 7. body | +5 b. v obou / nevyplněno | 138 | 3/5 / 4/5 |
| 8. prospěch | 3,0 místo 1,4 | 138 | 1/5 |
| 9. školné | nerozhoduje / jen zdarma | 208 / 129 | 1/5 / 0/5 |
| 10. priorita | jistota místo kvality | 138 | 3/5 |
| 11. jazyk | němčina | 138 | 3/5 |
| 12. talentovky | zapnuto | 139 | 0/5 |

Tohle měření odhalilo, že složka `typ` původně nedělala nic (0–1 z 5) —
měla jen 16 % váhy a její surové hodnoty se mačkaly kolem 0,75. Opravou
bylo zvýšení váhy na 21 % **a normalizace proti kandidátům**, takže
rozhoduje pořadí typů, ne jejich absolutní hodnota.

### Co se do výsledku nedostane vůbec

**Obory s talentovou zkouškou** (52 nabídek: 48 uměleckých, 4 sportovní
gymnázia) bez zaškrtnutí otázky 12. Není to přísnost, ale oprava chyby:
talentovka je **jiná vstupní brána, ne nižší laťka**. Gymnázium Přípotoční má
u sportovního oboru hranici JPZ o 34 bodů nižší než u akademického na téže
adrese — ne proto, že by o něj byl menší zájem, ale protože se vybírá podle
talentu. Průvodce to bral jako snadnější cestu a stavěl sportovní gymnázium
na první místo uchazeči, který o sportu neřekl ani slovo. Naměřená data to
potvrzují: u sportovního oboru je míra přijetí napříč bodovými pásmy plochá
(25 / 56 / 24 / 25 %), body tam prakticky nerozhodují.

**Soukromé školy s neuvedeným školným**, když je zadaný strop (28 nabídek).
Chybějící údaj se nesmí brát jako nula: PORG má u gymnázia 199 100 Kč, ale
u pedagogického oboru v datech nic — filtr „do 30 tisíc" takovou školu tiše
propouštěl. U veřejného zřizovatele je neuvedené školné bezpečně nula.

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

Vážený průměr osmi složek, každá normalizovaná na 0–1, výsledek na 0–100.
Váhy jsou v `SLOZKY_SKORE`, zvolená priorita svou složku zdvojnásobí
(`PARAMETRY["priorita_nasobek"]`, **u každé složky nejvýš jednou**):

| Složka | Váha | Co měří |
|---|---|---|
| `zajem` | 3,0 | jak přesně obor sedí do zvolených oblastí a zaměření |
| `typ` | 3,0 | typ vzdělání odvozený z osobnostních otázek |
| `dosazitelnost` | 2,5 | reálnost přijetí (šance + doporučený prospěch) |
| `kvalita` | 1,5 | percentil a úspěšnost maturit, posun žáků (inspekce zatím ne) |
| `blizkost` | 1,5 | zvolený obvod / sousední / jinde |
| `cena` | 1,0 | školné proti zadanému stropu |
| `prostredi` | 1,0 | velikost školy, vybavení, praxe — jen podle priorit |
| `jazyk` | 1,0 | učí škola jazyk, který uchazeč chce |

Všechna ostatní čísla ze vzorců složek (prahy, násobky, neutrální 0,5,
pásma šance z poptávky, meze šance 3–97 %) jsou v `PARAMETRY`,
`SANCE_Z_POPTAVKY` a `OMEZ` v `pruvodce.py`. Exportují se do `data.js`
a web z nich počítá **i skládá veřejný popis** v kroku „Jak hodnotíme"
(`#jak-hodnotime`) — ladí se tedy na jednom místě a popis nemůže zastarat.

### Revize hodnocení (září 2026)

- **Priority se na jedné složce násobily.** Sport + umění + praxe míří všechny
  na `prostredi` a daly mu váhu 1 × 2 × 2 × 2 = 8 — víc než zájem nebo typ.
  Teď se každá složka zdvojnásobí nejvýš jednou.
- **Cena veřejné školy bez údaje o školném** byla neutrální 0,5, přestože filtr
  školného ji (správně) bere jako nulu. Veřejná škola tak prošla filtrem „jen
  bez školného", ale v ceně prohrávala se soukromou, která nulu vyplnila.
  Teď dostane 1,0 stejně jako filtr.
- Magická čísla ze `_skore_*` (a jejich opisy v `web/index.html`) přesunuta do
  `PARAMETRY`; web je čte z dat, takže opis v JavaScriptu už nese jen tvar vzorce.
- Tabulka výše uváděla šest složek a `typ` s vahou 2,0 — neplatilo od přidání
  složky `jazyk` a zvýšení váhy typu. Patička webu tvrdila, že šance je normální
  rozdělení kolem hranice; přednost má ale naměřený podíl přijatých.

Co zůstává k ladění (vědomá rozhodnutí, ne chyby): skok ceny z 1,0 na
nejvýš 0,8 u i malého školného (`cena_strop_placene`), neznámá šance =
0,4 dosažitelnosti (odpovídá 16 % šance) a lineární, ne logaritmická škála
velikosti školy.

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
čtyřech úrovních podle toho, co o nabídce víme (`sance_prijeti`):

**1. Naměřený podíl přijatých** (629 ze 702 nabídek). CERMAT zveřejňuje
soubory uchazečů — jeden řádek = jeden anonymizovaný uchazeč, jeho % skór
a až pět přihlášek s výsledkem. Importér `jaknastredni.cermat_uchazeci` z nich
spočítá tabulku `prijimacky_pasmo`: kolik lidí se v jakém bodovém pásmu na
který obor hlásilo a kolik jich vzali. Odhad pak **není model, ale
pozorování**: „ze 115 uchazečů s podobným skórem se jich dostalo 39".

Do jmenovatele jdou jen **věcně posouzené** přihlášky (přijatí plus
nepřijatí pro nedostatečnou kapacitu nebo nesplnění podmínek). Kdo byl
nepřijat proto, že se dostal na vyšší prioritu, posouzen nebyl a nepočítá se
— jinak by každá druhá volba vypadala nedostupně.

**2. Známá hranice přijetí** (min. % skór posledního přijatého): normální
rozdělení kolem očekávané hranice, σ = 18 až 32 podle naměřeného meziročního
rozptylu (směrodatná odchylka meziroční změny je 20,4 bodu na 598 dvojicích
škola×obor). Slouží jako záloha a zároveň jako **kotva smršťování** pro
úroveň 1.

**3. Poměr přihlášek ku kapacitě** (`index_poptavky`), případně loňský poměr
přihlášených ku přijatým z Atlasu. Hrubý odhad z pásem.

**4. Nic z toho**: None — karta ukáže „data chybí", ne vymyšlené procento.

### Proč naměřená data, když hranice přijetí existuje

Hranice je **minimální** skór přijatého, tedy ocasová hodnota — často jeden
uchazeč, který se dostal na body za prospěch nebo v rozřazení při shodě.
Odhad postavený na ní je systematicky optimistický. Měřeno proti skutečnosti
u profilu se 108 body z 200:

| Škola / obor | odhad z hranice | naměřeno |
|---|---|---|
| Gymnázium Písnická | 24 % | **10 %** |
| SPŠ elektrotechnická V Úžlabině (IT) | 53 % | **29 %** |
| SOŠ automobilní a informatiky (IT) | 62 % | **49 %** |
| Gymnázium Přípotoční — sportovní příprava | 44 % | **22 %** |

Dát rodiči 24 %, když se z jeho pásma nedostal ani jeden ze čtrnácti, je ta
nejhorší chyba, jakou tenhle nástroj může udělat.

### Tři věci, které musely doplnit surová čísla

**Vyhlazení (`_monotonni_pasma`).** V pásmu o osmi lidech rozhodne jeden,
takže naměřené podíly po pásmech skáčou nahoru a dolů. Bez úpravy průvodce
tvrdil „se 140 body 90 %, se 156 body 79 %" — nesmysl, protože víc bodů
uchazeči uškodit nemůže. Řeší to **isotonická regrese metodou PAVA**: dokud
je pásmo nižší než to před ním, slijí se do bloku se společným, vahou
váženým podílem. Váha je počet posouzených přihlášek, takže velká pásma
táhnou malá.

**Rozhodnutí o metodě jednou za nabídku.** Dřív se o použití naměřených dat
rozhodovalo podle vzorku v okolí uchazečova skóru — jenže pak odhad uprostřed
rozsahu přepnul na jinou metodu a na tom přepnutí vznikl útes („se 170 body
95 %, se 180 body 52 %"). Teď platí: buď o nabídce data máme (aspoň
`MIN_VZOREK` posouzených přihlášek celkem), nebo ne. Nad i pod rozsahem
naměřených pásem se drží krajní hodnota křivky. **Výsledek je ověřený
testem: napříč všemi 702 nabídkami a celým rozsahem skóre šance ani jednou
neklesne s rostoucími body** (`test_sance_nikdy_neklesa_se_skorem`).

**Obory, kde nerozhoduje jednotná zkouška.** U oborů s výučním listem se JPZ
nekoná — v roce 2026 nemělo % skór 37 004 ze 156 210 uchazečů. Bodovaní
uchazeči u takového oboru jsou jen ti, kdo si vedle toho podali i maturitní
obor, a odhadovat z nich šanci je nepřesné i nemonotonní. Pozná se to podle
toho, že uchazečů bez skóru je aspoň tolik co s ním (`_prevazuje_bez_jpz`);
pak se skór ignoruje a použije se míra přijetí za obor jako celek.

### Smršťování

Naměřený podíl se míchá s odhadem z hranice (úroveň 2) vahou podle velikosti
vzorku: `(podíl × N + SMRSTENI × kotva) / (N + SMRSTENI)`, kde `SMRSTENI = 5`.
Brání tomu, aby „0 z 12" znamenalo tvrdou nulu — škola může letos vzít víc
lidí a kritéria se mění. Váha je **celkový** vzorek nabídky, ne lokální:
konstantní váha drží výsledek monotonní, protože konvexní kombinace dvou
neklesajících funkcí je neklesající.

Odhad se vždy ořízne na 3–97 %. Stoprocentní jistota neexistuje, protože
škola si k JPZ přidává vlastní kritéria (prospěch, talentovka, pohovor),
která v datech nejsou.

### Co soubory uchazečů neobsahují

**Žádný údaj o základní škole ani o známkách.** Odhadnout šanci „podle
vysvědčení" tedy z veřejných dat nejde a tenhle soubor je nejblíž, co
existuje. Jediný náznak vazby známka → přijetí je `doporuceny_prospech`
z Atlasu školství (72 nabídek) a text „body za prospěch" v kritériích škol —
což je doporučení školy, ne změřený vztah.

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

Když má škola víc oborů, zobrazí se jen jeden — ale ostatní se **nesmějí
ztratit**: vypíšou se pod kartou jako „táž škola nabízí i …" s vlastní šancí.
Bez toho se uchazeč nedozvěděl, že Gymnázium Přípotoční má vedle sportovního
oboru i akademický, na který je zrovna 37 bodů krátký — což je užitečná
informace sama o sobě.

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
2017–2023 × `maturita` 2015+, 611 ze 702 nabídek má výsledek).

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

## Zaměření uvnitř oboru

Kód KKOV je na rozhodování hrubý. Pod `18-20-M/01` (Informační technologie)
učí v Praze desítky škol a každá něco jiného:

| Škola | Název ŠVP | Co o tom píše ve svém popisu |
|---|---|---|
| SPŠE Ječná | Programování a digitální technologie | „robotické laboratoře, síťové učebny s vlastními servery", certifikáty Cisco a Oracle |
| SPŠE V Úžlabině | Informační technologie | „správce serverových služeb operačních systémů a počítačových sítí"; volitelné specializace programování, web, herní grafika, kyberbezpečnost |

Rozdíl, podle kterého se uchazeč rozhoduje, je **jen v těchhle textech** —
v žádném číselníku není. Proto se zaměření hledá klíčovými slovy
(`oblasti.ZAMERENI`, 30 zaměření) ve čtyřech polích: název oboru z rejstříku,
`svp_nazev` (infoabsolvent), `zamereni_oboru` (CERMAT) a volný popis školy
(`doplnujici_informace` z Atlasu, `vybaveni_a_nabidka` z infoabsolventu).

**Je to heuristika, ne číselník**, a průvodce to nesmí vydávat za fakt.
Rozlišuje proto dvě síly důkazu a kartě to napíše:

| Úroveň | Kdy | Násobí skóre `zajem` | Věta na kartě |
|---|---|---|---|
| `obor` | zaměření sedí na texty **o oboru** (název, ŠVP, zaměření z CERMATu) | ×1,0 | „Sedí na tvoje zaměření (…) — ŠVP …" |
| `skola` | sedí jen na volný popis **celé školy** | ×0,9 | „Škola … uvádí ve svém popisu, ale u tohohle oboru to doložené nemáme" |
| `nevime` | o oboru nevíme nic bližšího | ×0,8 | „O bližším zaměření tohohle oboru nemáme data" |
| `jine` | obor **má** rozpoznané zaměření a je jiné | ×0,6 | „Pozor: obor je podle popisu spíš …" |

Popis školy váží míň schválně: platí pro všechny její obory dohromady, takže
z Úžlabiny vyjde dvanáct zaměření včetně sportu (z „sportovní kurzy") a
společenských věd (z popisu gymnázia). Jako důkaz o konkrétním oboru je to
slabé — ale pořád je to jediné místo, kde se ta síťařina dá vyčíst.

V pražské nabídce (702 nabídek) má **420 rozpoznané zaměření u oboru**, 257
jen z popisu školy a 25 ani to. Otázka není mrtvá: ze 46 kombinací
oblast × zaměření jich **36 (78 %) změní aspoň jednu školu v pětici**.

Zaměření nic nefiltruje, jen přeskládá pořadí — a počítá se jen tehdy, když
patří k některé ze zvolených oblastí (`Profil.hledana_zamereni`).

**Srážka jen v oblasti, kde nabídka soutěží** (září 2026). Zaměření
„Programování" zaškrtnuté u IT dřív srazilo i každé gymnázium (nemá ŠVP
„programování" → úroveň `nevime`, ×0,8), přestože gymnázium do IT vůbec
nepatří a informatiku učí jako předmět. Teď se sráží jen za zaměření, jehož
oblast je mezi oblastmi, přes které nabídka prošla; jinak je úroveň `mimo`
(×1,0). Shoda u oboru platí vždy, takže gymnázium s „programováním" v ŠVP
dostane důvod na kartě. Pro gymnázia a lycea přibyla vlastní zaměření
u oblasti „Všeobecné vzdělání": `informatika` a `ekonomie`.

Na profilu uchazeče se zaškrtnutým všeobecným vzděláním, humanitními obory
a IT (programování + elektro), s odpovědí „něco od obojího" a skóre ~120
nebylo v první desítce žádné gymnázium (nejlepší až 24.). Kromě srážky za
zaměření to dělaly ještě dvě věci:

- **Šířka výběru přebíjela explicitní „chci si nechat otevřené dveře"**
  (viz „Šířka výběru"). Kdo zaškrtne všeobecné vzdělání, na tuhle otázku
  už odpověděl sám; úzký výběr „jen všeobecné + informatika" navíc
  znamená „chci gymnázium", ne „vím přesně, chci obor". `Profil.sirka` je
  proto se zaškrtnutým `vseobecne` None. Bez toho vyšlo profilu „jen
  všeobecné + informatika" deset lyceí a žádné gymnázium.
- **„Něco od obojího" dávalo gymnáziu 0,5** proti lyceu 0,9. Protože se
  typ normalizuje proti kandidátům, byla z toho plná nula. Nově 0,75.

**Co v datech o gymnáziích opravdu je.** Názvy ŠVP gymnázií jsou většinou
motta („Per aspera ad astra", „Klíč ke vzdělání"); profilaci nese jen asi
čtvrtina. Podle toho, co tam je, přibyla/rozšířila se zaměření:
`informatika` (1. IT Gymnázium, Arabská, Doppler, Třebešín, esporty),
`ekonomie` (ART ECON, „s ekonomickým zaměřením"), `medicina` (FOSTRA Meda),
výtvarno (`umeni_design` nově i u všeobecného: Pražačka, „esteticko-výchovné"),
mezinárodní programy (International, AP, IB) pod `jazyky`, geografie pod
`prirodni_vedy`, „právo a bezpečnost" pod `pravo_verejna_sprava`.

**Povinný základ gymnázia** (`ZAKLAD_GYMNAZIA`): přírodní vědy, jazyky,
společenské vědy a informatiku učí podle RVP G každé gymnázium. Bez
doložené rozšířené výuky je proto úroveň `zaklad` (×0,9), ne `nevime`
(×0,8), a karta to řekne.

**Šum v „zaměření z popisu školy".** Pole `vybaveni_a_nabidka` z
infoabsolventu je zaškrtávací seznam: „multimediální jazyková učebna"
dávala `media` 89 školám a `jazyky` 80, „zájmový kroužek sportovní, …,
přírodovědný" `sport` 78 a `prirodni_vedy` 36. `oblasti.zamereni_vybaveni`
tyhle standardní položky zahodí. A „na našich webových stránkách" (108
škol) už nedělá zaměření `web`.

Aby se nepřehouplo na opačnou stranu (deset gymnázií, žádná průmyslovka
u uchazeče, který si IT zaškrtl), má při víc zaškrtnutých oblastech každá
z nich v doporučených `REZERVA_OBLASTI` = 2 místa (`vyber_top`). Doporučuje
se nově deset škol (`POCET_DOPORUCENYCH`), ne pět.

### Co tahle cesta neumí

- **Naměřenou šanci rozlišit po zaměření.** Soubory uchazečů CERMATu nesou
  jen REDIZO + KKOV, zaměření v nich není — `prijimacky_pasmo` je proto
  sdílené. Hranice, kapacita a poptávka už po zaměření rozlišené jsou (viz
  „Nabídka = škola × obor × zaměření"), takže Gymnázium Na Pražačce ukazuje
  hranice 146 / 130 / 62, ale u všech tří stejnou naměřenou šanci 32 %.
  **Karta to musí přiznat**, jinak se to čte jako fakt o tom konkrétním
  zaměření: `Nabidka.pasma_sdileno` řekne, kolik nabídek se o křivku dělí,
  a mezi varování (`!`) přibude „Naměřená šance je za celý obor 79-41-K/61
  dohromady (3 zaměření) — u zaměření s vyšší hranicí je ve skutečnosti
  nižší, u snazšího vyšší.".
- **Co škola nenapsala.** Slovník vzorů pozná jen to, co je v textu.

## Nabídka = škola × obor × zaměření

Jednotkou není (IZO × KKOV), ale **(IZO × KKOV × zaměření)** — 702 pražských
nabídek místo 623. Dokud se zaměření slévala váženým průměrem, platilo pro
Gymnázium Na Pražačce jedno číslo 113, i když se uchazeč rozhoduje mezi:

| Zaměření (79-41-K/61) | Hranice 2026 | Přijato |
|---|---|---|
| Všeobecné | 146 | 30 |
| Německý jazyk | 130 | 30 |
| Výtvarná výchova | 62 | 30 |

Rozdělených nabídek s víc než jednou hranicí je **38**; u **13** se aspoň
jedno zaměření liší od starého průměru o 10 bodů a víc, u **8** o 15 a víc,
u **3** o 30 a víc. Největší je Na Pražačce (62 vs. 146) a Gymnázium
Přípotoční, kde se sportovní příprava dělí na volejbal (156) až atletiku (90).

Dvě věci, které se u toho ukázaly a které s zaměřeními vůbec nesouvisely:

- **Nedenní formy se počítaly do hranic denního studia.** `prijimaci_rizeni`
  vede pod týmž IZO a KKOV i dálkové, kombinované a distanční kohorty —
  79 řádků u 28 pražských nabídek. Karlínské gymnázium tak mělo hranici 121
  z pražské denní třídy (142) a dálkového programu „Druhá šance" (22);
  Českoslovanská akademie 4letou denní 108 smíchanou s 5letou dálkovou 40.
  Soubory uchazečů (`cermat_uchazeci`) filtrují na `forma == 'den'` odjakživa,
  tahle strana to jen doháněla (`pruvodce.FORMA_DENNI`).
- **Mimopražské pobočky pod pražským IZO.** PORG vede pod `79-41-K/81`
  vedle pražských tříd (146 a 144) i „8leté PORG Brno" (114) a „8leté PORG
  Ostrava" (80), policejní škola vedle Prahy i „Bezpečnostní pracovník,
  Sokolov". Do pražského průvodce nepatří a vyřazují se: pozná se to tak,
  že název zaměření pojmenovává obec, kde má škola podle rejstříku
  (`misto_vyuky`) místo výuky mimo Prahu — netýká se to seznamu měst
  v kódu, ale pěti konkrétních škol, které mimopražskou výuku doložené mají.

Po obojím rozliší zaměření pražskou denní nabídku **beze zbytku** — nezůstala
ani jedna dvojice řádků, kterou by klíč nerozdělil. Délka ani jazyk studia
proto v klíči nejsou; co by se pod jedním klíčem přesto sešlo, slije se
váženým průměrem podle počtu přijatých jako dřív.

Sesterská zaměření téže školy se do pětice nedostanou dvakrát (`vyber_top`
pouští nejvýš jednu nabídku na REDIZO) — zbylá se vypíšou pod kartou jako
„Táž škola nabízí i: Gymnázium — Německý jazyk (79-41-K/61, šance 32 %)".

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
| `doporuceny_prospech` | 89 ze 702 nabídek | otázka 6 — složka `dosazitelnost` a text na kartě |
| `loni_prijati` | 626 ze 702 | **skutečně** přijatí, ne plán (3. úroveň odhadu šance) |
| `plp` | 650 ze 702 (375× ano) | povinná lékařská prohlídka — konkrétní úkol pro rodiče |

**Názvy klíčů se mezi scrapery liší** a záměrně se nesjednocují: každý
scraper pojmenovává pole podle svého webu, aby šla dohledat ke zdroji.
Aliasy řeší až `_prvni()` v průvodci — `den_otevrenych_dveri` vs.
`dny_otevrenych_dveri`, `letos_plan_prijmout` vs. `planovany_pocet_prijmout`.
Atlas navíc u oboru **neuvádí formu studia** (nemá pro ni sloupec), takže
filtr na denní formu jeho řádky propouští; spojovacím klíčem je KKOV.

### Co Atlas na odhadu šance nezměnil

`loni_prijati` mělo podle původního návrhu pokrýt učňovské obory bez JPZ,
kde odhad šance chyběl. Pokrývá jich málo: **49 nabídek nemá data
o přijímacím řízení** a jen 9 z nich má oborový řádek v Atlasu nebo
v infoabsolventu (škola se páruje přes REDIZO, ale ten konkrétní obor
v jejich tabulce oborů často není). Zbylé obory bez jednotné zkoušky mají
v CERMAT řádek s kapacitou a přihláškami, takže na ně sahá už 2. úroveň
odhadu (`index_poptavky`). `loni_prijati` tedy dnes slouží hlavně jako
druhý zdroj čísel na kartě a jako pojistka, kdyby CERMAT řádek chyběl.

Otevřená možnost do budoucna: u nabídek **bez zveřejněné hranice** (42 %)
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

### Šířka výběru jako měření nerozhodnosti

Otázka 3b („A co konkrétně z toho?") nese víc informace, než kolik z ní
průvodce původně četl. **Kolik** políček uchazeč zaškrtl je samo o sobě
odpověď — a to na otázku, na kterou se průvodce už ptá jinde:
`rozhodnuto` („Víš už, čemu se chceš věnovat?"). Kdo zaškrtne osm zaměření
z osmi, tím řekl „ještě nevím" spolehlivěji, než jak na to umí odpovědět
přímo. Je to chování, ne sebehodnocení, a u čtrnáctiletého je chování lepší
důkaz — proto šířka výběru odpověď na `rozhodnuto` **nahrazuje**, i když ji
uchazeč vyplnil. S ostatními dvěma osobnostními otázkami (`po_skole`,
`praxe`) se dál průměruje, takže vyhrává otázku, kterou měří, ne celé skóre.

Než tohle přibylo, chovalo se to **obráceně**. `_uroven_zamereni` bere
maximum přes zaškrtnutá zaměření: stačí jedna trefa z jedenácti a odborná
škola má násobek 1,0, kdežto gymnázium má `zamereni_kody` skoro vždycky
prázdné a zůstane trčet na 0,8 („nevíme") ať uchazeč zaškrtne cokoli.
Naměřeno na oblastech IT + všeobecné (200 nabídek): při žádném zaškrtnutém
zaměření měla gymnázia průměrnou shodu 0,743 proti 0,681 u odborných škol,
při sedmi už 0,839 proti 0,931 — a v pětici nezbylo ani jedno gymnázium.
Čím širší výběr, tím víc to tlačilo *od* všeobecného vzdělání.

Měří se dvě věci, vážené 3:1 (`VAHA_PODILU_ZAMERENI`):

- **Podíl zaměření** (`zvolená / nabízená`), ne jejich počet. Čtyři ze čtyř
  nabízených je něco jiného než čtyři z osmadvaceti; absolutní počet by
  trestal uchazeče, kterým formulář nabídl užší výběr.
- **Počet oblastí**, protože šířka *uvnitř* jedné oblasti není nerozhodnost.
  Kdo zaškrtne všech osm IT zaměření, neříká „nevím, co chci" — říká „chci
  IT, je mi jedno jaké", a tomu sedí široká průmyslovka, ne gymnázium.

Výsledná šířka 0–1 interpoluje mezi tabulkami variant `obor` a `otevreno`
otázky `rozhodnuto` (`SIRKA_ROZHODNUTO` = 0,25, `SIRKA_OTEVRENO` = 0,75),
takže nepřináší žádná nová čísla — jen jiný způsob, jak se na tutéž otázku
dostat odpověď.

#### Otázka 3c: gymnázia, která filtr vyhodil

Samotné řazení by ale nestačilo. Kdo zaškrtne jen oblast „IT", tomu tvrdý
filtr oblastí vyhodí **všech 148 pražských gymnázií** a žádná změna skóre
je nevrátí. Při šířce nad `PRAH_SIROKY_VYBER` (0,5) se proto objeví
doplňující otázka 3c: *„Zaškrtl sis 8 z 8 zaměření. Gymnázia a lycea ti
tvůj výběr oblastí vyřadil — přitom právě ony nechávají rozhodnutí o oboru
na později. Chceš je vidět taky?"* Ptá se, místo aby je potichu přidal —
je to nabídka toho, co uchazeč **nezaškrtl**. Neptá se, když si oblast
`vseobecne` zaškrtl sám; tam gymnázia ve výběru dávno jsou.

Po „ano" platí přidaná oblast pro filtr **i pro skóre zájmu**
(`Profil.ucinne_oblasti`). Musí to být jeden seznam pro obojí: kdyby
`vseobecne` prošlo jen filtrem, gymnázium by dostalo zájem 0,0 a skončilo
na chvostu — stejně neviditelné, jen s větší prací. Zároveň se zájem srazí
na `ZAJEM_PRIDANA_OBLAST` (0,75), protože přidaná oblast je odvozené
zjištění, ne zaškrtnutá volba — stejná logika, podle které zaměření
z popisu školy váží míň než doložené u oboru.

A ještě jedna past: složka typu se normalizuje přes kandidáty, takže jakmile
gymnázium porazí průmyslovku, porazí ji **každé** gymnázium. Uchazeč, který
napsal „baví mě IT", pak dostal pětici gymnázií a ani jednu průmyslovku —
druhý extrém, ne oprava. `vyber_top` proto drží `REZERVA_ZVOLENYCH` (2) míst
z pěti pro oblasti, které uchazeč doopravdy zaškrtl. Smysl přidání je dát
obojí vedle sebe na porovnání, ne jedno nahradit druhým. Na profilu „jen
IT, 8 z 8 zaměření, skór 80/76" vypadá výsledek takhle:

| zaškrtnuto | pětice |
| --- | --- |
| 2 z 8 | 5× průmyslovka (typ M) |
| 5 z 8 | 5× průmyslovka |
| 8 z 8, bez otázky 3c | 5× průmyslovka |
| 8 z 8, po „ano" ve 3c | 3× gymnázium + 2× průmyslovka |

### Ladicí výpis

Karta ukazuje závěr, ne vstup. Když pořadí nesedí očekávání („proč je ta
druhá škola výš, když první sedí líp na zaměření?"), není z čeho poznat,
jestli je chyba v datech, v pravidlech, nebo v očekávání — a hádat se o tom
bez čísel nemá cenu. Proto je pod výsledkem rozbalovací **Ladicí výpis** se
třemi částmi:

1. **Zadaný profil** ve tvaru, který bere `pruvodce.Profil.z_json`. Uloží se
   jako `profil.json` a `python -m jaknastredni.pruvodce --profil profil.json`
   musí vydat **totéž pořadí**. Tím se spor „web říká něco jiného než CLI"
   rozhodne za deset vteřin. Pozor na `skor_cj`/`skor_ma`: do profilu jdou
   **bez** zlepšení, to jede vedle jako `zlepseni_bodu` — `Profil.skor` si ho
   přičítá samo a jinak by se započítalo dvakrát.
2. **Pořadí a rozpad skóre** — tabulka všech nabídek, co prošly filtrem,
   se složkami 0–1 i s tím, **kolik ze 100 bodů** složka po započtení váhy
   dala. To druhé číslo je to podstatné: holá hodnota 0–1 svádí číst složku
   s vahou 1,0 stejně jako složku s vahou 3,0.
3. **Konkrétní škola** — syrová data jejích nabídek včetně těch, které
   filtrem neprošly, a u každé **důvod** (`duvodFiltru`). Tady se pozná
   rozdíl mezi „průvodce to spočítal špatně" a „škola to nikam nenapsala",
   což je u zaměření (heuristika nad volným textem) ta nejčastější otázka.

Stejné funkce jsou i v konzoli jako `window.JNS` (`JNS.stav`, `JNS.ohodnot()`,
`JNS.duvodFiltru(n)`, `JNS.profil()`, `JNS.prekresli()`).

### Ověření webu proti Pythonu

Tvrzení „stránka čte konstanty z dat, takže se od `pruvodce.py` nemůže
rozejít" **neplatilo**: konstanty sedí, ale port se rozešel v tom, co
vlastně počítá. Nalezeno a opraveno najednou:

| co | web dělal | Python dělá |
| --- | --- | --- |
| složka `jazyk` | nepočítala se vůbec, váha 1,0 ale zůstala ve jmenovateli | `_skore_jazyk` |
| složka `typ` | surová preference (pásmo ~0,75, neřídila nic) | normalizace proti kandidátům, `_normalizuj` |
| priorita „hodně jazyků" | počítala jazyky do složky `prostredi` | zdvojnásobuje složku `jazyk` (`PRIORITY`) |
| jazyk ve filtru | tvrdý filtr vždy | tvrdý jen na `jazyk_povinny` |
| obory bez JPZ | podíl jako přijato/posouzeno | podíl **vážený roky** (`ROKY_JPZ`) |
| vzorek na kartě | celkový vzorek nabídky | vzorek v okolí ±`OKNO_PASMA` |
| `fit` v exportu | zaokrouhlený na 4 des. místa | plná přesnost (rozdíl až 2e-3 bodu skóre) |

Dvě poslední se daly opravit jen v exportu — `bez_jpz` proto nese i hotový
vážený podíl a `fit` ke každému pásmu i jeho počet.

Regresi hlídají testy `test_web_*` v `tests/test_pruvodce.py` (čtou
`index.html` jako text a hlídají, že se na žádnou složku nezapomnělo).
Na shodu **čísel** je tenhle skript — pustí obě implementace na stejných
profilech a porovná skóre, složky i pořadí:

```bash
npm install playwright        # stránka se otevírá z file://, server netřeba
python -m jaknastredni.export_web --db data/jaknastredni.db -o web/data.js
node - <<'EOF' > js.json
import { chromium } from 'playwright';
const profily = [{ trida: 9, oblasti_zajmu: ['it'], zamereni: ['programovani'] }];
const b = await chromium.launch(); const pg = await b.newPage();
await pg.goto('file://' + process.cwd() + '/web/index.html');
await pg.waitForFunction(() => window.JNS !== undefined);
const out = [];
for (const pr of profily) out.push(await pg.evaluate((pr) => {
  Object.assign(window.JNS.stav, { trida: pr.trida, oblasti: pr.oblasti_zajmu || [],
                                   zamereni: pr.zamereni || [] });
  return window.JNS.ohodnot().map(x => ({ izo: x.n.izo, kkov: x.n.kod_kkov,
                                          skore: +x.skore.toFixed(4) }));
}, pr));
await b.close(); console.log(JSON.stringify(out));
EOF
```

Výsledek se porovná s `pruvodce.ohodnot(Profil.z_json(profil), nabidky)`.
Rozdíl ve skóre nad 0,02 bodu je chyba v portu, ne zaokrouhlení.

## Další kroky

1. **Plnohodnotné webové UI.** Prototyp je jednostránkový a ukazuje všechny
   otázky naráz; ostrá verze by měla mít průchod po krocích s možností
   kdykoli přeskočit a sdílitelný odkaz na výsledek. `--json` výstup CLI je
   přesně to, co takový frontend potřebuje.
2. **Srovnávací pohled** pro 2–3 vybrané školy vedle sebe (tabulka let,
   hranice, maturity) — to, co si uživatel stejně dělá ručně v Excelu.
3. **Dojezd MHD** (GTFS) — největší jednotlivé zlepšení kvality výsledku.
4. **Závěry inspekčních zpráv** — extrakce sekcí ze ČŠI PDF pro školy
   v užším výběru, ne pro všech 214 organizací.
5. **Kalibrace na skutečnosti.** Až budou známé výsledky 2027, porovnat
   odhad šance s tím, jak to dopadlo, a případně upravit `σ`.
6. **Naměřená šance po zaměřeních.** Rozdělení nabídky je hotové (viz
   „Nabídka = škola × obor × zaměření"), ale `prijimacky_pasmo` zůstává
   sdílené přes celý KKOV — soubory uchazečů zaměření neuvádějí. Kdyby je
   CERMAT začal zveřejňovat, byla by to poslední složka, která zaměření
   nerozlišuje.
