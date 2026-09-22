"""Sestaví/aktualizuje SQLite databázi ze všech syrových dat lokálně uložených
v `data/raw/` — druhá polovina dvoukrokového procesu (fetch → build).

Na rozdíl od `jaknastredni.fetch_all` (a od jednotlivých importérů spuštěných
samostatně) tenhle skript **neprovádí žádné síťové požadavky** — jen prohledá
`data/raw/` a naimportuje, co tam najde. Právě proto, že syrová data se
commitují do repozitáře (viz README), ale výsledná databáze ne, je tohle
skript, který má smysl spouštět v CI/CD při nasazení: `git clone` + tenhle
skript => hotová databáze, bez závislosti na dostupnosti/rychlosti/rate
limitům zdrojových webů.

Použití:
    python -m jaknastredni.build_db --db data/jaknastredni.db
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from . import atlas, cermat_jpz, cermat_jpz_old, cermat_mz, csi, db, infoabsolvent, msmt

log = logging.getLogger(__name__)

_MZ_RE = re.compile(r"^MZ(\d{4})(j|jap)_SC_skolobory\.xlsx$")
_JPZ_STARY_RE = re.compile(r"^JPZ(\d{4})_skoly-skolobory_vysledky\.xlsx$")
_JPZ_NOVY_RE = re.compile(r"^PZ(\d{4})_kolo(\d)_skolobory_(vysledky|prihlasky|kapacity)\.xlsx$")


def _nejnovejsi(cesty) -> Path | None:
    cesty = list(cesty)
    return max(cesty, key=lambda p: p.name) if cesty else None


def _build_msmt(conn, raw_dir: Path) -> None:
    path = _nejnovejsi((raw_dir / "msmt").glob("*.jsonld"))
    if path is None:
        log.warning("MŠMT: v %s/msmt nic nenalezeno, přeskočeno", raw_dir)
        return
    data = msmt.load(path)
    log.info("MŠMT (%s): %s", path.name, msmt.import_data(conn, data, soubor=path))


def _build_maturita(conn, raw_dir: Path) -> None:
    for path in sorted((raw_dir / "cermat").glob("MZ*_SC_skolobory.xlsx")):
        m = _MZ_RE.match(path.name)
        if not m:
            continue
        rok, obdobi = int(m.group(1)), m.group(2)
        rows = list(cermat_mz.parse(path, obdobi))
        log.info("MZ%s%s: %s", rok, obdobi, cermat_mz.import_rows(conn, rows, soubor=path, rok=rok, obdobi=obdobi))


def _build_jpz_stary(conn, raw_dir: Path) -> None:
    for path in sorted((raw_dir / "cermat").glob("JPZ*_skoly-skolobory_vysledky.xlsx")):
        m = _JPZ_STARY_RE.match(path.name)
        if not m:
            continue
        rok = int(m.group(1))
        rows = list(cermat_jpz_old.parse(path, rok))
        log.info("JPZ%s: %s", rok, cermat_jpz_old.import_rows(conn, rows, soubor=path, rok=rok))


def _build_jpz_novy(conn, raw_dir: Path) -> None:
    combos: dict[tuple[int, int], dict[str, Path]] = {}
    for path in (raw_dir / "cermat").glob("PZ*_kolo*_skolobory_*.xlsx"):
        m = _JPZ_NOVY_RE.match(path.name)
        if not m:
            continue
        rok, kolo, soubor = int(m.group(1)), int(m.group(2)), m.group(3)
        combos.setdefault((rok, kolo), {})[soubor] = path
    for (rok, kolo), paths in sorted(combos.items()):
        if "vysledky" not in paths:
            log.warning("PZ%s kolo %d: chybí vysledky.xlsx, přeskočeno", rok, kolo)
            continue
        rows = list(cermat_jpz.parse(paths))
        stats = cermat_jpz.import_rows(conn, rows, soubor=paths["vysledky"], rok=rok, kolo=kolo)
        log.info("PZ%s kolo %d: %s (soubory: %s)", rok, kolo, stats, sorted(paths))


def _build_csi(conn, raw_dir: Path) -> None:
    path = _nejnovejsi((raw_dir / "csi").glob("inspekcni_zpravy-*.csv"))
    if path is None:
        log.warning("ČŠI: v %s/csi nic nenalezeno, přeskočeno", raw_dir)
        return
    parse_stats: dict[str, int] = {}
    rows = list(csi.parse(path, stats=parse_stats))
    stats = csi.import_rows(conn, rows, soubor=path, preskoceno=parse_stats.get("preskoceno"))
    log.info("ČŠI (%s): %s", path.name, stats)


def _build_infoabsolvent(conn, raw_dir: Path) -> None:
    log.info("infoabsolvent: %s", infoabsolvent.import_from_local(conn, raw_dir / "infoabsolvent"))


def _build_atlas(conn, raw_dir: Path) -> None:
    log.info("atlas: %s", atlas.import_from_local(conn, raw_dir / "atlas"))


def build_all(conn, raw_dir: Path) -> None:
    _build_msmt(conn, raw_dir)
    _build_maturita(conn, raw_dir)
    _build_jpz_stary(conn, raw_dir)
    _build_jpz_novy(conn, raw_dir)
    _build_csi(conn, raw_dir)
    _build_infoabsolvent(conn, raw_dir)
    _build_atlas(conn, raw_dir)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Sestaví/aktualizuje databázi ze souborů v data/raw/ (offline, bez sítě)."
    )
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"), help="kořen se syrovými daty")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    conn = db.connect(args.db)
    build_all(conn, args.raw_dir)
    log.info("Build dokončen (%s).", args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
