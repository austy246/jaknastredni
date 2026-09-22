"""Testy scraperu atlasskolstvi.cz.

Fixtury jsou minimální HTML konzistentní se selektory popsanými v
docs/research/atlas-infoabsolvent.md (oddíl 1) — na rozdíl od
tests/test_infoabsolvent.py nejde o výřezy skutečně stažených stránek (živé
HTML atlasskolstvi.cz nebylo v tomto prostředí k dispozici), ale o realistické
fixtury odpovídající zdokumentované struktuře (`ul.schoollist`,
`div.pagination[data-maxpages]`, `<strong>Redizo:</strong>`, `table.oborTable`
s `data-name` atributy).
"""
from __future__ import annotations

import json

from jaknastredni import atlas, db

# --------------------------------------------------------------------------- fixtury

LIST_HTML = """
<html><body>
<div class="pagination" data-maxpages="11" data-nextpage="2"></div>
<ul class="schoollist cols1">
<li><a href="/ss16-stredni-prumyslova-skola-strojnicka-praha-1">
  <h2>Střední průmyslová škola strojnická</h2>
  <article>Betlémská 287/4, Praha 1, 110 00</article>
</a></li>
<li><a href="/ss183-obchodni-akademie-heroldovy-sady">
  <h2>Obchodní akademie</h2>
  <article>Heroldovy sady 1, Praha 10, 101 00</article>
</a></li>
</ul>
</body></html>
"""

LIST_PAGE2_HTML = """
<html><body>
<div class="pagination" data-maxpages="11" data-nextpage="3"></div>
<ul class="schoollist cols1">
<li><a href="/ss42-gymnazium-nad-alejí">
  <h2>Gymnázium Nad Alejí</h2>
  <article>Nad Alejí 1952, Praha 6, 162 00</article>
</a></li>
</ul>
</body></html>
"""

# Detail školy (REDIZO 600004686), zdarma dostupná pole + jeden obor s
# odkazem na placenou "Statistiku" (ten se nesmí parsovat/následovat).
DETAIL_SIMPLE_HTML = """
<html><body>
<div class="schoolDetail">
  <h1>Střední průmyslová škola strojnická</h1>
  <div class="contactInfo">
    <p><strong>Adresa:</strong> Betlémská 287/4, Praha 1</p>
    <p><strong>IČ:</strong> 63109357</p>
    <p><strong>Redizo:</strong> 600004686</p>
    <p><strong>Zřizovatel:</strong> Hlavní město Praha</p>
  </div>
  <div class="doplnujiciInfo">
    <h3>Dny otevřených dveří</h3>
    <p>12. 12. 2026, 16. 1. 2027</p>
    <h3>Doplňující informace</h3>
    <p>Škola se zaměřuje na strojírenství a informační technologie.</p>
    <h3>Cizí jazyky</h3>
    <p>anglický, německý</p>
    <h3>Ubytování</h3>
    <p>škola nezajišťuje</p>
    <h3>Stravování</h3>
    <p>250 Kč/měsíc</p>
  </div>
  <table class="oborTable">
    <thead>
      <tr>
        <td data-name="Obor, zaměření, kód oboru KKOV">Obor</td>
        <td data-name="Typ ukončení">Typ ukončení</td>
        <td data-name="Délka studia">Délka studia</td>
        <td data-name="Přijmou 2026/27">Přijmou 2026/27</td>
        <td data-name="Přihl./přij. 2025/26">Přihl./přij. 2025/26</td>
        <td data-name="Přijímací zkoušky">Přijímací zkoušky</td>
        <td data-name="PLP">PLP</td>
        <td data-name="OZP">OZP</td>
        <td data-name="Doporučený prospěch">Doporučený prospěch</td>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td data-name="Obor, zaměření, kód oboru KKOV">Informační technologie (18-20-M/01)</td>
        <td data-name="Typ ukončení">maturitní zkouška</td>
        <td data-name="Délka studia">4</td>
        <td data-name="Přijmou 2026/27">30</td>
        <td data-name="Přihl./přij. 2025/26">89/30</td>
        <td data-name="Přijímací zkoušky">ČJ, M</td>
        <td data-name="PLP">ne</td>
        <td data-name="OZP">ano</td>
        <td data-name="Doporučený prospěch">1,5</td>
        <td><a href="?obor=3716&amp;forma=1&amp;typ=1&amp;delka_studia=4">Statistika</a></td>
      </tr>
    </tbody>
  </table>
</div>
</body></html>
"""

# Výřez s učňovským oborem (bez maturity, bez placené "Statistiky" u odkazu).
DETAIL_UCNOVSKY_HTML = """
<html><body>
<div class="contactInfo">
  <p><strong>Redizo:</strong> 600006573</p>
</div>
<table class="oborTable">
  <tbody>
    <tr>
      <td data-name="Obor, zaměření, kód oboru KKOV">Truhlář (33-56-H/01)</td>
      <td data-name="Typ ukončení">výuční list</td>
      <td data-name="Délka studia">3</td>
      <td data-name="Přijmou 2026/27">15</td>
      <td data-name="Přihl./přij. 2025/26">12/12</td>
      <td data-name="PLP">ano</td>
      <td data-name="OZP">ne</td>
    </tr>
  </tbody>
</table>
</body></html>
"""

DETAIL_NO_REDIZO_HTML = """
<html><body><div class="contactInfo"><p>Stránka bez detailu.</p></div></body></html>
"""


# --------------------------------------------------------------------------- seznam

def test_parse_list_extracts_atlas_id_and_url():
    schools = atlas.parse_list(LIST_HTML)
    assert [s["atlas_id"] for s in schools] == ["16", "183"]
    assert schools[0]["url"] == "https://www.atlasskolstvi.cz/ss16-stredni-prumyslova-skola-strojnicka-praha-1"


def test_parse_list_atlas_id_is_not_redizo():
    """Atlas ID v URL seznamu (ss16, ss183) má jinou délku/formát než REDIZO (9 číslic)
    — je to jen interní ID Atlasu, ne klíč pro propojení, viz modul docstring."""
    schools = atlas.parse_list(LIST_HTML)
    assert all(not (s["atlas_id"].isdigit() and len(s["atlas_id"]) == 9) for s in schools)


def test_parse_list_deduplicates_atlas_id():
    html = LIST_HTML + '<ul class="schoollist"><li><a href="/ss16-jiny-slug">duplicitní</a></li></ul>'
    schools = atlas.parse_list(html)
    assert [s["atlas_id"] for s in schools].count("16") == 1


def test_parse_maxpages():
    assert atlas._parse_maxpages(LIST_HTML) == 11


def test_parse_maxpages_defaults_to_one_without_pagination():
    assert atlas._parse_maxpages("<html><body>no pagination here</body></html>") == 1


# --------------------------------------------------------------------------- detail: obecná pole

def test_parse_detail_extracts_redizo_from_page_text():
    redizo, _data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert redizo == "600004686"


def test_parse_detail_returns_none_redizo_when_missing():
    redizo, data = atlas.parse_detail(DETAIL_NO_REDIZO_HTML)
    assert redizo is None
    assert data == {}


def test_parse_detail_doplnujici_fields():
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert data["dny_otevrenych_dveri"] == "12. 12. 2026, 16. 1. 2027"
    assert "strojírenství" in data["doplnujici_informace"]
    assert data["cizi_jazyky"] == "anglický, německý"
    assert data["ubytovani"] == "škola nezajišťuje"
    assert data["stravovani"] == "250 Kč/měsíc"


def test_parse_detail_no_personal_or_redundant_data():
    """Adresa, IČ, zřizovatel a jméno ředitele se nevytahují (redundantní vůči MŠMT
    rejstříku / osobní údaj, stejná zásada jako u infoabsolventu)."""
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    blob = json.dumps(data, ensure_ascii=False).lower()
    assert "adresa" not in data
    assert "ic" not in data and "ič" not in data
    assert "zrizovatel" not in data and "zřizovatel" not in data
    assert "reditel" not in blob
    assert "betlémská" not in blob  # adresa se nikam nepropsala


# --------------------------------------------------------------------------- detail: obory

def test_parse_detail_obor_basic_fields():
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert len(data["obory"]) == 1
    obor = data["obory"][0]
    assert obor["nazev_oboru"] == "Informační technologie"
    assert obor["kod_kkov"] == "18-20-M/01"
    assert obor["typ_ukonceni"] == "maturitní zkouška"
    assert obor["delka_studia"] == "4"
    assert obor["prijimaci_zkousky"] == "ČJ, M"


def test_parse_detail_obor_prihlaseni_prijati_split():
    """Atlas na rozdíl od infoabsolventu uvádí SKUTEČNÝ loňský počet přijatých,
    ne jen plán — proto dva oddělené sloupce loni_prihlaseni/loni_prijati."""
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    obor = data["obory"][0]
    assert obor["loni_prihlaseni"] == 89
    assert obor["loni_prijati"] == 30
    assert obor["planovany_pocet_prijmout"] == 30


def test_parse_detail_obor_plp_ozp_prospech():
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    obor = data["obory"][0]
    assert obor["plp"] is False
    assert obor["ozp"] is True
    assert obor["doporuceny_prospech"] == 1.5


def test_parse_detail_paid_statistika_link_not_followed_or_stored():
    """Odkaz "Statistika" (placená stránka `?obor=...`) se nesmí objevit v datech —
    viz modul docstring a docs/research/atlas-infoabsolvent.md, oddíl 1.4 a 3."""
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    blob = json.dumps(data, ensure_ascii=False)
    assert "obor=3716" not in blob
    assert "statistika" not in blob.lower()


def test_parse_detail_ucnovsky_obor_free_pocty_prihlasenych_prijatych():
    """U učňovských oborů jsou počty přihlášených/přijatých taky zdarma (bez placené
    Statistiky), viz research doc oddíl 1.4."""
    redizo, data = atlas.parse_detail(DETAIL_UCNOVSKY_HTML)
    assert redizo == "600006573"
    obor = data["obory"][0]
    assert obor["typ_ukonceni"] == "výuční list"
    assert obor["loni_prihlaseni"] == 12
    assert obor["loni_prijati"] == 12


# --------------------------------------------------------------------------- import do DB

def test_import_profil_stores_json_blob():
    conn = db.connect(":memory:")
    redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    atlas.import_profil(conn, redizo, data, stazeno="2026-09-22", url="https://example/ss16")
    row = conn.execute(
        "SELECT redizo, zdroj, stazeno, url, data FROM web_profil WHERE redizo = '600004686'"
    ).fetchone()
    assert row["zdroj"] == "atlas"
    assert row["stazeno"] == "2026-09-22"
    stored = json.loads(row["data"])
    assert stored["obory"][0]["kod_kkov"] == "18-20-M/01"


def test_import_profil_is_idempotent_same_day():
    """Reimport se stejným (redizo, zdroj, stazeno) přepíše řádek, nezdvojí ho —
    klíč `web_profil` zahrnuje zdroj, takže infoabsolvent a atlas mohou mít
    zvlášť řádek pro stejné REDIZO stejný den."""
    conn = db.connect(":memory:")
    redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    atlas.import_profil(conn, redizo, data, stazeno="2026-09-22")
    atlas.import_profil(conn, redizo, data, stazeno="2026-09-22")
    n = conn.execute("SELECT COUNT(*) FROM web_profil WHERE redizo = ? AND zdroj = 'atlas'", (redizo,)).fetchone()[0]
    assert n == 1


def test_import_profil_different_day_keeps_history():
    conn = db.connect(":memory:")
    redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    atlas.import_profil(conn, redizo, data, stazeno="2026-09-22")
    atlas.import_profil(conn, redizo, data, stazeno="2026-09-23")
    n = conn.execute("SELECT COUNT(*) FROM web_profil WHERE redizo = ? AND zdroj = 'atlas'", (redizo,)).fetchone()[0]
    assert n == 2


def test_import_profil_coexists_with_infoabsolvent_same_redizo():
    """Stejné REDIZO může mít řádek od obou zdrojů zároveň (klíč zahrnuje `zdroj`)."""
    from jaknastredni import infoabsolvent as ia

    conn = db.connect(":memory:")
    redizo, atlas_data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    atlas.import_profil(conn, redizo, atlas_data, stazeno="2026-09-22")
    ia.import_profil(conn, redizo, {"velikost_skoly": "SŠ 451 - 500 žáků"}, stazeno="2026-09-22")
    n = conn.execute("SELECT COUNT(*) FROM web_profil WHERE redizo = ?", (redizo,)).fetchone()[0]
    assert n == 2


# --------------------------------------------------------------------------- import_from_local / fetch_raw

def test_import_from_local_skips_school_without_redizo(tmp_path, caplog):
    raw_dir = tmp_path / "atlas"
    raw_dir.mkdir()
    (raw_dir / "16.html").write_text(DETAIL_SIMPLE_HTML, encoding="utf-8")
    (raw_dir / "99.html").write_text(DETAIL_NO_REDIZO_HTML, encoding="utf-8")
    manifest = {
        "stazeno": "2026-09-22",
        "region": "hlm-praha",
        "list_url": "https://www.atlasskolstvi.cz/stredni-skoly?region=hlm-praha",
        "schools": [
            {"atlas_id": "16", "url": "https://www.atlasskolstvi.cz/ss16-x"},
            {"atlas_id": "99", "url": "https://www.atlasskolstvi.cz/ss99-x"},
        ],
    }
    (raw_dir / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    conn = db.connect(":memory:")
    stats = atlas.import_from_local(conn, raw_dir)

    assert stats == {"celkem": 2, "ok": 1, "chybi_html": 0, "bez_redizo": 1}
    n = conn.execute("SELECT COUNT(*) FROM web_profil WHERE zdroj = 'atlas'").fetchone()[0]
    assert n == 1


def test_import_from_local_missing_manifest_returns_zero(tmp_path):
    conn = db.connect(":memory:")
    stats = atlas.import_from_local(conn, tmp_path / "nic-tu-neni")
    assert stats == {"celkem": 0, "ok": 0, "chybi_html": 0, "bez_redizo": 0}


def test_fetch_raw_paginates_and_saves_html(tmp_path):
    # maxpages=2 (na rozdíl od LIST_HTML výše s 11), ať fake session pokryje
    # přesně stránky, které fetch_raw skutečně stáhne.
    list_page1 = LIST_HTML.replace('data-maxpages="11"', 'data-maxpages="2"')
    pages = {
        "https://www.atlasskolstvi.cz/stredni-skoly?region=hlm-praha": list_page1,
        "https://www.atlasskolstvi.cz/stredni-skoly?p=2&region=hlm-praha": LIST_PAGE2_HTML,
    }
    details = {
        "https://www.atlasskolstvi.cz/ss16-stredni-prumyslova-skola-strojnicka-praha-1": DETAIL_SIMPLE_HTML,
        "https://www.atlasskolstvi.cz/ss183-obchodni-akademie-heroldovy-sady": DETAIL_UCNOVSKY_HTML,
        "https://www.atlasskolstvi.cz/ss42-gymnazium-nad-alejí": DETAIL_SIMPLE_HTML,
    }

    class _FakeSession:
        def get(self, url: str) -> str:
            if url in pages:
                return pages[url]
            return details[url]

    raw_dir = tmp_path / "atlas"
    stats = atlas.fetch_raw(_FakeSession(), raw_dir)

    assert stats == {"celkem": 3, "ok": 3, "selhalo": 0}
    assert (raw_dir / "16.html").exists()
    assert (raw_dir / "183.html").exists()
    assert (raw_dir / "42.html").exists()
    manifest = json.loads((raw_dir / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["region"] == "hlm-praha"
    assert len(manifest["schools"]) == 3


def test_fetch_raw_respects_limit(tmp_path):
    pages = {"https://www.atlasskolstvi.cz/stredni-skoly?region=hlm-praha": LIST_HTML}

    class _FakeSession:
        def __init__(self):
            self.detail_calls = 0

        def get(self, url: str) -> str:
            if url in pages:
                return pages[url]
            self.detail_calls += 1
            return DETAIL_SIMPLE_HTML

    # Jedna stránka (maxpages=11 v LIST_HTML, ale limit ořeže seznam škol na 1
    # ještě před stahováním detailů — maxpages ovlivňuje jen stránkování seznamu).
    html_one_page = LIST_HTML.replace('data-maxpages="11"', 'data-maxpages="1"')
    pages["https://www.atlasskolstvi.cz/stredni-skoly?region=hlm-praha"] = html_one_page

    session = _FakeSession()
    stats = atlas.fetch_raw(session, tmp_path / "atlas", limit=1)
    assert stats["celkem"] == 1
    assert session.detail_calls == 1


# --------------------------------------------------------------------------- robots.txt

class _FakeRobotsSession:
    def __init__(self, text: str):
        self._text = text

    def get(self, url: str) -> str:
        return self._text


ROBOTS_TXT = """User-agent: *
Disallow: /admin/
"""


def test_check_robots_allows_school_list_and_detail():
    session = _FakeRobotsSession(ROBOTS_TXT)
    # nesmí vyhodit výjimku
    atlas.check_robots_allows(session, ["/stredni-skoly", "/ss16-nejaka-skola"])


def test_check_robots_disallowed_path_raises():
    session = _FakeRobotsSession(ROBOTS_TXT)
    try:
        atlas.check_robots_allows(session, ["/admin/cokoli"])
    except atlas.RobotsDisallowed:
        pass
    else:
        raise AssertionError("očekávána výjimka RobotsDisallowed")
