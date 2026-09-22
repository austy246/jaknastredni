"""Scraper atlasskolstvi.cz (Scio) — druhý zdroj doplňkových informací o
středních školách, vedle infoabsolvent.cz (`jaknastredni/infoabsolvent.py`,
jehož architekturu tenhle modul zrcadlí téměř 1:1). Přináší navíc pole, které
infoabsolvent nemá: **skutečný loňský počet přijatých** (infoabsolvent uvádí
jen loňský plán přijmout, ne kolik se jich skutečně přijalo) a **doporučený
průměrný prospěch** u přijímacího řízení.

Zdroj je jen server-rendered HTML bez API. Podrobný průzkum:
docs/research/atlas-infoabsolvent.md, oddíl 1.

robots.txt (ověřeno 2026-09-22, viz stejný dokument) zakazuje jen `/admin/`.
Seznam (`/stredni-skoly`) a detail školy (`/ss{id}-...`) nejsou zakázané pro
obecného robota (`User-agent: *`).

**Placená část se neimplementuje.** Odkaz "Statistika" u maturitních oborů
vede na placenou stránku s historickými výsledky JPZ/maturit — VOP definují
službu jako "pro osobní potřebu" se zákazem poskytování třetí osobě (viz
docs/research/atlas-infoabsolvent.md, oddíl 1.4 a 3, bod 1), navíc totéž je
zdarma v CERMAT XLSX (`jaknastredni/cermat_jpz.py`, `cermat_mz.py`). Tenhle
modul čte jen bezplatná pole a odkazy `?obor=...` na placenou statistiku
nikdy nenásleduje.

**REDIZO není v URL** (na rozdíl od infoabsolventu) — URL detailu má tvar
`/ss{interní ID Atlasu}-{slug}`, kde ID není REDIZO/IZO/IČO. REDIZO je čitelné
až na detailu školy (text "Redizo: 600004686") a čte se odtamtud v
`parse_detail()`, který ho vrací jako první prvek dvojice `(redizo, data)`.
`parse_list()` tedy vrací jen `{atlas_id, url}` (bez REDIZO) a soubory se v
`data/raw/atlas/` ukládají podle `atlas_id`, ne podle REDIZO (to se dozvíme
až při importu z uloženého HTML).

Schéma JSON blobu v `web_profil.data` (zdroj `'atlas'`):
    {
        "dny_otevrenych_dveri": str,
        "doplnujici_informace": str,
        "cizi_jazyky": str,
        "ubytovani": str,
        "stravovani": str,
        "obory": [
            {
                "nazev_oboru": str,
                "kod_kkov": str | None,
                "typ_ukonceni": str,       # "maturitní zkouška" / "výuční list"
                "delka_studia": str,
                "planovany_pocet_prijmout": int | None,  # "Přijmou {rok}/{rok+1}"
                "loni_prihlaseni": int | None,            # "Přihl./přij. {rok-1}/{rok}", levá část
                "loni_prijati": int | None,               # tatáž buňka, pravá část — na rozdíl od
                                                            # infoabsolventu SKUTEČNÝ počet přijatých
                "prijimaci_zkousky": str | None,
                "plp": bool | None,
                "ozp": bool | None,
                "skolne_rocne": int | None,
                "doporuceny_prospech": float | None,
            },
            ...
        ],
    }

Adresa, IČ, ředitel/ka, zřizovatel, telefon/e-mail/web se z Atlasu úmyslně
nevytahují — jsou redundantní vůči `organizace`/`misto_vyuky`/`zrizovatel`
z MŠMT rejstříku a jméno ředitele je osobní údaj, který se už jednou ukládá
v `organizace.reditel_jmeno` (stejná zásada jako u infoabsolventu, viz
`jaknastredni/infoabsolvent.py`, komentář u `_GENINFO_LABELS`, a
docs/datovy-model.md, "Zásady").

Použití (jeden krok, stáhne i naimportuje):
    python -m jaknastredni.atlas --db data/jaknastredni.db
    python -m jaknastredni.atlas --db data/jaknastredni.db --limit 5 -v

Modul odděluje síťovou část (`fetch_raw`, ukládá HTML + `_manifest.json` do
`data/raw/atlas/`) od importu (`import_from_local`, čistě offline) — viz
`jaknastredni/fetch_all.py` a `jaknastredni/build_db.py`.

Rate limit: 1 požadavek/s, stejně jako infoabsolvent, viz `RATE_LIMIT_SECONDS`.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup, Tag

from . import db

log = logging.getLogger(__name__)

BASE_URL = "https://www.atlasskolstvi.cz"
LIST_URL = BASE_URL + "/stredni-skoly"
REGION_PRAHA = "hlm-praha"
USER_AGENT = "jaknastredni/0.1 (+https://github.com/austy246/jaknastredni; osobni projekt, vyber SS)"
RATE_LIMIT_SECONDS = 1.0
ZDROJ = "atlas"

_SKOLA_HREF_RE = re.compile(r"^/ss(\d+)-[^/?]+$")
_REDIZO_RE = re.compile(r"(\d{9})")
_SLASH_RE = re.compile(r"(\d+)\s*/\s*(\d+)")

# Popisky nadpisů <h2> v `div.description` (volný text v následujícím
# `<article><div>...</div></article>`).
_POPIS_HEADING_LABELS = {
    "Dny otevřených dveří": "dny_otevrenych_dveri",
    "Doplňující informace": "doplnujici_informace",
}

# Popisky v `ul.advinfo > li > div > strong` (hodnota je sourozenec `<span>`).
_ADVINFO_LABELS = {
    "Cizí jazyky": "cizi_jazyky",
    "Ubytování": "ubytovani",
    "Stravování": "stravovani",
}


class RobotsDisallowed(RuntimeError):
    """Cesta, kterou chceme stáhnout, je v robots.txt zakázaná."""


# --------------------------------------------------------------------------- HTTP

class RateLimitedSession:
    """`requests.Session` s vynuceným minimálním odstupem mezi požadavky."""

    def __init__(self, min_interval: float = RATE_LIMIT_SECONDS, timeout: int = 30):
        import requests  # lokální import, ať jde modul importovat bez sítě/testů

        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self.timeout = timeout
        self._last_request: float | None = None

    def get(self, url: str) -> str:
        if self._last_request is not None:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        resp = self._session.get(url, timeout=self.timeout)
        self._last_request = time.monotonic()
        resp.raise_for_status()
        if "charset" not in (resp.headers.get("Content-Type") or "").lower():
            # Bez deklarovaného charsetu `requests` defaultuje na ISO-8859-1 — na
            # `robots.txt` s BOM by to zmrzačilo první řádek a `check_robots_allows`
            # by potichu přestal fungovat, viz stejná oprava v `infoabsolvent.py`
            # (tam ověřeno živě, u atlasskolstvi.cz aktuálně BOM není, ale stejné
            # riziko).
            resp.encoding = resp.apparent_encoding
        text = resp.text
        # `apparent_encoding` může uhodnout "utf-8" místo "utf-8-sig" a nechat
        # v textu doslovný znak BOM (U+FEFF) — ten by se stejně nerozpoznal jako
        # "user-agent:" na začátku řádku, viz `infoabsolvent.py`.
        return text.lstrip("﻿")


# --------------------------------------------------------------------------- seznam

def _parse_maxpages(html: str) -> int:
    """Vrátí počet stran seznamu (1, pokud chybí).

    Skutečné HTML (ověřeno živě, liší se od dřívějšího průzkumu) má
    `data-maxpages` na vnořeném `<div>` uvnitř `<div class="pagination">`, ne
    na tomtéž elementu, který nese třídu `pagination` — proto `div[data-maxpages]`,
    ne `div.pagination[data-maxpages]`.
    """
    soup = BeautifulSoup(html, "html.parser")
    div = soup.select_one("div.pagination div[data-maxpages]")
    if not div:
        return 1
    try:
        return int(div["data-maxpages"])
    except (KeyError, ValueError):
        return 1


def parse_list(html: str) -> list[dict[str, str]]:
    """Vrátí [{atlas_id, url}] pro odkazy na detail školy v seznamu.

    Atlas ID (`/ss{id}-...`) NENÍ REDIZO — je to jen interní ID Atlasu, viz
    modul docstring. REDIZO se čte až z detailu v `parse_detail()`.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for a in soup.select('ul.schoollist a[href^="/ss"]'):
        m = _SKOLA_HREF_RE.match(a.get("href", ""))
        if not m:
            continue
        atlas_id = m.group(1)
        if atlas_id in seen:
            continue
        seen.add(atlas_id)
        out.append({"atlas_id": atlas_id, "url": BASE_URL + a["href"]})
    return out


# --------------------------------------------------------------------------- detail

def _text(el: Tag | None) -> str | None:
    if el is None:
        return None
    t = el.get_text(" ", strip=True)
    return t or None


def _int(text: str | None) -> int | None:
    """Vytáhne první celé číslo z textu. Odstraňuje i pevnou mezeru `\\xa0`
    použitou na atlasskolstvi.cz jako oddělovač tisíců (např. "74\\xa0800 Kč"),
    ne jen obyčejnou mezeru — jinak by se číslo useklo na první skupinu.
    """
    if not text:
        return None
    m = re.search(r"-?\d+", re.sub(r"\s", "", text))
    return int(m.group()) if m else None


def _float(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", text)
    return float(m.group().replace(",", ".")) if m else None


def _bool_ano_ne(text: str | None) -> bool | None:
    if not text:
        return None
    t = text.strip().lower()
    if t.startswith("ano"):
        return True
    if t.startswith("ne"):
        return False
    return None


def _extract_redizo(soup: BeautifulSoup) -> str | None:
    """Přečte REDIZO z čitelného textu stránky (`<strong>Redizo:</strong> 600004686`,
    ve `<li>` sdíleném se Zřizovatelem a IČ), viz
    docs/research/atlas-infoabsolvent.md, oddíl 1.3 — Atlas ho na rozdíl od
    infoabsolventu nemá v URL. Čte se z textového uzlu hned za `<strong>`, ne
    z celého okolního textu (ten obsahuje i IČ, což je taky číslo).
    """
    strong = soup.find("strong", string=re.compile(r"Redizo"))
    if strong is None:
        return None
    tail = strong.next_sibling
    text = str(tail) if tail is not None else ""
    m = _REDIZO_RE.search(text)
    if m:
        return m.group(1)
    # záložní varianta: celý text rodiče (pro neočekávanou strukturu)
    parent = strong.parent
    if parent is not None:
        m = _REDIZO_RE.search(parent.get_text(" ", strip=True))
        return m.group(1) if m else None
    return None


def _parse_doplnujici(soup: BeautifulSoup) -> dict[str, Any]:
    out: dict[str, Any] = {}
    desc = soup.select_one("div.description")
    if desc is not None:
        for h2 in desc.select("h2"):
            key = _POPIS_HEADING_LABELS.get(h2.get_text(strip=True))
            if not key:
                continue
            article = h2.find_next_sibling("article")
            if article is None:
                continue
            div = article.select_one("div")
            val = _text(div) if div is not None else _text(article)
            if val:
                out[key] = val
    advinfo = soup.select_one("ul.advinfo")
    if advinfo is not None:
        for li in advinfo.select("li"):
            strong = li.select_one("strong")
            if strong is None:
                continue
            key = _ADVINFO_LABELS.get(strong.get_text(strip=True))
            if not key:
                continue
            val = _text(li.select_one("span"))
            if val:
                out[key] = val
    return out


def _find_cell(tr: Tag, prefix: str) -> Tag | None:
    """Najde `<th>`/`<td data-name="...">` podle prefixu popisku sloupce —
    hlavičky "Přijmou {rok}/{rok+1}" a "Přihl./přij. {rok-1}/{rok}" mají rok
    zapečený v textu (a chybí úplně, když škola loňská data nemá), proto se
    nepárují přesnou shodou, ale prefixem.
    """
    for el in tr.select("[data-name]"):
        if el["data-name"].startswith(prefix):
            return el
    return None


def _parse_obor_header_row(tr: Tag) -> dict[str, Any]:
    """Naparsuje první ze dvou `<tr>`, které v `table.sslist` tvoří jeden obor
    — obsahuje buňku `data-name="Obor, zaměření, kód oboru KKOV"` (název v
    `<strong>` uvnitř `<a>`, kód KKOV v sourozeneckém `<span>`), ukončení
    studia (typ v `<strong>`, délka v `<span>`), plán přijmout, loňský
    přihlášení/přijatí (odděleno lomítkem), přijímací zkoušky, PLP, OZP.
    """
    obor_cell = _find_cell(tr, "Obor")
    nazev_oboru = kod_kkov = None
    if obor_cell is not None:
        nazev_oboru = _text(obor_cell.select_one("strong")) or _text(obor_cell)
        kod_kkov = _text(obor_cell.select_one("span"))

    ukonceni_cell = _find_cell(tr, "Ukončení")
    typ_ukonceni = delka_studia = None
    if ukonceni_cell is not None:
        typ_ukonceni = _text(ukonceni_cell.select_one("strong"))
        delka_studia = _text(ukonceni_cell.select_one("span"))

    prihl_prijati_text = _text(_find_cell(tr, "Přihl./přij."))
    loni_prihlaseni = loni_prijati = None
    if prihl_prijati_text:
        m = _SLASH_RE.search(prihl_prijati_text)
        if m:
            loni_prihlaseni, loni_prijati = int(m.group(1)), int(m.group(2))

    return {
        "nazev_oboru": nazev_oboru,
        "kod_kkov": kod_kkov,
        "typ_ukonceni": typ_ukonceni,
        "delka_studia": delka_studia,
        "planovany_pocet_prijmout": _int(_text(_find_cell(tr, "Přijmou"))),
        "loni_prihlaseni": loni_prihlaseni,
        "loni_prijati": loni_prijati,
        "prijimaci_zkousky": _text(_find_cell(tr, "Přijímací zkoušky")),
        "plp": _bool_ano_ne(_text(_find_cell(tr, "PLP"))),
        "ozp": _bool_ano_ne(_text(_find_cell(tr, "OZP"))),
    }


def _merge_obor_continuation_row(row: dict[str, Any], tr: Tag) -> None:
    """Doplní do rozestavěného řádku oboru druhý ze dvou `<tr>` (`class="nobg"`):
    školné a doporučený prospěch."""
    skolne = _int(_text(_find_cell(tr, "Školné")))
    if skolne is not None:
        row["skolne_rocne"] = skolne
    prospech = _float(_text(_find_cell(tr, "Doporučený prospěch")))
    if prospech is not None:
        row["doporuceny_prospech"] = prospech


def _parse_obory(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Naparsuje `table.sslist` — každý obor zabírá DVA `<tr>` (hlavní řádek +
    `<tr class="nobg">` se školným/prospěchem), proto se páruje průchodem
    seznamu řádků, ne 1:1 na `<tr>`. Řádky-oddělovače sekcí ("Dálkové
    studium:", "Nástavby:") nemají buňku oboru ani školné/prospěch — přeskočí
    se, aniž by přerušily rozestavěný obor.
    """
    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for tr in soup.select("table.sslist tbody tr"):
        if _find_cell(tr, "Obor") is not None:
            if current is not None:
                out.append({k: v for k, v in current.items() if v is not None})
            current = _parse_obor_header_row(tr)
        elif current is not None and (
            _find_cell(tr, "Školné") is not None or _find_cell(tr, "Doporučený prospěch") is not None
        ):
            _merge_obor_continuation_row(current, tr)
    if current is not None:
        out.append({k: v for k, v in current.items() if v is not None})
    return out


def parse_detail(html: str) -> tuple[str | None, dict[str, Any]]:
    """Naparsuje detail školy. Vrátí `(redizo, data)` — REDIZO se čte z textu
    stránky (viz `_extract_redizo`), `None` pokud chybí (stránka bez detailu
    nebo se struktura změnila; volající by měl takovou školu přeskočit a
    zalogovat, ne uložit řádek bez klíče). Placená statistika (`?obor=...`)
    se nikdy nenačítá ani neparsuje, viz modul docstring.
    """
    soup = BeautifulSoup(html, "html.parser")
    redizo = _extract_redizo(soup)
    data: dict[str, Any] = {}
    data.update(_parse_doplnujici(soup))
    obory = _parse_obory(soup)
    if obory:
        data["obory"] = obory
    return redizo, data


# --------------------------------------------------------------------------- import

def import_profil(conn: sqlite3.Connection, redizo: str, data: dict[str, Any], *,
                   stazeno: str, zdroj: str = ZDROJ, url: str | None = None) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO web_profil (redizo, zdroj, stazeno, url, data) VALUES (?, ?, ?, ?, ?)",
            (redizo, zdroj, stazeno, url, json.dumps(data, ensure_ascii=False)),
        )


def _log_import_run(conn: sqlite3.Connection, *, url: str, pocet: int, poznamka: str | None = None) -> None:
    with conn:
        conn.execute(
            "INSERT INTO import_run (zdroj, url, datum_vystupu, stazeno_utc, pocet_zaznamu, poznamka)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (ZDROJ, url, datetime.now(timezone.utc).date().isoformat(),
             datetime.now(timezone.utc).isoformat(timespec="seconds"), pocet, poznamka),
        )


def fetch_raw(session: RateLimitedSession, raw_dir: Path, *,
              region: str = REGION_PRAHA, limit: int | None = None) -> dict[str, int]:
    """Stáhne stránkovaný seznam škol a HTML detailu každé z nich do `raw_dir`,
    bez zápisu do databáze — odděluje pomalou/rate-limitovanou síťovou část od
    importu (viz `jaknastredni/fetch_all.py`). Ukládá `{atlas_id}.html` na
    školu (ne `{redizo}.html` — to se dozvíme až z detailu, viz modul
    docstring) a `_manifest.json`, který `import_from_local()` potřebuje.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    list_url = f"{LIST_URL}?region={region}"
    log.info("Stahuji 1. stránku seznamu škol: %s", list_url)
    first_page = session.get(list_url)
    maxpages = _parse_maxpages(first_page)
    log.info("Seznam má %d stran", maxpages)

    schools: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add_page(html: str) -> None:
        for s in parse_list(html):
            if s["atlas_id"] not in seen:
                seen.add(s["atlas_id"])
                schools.append(s)

    _add_page(first_page)
    for page in range(2, maxpages + 1):
        page_url = f"{LIST_URL}?p={page}&region={region}"
        log.debug("Stahuji stránku seznamu %d/%d: %s", page, maxpages, page_url)
        _add_page(session.get(page_url))

    log.info("Seznam obsahuje %d škol", len(schools))
    if limit is not None:
        schools = schools[:limit]

    stazeno = datetime.now(timezone.utc).date().isoformat()
    ok = 0
    failed: list[tuple[str, str]] = []
    for i, school in enumerate(schools, 1):
        atlas_id, url = school["atlas_id"], school["url"]
        log.debug("(%d/%d) %s %s", i, len(schools), atlas_id, url)
        try:
            html = session.get(url)
            (raw_dir / f"{atlas_id}.html").write_text(html, encoding="utf-8")
            ok += 1
        except Exception as exc:  # noqa: BLE001 - chceme pokračovat i po chybě jedné školy
            log.warning("Škola %s (%s) selhala: %s", atlas_id, url, exc)
            failed.append((atlas_id, str(exc)))

    manifest = {"stazeno": stazeno, "region": region, "list_url": list_url, "schools": schools}
    (raw_dir / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Staženo %d/%d škol (%d selhalo)", ok, len(schools), len(failed))
    return {"celkem": len(schools), "ok": ok, "selhalo": len(failed)}


def import_from_local(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Naimportuje profily z lokálně stažených HTML (viz `fetch_raw`) do `web_profil`,
    zcela bez síťových požadavků. Vyžaduje `_manifest.json` v `raw_dir` — pokud
    chybí, nic se neimportuje (nejdřív je nutné spustit fetch).
    """
    manifest_path = raw_dir / "_manifest.json"
    if not manifest_path.exists():
        log.warning("%s neexistuje, atlas přeskočen (nejdřív spusť fetch)", manifest_path)
        return {"celkem": 0, "ok": 0, "chybi_html": 0, "bez_redizo": 0}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stazeno = manifest["stazeno"]
    schools = manifest["schools"]

    ok = 0
    missing: list[str] = []
    bez_redizo: list[str] = []
    for school in schools:
        atlas_id, url = school["atlas_id"], school["url"]
        html_path = raw_dir / f"{atlas_id}.html"
        if not html_path.exists():
            missing.append(atlas_id)
            continue
        redizo, data = parse_detail(html_path.read_text(encoding="utf-8"))
        if not redizo:
            log.warning("Atlas ID %s (%s): REDIZO nenalezeno na stránce, přeskočeno", atlas_id, url)
            bez_redizo.append(atlas_id)
            continue
        import_profil(conn, redizo, data, stazeno=stazeno, url=url)
        ok += 1

    poznamka = None
    if missing or bez_redizo:
        poznamka = json.dumps(
            {"celkem": len(schools), "ok": ok, "chybi_html": missing, "bez_redizo": bez_redizo},
            ensure_ascii=False,
        )
    _log_import_run(conn, url=manifest.get("list_url"), pocet=ok, poznamka=poznamka)
    log.info("atlas (lokálně): %d/%d škol naimportováno (%d chybí HTML, %d bez REDIZO)",
              ok, len(schools), len(missing), len(bez_redizo))
    return {"celkem": len(schools), "ok": ok, "chybi_html": len(missing), "bez_redizo": len(bez_redizo)}


# --------------------------------------------------------------------------- robots.txt

def check_robots_allows(session: RateLimitedSession, paths: Iterable[str]) -> None:
    """Ověří, že žádná z `paths` není v robots.txt zakázaná pro `User-agent: *`.

    Jednoduchý parser: bere jen sekci `User-agent: *`, ne plný RFC 9309 algoritmus
    (na atlasskolstvi.cz stačí, viz docs/research/atlas-infoabsolvent.md).
    """
    text = session.get(BASE_URL + "/robots.txt")
    disallow: list[str] = []
    in_star = False
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            in_star = line.split(":", 1)[1].strip() == "*"
        elif in_star and line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                disallow.append(path)
    for p in paths:
        for d in disallow:
            if p.startswith(d):
                raise RobotsDisallowed(f"{p} je v robots.txt zakázané pravidlem 'Disallow: {d}'")


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Scraper atlasskolstvi.cz do tabulky web_profil (stáhne a rovnou naimportuje)."
    )
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/atlas"),
                    help="kam ukládat stažené HTML (a odkud se čte manifest)")
    p.add_argument("--region", default=REGION_PRAHA, help="kód regionu Atlasu, výchozí Praha")
    p.add_argument("--limit", type=int, default=None, help="omezit na prvních N škol (test/rychlý běh)")
    p.add_argument("--skip-robots-check", action="store_true", help="přeskočit ověření robots.txt (needoporučeno)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    session = RateLimitedSession()
    if not args.skip_robots_check:
        check_robots_allows(session, ["/stredni-skoly", "/ss"])

    fetch_raw(session, args.raw_dir, region=args.region, limit=args.limit)
    conn = db.connect(args.db)
    stats = import_from_local(conn, args.raw_dir)
    log.info("Import hotov: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
