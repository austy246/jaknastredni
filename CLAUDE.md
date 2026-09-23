# Pokyny pro Claude v tomto repozitáři

- **Vyvíjej přímo ve větvi `main`.** Tenhle projekt zatím nepoužívá feature
  větve ani pull requesty — commituj a pushuj rovnou do `main`, pokud
  vlastník repa výslovně neřekne jinak pro konkrétní úkol.
- **Na konci session musí být vše commitnuté a pushnuté do `main`.**
  Neukončuj session s necommitnutými změnami ani s commity, které jsou jen
  lokální — pushni je, ať v `main` na originu vždy odpovídá aktuální stav
  práce.
- Databáze `data/jaknastredni.db` se **neverzuje v gitu** (viz `.gitignore`
  a README, sekce "Rozhodnutí o vývoji a ukládání dat") — je 100%
  reprodukovatelná z `data/raw/` skriptem `python -m jaknastredni.build_db`.
  Syrová stažená data v `data/raw/` se naopak commitují.
- **Webový prototyp `web/index.html` je ruční port `jaknastredni/pruvodce.py`
  do JavaScriptu a může se od něj rozejít — taky se rozešel.** Konstanty si
  sice čte z `data.js`, takže nemůže mít jiné *váhy*, ale klidně počítá něco
  jiného: chyběla v něm celá složka skóre (jejíž váha zůstala ve jmenovateli),
  `typ` se nenormalizoval, priorita „hodně jazyků" zdvojnásobovala jinou
  složku a obory bez JPZ se nevážily roky. Nic z toho žádný test nechytil,
  protože testy sahaly jen na Python. Když měníš filtr nebo hodnocení, **uprav
  obojí a ověř to proti sobě** skriptem z `docs/pruvodce-ux.md`, oddíl
  „Ověření webu proti Pythonu" (pustí obě implementace na stejných profilech
  a porovná skóre, složky, šanci i pořadí; rozdíl nad 0,001 bodu je chyba
  v portu, ne zaokrouhlení). Testy `test_web_*` v `tests/test_pruvodce.py`
  hlídají jen to, že se na složku nezapomnělo — čísla neověří.
- `web/data.js` se **neverzuje** ze stejného důvodu jako databáze (odvozený
  artefakt). Bez něj je stránka prázdná, takže po `git clone` je potřeba:
  `python -m jaknastredni.build_db && python -m jaknastredni.export_web
  --db data/jaknastredni.db -o web/data.js`. Na Pages to dělá workflow.
- **Když pořadí škol nesedí, nehádej — použij ladicí výpis** dole na stránce
  (`docs/pruvodce-ux.md`, oddíl „Ladicí výpis"). Vydá zadaný profil ve tvaru,
  který spolkne `Profil.z_json`, takže jde `python -m jaknastredni.pruvodce
  --profil profil.json` a musí vyjít totéž pořadí; ukáže i rozpad skóre po
  složkách a syrová data konkrétní školy včetně důvodu, proč vypadla z filtru.
- **Test nepiš proti té konstantě, kterou má hlídat.** `assert typy.count("M")
  == REZERVA_ZVOLENYCH` projde i s rezervou nastavenou na nulu; patří tam
  natvrdo `== 2`. Totéž u násobičů: `assert x == y * KONSTANTA` projde
  i s konstantou 1,0. U nové konstanty v hodnocení si ověř mutací, že ji
  aspoň jeden test opravdu chytí — dva testy v tomhle repu takhle vadné byly.
- Než začneš pracovat na importéru/datovém modelu, přečti si README.md
  (sekce "Rozhodnutí o vývoji a ukládání dat") a `docs/datovy-model.md`
  (sekce "Zásady") — obsahují ustálené konvence (REDIZO/IZO jako TEXT s
  vedoucími nulami, mapování sloupců XLSX podle jména hlavičky ne podle
  pozice, žádný cizí klíč z CERMAT/ČŠI tabulek na `organizace`/`skola`,
  atd.), ať se nevymýšlí znovu nebo jinak pro každý nový zdroj.
