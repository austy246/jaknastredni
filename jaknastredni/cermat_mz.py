"""Importér agregovaných maturitních výsledků CERMAT (MZ, po školách).

Zdroj: `/files/files/MZ/agregovana_data_skoly/MZ{rok}{obdobi}_SC_skolobory.xlsx`
na data.cermat.cz, roky 2015–2026, období 'j' (jarní) nebo 'jap' (jaro+podzim).
Podrobný průzkum: docs/research/cermat.md, oddíly 4, 7, 10.

Formát je napříč roky stabilní: hlavička je na 2. řádku listu (1. řádek je
sloučený titulek), řádky se filtrují podle sloupce TŘÍDĚNÍ (resp.
entita_id_row) na hodnoty 'redizo' (škola celkem) a 'redizo_smo16' (škola ×
skupina oborů). Za fixními sloupci (TŘÍDĚNÍ..KRAJ - NÁZEV) následují bloky
předmětů ve stálém pořadí: SPOLEČNÁ ČÁST MZ CELKEM, ČESKÝ JAZYK, MATEMATIKA,
ANGLIČTINA, NĚMČINA, RUŠTINA, FRANCOUZŠTINA, ŠPANĚLŠTINA. Sloupce se mapují
podle názvu v hlavičce, ne podle pozice, protože starší soubory (2015–2017
"j") nemají dva úvodní ID sloupce (entita_id_row, id_row) a novější "jap"
soubory je mají pojmenované až od roku 2025 (dřív jen druhý, "entita").

Použití:
    python -m jaknastredni.cermat_mz --db data/jaknastredni.db --roky 2015-2026 --obdobi jap
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

BASE_URL = "https://data.cermat.cz/files/files/MZ/agregovana_data_skoly/MZ{rok}{obdobi}_SC_skolobory.xlsx"
USER_AGENT = "jaknastredni/0.1 (+https://github.com/austy246/jaknastredni)"

# Bloky předmětů v pevném, napříč roky 2015-2026 ověřeném pořadí (viz
# docs/research/cermat.md, oddíl 9). "celkem" blok nemá skór/percentil
# (přihlášení k celé MZ), ostatní ano; volitelné předměty (vše kromě ČJ)
# navíc mají "podíl volby předmětu".
_METRIKY_CELKEM = ["prihlaseni", "konali", "uspeli", "neuspeli", "nekonali",
                    "podil_uspesnych", "cista_neuspesnost"]
# za "cista_neuspesnost" v CELKEM bloku následují ještě "hrubá neúspěšnost" a
# "neúčast" - do datového modelu se neukládají, proto se přeskočí (viz níže).
_METRIKY_PREDMET = ["prihlaseni", "konali", "uspeli", "neuspeli", "nekonali",
                     "prumerny_skor", "smerodatna_odchylka", "prumerny_percentil",
                     "podil_uspesnych", "cista_neuspesnost"]

BLOKY = [
    ("CELKEM", 9, _METRIKY_CELKEM, False),
    ("CJ", 10, _METRIKY_PREDMET, False),
    ("MA", 11, _METRIKY_PREDMET, True),
    ("AJ", 11, _METRIKY_PREDMET, True),
    ("NJ", 11, _METRIKY_PREDMET, True),
    ("RJ", 11, _METRIKY_PREDMET, True),
    ("FJ", 11, _METRIKY_PREDMET, True),
    ("SJ", 11, _METRIKY_PREDMET, True),
]

RADKY_SKOLA = ("redizo", "redizo_smo16")

Row = dict[str, Any]


# --------------------------------------------------------------------------- stažení

def download(rok: int, obdobi: str, raw_dir: Path = Path("data/raw/cermat"), timeout: int = 120) -> Path:
    """Stáhne soubor pro daný rok a období a uloží ho do raw_dir. Vrací cestu."""
    import requests  # lokální import, ať jdou testy bez sítě

    url = BASE_URL.format(rok=rok, obdobi=obdobi)
    log.info("Stahuji %s", url)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"MZ{rok}{obdobi}_SC_skolobory.xlsx"
    path.write_bytes(resp.content)
    log.info("Uloženo %s (%d B)", path, len(resp.content))
    return path


# --------------------------------------------------------------------------- parsování

def _redizo(v: Any) -> str:
    """REDIZO má 9 číslic; v souborech přichází občas jako číslo, občas jako text."""
    if isinstance(v, float):
        v = int(v)
    return str(v).strip().zfill(9)


def _num(v: Any) -> float | int | None:
    """CERMAT používá '-' jako hodnotu pro předměty bez jediného přihlášeného."""
    if v is None or v == "" or v == "-":
        return None
    return v


def parse(path: Path, obdobi: str) -> Iterator[Row]:
    """Naparsuje soubor MZ{rok}{obdobi}_SC_skolobory.xlsx, vrátí řádky za jednotlivé
    školy (TŘÍDĚNÍ IN ('redizo', 'redizo_smo16')), jeden řádek na (škola, smo16, předmět).
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet_name = next(s for s in wb.sheetnames if s != "vysvetlivky")
        ws = wb[sheet_name]
        # hlavička je vždy na 2. řádku, 1. řádek je sloučený titulek (viz cermat.md, oddíl 7)
        rows_iter = ws.iter_rows(min_row=2, values_only=True)
        header = list(next(rows_iter))
        if "TŘÍDĚNÍ" not in header:
            raise ValueError(f"{path}: na řádku 2 chybí sloupec TŘÍDĚNÍ, neočekávaný formát")

        tridebni_idx = header.index("TŘÍDĚNÍ")
        rok_idx = header.index("ROK")
        redizo_idx = header.index("REDIZO")
        smo16_idx = header.index("SMO16")
        kraj_nazev_idx = header.index("KRAJ - NÁZEV")

        offsets = []  # (predmet, start, metriky, ma_volbu)
        start = kraj_nazev_idx + 1
        for predmet, size, metriky, ma_volbu in BLOKY:
            offsets.append((predmet, start, metriky, ma_volbu))
            start += size
        if start != len(header):
            raise ValueError(f"{path}: neočekávaný počet sloupců ({len(header)}, čekáno {start})")

        for row in rows_iter:
            if row[tridebni_idx] not in RADKY_SKOLA:
                continue
            redizo = _redizo(row[redizo_idx])
            rok = int(row[rok_idx])
            smo16 = row[smo16_idx]
            for predmet, base, metriky, ma_volbu in offsets:
                vals = row[base:base + len(metriky) + (1 if ma_volbu else 0)]
                data = dict(zip(metriky, vals[:len(metriky)]))
                yield {
                    "redizo": redizo,
                    "rok": rok,
                    "obdobi": obdobi,
                    "smo16": smo16,
                    "predmet": predmet,
                    "prihlaseni": _num(data.get("prihlaseni")),
                    "konali": _num(data.get("konali")),
                    "uspeli": _num(data.get("uspeli")),
                    "neuspeli": _num(data.get("neuspeli")),
                    "nekonali": _num(data.get("nekonali")),
                    "prumerny_skor": _num(data.get("prumerny_skor")),
                    "smerodatna_odchylka": _num(data.get("smerodatna_odchylka")),
                    "prumerny_percentil": _num(data.get("prumerny_percentil")),
                    "podil_uspesnych": _num(data.get("podil_uspesnych")),
                    "cista_neuspesnost": _num(data.get("cista_neuspesnost")),
                    "podil_volby_predmetu": _num(vals[len(metriky)]) if ma_volbu else None,
                }
    finally:
        wb.close()


# --------------------------------------------------------------------------- import

def import_rows(conn: sqlite3.Connection, rows: Iterable[Row], *, url: str | None = None,
                 soubor: Path | None = None, rok: int | None = None, obdobi: str | None = None,
                 jen_redizo: set[str] | None = None) -> dict[str, int]:
    """Vloží řádky do tabulky maturita (INSERT OR REPLACE, import je idempotentní)."""
    rows = list(rows)
    if jen_redizo is not None:
        rows = [r for r in rows if r["redizo"] in jen_redizo]
    cols = ["redizo", "rok", "obdobi", "smo16", "predmet", "prihlaseni", "konali", "uspeli",
            "neuspeli", "nekonali", "prumerny_skor", "smerodatna_odchylka", "prumerny_percentil",
            "podil_uspesnych", "cista_neuspesnost", "podil_volby_predmetu"]
    sql = f"INSERT OR REPLACE INTO maturita ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with conn:
        if rows:
            conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        sha = hashlib.sha256(soubor.read_bytes()).hexdigest() if soubor and soubor.exists() else None
        conn.execute(
            "INSERT INTO import_run (zdroj, url, soubor, sha256, datum_vystupu, stazeno_utc, pocet_zaznamu, poznamka)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("cermat_mz", url, str(soubor) if soubor else None, sha,
             str(rok) if rok else None, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             len(rows), obdobi),
        )
    return {"maturita": len(rows)}


# --------------------------------------------------------------------------- CLI

def _parse_roky(spec: str) -> list[int]:
    m = re.fullmatch(r"(\d{4})-(\d{4})", spec)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    return [int(x) for x in spec.split(",")]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import agregovaných maturitních výsledků CERMAT do SQLite.")
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--roky", default=str(datetime.now().year), help="rok nebo rozsah, např. 2015-2026")
    p.add_argument("--obdobi", default="jap", choices=["j", "jap"], help="jarní (j) nebo jaro+podzim (jap)")
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
        url = BASE_URL.format(rok=rok, obdobi=args.obdobi)
        path = download(rok, args.obdobi, args.raw_dir)
        rows = list(parse(path, args.obdobi))
        stats = import_rows(conn, rows, url=url, soubor=path, rok=rok, obdobi=args.obdobi, jen_redizo=jen_redizo)
        log.info("MZ%s%s: %s", rok, args.obdobi, stats)

    n = conn.execute("SELECT COUNT(*) FROM maturita").fetchone()[0]
    log.info("Import hotov, tabulka maturita má celkem %d řádků", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
