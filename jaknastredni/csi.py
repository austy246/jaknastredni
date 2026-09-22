"""Importér seznamu inspekčních zpráv České školní inspekce (ČŠI).

Zdroj: CSV dataset „Inspekční zprávy" (id 69) na opendata.csicr.cz,
`https://opendata.csicr.cz/Transformation/Download/137`. Podrobný průzkum:
docs/research/csi.md.

Ověřeno stažením 22. 9. 2026 (viz i docs/research/csi.md, doplněk na konci):
- Encoding: čisté **UTF-8** (ne windows-1250, jak bývá u některých českých
  open-data CSV zvykem) — potvrzeno `file(1)` i úspěšným dekódováním.
- Formát: standardní RFC4180 CSV, `,` jako oddělovač, všechna pole v
  uvozovkách, uvozovky uvnitř pole zdvojené (`""`), `\r\n` konce řádků.
- Hlavička přesně: `REDIZO,Jmeno,DatumOd,DatumDo,LinkIZ,PortalLink` (žádné
  odchylky ve velikosti písmen ani mezerách).
- **14 912 datových řádků** (+ 1 hlavička = 14 913 řádků souboru), stav k
  22. 9. 2026. REDIZO je ve všech řádcích přesně 9číselný text bez mezer,
  žádné prázdné REDIZO/Jmeno/DatumOd/DatumDo/LinkIZ/PortalLink. Datumy jsou
  ISO 8601 s časem, např. `2017-10-03T00:00:00.0000000` — stačí prvních 10
  znaků pro `YYYY-MM-DD`. Klíč `(REDIZO, DatumOd)` je v celém souboru
  jedinečný (0 kolizí).
- **Zvláštnost**: pár starých/archivních záznamů má `DatumDo` daleko v
  budoucnosti (`2203-05-22`, `3000-01-01`) — technický artefakt ČŠI pro
  „stále platné"/archivní záznamy, ne skutečné datum. Politika tohoto
  importéru: rok `DatumDo >= 2100` se ukládá jako `NULL` (viz `_datum`),
  protože nejde o použitelné datum konce inspekce; `DatumOd` je vždy validní
  v pozorovaných datech, ale kdyby validace selhala, řádek se přeskočí a
  započítá do `stats["preskoceno"]` (je součástí primárního klíče, takže bez
  něj řádek nejde uložit smysluplně).
- Dataset nemá kraj ani typ školy → filtr na Prahu/SŠ jde jen přes JOIN s
  `organizace` (nebo `--jen-praha` při importu, stejná konvence jako CERMAT).
  REDIZO v datasetu může odkazovat na školy mimo Prahu i na zaniklé/historické
  školy, které v místním MŠMT snapshotu vůbec nejsou — proto `inspekce` nemá
  cizí klíč na `organizace(redizo)`.
- PDF zprávy (`LinkIZ`) se v tomto importéru **nestahují** — to je záměrně
  mimo rozsah (viz README, bod 3), jde jen o import seznamu/metadat.

Použití:
    python -m jaknastredni.csi --db data/jaknastredni.db
    python -m jaknastredni.csi --db data/jaknastredni.db --jen-praha
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
import re
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from . import db

log = logging.getLogger(__name__)

URL = "https://opendata.csicr.cz/Transformation/Download/137"
USER_AGENT = "jaknastredni/0.1 (+https://github.com/austy246/jaknastredni)"

# Rok >= tato hodnota v DatumDo je technický artefakt ("stále platné"/archivní
# záznamy typu 2203-05-22 nebo 3000-01-01), ne skutečné datum - viz docstring.
_SENTINEL_ROK = 2100

_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

Row = dict[str, Any]


# --------------------------------------------------------------------------- stažení

def download(raw_dir: Path = Path("data/raw/csi"), timeout: int = 120) -> Path:
    """Stáhne CSV dataset inspekčních zpráv a uloží ho do raw_dir. Vrací cestu."""
    import requests  # lokální import, ať jdou testy bez sítě

    log.info("Stahuji %s", URL)
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    raw_dir.mkdir(parents=True, exist_ok=True)
    datum = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = raw_dir / f"inspekcni_zpravy-{datum}.csv"
    path.write_bytes(resp.content)
    log.info("Uloženo %s (%d B)", path, len(resp.content))
    return path


# --------------------------------------------------------------------------- parsování

def _redizo(v: str) -> str | None:
    """REDIZO má 9 číslic. Vrátí None, pokud hodnota po očištění není číselná."""
    v = (v or "").strip()
    if not v:
        return None
    v = v.zfill(9)
    return v if v.isdigit() and len(v) == 9 else None


def _datum(v: str, *, drop_sentinel: bool = True) -> str | None:
    """Ořízne ISO datetime na YYYY-MM-DD. Vrátí None, pokud je hodnota prázdná,
    nevalidní, nebo (u drop_sentinel) rok je technický artefakt >= _SENTINEL_ROK.
    """
    v = (v or "").strip()
    if not v:
        return None
    iso = v[:10]
    if not _DATUM_RE.match(iso):
        return None
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return None
    if drop_sentinel and d.year >= _SENTINEL_ROK:
        return None
    return iso


def parse(path_or_text: Path | str, *, stats: dict[str, int] | None = None) -> Iterator[Row]:
    """Naparsuje CSV inspekčních zpráv. Vrací řádky s normalizovaným REDIZO a
    daty; řádky s chybějícím/nevalidním REDIZO, DatumOd nebo Jmeno se
    přeskakují (REDIZO a DatumOd jsou součástí primárního klíče, bez nich
    nejde řádek smysluplně uložit). Když je předán `stats`, naplní se do něj
    `celkem` (počet datových řádků v CSV) a `preskoceno`.
    """
    if isinstance(path_or_text, Path):
        text = path_or_text.read_text(encoding="utf-8")
    else:
        text = path_or_text
    reader = csv.DictReader(io.StringIO(text))
    expected = {"REDIZO", "Jmeno", "DatumOd", "DatumDo", "LinkIZ", "PortalLink"}
    missing = expected - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV chybí očekávané sloupce: {missing}")

    celkem = 0
    preskoceno = 0
    for raw in reader:
        celkem += 1
        redizo = _redizo(raw.get("REDIZO", ""))
        datum_od = _datum(raw.get("DatumOd", ""), drop_sentinel=False)
        nazev = (raw.get("Jmeno") or "").strip()
        if redizo is None or datum_od is None or not nazev:
            preskoceno += 1
            continue
        yield {
            "redizo": redizo,
            "datum_od": datum_od,
            "nazev": nazev,
            "datum_do": _datum(raw.get("DatumDo", "")),
            "pdf_url": (raw.get("LinkIZ") or "").strip() or None,
            "portal_url": (raw.get("PortalLink") or "").strip() or None,
        }
    if stats is not None:
        stats["celkem"] = celkem
        stats["preskoceno"] = preskoceno


# --------------------------------------------------------------------------- import

def import_rows(conn: sqlite3.Connection, rows: Iterable[Row], *, url: str | None = None,
                 soubor: Path | None = None, preskoceno: int | None = None,
                 jen_redizo: set[str] | None = None) -> dict[str, int]:
    """Vloží řádky do tabulky inspekce (INSERT OR REPLACE, import je idempotentní).
    `preskoceno` (počet řádků vyřazených v `parse()` kvůli chybějícím/nevalidním
    hodnotám) se jen zaznamená do poznámky v `import_run`, na vkládaná data nemá vliv.
    """
    rows = list(rows)
    if jen_redizo is not None:
        rows = [r for r in rows if r["redizo"] in jen_redizo]
    cols = ["redizo", "datum_od", "nazev", "datum_do", "pdf_url", "portal_url"]
    sql = f"INSERT OR REPLACE INTO inspekce ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with conn:
        if rows:
            conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        sha = hashlib.sha256(soubor.read_bytes()).hexdigest() if soubor and soubor.exists() else None
        conn.execute(
            "INSERT INTO import_run (zdroj, url, soubor, sha256, datum_vystupu, stazeno_utc, pocet_zaznamu, poznamka)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("csi", url, str(soubor) if soubor else None, sha, None,
             datetime.now(timezone.utc).isoformat(timespec="seconds"), len(rows),
             f"přeskočeno {preskoceno} řádků (chybějící/nevalidní REDIZO, DatumOd nebo Jmeno)" if preskoceno else None),
        )
    return {"inspekce": len(rows)}


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import seznamu inspekčních zpráv ČŠI do SQLite.")
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/csi"), help="kam ukládat stažený soubor")
    p.add_argument("--jen-praha", action="store_true",
                    help="importovat jen REDIZO přítomná v tabulce organizace")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    conn = db.connect(args.db)
    jen_redizo = None
    if args.jen_praha:
        jen_redizo = {r[0] for r in conn.execute("SELECT redizo FROM organizace")}

    path = download(args.raw_dir)
    parse_stats: dict[str, int] = {}
    all_rows = list(parse(path, stats=parse_stats))
    log.info("Naparsováno %d řádků, přeskočeno %d", parse_stats.get("celkem", 0), parse_stats.get("preskoceno", 0))
    stats = import_rows(conn, all_rows, url=URL, soubor=path, preskoceno=parse_stats.get("preskoceno"),
                         jen_redizo=jen_redizo)
    log.info("ČŠI inspekce: %s", stats)

    n = conn.execute("SELECT COUNT(*) FROM inspekce").fetchone()[0]
    log.info("Import hotov, tabulka inspekce má celkem %d řádků", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
