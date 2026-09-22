# Pokyny pro Claude v tomto repozitáři

- **Vyvíjej přímo ve větvi `main`.** Tenhle projekt zatím nepoužívá feature
  větve ani pull requesty — commituj a pushuj rovnou do `main`, pokud
  vlastník repa výslovně neřekne jinak pro konkrétní úkol.
- Databáze `data/jaknastredni.db` se **neverzuje v gitu** (viz `.gitignore`
  a README, sekce "Rozhodnutí o vývoji a ukládání dat") — je 100%
  reprodukovatelná z `data/raw/` skriptem `python -m jaknastredni.build_db`.
  Syrová stažená data v `data/raw/` se naopak commitují.
- Než začneš pracovat na importéru/datovém modelu, přečti si README.md
  (sekce "Rozhodnutí o vývoji a ukládání dat") a `docs/datovy-model.md`
  (sekce "Zásady") — obsahují ustálené konvence (REDIZO/IZO jako TEXT s
  vedoucími nulami, mapování sloupců XLSX podle jména hlavičky ne podle
  pozice, žádný cizí klíč z CERMAT/ČŠI tabulek na `organizace`/`skola`,
  atd.), ať se nevymýšlí znovu nebo jinak pro každý nový zdroj.
