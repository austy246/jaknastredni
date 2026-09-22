"""Scraper infoabsolvent.cz (NPI ČR) — doplňkové informace o středních školách,
které rejstřík MŠMT nemá (přijímací kritéria, školné, dny otevřených dveří,
jazyky, vybavení, loňský poměr přihlášených/plánu přijmout).

Zdroj je jen server-rendered HTML bez API. Podrobný průzkum:
docs/research/atlas-infoabsolvent.md, oddíl 2.

robots.txt (ověřeno 2026-09-22, viz stejný dokument) zakazuje jen
`/Obory/PorovnaniOboru`, `/Skoly/KartaSkolyPorovnavaneObory/` a
`/Tools/SaveAsWord`, a kompletně blokuje jen crawler `meta-externalagent`.
Seznam (`/Skoly/Seznam/...`) a detail (`/Skoly/Skola/...`) škol nejsou
zakázané pro obecného robota (`User-agent: *`).

Použití (jeden krok, stáhne i naimportuje):
    python -m jaknastredni.infoabsolvent --db data/jaknastredni.db
    python -m jaknastredni.infoabsolvent --db data/jaknastredni.db --limit 5 -v

Modul odděluje síťovou část (`fetch_raw`, ukládá HTML + `_manifest.json` do
`data/raw/infoabsolvent/`) od importu (`import_from_local`, čistě offline) —
viz `jaknastredni/fetch_all.py` a `jaknastredni/build_db.py`, které tyhle dvě
funkce volají samostatně napříč všemi zdroji.

Rate limit: 1 požadavek/s (doporučení průzkumu), viz `RATE_LIMIT_SECONDS`.
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

BASE_URL = "https://www.infoabsolvent.cz"
LIST_URL = BASE_URL + "/Skoly/Seznam/SOS"
KRAJ_PRAHA = "CZ011"
USER_AGENT = "jaknastredni/0.1 (+https://github.com/austy246/jaknastredni; osobni projekt, vyber SS)"
RATE_LIMIT_SECONDS = 1.0
ZDROJ = "infoabsolvent"

_SKOLA_HREF_RE = re.compile(r"^/Skoly/Skola/(\d{9})/([^/]+)/(\w+)$")

# Mapování popisků z genInfoList (ul.genInfoList > li > span.label/span.data)
# na klíče v JSON. Labely, které chybí, se v datech prostě nevyskytnou.
_GENINFO_LABELS = {
    "Vybavení školy a její nabídka": "vybaveni_a_nabidka",
    "Velikost školy": "velikost_skoly",
    "Ubytování": "ubytovani",
    "Stravování": "stravovani",
    "Přístup k PC": "pristup_pc_mimo_vyuku",
    "Přístup k internetu": "pristup_internet_mimo_vyuku",
    "Den otevřených dveří": "den_otevrenych_dveri",
    "Cizí jazyky": "cizi_jazyky",
    "Poznámka SŠ": "poznamka_ss",
    # Adresa/Okres/Typ školy/Zřizovatel se úmyslně nevytahují — jsou (nebo
    # budou) redundantní vůči organizace/misto_vyuky/zrizovatel z MŠMT
    # rejstříku (viz docs/datovy-model.md, "Osobní údaje minimalizujeme" a
    # zásada nepočítat duplicitní data).
}

# Popisky v okně "Informace k přijímacímu řízení" (td.popisek/td.info páry).
_PRIJIMACKY_LABELS = {
    "Jednotná příj. zkouška": "jednotna_prijimaci_zkouska",
    "Ústní zkouška": "ustni_zkouska",
    "Písemná zkouška": "pisemna_zkouska",
    "Talentová zkouška": "talentova_zkouska",
    "Praktická zkouška": "prakticka_zkouska",
    "Jiná kritéria přijímání": "jina_kriteria_prijimani",
    "Přihlášky podejte do": "prihlasky_podejte_do",
    "Termíny školních a talentových přijímacích zkoušek": "terminy_skolnich_a_talentovych_zkousek",
    "Termíny jednotné zkoušky": "terminy_jednotne_zkousky",
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
            # Bez deklarovaného charsetu `requests` defaultuje na ISO-8859-1 (staré
            # HTTP chování pro text/*) — na `robots.txt` s UTF-8 BOM (ověřeno živě u
            # infoabsolvent.cz) to zmrzačí první řádek ("User-agent: *" se stane
            # nerozpoznatelným), takže `check_robots_allows` níže nikdy nenajde
            # sekci `User-agent: *` a Disallow pravidla potichu ignoruje.
            resp.encoding = resp.apparent_encoding
        text = resp.text
        # `apparent_encoding` může uhodnout "utf-8" místo "utf-8-sig" (záleží na
        # verzi detekční knihovny) a nechat v textu doslovný znak BOM (U+FEFF) —
        # ten se pak stejně nerozpozná jako "user-agent:" na začátku řádku.
        return text.lstrip("﻿")


# --------------------------------------------------------------------------- seznam

def parse_list(html: str) -> list[dict[str, str]]:
    """Vrátí [{redizo, slug, url}] pro odkazy na detail školy v seznamu."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for a in soup.select('a[href^="/Skoly/Skola/"]'):
        m = _SKOLA_HREF_RE.match(a.get("href", ""))
        if not m:
            continue
        redizo, slug, kategorie = m.groups()
        if redizo in seen:
            continue
        seen.add(redizo)
        out.append({"redizo": redizo, "slug": slug, "url": BASE_URL + a["href"]})
    return out


# --------------------------------------------------------------------------- detail

def _text(el: Tag | None) -> str | None:
    if el is None:
        return None
    t = el.get_text(" ", strip=True)
    return t or None


def _int(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"-?\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def _parse_geninfo(soup: BeautifulSoup) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for li in soup.select("ul.genInfoList > li"):
        label_el = li.select_one("span.label")
        data_el = li.select_one("span.data")
        if not label_el or not data_el:
            continue
        label = label_el.get_text(strip=True).rstrip(":")
        key = _GENINFO_LABELS.get(label)
        if key:
            out[key] = _text(data_el)
    return out


def _parse_kontakt(soup: BeautifulSoup) -> dict[str, Any]:
    out: dict[str, Any] = {}
    box = soup.select_one("div.addInfoBox ul.contactList")
    if not box:
        return out
    mapping = {"www": "www", "E-mail": "email", "Telefon": "telefon"}
    for li in box.select("li"):
        label_el = li.select_one("span.label")
        data_el = li.select_one("span.data")
        if not label_el or not data_el:
            continue
        key = mapping.get(label_el.get_text(strip=True))
        if key:
            out[key] = _text(data_el)
    return out


def _parse_csi_link(soup: BeautifulSoup) -> str | None:
    a = soup.find("a", href=re.compile(r"portal\.csicr\.cz"))
    return a["href"] if a else None


def _parse_prijimaci_rizeni(okno: Tag) -> dict[str, str]:
    out: dict[str, str] = {}
    for tr in okno.select("tbody tr"):
        pop = tr.select_one("td.popisek")
        info = tr.select_one("td.info")
        if not pop or not info:
            continue
        label = pop.get_text(strip=True).rstrip(":")
        key = _PRIJIMACKY_LABELS.get(label)
        val = _text(info)
        if key and val:
            out[key] = val
    return out


def _parse_poznamky_k_oboru(td: Tag | None) -> str | None:
    if td is None:
        return None
    bold = td.find("b", string=re.compile(r"Pozn[áa]mky k oboru"))
    if not bold:
        return None
    # text hned za <b>Poznámky k oboru:</b> uvnitř stejného rodičovského <div>
    parent = bold.parent
    if parent is None:
        return None
    full = parent.get_text(" ", strip=True)
    label = bold.get_text(strip=True)
    text = full[len(label):].strip()
    return text or None


def _parse_obor_row(ob: Tag, idx: str, position: int) -> dict[str, Any]:
    def cell(prefix: str) -> Tag | None:
        return ob.find(id=f"{prefix}-{idx}")

    svp_td = cell("A-nazev-oboru")
    svp_span = svp_td.select_one("span.nazevOboruJeSvp") if svp_td else None
    svp_nazev = _text(svp_span) if svp_span else _text(svp_td)

    prihl_plan = _text(cell("F-prihlaseni-prijati"))
    loni_prihlaseni = loni_plan = None
    if prihl_plan and "/" in prihl_plan:
        a, b = prihl_plan.split("/", 1)
        loni_prihlaseni, loni_plan = _int(a), _int(b)

    zkouska_text = _text(cell("H-prijimaci-zkouska"))
    zkouska_kona_se: bool | None = None
    if zkouska_text:
        zkouska_kona_se = "nekon" not in zkouska_text.lower()

    row: dict[str, Any] = {
        "svp_nazev": svp_nazev,
        "delka_studia": _text(cell("B-delka")),
        "forma_studia": _text(cell("C-forma")),
        "pocet_povinnych_jazyku": _int(_text(cell("D-pocet-jazyku"))),
        "vyucovane_jazyky": _text(cell("E-jazyky")),
        "loni_prihlaseni": loni_prihlaseni,
        "loni_plan_prijmout": loni_plan,
        "letos_plan_prijmout": _int(_text(cell("G-pocet-prijatych"))),
        "prijimaci_zkouska_kona_se": zkouska_kona_se,
        "skolne_rocne": _int(_text(cell("I-skolne"))),
        "moznost_studia_pro_zp": _text(cell("J-ztp")),
    }

    # Okno "Informace k přijímacímu řízení" a poznámky k oboru mají svoje
    # vlastní id/číslování (ID oboru v systému, ne řádkový index výše), ale
    # v HTML jsou v tom samém pořadí jako řádky ŠVP/zaměření v rámci jednoho
    # `div.oborRvp` — proto se párují podle pozice (`position`), ne podle `idx`.
    oknos = ob.select("div.prijimackyOkno")
    if position < len(oknos):
        rizeni = _parse_prijimaci_rizeni(oknos[position])
        if rizeni:
            row["prijimaci_rizeni"] = rizeni

    poznamky_tds = ob.select("td.poznamky")
    if position < len(poznamky_tds):
        pozn = _parse_poznamky_k_oboru(poznamky_tds[position])
        if pozn:
            row["poznamky_k_oboru"] = pozn

    return {k: v for k, v in row.items() if v is not None}


def _parse_obory(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out = []
    for ob in soup.select("div.oborRvp"):
        kod_el = ob.select_one("span.kodOboru")
        nazev_el = ob.select_one("span.nazevOboru")
        if not kod_el:
            continue
        kod = kod_el.get_text(strip=True)
        nazev = _text(nazev_el)
        svp_tds = ob.select('td[id^="A-nazev-oboru-"]')
        if not svp_tds:
            out.append({"kod_kkov": kod, "nazev_oboru": nazev})
            continue
        for position, td in enumerate(svp_tds):
            idx = td["id"].rsplit("-", 1)[1]
            row = _parse_obor_row(ob, idx, position)
            row = {"kod_kkov": kod, "nazev_oboru": nazev, **row}
            out.append(row)
    return out


def parse_detail(html: str, redizo: str) -> dict[str, Any]:
    """Naparsuje detail školy. `redizo` je autoritativní z URL (viz modul docstring),
    hodnota skrytého pole `redIzo` na stránce se použije jen jako kontrola shody.
    """
    soup = BeautifulSoup(html, "html.parser")

    hidden = soup.select_one("input#redIzo")
    if hidden and hidden.get("value") and hidden["value"] != redizo:
        log.warning("REDIZO z URL (%s) se neshoduje se skrytým polem na stránce (%s), používám URL",
                    redizo, hidden["value"])

    data: dict[str, Any] = {}
    data.update(_parse_geninfo(soup))
    data.update(_parse_kontakt(soup))
    csi = _parse_csi_link(soup)
    if csi:
        data["csi_zpravy_url"] = csi
    obory = _parse_obory(soup)
    if obory:
        data["obory"] = obory
    return data


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
              kraj: str = KRAJ_PRAHA, limit: int | None = None) -> dict[str, int]:
    """Stáhne seznam škol a HTML detailu každé z nich do `raw_dir`, bez zápisu do
    databáze — odděluje pomalou/rate-limitovanou síťovou část od importu (viz
    `jaknastredni/fetch_all.py`). Ukládá `{redizo}.html` na školu a `_manifest.json`
    (seznam škol + datum stažení + URL seznamu), který `import_from_local()`
    potřebuje k offline importu.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    list_url = f"{LIST_URL}?Kraj={kraj}"
    log.info("Stahuji seznam škol: %s", list_url)
    schools = parse_list(session.get(list_url))
    log.info("Seznam obsahuje %d škol", len(schools))
    if limit is not None:
        schools = schools[:limit]

    stazeno = datetime.now(timezone.utc).date().isoformat()
    ok = 0
    failed: list[tuple[str, str]] = []
    for i, school in enumerate(schools, 1):
        redizo, url = school["redizo"], school["url"]
        log.debug("(%d/%d) %s %s", i, len(schools), redizo, url)
        try:
            html = session.get(url)
            (raw_dir / f"{redizo}.html").write_text(html, encoding="utf-8")
            ok += 1
        except Exception as exc:  # noqa: BLE001 - chceme pokračovat i po chybě jedné školy
            log.warning("Škola %s (%s) selhala: %s", redizo, url, exc)
            failed.append((redizo, str(exc)))

    manifest = {"stazeno": stazeno, "kraj": kraj, "list_url": list_url, "schools": schools}
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
        log.warning("%s neexistuje, infoabsolvent přeskočen (nejdřív spusť fetch)", manifest_path)
        return {"celkem": 0, "ok": 0, "chybi_html": 0}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stazeno = manifest["stazeno"]
    schools = manifest["schools"]

    ok = 0
    missing: list[str] = []
    for school in schools:
        redizo, url = school["redizo"], school["url"]
        html_path = raw_dir / f"{redizo}.html"
        if not html_path.exists():
            missing.append(redizo)
            continue
        data = parse_detail(html_path.read_text(encoding="utf-8"), redizo)
        import_profil(conn, redizo, data, stazeno=stazeno, url=url)
        ok += 1

    _log_import_run(conn, url=manifest.get("list_url"), pocet=ok,
                     poznamka=json.dumps({"celkem": len(schools), "ok": ok, "chybi_html": missing},
                                          ensure_ascii=False) if missing else None)
    log.info("infoabsolvent (lokálně): %d/%d škol naimportováno (%d chybí HTML)", ok, len(schools), len(missing))
    return {"celkem": len(schools), "ok": ok, "chybi_html": len(missing)}


# --------------------------------------------------------------------------- robots.txt

def check_robots_allows(session: RateLimitedSession, paths: Iterable[str]) -> None:
    """Ověří, že žádná z `paths` není v robots.txt zakázaná pro `User-agent: *`.

    Jednoduchý parser: bere jen sekci `User-agent: *`, ne plný RFC 9309 algoritmus
    (na infoabsolvent.cz stačí, viz docs/research/atlas-infoabsolvent.md).
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
        description="Scraper infoabsolvent.cz do tabulky web_profil (stáhne a rovnou naimportuje)."
    )
    p.add_argument("--db", default="data/jaknastredni.db", help="cesta k SQLite databázi")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/infoabsolvent"),
                    help="kam ukládat stažené HTML (a odkud se čte manifest)")
    p.add_argument("--kraj", default=KRAJ_PRAHA, help="kód kraje (CZ-NUTS), výchozí Praha")
    p.add_argument("--limit", type=int, default=None, help="omezit na prvních N škol (test/rychlý běh)")
    p.add_argument("--skip-robots-check", action="store_true", help="přeskočit ověření robots.txt (needoporučeno)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    session = RateLimitedSession()
    if not args.skip_robots_check:
        check_robots_allows(session, ["/Skoly/Seznam/SOS", "/Skoly/Skola/"])

    fetch_raw(session, args.raw_dir, kraj=args.kraj, limit=args.limit)
    conn = db.connect(args.db)
    stats = import_from_local(conn, args.raw_dir)
    log.info("Import hotov: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
