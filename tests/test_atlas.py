"""Testy scraperu atlasskolstvi.cz.

Fixtury jsou zkrácené výřezy inspirované skutečně staženými stránkami
(REDIZO 600004686 „Střední průmyslová škola strojnická" a REDIZO 600005216
„Střední škola gastronomická a hotelová", ověřeno živým stažením 2026-09-22,
viz `_parse_maxpages`/`_extract_redizo`/`_parse_obory` komentáře v
`jaknastredni/atlas.py`) — na rozdíl od dřívější verze těchto testů, psané jen
podle `docs/research/atlas-infoabsolvent.md` bez živého ověření, byla ta
verze v několika ohledech nesprávná (vnořený `data-maxpages`, `div.description`
místo `div.doplnujiciInfo`, `table.sslist` místo `table.oborTable`, obor
rozložený do DVOU `<tr>`) — teď fixtury odpovídají reálné struktuře.
"""
from __future__ import annotations

import json

from jaknastredni import atlas, db

# --------------------------------------------------------------------------- fixtury

LIST_HTML = """
<html><body>
<div class="pagination"><div data-maxpages="11" data-nextpage="2"></div></div>
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
<div class="pagination"><div data-maxpages="11" data-nextpage="3"></div></div>
<ul class="schoollist cols1">
<li><a href="/ss42-gymnazium-nad-alejí">
  <h2>Gymnázium Nad Alejí</h2>
  <article>Nad Alejí 1952, Praha 6, 162 00</article>
</a></li>
</ul>
</body></html>
"""

# Detail školy (REDIZO 600004686) — kontaktní <li> sdílené se Zřizovatelem/IČ
# (REDIZO se musí číst jen z textu hned za vlastním <strong>, ne z celého
# textu <li>, jinak by IČ hrozilo kolizi), `div.description` s volnými poli a
# `ul.advinfo`, a `table.sslist` s jedním oborem rozloženým do dvou <tr>
# (hlavní řádek + `tr.nobg` se školným/prospěchem) + odkaz na placenou
# "Statistiku", který se nesmí propsat do dat.
DETAIL_SIMPLE_HTML = """
<html><body>
<ul class="contactBox">
  <li class="director"><strong>Mgr. Michal Prutyszyn, MBA</strong> <em>ředitel/ka</em></li>
  <li>
    <strong>Zřizovatel:</strong> Kraj<br>
    <strong>IČ:</strong> 70872589<br>
    <strong>Redizo:</strong> 600004686<br>
  </li>
</ul>
<div class="description">
  <h2>Dny otevřených dveří</h2>
  <article class="small">
    <div>st 8. 10. 2025 (od 16:00 do 18:00 hod.), so 6. 12. 2025 (od 10:00 do 13:00 hod.)</div>
    <button aria-expanded="false" class="more">Zobrazit více</button>
  </article>
  <h2>Doplňující informace</h2>
  <article class="small">
    <div>Žáci budou přijímáni na základě studijních výsledků na základní škole a přijímacích zkoušek.</div>
    <button aria-expanded="false" class="more">Zobrazit více</button>
  </article>
  <ul class="advinfo">
    <li class="languages" data-help="...">
      <div><strong>Cizí jazyky</strong><span>AJ, NJ, ŠJ</span></div>
    </li>
    <li class="lodging" data-help="...">
      <div><strong>Ubytování</strong><span>Neuvedeno</span></div>
    </li>
    <li class="food" data-help="...">
      <div><strong>Stravování</strong><span>840&nbsp;Kč/měsíc</span></div>
    </li>
  </ul>
  <h2>Obory a zaměření</h2>
  <div class="branchlist">
    <table cellspacing="0" cellpadding="0" class="sslist">
      <caption>Seznam oborů studia</caption>
      <tbody>
        <tr>
          <th data-name="Obor, zaměření, kód oboru KKOV" rowspan="2" scope="row">
            <a href="?obor=3716&amp;forma=2&amp;typ=10&amp;delka_studia=4"><strong>Informační technologie</strong></a>
            <span>18-20-M/01 </span>
          </th>
          <td data-name="Ukončení studia" rowspan="2"><strong>Maturitní zkouška</strong><span>4&nbsp;roky</span></td>
          <td data-name="Přijmou 2026/27"><strong>30</strong></td>
          <td data-name="Přihl./přij. 2025/26">183/30
            <a href="?obor=3716&amp;forma=2&amp;typ=10&amp;delka_studia=4" class="small">Statistika</a></td>
          <td data-name="Přijímací zkoušky">ČJ, M</td>
          <td data-name="PLP" class="yes"><strong><span>ANO</span></strong></td>
          <td data-name="OZP" class="yes"><strong><span>ANO</span></strong></td>
        </tr>
        <tr class="nobg">
          <td colspan="2" data-name="Školné" data-help="..."></td>
          <td colspan="3" data-name="Doporučený prospěch" data-help="...">
            <text><span>Doporučený prospěch:&nbsp;</span>2.3</text>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
</body></html>
"""

# Výřez s výučním oborem (REDIZO 600006573) — má taky zdarma loňský
# přihlášení/přijatí (bez placené Statistiky), navíc školné bez doporučeného
# prospěchu (prázdná buňka).
DETAIL_UCNOVSKY_HTML = """
<html><body>
<ul class="contactBox">
  <li><strong>Redizo:</strong> 600006573<br></li>
</ul>
<div class="description">
  <div class="branchlist">
    <table class="sslist">
      <tbody>
        <tr>
          <th data-name="Obor, zaměření, kód oboru KKOV" rowspan="2" scope="row">
            <a href="?obor=3772&amp;forma=2&amp;delka_studia=3"><strong>Cukrář</strong></a>
            <span>29-54-H/01</span>
          </th>
          <td data-name="Ukončení studia" rowspan="2"><strong>Výuční list</strong><span>3&nbsp;roky</span></td>
          <td data-name="Přijmou 2026/27"><strong>60</strong></td>
          <td data-name="Přihl./přij. 2025/26">168/60
            <a href="?obor=3772&amp;forma=2&amp;delka_studia=3" class="small">Statistika</a></td>
          <td data-name="Přijímací zkoušky">ČJ</td>
          <td data-name="PLP" class="yes"><strong><span>ANO</span></strong></td>
          <td data-name="OZP" class="no"><strong><span>NE</span></strong></td>
        </tr>
        <tr class="nobg">
          <td colspan="2" data-name="Školné" data-help="..."><span>Školné:</span> 21&nbsp;000 Kč</td>
          <td colspan="3" data-name="Doporučený prospěch" data-help="..."></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
</body></html>
"""

# Dva obory oddělené řádkem-oddělovačem sekce ("Nástavby:", bez buňky oboru
# ani školného/prospěchu) — nesmí přerušit párování dvojic <tr> u druhého
# oboru ani vytvořit fiktivní obor navíc.
DETAIL_MULTI_OBOR_WITH_SECTION_HTML = """
<html><body>
<ul class="contactBox"><li><strong>Redizo:</strong> 600005216<br></li></ul>
<div class="description">
  <div class="branchlist">
    <table class="sslist">
      <tbody>
        <tr>
          <th data-name="Obor, zaměření, kód oboru KKOV" rowspan="2" scope="row">
            <a href="?obor=3924"><strong>Gymnázium</strong></a>
            <span>79-41-K/41</span>
          </th>
          <td data-name="Ukončení studia" rowspan="2"><strong>Maturitní zkouška</strong><span>4&nbsp;roky</span></td>
          <td data-name="Přijmou 2026/27"><strong>30</strong></td>
          <td data-name="Přihl./přij. 2025/26">123/28</td>
          <td data-name="Přijímací zkoušky">ČJ, M</td>
          <td data-name="PLP" class="no"><strong><span>NE</span></strong></td>
          <td data-name="OZP" class="no"><strong><span>NE</span></strong></td>
        </tr>
        <tr class="nobg">
          <td colspan="2" data-name="Školné" data-help="..."></td>
          <td colspan="3" data-name="Doporučený prospěch" data-help="..."></td>
        </tr>
        <tr class="nastavby"><td class="first" colspan="7"><strong>Nástavby:</strong></td></tr>
        <tr>
          <th data-name="Obor, zaměření, kód oboru KKOV" rowspan="2" scope="row">
            <a href="?obor=3883"><strong>Podnikání; Kombinovaná; VYU</strong></a>
            <span>64-41-L/51</span>
          </th>
          <td data-name="Ukončení studia" rowspan="2"><strong>Maturitní zkouška</strong><span>2&nbsp;roky</span></td>
          <td data-name="Přijmou 2026/27"><strong>30</strong></td>
          <td data-name="Přihl./přij. 2025/26">346/198</td>
          <td data-name="Přijímací zkoušky">AJ, ČJ, M</td>
          <td data-name="PLP" class="no"><strong><span>NE</span></strong></td>
          <td data-name="OZP" class="no"><strong><span>NE</span></strong></td>
        </tr>
        <tr class="nobg">
          <td colspan="2" data-name="Školné" data-help="..."><span>Školné:</span> 34&nbsp;000 Kč</td>
          <td colspan="3" data-name="Doporučený prospěch" data-help="..."></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
</body></html>
"""

DETAIL_NO_REDIZO_HTML = """
<html><body><div class="description">Stránka bez detailu.</div></body></html>
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
    """`data-maxpages` je na vnořeném `<div>` uvnitř `div.pagination`, ne na tomtéž
    elementu, který nese třídu `pagination` (ověřeno živě, liší se od průzkumu)."""
    assert atlas._parse_maxpages(LIST_HTML) == 11


def test_parse_maxpages_defaults_to_one_without_pagination():
    assert atlas._parse_maxpages("<html><body>no pagination here</body></html>") == 1


# --------------------------------------------------------------------------- detail: obecná pole

def test_parse_detail_extracts_redizo_from_page_text():
    redizo, _data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert redizo == "600004686"


def test_parse_detail_redizo_not_confused_with_ic_in_same_li():
    """Zřizovatel/IČ/Redizo jsou tři <strong> ve stejném <li> — REDIZO se musí
    číst z textu hned za svým vlastním <strong>, ne z IČ o pár znaků dřív."""
    redizo, _data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert redizo != "70872589"
    assert redizo == "600004686"


def test_parse_detail_returns_none_redizo_when_missing():
    redizo, data = atlas.parse_detail(DETAIL_NO_REDIZO_HTML)
    assert redizo is None
    assert data == {}


def test_parse_detail_doplnujici_fields():
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert "8. 10. 2025" in data["dny_otevrenych_dveri"]
    assert "přijímacích zkoušek" in data["doplnujici_informace"]
    assert data["cizi_jazyky"] == "AJ, NJ, ŠJ"
    assert data["ubytovani"] == "Neuvedeno"
    assert "840" in data["stravovani"]


def test_parse_detail_no_personal_or_redundant_data():
    """Adresa, IČ, zřizovatel a jméno ředitele se nevytahují (redundantní vůči MŠMT
    rejstříku / osobní údaj, stejná zásada jako u infoabsolventu)."""
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    blob = json.dumps(data, ensure_ascii=False).lower()
    assert "adresa" not in data
    assert "ic" not in data and "ič" not in data
    assert "zrizovatel" not in data and "zřizovatel" not in data
    assert "reditel" not in blob
    assert "prutyszyn" not in blob  # jméno ředitele se nikam nepropsalo
    assert "70872589" not in blob  # IČ taky ne


# --------------------------------------------------------------------------- detail: obory

def test_parse_detail_obor_basic_fields():
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    assert len(data["obory"]) == 1
    obor = data["obory"][0]
    assert obor["nazev_oboru"] == "Informační technologie"
    assert obor["kod_kkov"] == "18-20-M/01"
    assert obor["typ_ukonceni"] == "Maturitní zkouška"
    assert obor["delka_studia"] == "4\xa0roky"
    assert obor["prijimaci_zkousky"] == "ČJ, M"


def test_parse_detail_obor_prihlaseni_prijati_split():
    """Atlas na rozdíl od infoabsolventu uvádí SKUTEČNÝ loňský počet přijatých,
    ne jen plán — proto dva oddělené sloupce loni_prihlaseni/loni_prijati."""
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    obor = data["obory"][0]
    assert obor["loni_prihlaseni"] == 183
    assert obor["loni_prijati"] == 30
    assert obor["planovany_pocet_prijmout"] == 30


def test_parse_detail_obor_plp_ozp_prospech():
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    obor = data["obory"][0]
    assert obor["plp"] is True
    assert obor["ozp"] is True
    assert obor["doporuceny_prospech"] == 2.3


def test_parse_detail_paid_statistika_link_not_followed_or_stored():
    """Odkaz "Statistika" (placená stránka `?obor=...`) se nesmí objevit v datech —
    viz modul docstring a docs/research/atlas-infoabsolvent.md, oddíl 1.4 a 3."""
    _redizo, data = atlas.parse_detail(DETAIL_SIMPLE_HTML)
    blob = json.dumps(data, ensure_ascii=False)
    assert "obor=3716" not in blob
    assert "statistika" not in blob.lower()


def test_parse_detail_ucnovsky_obor_free_pocty_prihlasenych_prijatych():
    """U výučních oborů jsou loňské počty přihlášených/přijatých taky zdarma
    (bez placené Statistiky), viz research doc oddíl 1.4."""
    redizo, data = atlas.parse_detail(DETAIL_UCNOVSKY_HTML)
    assert redizo == "600006573"
    obor = data["obory"][0]
    assert obor["typ_ukonceni"] == "Výuční list"
    assert obor["loni_prihlaseni"] == 168
    assert obor["loni_prijati"] == 60


def test_parse_detail_obor_skolne_with_nbsp_thousands_separator():
    """Školné používá pevnou mezeru (\\xa0) jako oddělovač tisíců — muselo by se
    jinak useknout na první skupinu číslic (viz `atlas._int`)."""
    _redizo, data = atlas.parse_detail(DETAIL_UCNOVSKY_HTML)
    obor = data["obory"][0]
    assert obor["skolne_rocne"] == 21000
    assert "doporuceny_prospech" not in obor  # prázdná buňka u tohoto oboru


def test_parse_detail_section_separator_row_does_not_break_pairing():
    """Řádek-oddělovač sekce ("Nástavby:") nemá buňku oboru ani školné/prospěch
    — nesmí se stát fiktivním obor, ani přerušit spárování dalšího oboru se
    svým pokračovacím řádkem (`tr.nobg`)."""
    redizo, data = atlas.parse_detail(DETAIL_MULTI_OBOR_WITH_SECTION_HTML)
    assert redizo == "600005216"
    obory = data["obory"]
    assert len(obory) == 2
    assert obory[0]["nazev_oboru"] == "Gymnázium"
    assert obory[1]["nazev_oboru"] == "Podnikání; Kombinovaná; VYU"
    assert obory[1]["skolne_rocne"] == 34000
    assert obory[1]["loni_prihlaseni"] == 346
    assert obory[1]["loni_prijati"] == 198


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
