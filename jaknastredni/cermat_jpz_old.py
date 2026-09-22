"""Importér agregovaných výsledků JPZ (jednotná přijímací zkouška) CERMAT,
"starý formát" 2017–2023, po školách a oborových skupinách.

Zdroj: `/files/files/JPZ/agregovana_data_skoly/JPZ{rok}_skoly-skolobory_vysledky.xlsx`
na data.cermat.cz, jeden soubor na rok (řádný i náhradní termín souhrnně,
žádné samostatné "kolo"). Podrobný průzkum: docs/research/cermat.md, oddíly
3, 5, 9, 13.

Formát je mnohem hrubší než maturita nebo JPZ 2024+: žádné IZO, obor jen jako
hrubá "oborová skupina" (GY8, GY4, LYC, 4LETÉ OBORY, ...), metrika úspěšnosti
je průměrné percentilové umístění (0-100 percentil) a jeho směrodatná
odchylka, ne bodové skóre. List míchá tři typy řádků (celorepublikové součty,
krajské součty, jednotlivé školy) bez jakéhokoliv sloupce typu "TŘÍDĚNÍ" —
školní řádky se poznají jen podle toho, že první sloupec je číselné REDIZO.

Hlavička je stabilní napříč roky 2017-2023 co do jmen a pořadí fixních
sloupců (REDIZO.. / OBOROVÁ SKUPINA / ROČNÍK / .. / ZŘIZOVATEL) a datových
bloků ČJ/MA (PŘIHLÁŠENI, KONALI, [absence], PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ,
SMĚRODATNÁ ODCHYLKA (PERCENTIL. UMÍSTĚNÍ)) — jediný rozdíl je počet a
pojmenování "absenčních" sloupců mezi KONALI a PRŮMĚRNÉ PERCENTILOVÉ
UMÍSTĚNÍ: jeden sloupec NEKONALI (2017,2018,2019,2021,2022,2023) vs. tři
sloupce OMLUVENI/NEOMLUVENI/VYLOUČENI (2020). Tyto sloupce se do datového
modelu neukládají (schéma je nepotřebuje), takže se mapuje jen podle jména a
ignoruje se, co mezi KONALI a PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ přesně je.

Použití:
    python -m jaknastredni.cermat_jpz_old --db data/jaknastredni.db --roky 2017-2023
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from . import db

log = logging.getLogger(__name__)

BASE_URL = "https://data.cermat.cz/files/files/JPZ/agregovana_data_skoly/JPZ{rok}_skoly-skolobory_vysledky.xlsx"
USER_AGENT = "jaknastredni/0.1 (+https://github.com/austy246/jaknastredni)"

# Jména sloupců, podle kterých se hledají indexy v hlavičce (řádek 2, index 1
# při 0-based iteraci od min_row=2). "PŘIHLÁŠENI", "KONALI", "PRŮMĚRNÉ
# PERCENTILOVÁ UMÍSTĚNÍ" a "SMĚRODATNÁ ODCHYLKA (...)" se v hlavičce
# vyskytují přesně dvakrát: poprvé v bloku ČESKÝ JAZYK, podruhé v bloku
# MATEMATIKA (viz cermat.md, oddíl 13).
_SKUPINA_COL = "OBOROVÁ SKUPINA"
_ROCNIK_COL = "ROČNÍK"
_PRIHLASENI_COL = "PŘIHLÁŠENI"
_KONALI_COL = "KONALI"
_PERCENTIL_COL = "PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ"
_ODCHYLKA_COL = "SMĚRODATNÁ ODCHYLKA (PERCENTIL. UMÍSTĚNÍ)"

Row = dict[str, Any]


# --------------------------------------------------------------------------- stažení

def download(rok: int, raw_dir: Path = Path("data/raw/cermat"), timeout: int = 120) -> Path:
    """Stáhne soubor pro daný rok a uloží ho do raw_dir. Vrací cestu."""
    import requests  # lokální import, ať jdou testy bez sítě

    url = BASE_URL.format(rok=rok)
    log.info("Stahuji %s", url)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"JPZ{rok}_skoly-skolobory_vysledky.xlsx"
    path.write_bytes(resp.content)
    log.info("Uloženo %s (%d B)", path, len(resp.content))
    return path


# --------------------------------------------------------------------------- parsování

def _is_numeric_redizo(v: Any) -> bool:
    """Školní řádky mají v 1. sloupci číselné REDIZO; krajské/celkové řádky
    tam mají text (název kraje, "CELKEM" apod.) nebo None."""
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    s = str(v).strip()
    return bool(re.fullmatch(r"\d+(\.0)?", s))


def _redizo(v: Any) -> str:
    return str(int(float(v))).zfill(9)


def _num(v: Any) -> float | int | None:
    """CERMAT používá '-' jako hodnotu pro nulu přihlášených apod."""
    if v is None or v == "" or v == "-":
        return None
    return v


def _find_pair(header: list, name: str) -> tuple[int, int]:
    """Vrátí (index v bloku ČJ, index v bloku MA) pro sloupec daného jména,
    který se v hlavičce vyskytuje přesně dvakrát."""
    idxs = [i for i, h in enumerate(header) if h == name]
    if len(idxs) != 2:
        raise ValueError(f"sloupec {name!r} se v hlavičce vyskytuje {len(idxs)}x, čekány 2 výskyty")
    return idxs[0], idxs[1]


def parse(path: Path, rok: int | None = None) -> Iterator[Row]:
    """Naparsuje soubor JPZ{rok}_skoly-skolobory_vysledky.xlsx, vrátí řádky za
    jednotlivé školy (1. sloupec = číselné REDIZO), jeden řádek na
    (škola, oborová skupina, ročník)."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        # hlavní list = jediný list, který není číselník "ciselniky"; název
        # hlavního listu se mezi roky mění (JPZ2017_red, JPZ2021, List1, ...)
        main_sheets = [s for s in wb.sheetnames if s.lower() != "ciselniky"]
        if len(main_sheets) != 1:
            raise ValueError(f"{path}: čekán 1 hlavní list (mimo 'ciselniky'), nalezeno {main_sheets}")
        ws = wb[main_sheets[0]]

        # hlavička je vždy na 2. řádku, 1. řádek je sloučený titulek (viz cermat.md, oddíl 5)
        rows_iter = ws.iter_rows(min_row=2, values_only=True)
        header = list(next(rows_iter))
        if _SKUPINA_COL not in header or _ROCNIK_COL not in header:
            raise ValueError(f"{path}: na řádku 2 chybí {_SKUPINA_COL!r}/{_ROCNIK_COL!r}, neočekávaný formát")

        skupina_idx = header.index(_SKUPINA_COL)
        rocnik_idx = header.index(_ROCNIK_COL)
        prihlaseni_cj_idx, prihlaseni_ma_idx = _find_pair(header, _PRIHLASENI_COL)
        konali_cj_idx, konali_ma_idx = _find_pair(header, _KONALI_COL)
        percentil_cj_idx, percentil_ma_idx = _find_pair(header, _PERCENTIL_COL)
        odchylka_cj_idx, odchylka_ma_idx = _find_pair(header, _ODCHYLKA_COL)

        for row in rows_iter:
            if not _is_numeric_redizo(row[0]):
                continue
            yield {
                "redizo": _redizo(row[0]),
                "skupina_oboru": row[skupina_idx],
                "rocnik": int(row[rocnik_idx]),
                "rok": rok,
                "prihlaseni_cj": _num(row[prihlaseni_cj_idx]),
                "konali_cj": _num(row[konali_cj_idx]),
                "prumerny_percentil_cj": _num(row[percentil_cj_idx]),
                "smerodatna_odchylka_cj": _num(row[odchylka_cj_idx]),
                "prihlaseni_ma": _num(row[prihlaseni_ma_idx]),
                "konali_ma": _num(row[konali_ma_idx]),
                "prumerny_percentil_ma": _num(row[percentil_ma_idx]),
                "smerodatna_odchylka_ma": _num(row[odchylka_ma_idx]),
            }
    finally:
        wb.close()


# --------------------------------------------------------------------------- import

def import_rows(conn: sqlite3.Connection, rows: Iterable[Row], *, url: str | None = None,
                 soubor: Path | None = None, rok: int | None = None,
                 jen_redizo: set[str] | None = None) -> dict[str, int]:
    """Vloží řádky do tabulky jpz_skupina (INSERT OR REPLACE, import je idempotentní)."""
    rows = list(rows)
    if jen_redizo is not None:
        rows = [r for r in rows if r["redizo"] in jen_redizo]
    cols = ["redizo", "skupina_oboru", "rocnik", "rok", "prihlaseni_cj", "konali_cj",
            "prumerny_percentil_cj", "smerodatna_odchylka_cj", "prihlaseni_ma", "konali_ma",
            "prumerny_percentil_ma", "smerodatna_odchylka_ma"]
    sql = f"INSERT OR REPLACE INTO jpz_skupina ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with conn:
        if rows:
            conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        sha = hashlib.sha256(soubor.read_bytes()).hexdigest() if soubor and soubor.exists() else None
        conn.execute(
            "INSERT INTO import_run (zdroj, url, soubor, sha256, datum_vystupu, stazeno_utc, pocet_zaznamu, poznamka)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("cermat_jpz_old", url, str(soubor) if soubor else None, sha,
             str(rok) if rok else None, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             len(rows), None),
        )
    return {"jpz_skupina": len(rows)}


# --------------------------------------------------------------------------- CLI

def _parse_roky(spec: str) -> list[int]:
    m = re.fullmatch(r"(\d{4})-(\d{4})", spec)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    return [int(x) for x in spec.split(",")]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import agregovaných výsledků JPZ CERMAT (starý formát 2017-2023) do SQLite.")
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--roky", default="2017-2023", help="rok nebo rozsah, např. 2017-2023")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/cermat"), help="kam ukládat stažené soubory")
    p.add_argument("--jen-praha", action="store_true",
                    help="importovat jen REDIZO přítomná v tabulce organizace")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    conn = db.connect(args.db)
    jen_redizo = None
    if args.jen_praha:
        jen_redizo = {r[0] for r in conn.execute("SELECT redizo FROM organizace")}

    for rok in _parse_roky(args.roky):
        url = BASE_URL.format(rok=rok)
        path = download(rok, args.raw_dir)
        rows = list(parse(path, rok))
        stats = import_rows(conn, rows, url=url, soubor=path, rok=rok, jen_redizo=jen_redizo)
        log.info("JPZ%s: %s", rok, stats)

    n = conn.execute("SELECT COUNT(*) FROM jpz_skupina").fetchone()[0]
    log.info("Import hotov, tabulka jpz_skupina má celkem %d řádků", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
