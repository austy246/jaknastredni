"""Stáhne syrová data ze všech zdrojů do `data/raw/`, bez zápisu do databáze.

Toto je první polovina dvoukrokového procesu (fetch → build), zavedeného
proto, aby šlo sestavení databáze (`jaknastredni.build_db`) spouštět čistě
offline v CI/CD — stažená surová data se commitují do repozitáře (viz
README, sekce „Rozhodnutí o vývoji a ukládání dat"), samotná databáze ne.

Použití:
    python -m jaknastredni.fetch_all
    python -m jaknastredni.fetch_all --raw-dir data/raw -v

Roky pro CERMAT maturitu a JPZ nový formát jdou od pevného počátku (2015,
resp. 2024) do aktuálního roku (nebo `--rok-do`); JPZ starý formát má pevný
rozsah 2017–2023 (formát se v roce 2024 změnil, nové soubory v něm už
nevychází). Chybějící/ještě nepublikovaný soubor (např. 2. kolo přijímaček
běžícího ročníku) se přeskočí s varováním, nepřeruší zbytek stahování.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from . import (atlas, cermat_jpz, cermat_jpz_old, cermat_mz, cermat_uchazeci, csi,
               infoabsolvent, msmt)

log = logging.getLogger(__name__)

ROK_MATURITA_OD = 2015
ROK_JPZ_STARY_OD, ROK_JPZ_STARY_DO = 2017, 2023
ROK_JPZ_NOVY_OD = 2024


def _stahni(popis: str, fn, *args, **kwargs) -> None:
    """Spustí jedno stažení; síťovou/HTTP chybu zaloguje a nechá pokračovat dál,
    ať jeden chybějící/ještě nepublikovaný soubor nezastaví celé stahování."""
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        log.warning("%s selhalo: %s", popis, exc)


def fetch_all(raw_dir: Path, *, rok_do: int | None = None, skip_infoabsolvent: bool = False,
              skip_atlas: bool = False) -> None:
    rok_do = rok_do or datetime.now().year
    cermat_dir = raw_dir / "cermat"

    log.info("== MŠMT rejstřík ==")
    _stahni("MŠMT", msmt.download, raw_dir=raw_dir / "msmt")

    log.info("== CERMAT maturita (%d-%d, jarní i jaro+podzim) ==", ROK_MATURITA_OD, rok_do)
    for rok in range(ROK_MATURITA_OD, rok_do + 1):
        for obdobi in ("j", "jap"):
            _stahni(f"MZ{rok}{obdobi}", cermat_mz.download, rok, obdobi, raw_dir=cermat_dir)

    log.info("== CERMAT JPZ starý formát (%d-%d) ==", ROK_JPZ_STARY_OD, ROK_JPZ_STARY_DO)
    for rok in range(ROK_JPZ_STARY_OD, ROK_JPZ_STARY_DO + 1):
        _stahni(f"JPZ{rok}", cermat_jpz_old.download, rok, raw_dir=cermat_dir)

    log.info("== CERMAT JPZ nový formát (%d-%d) ==", ROK_JPZ_NOVY_OD, rok_do)
    for rok in range(ROK_JPZ_NOVY_OD, rok_do + 1):
        for kolo in (1, 2):
            for soubor in ("vysledky", "prihlasky", "kapacity"):
                _stahni(f"PZ{rok} kolo{kolo} {soubor}", cermat_jpz.download, rok, kolo, soubor, raw_dir=cermat_dir)

    log.info("== CERMAT soubory uchazečů (%d-%d, ~16 MB na kolo 1) ==", ROK_JPZ_NOVY_OD, rok_do)
    for rok in range(ROK_JPZ_NOVY_OD, rok_do + 1):
        for kolo in (1, 2):
            _stahni(f"PZ{rok} kolo{kolo} uchazeči", cermat_uchazeci.download, rok, kolo,
                    raw_dir=cermat_dir)

    log.info("== ČŠI inspekce ==")
    _stahni("ČŠI", csi.download, raw_dir=raw_dir / "csi")

    if skip_infoabsolvent:
        log.info("== infoabsolvent.cz přeskočeno (--skip-infoabsolvent) ==")
    else:
        log.info("== infoabsolvent.cz (scraping 1 req/s, ~5 minut) ==")
        session = infoabsolvent.RateLimitedSession()
        infoabsolvent.check_robots_allows(session, ["/Skoly/Seznam/SOS", "/Skoly/Skola/"])
        _stahni("infoabsolvent", infoabsolvent.fetch_raw, session, raw_dir / "infoabsolvent")

    if skip_atlas:
        log.info("== atlasskolstvi.cz přeskočeno (--skip-atlas) ==")
    else:
        log.info("== atlasskolstvi.cz (scraping 1 req/s, ~4 minuty) ==")
        atlas_session = atlas.RateLimitedSession()
        atlas.check_robots_allows(atlas_session, ["/stredni-skoly", "/ss"])
        _stahni("atlas", atlas.fetch_raw, atlas_session, raw_dir / "atlas")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stáhne syrová data ze všech zdrojů do data/raw/ (bez zápisu do DB).")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"), help="kořen pro syrová data")
    p.add_argument("--rok-do", type=int, default=None, help="poslední rok k stažení (výchozí: aktuální rok)")
    p.add_argument("--skip-infoabsolvent", action="store_true",
                    help="přeskočit scraper infoabsolvent.cz (nejpomalejší krok, ~5 minut)")
    p.add_argument("--skip-atlas", action="store_true",
                    help="přeskočit scraper atlasskolstvi.cz (~4 minuty)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    fetch_all(args.raw_dir, rok_do=args.rok_do, skip_infoabsolvent=args.skip_infoabsolvent,
              skip_atlas=args.skip_atlas)
    log.info("Stažení dokončeno, syrová data jsou v %s", args.raw_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
