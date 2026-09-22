"""Importér Rejstříku škol a školských zařízení MŠMT (otevřená data, JSON).

Zdroj: dataset NKOD 00022985, krajský snapshot pro Prahu na lkod-ftp.msmt.gov.cz
(denní aktualizace, licence CC0). Podrobný průzkum: docs/research/msmt-rejstrik.md

Použití:
    python -m jaknastredni.msmt --db data/jaknastredni.db            # stáhne a naimportuje Prahu
    python -m jaknastredni.msmt --db data/jaknastredni.db --file x.jsonld   # z lokálního souboru
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import ciselniky, db

log = logging.getLogger(__name__)

# Přímé URL distribuce datasetu "Rejstřík škol a školských zařízení - Hl. m. Praha".
# Ověřeno 2026-09-22. Kdyby přestalo fungovat, aktuální URL vrátí SPARQL dotaz
# na https://data.gov.cz/sparql (viz docs/research/msmt-rejstrik.md).
URL_PRAHA = (
    "https://lkod-ftp.msmt.gov.cz/00022985/"
    "21e5fd4a-5378-4d64-90e9-759b15d01f28/RSSZ-Hl-m-Praha.jsonld"
)
USER_AGENT = "jaknastredni/0.1 (+https://github.com/austy246/jaknastredni)"

Json = dict[str, Any]


# --------------------------------------------------------------------------- stažení

def download(url: str = URL_PRAHA, raw_dir: Path = Path("data/raw/msmt"), timeout: int = 120) -> Path:
    """Stáhne snapshot a uloží ho do raw_dir pod názvem s datem výstupu. Vrací cestu."""
    import requests  # lokální import, ať jdou testy bez sítě

    log.info("Stahuji %s", url)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    datum = data.get("datumVystupu", datetime.now(timezone.utc).date().isoformat())
    raw_dir.mkdir(parents=True, exist_ok=True)
    stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    path = raw_dir / f"{stem}-{datum}.jsonld"
    path.write_bytes(resp.content)
    log.info("Uloženo %s (%d B, datumVystupu=%s)", path, len(resp.content), datum)
    return path


def load(path: Path) -> Json:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "list" not in data or "datumVystupu" not in data:
        raise ValueError(f"{path}: neočekávaná struktura, chybí 'list' nebo 'datumVystupu'")
    return data


# --------------------------------------------------------------------------- parsování

def _adresa(a: Json | None, prefix: str = "") -> dict[str, Any]:
    a = a or {}
    return {
        f"{prefix}ulice": a.get("ulice"),
        f"{prefix}cislo_domovni": a.get("cisloDomovni"),
        f"{prefix}typ_cisla_domovniho": a.get("typCislaDomovniho"),
        f"{prefix}cislo_orientacni": a.get("cisloOrientacni"),
        f"{prefix}dodatek_orientacniho": a.get("dodatekOrientacnihoCisla"),
        f"{prefix}obec": a.get("obec"),
        f"{prefix}cast_obce": a.get("castObce"),
        f"{prefix}obvod_prahy": a.get("cisloObvoduPrahy"),
        f"{prefix}psc": a.get("psc"),
        f"{prefix}kod_ruian": a.get("kodRUIAN"),
    }


def parse_organizace(o: Json, datum: str) -> dict[str, Any]:
    reditel = o.get("reditel") or {}
    adresa = o.get("adresa") or {}
    row = {
        "redizo": o["redIzo"],
        "ico": o.get("ico"),
        "nazev": o["uplnyNazev"],
        "zkraceny_nazev": o.get("zkracenyNazev"),
        "kraj": o.get("kraj"),
        "pravni_forma": o.get("pravniForma"),
        "typ_zrizovatele": o.get("typZrizovatele"),
        "okres": adresa.get("okres"),
        "orp": adresa.get("uzemiDleORP"),
        "emaily": json.dumps(o.get("emaily") or [], ensure_ascii=False),
        "platnost_neurcita": int(bool(o.get("platnostNaDobuNeurcitou"))),
        "reditel_jmeno": reditel.get("nazevOsoby"),
        "reditel_od": reditel.get("datumVznikuFunkce"),
        "aktualizovano": datum,
    }
    row.update(_adresa(adresa))
    return row


def parse_zrizovatele(o: Json) -> list[dict[str, Any]]:
    # Ukládáme jen identifikaci; adresy a data narození fyzických osob záměrně ne.
    return [
        {
            "redizo": o["redIzo"],
            "poradi": i,
            "druh_osoby": z.get("druhOsoby"),
            "nazev": z.get("nazevOsoby") or "",
            "ico": z.get("ico"),
            "pravni_forma": z.get("pravniForma"),
        }
        for i, z in enumerate(o.get("zrizovatele") or [])
    ]


def parse_skola(s: Json, redizo: str, datum: str) -> dict[str, Any]:
    return {
        "izo": s["izo"],
        "redizo": redizo,
        "nazev": s["uplnyNazev"],
        "druh": s["druh"],
        "jazyk": s.get("jazyk"),
        "datum_zapisu": s.get("datumZapisu"),
        "datum_zahajeni": s.get("datumZahajeniCinnosti"),
        "aktualizovano": datum,
    }


def parse_kapacity(s: Json) -> list[dict[str, Any]]:
    return [
        {"izo": s["izo"], "merna_jednotka": k["mernaJednotka"], "nejvyssi_povoleny_pocet": k["nejvyssiPovolenyPocet"]}
        for k in s.get("kapacity") or []
    ]


def parse_mista(s: Json) -> list[dict[str, Any]]:
    rows = []
    for m in s.get("mistaVyuky") or []:
        row = {"izo": s["izo"], "id_mista": m.get("IDmista") or s["izo"], "typ": m.get("typ")}
        row.update(_adresa(m.get("adresa")))
        rows.append(row)
    return rows


def parse_obory(s: Json) -> list[dict[str, Any]]:
    return [
        {
            "izo": s["izo"],
            "kod_kkov": b["kod"],
            "nazev": b.get("nazev") or "",
            "forma": b.get("formaVzdelavani"),
            "delka": b.get("delkaVzdelavani"),
            "jazyk": b.get("jazykOboru"),
            "kapacita": b.get("kapacita"),
            "merna_jednotka": b.get("mernaJednotkaKapacit"),
            "dobihajici": int(bool(b.get("dobihajiciObor"))),
        }
        for b in s.get("obory") or []
    ]


# --------------------------------------------------------------------------- import

def _insert(conn: sqlite3.Connection, table: str, rows: Iterable[dict[str, Any]], replace: bool = False) -> int:
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0])
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    sql = f"{verb} INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


def _seed_ciselniky(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO ciselnik (ciselnik, kod, nazev, overeno) VALUES (?, ?, ?, ?)",
        [(c, k, n, int(o)) for c, k, n, o in ciselniky.ZNAME_KODY],
    )


def import_data(conn: sqlite3.Connection, data: Json, *, url: str | None = None,
                soubor: Path | None = None, prune: bool = True) -> dict[str, int]:
    """Naimportuje snapshot rejstříku. Snapshot je úplný stav, proto:

    - organizace/školy se přepisují (INSERT OR REPLACE),
    - podřízené řádky (zřizovatelé, kapacity, místa, obory) se smažou a vloží znovu,
    - s ``prune=True`` se organizace stejného kraje, které ve snapshotu chybí, smažou.
    """
    datum = data["datumVystupu"]
    stats = {"organizace": 0, "zrizovatel": 0, "skola": 0, "skola_kapacita": 0, "misto_vyuky": 0, "obor": 0}
    seen_redizo: set[str] = set()
    kraje: set[str] = set()

    with conn:
        _seed_ciselniky(conn)
        for o in data["list"]:
            redizo = o["redIzo"]
            seen_redizo.add(redizo)
            if o.get("kraj"):
                kraje.add(o["kraj"])

            stats["organizace"] += _insert(conn, "organizace", [parse_organizace(o, datum)], replace=True)
            conn.execute("DELETE FROM zrizovatel WHERE redizo = ?", (redizo,))
            stats["zrizovatel"] += _insert(conn, "zrizovatel", parse_zrizovatele(o))

            izos = []
            for s in o.get("skolyAZarizeni") or []:
                izos.append(s["izo"])
                stats["skola"] += _insert(conn, "skola", [parse_skola(s, redizo, datum)], replace=True)
                for table in ("skola_kapacita", "misto_vyuky", "obor"):
                    conn.execute(f"DELETE FROM {table} WHERE izo = ?", (s["izo"],))
                stats["skola_kapacita"] += _insert(conn, "skola_kapacita", parse_kapacity(s))
                stats["misto_vyuky"] += _insert(conn, "misto_vyuky", parse_mista(s), replace=True)
                stats["obor"] += _insert(conn, "obor", parse_obory(s), replace=True)
            # školy, které organizace už neprovozuje
            if izos:
                q = ",".join("?" for _ in izos)
                conn.execute(f"DELETE FROM skola WHERE redizo = ? AND izo NOT IN ({q})", (redizo, *izos))
            else:
                conn.execute("DELETE FROM skola WHERE redizo = ?", (redizo,))

        pruned = 0
        if prune and kraje:
            q = ",".join("?" for _ in kraje)
            rows = conn.execute(f"SELECT redizo FROM organizace WHERE kraj IN ({q})", tuple(kraje)).fetchall()
            stale = [r["redizo"] for r in rows if r["redizo"] not in seen_redizo]
            for r in stale:
                conn.execute("DELETE FROM organizace WHERE redizo = ?", (r,))
            pruned = len(stale)
        stats["smazano_organizaci"] = pruned

        sha = hashlib.sha256(soubor.read_bytes()).hexdigest() if soubor else None
        conn.execute(
            "INSERT INTO import_run (zdroj, url, soubor, sha256, datum_vystupu, stazeno_utc, pocet_zaznamu, poznamka)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("msmt", url, str(soubor) if soubor else None, sha, datum,
             datetime.now(timezone.utc).isoformat(timespec="seconds"), len(data["list"]),
             json.dumps(stats, ensure_ascii=False)),
        )
    return stats


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import rejstříku škol MŠMT do SQLite.")
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--file", type=Path, help="lokální JSON místo stažení")
    p.add_argument("--url", default=URL_PRAHA, help="URL snapshotu (výchozí Praha)")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/msmt"), help="kam ukládat stažené soubory")
    p.add_argument("--no-prune", action="store_true", help="nemazat organizace, které ve snapshotu chybí")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    path = args.file or download(args.url, args.raw_dir)
    data = load(path)
    conn = db.connect(args.db)
    stats = import_data(conn, data, url=None if args.file else args.url, soubor=path, prune=not args.no_prune)
    ss = conn.execute("SELECT COUNT(*) FROM skola WHERE druh = 'C00'").fetchone()[0]
    log.info("Import hotov (datumVystupu=%s): %s; středních škol (C00): %d", data["datumVystupu"], stats, ss)
    return 0


if __name__ == "__main__":
    sys.exit(main())
