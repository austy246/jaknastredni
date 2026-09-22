"""Testy scraperu infoabsolvent.cz.

Fixtury jsou zkrácené výřezy ze skutečných stránek stažených 2026-09-22
(seznam `/Skoly/Seznam/SOS?Kraj=CZ011` a detaily REDIZO 600004686 a 600004538),
uložené jako řetězcové literály, aby testy běžely offline (viz README, princip
testovacích fixtur používaný i pro CERMAT: tests/test_cermat_mz.py).
"""
from __future__ import annotations

import json

from jaknastredni import db, infoabsolvent as ia

# --------------------------------------------------------------------------- fixtury

LIST_HTML = """
<html><body>
<ul class="schoollist">
<li><a href="/Skoly/Skola/651028922/1-Slovanske-gymnazium-jazykova-skola-s-pravem-/SOS">
1. Slovanské gymnázium</a></li>
<li><a href="/Skoly/Skola/600004686/Stredni-prumyslova-skola-strojnicka-skola-/SOS">
Střední průmyslová škola strojnická</a></li>
<li><a href="/Skoly/Skola/600004520/Obchodni-akademie-Dusni/SOS">Obchodní akademie Dušní</a></li>
</ul>
<a href="/Obory/PorovnaniOboru">porovnat obory</a>
</body></html>
"""

# Zkrácený výřez detailu REDIZO 600004686 (SPŠ strojnická) — genInfoList,
# kontakt, odkaz ČŠI, hidden redIzo pole a jeden obor s jedním řádkem ŠVP.
DETAIL_SIMPLE_HTML = """
<html><body>
<div class="col2-1 dataCol">
  <h1 class="cb">Střední průmyslová škola strojnická</h1>
  <ul class="genInfoList">
    <li><span class="label">Adresa:</span><span class="data">Betlémská 287/4, Praha 1</span></li>
    <li><span class="label">Okres:</span><span class="data">Praha 1</span></li>
    <li><span class="label">Typ školy:</span><span class="data">střední škola, veřejná</span></li>
    <li><span class="label">Vybavení školy a její nabídka:</span>
      <span class="data">studovna, fitcentrum, <b>bezbariérové prostředí školy</b></span></li>
    <li><span class="label">Velikost školy:</span><span class="data">SŠ 451 - 500 žáků</span></li>
    <li><span class="label">Ubytování:</span><span class="data">škola nezajišťuje</span></li>
    <li><span class="label">Stravování:</span><span class="data">v školní jídelně</span></li>
    <li><span class="label">Přístup k PC</span>
      <span class="data">v době mimo vyučování: v omezené míře</span></li>
    <li><span class="label">Den otevřených dveří:</span><span class="data">viz web školy</span></li>
    <li><span class="label">Cizí jazyky:</span>
      <span class="data">anglický (A), německý (N), španělský (Š)</span></li>
    <li><span class="label">Poznámka SŠ:</span>
      <span class="data">Škola poskytuje systematickou podporu žákům se specifickými poruchami učení.</span></li>
    <li>Inspekční zprávy školy najdete na
      <a href='https://portal.csicr.cz/School/600004686' target='_blank'>webu České školní inspekce</a>.</li>
  </ul>
</div>
<div class="addInfoBox highBox">
  <h2>Kontakt</h2>
  <ul class="contactList">
    <li><span class="label">www</span>
      <span class="data"><a href="http://www.betlemska.cz">http://www.betlemska.cz</a></span></li>
    <li><span class="label">E-mail</span>
      <span class="data"><a href="mailto:sekretariat@betlemska.cz">sekretariat@betlemska.cz</a></span></li>
    <li><span class="label">Telefon</span><span class="data">251 092 161</span></li>
  </ul>
</div>
<div id="vzdelavaciNabidka">
<form id="filtrForm"><input id="redIzo" name="redIzo" type="hidden" value="600004686" /></form>
<div class="oboryRvp barvaPozadi"><div class="oborRvp">
  <div><span class="kodOboru">18-20-M/01</span>
    <span class="nazevOboru"><a href="/Obory/KartaOboru/1820M01/x">Informační technologie</a></span></div>
  <table><thead><tr><td id="A-nazev-oboru" class="first">Zaměření nebo ŠVP</td></tr></thead>
    <tbody><tr><td id="A-nazev-oboru-0">
      <div class="nazevOboru oborJeSvp"><div class="nazev">
        <span class="nazevOboruJeSvp">Informační technologie</span></div></div>
    </td></tr></tbody></table>
  <table><thead><tr>
      <td id="B-delka">Délka studia</td><td id="C-forma">Forma studia</td>
      <td id="D-pocet-jazyku">Počet povinných cizích jazyků</td><td id="E-jazyky">Vyučované jazyky</td>
    </tr></thead>
    <tbody><tr>
      <td id="B-delka-0">4,0</td><td id="C-forma-0">Denní</td>
      <td id="D-pocet-jazyku-0">1</td><td id="E-jazyky-0">A</td>
    </tr></tbody></table>
  <table><thead><tr>
      <td id="F-prihlaseni-prijati">LONI: přihlášení/plán přijmout</td>
      <td id="G-pocet-prijatych">LETOS: plán přijmout</td>
      <td id="H-prijimaci-zkouska">Přijímací zkouška</td>
      <td id="I-skolne">Roční školné</td><td id="J-ztp">Možnost studia pro ZP</td>
    </tr></thead>
    <tbody><tr>
      <td id="F-prihlaseni-prijati-0">229 / 30</td>
      <td id="G-pocet-prijatych-0">30</td>
      <td id="H-prijimaci-zkouska-0">
        <a href="" onclick="zapniVypni('prijimacky469070');return false;">koná se</a></td>
      <td id="I-skolne-0">0</td>
      <td id="J-ztp-0">Sluchově, Tělesně</td>
    </tr></tbody></table>
  <table><tbody><tr><td class="poznamky" colspan="9">
    <div class="prijimackyWrapper"><div id="prijimacky469070" class="prijimackyOkno">
      <table><thead><tr class="barvaPozadiNadpis"><td colspan="2">Informace k přijímacímu řízení</td></tr></thead>
        <tbody>
          <tr><td class="popisek">Jednotná příj. zkouška:</td><td class="info">ČJ a M</td></tr>
          <tr><td class="popisek">Ústní zkouška:</td><td class="info">nekoná se</td></tr>
          <tr><td class="popisek">Písemná zkouška:</td><td class="info">nekoná se</td></tr>
          <tr><td class="popisek">Talentová zkouška:</td><td class="info">nekoná se</td></tr>
          <tr><td class="popisek">Praktická zkouška:</td><td class="info">nekoná se</td></tr>
          <tr><td class="popisek">Přihlášky podejte do:</td><td class="info">20.2.2026</td></tr>
          <tr><td class="popisek">Termíny jednotné zkoušky:</td>
              <td class="info">10. 4. 2026 a 13. 4. 2026</td></tr>
        </tbody></table>
    </div></div>
    <div><b>Poznámky k oboru:</b> výuka CAD/CAM.</div>
  </td></tr></tbody></table>
</div></div>
</div>
</body></html>
"""

# Výřez s oborem majícím DVĚ řádky ŠVP se dvěma různými indexy (0 a 1), aby
# se ověřilo párování podle pozice (position), ne podle číselného indexu
# (id oken/poznámek je jiné číslo než index řádku, viz infoabsolvent._parse_obor_row).
DETAIL_MULTI_SVP_HTML = """
<html><body>
<ul class="genInfoList">
  <li><span class="label">Velikost školy:</span><span class="data">SŠ 551 - 600 žáků</span></li>
</ul>
<input id="redIzo" name="redIzo" type="hidden" value="600004538" />
<div class="oborRvp">
  <div><span class="kodOboru">82-44-P/01</span>
    <span class="nazevOboru"><a href="/Obory/KartaOboru/x">Hudba</a></span></div>
  <table><tbody>
    <tr><td id="A-nazev-oboru-5"><span class="nazevOboruJeSvp">Dirigování</span></td></tr>
    <tr><td id="A-nazev-oboru-6"><span class="nazevOboruJeSvp">Hra na violu</span></td></tr>
  </tbody></table>
  <table><tbody>
    <tr><td id="B-delka-5">6,0</td><td id="F-prihlaseni-prijati-5">6 / 1</td>
        <td id="G-pocet-prijatych-5">1</td></tr>
    <tr><td id="B-delka-6">6,0</td><td id="F-prihlaseni-prijati-6">4 / 4</td>
        <td id="G-pocet-prijatych-6">4</td></tr>
  </tbody></table>
  <div id="prijimacky1" class="prijimackyOkno"><table><tbody>
    <tr><td class="popisek">Talentová zkouška:</td><td class="info">Dirigování</td></tr>
  </tbody></table></div>
  <table><tbody><tr><td class="poznamky">
    <div><b>Poznámky k oboru:</b> první poznámka (dirigování).</div>
  </td></tr></tbody></table>
  <div id="prijimacky2" class="prijimackyOkno"><table><tbody>
    <tr><td class="popisek">Talentová zkouška:</td><td class="info">hra na nástroj</td></tr>
  </tbody></table></div>
  <table><tbody><tr><td class="poznamky">
    <div><b>Poznámky k oboru:</b> druhá poznámka (viola).</div>
  </td></tr></tbody></table>
</div>
</body></html>
"""


# --------------------------------------------------------------------------- seznam

def test_parse_list_extracts_redizo_from_url():
    schools = ia.parse_list(LIST_HTML)
    assert [s["redizo"] for s in schools] == ["651028922", "600004686", "600004520"]
    assert schools[1]["url"] == "https://www.infoabsolvent.cz/Skoly/Skola/600004686/Stredni-prumyslova-skola-strojnicka-skola-/SOS"


def test_parse_list_ignores_non_school_links():
    schools = ia.parse_list(LIST_HTML)
    assert all(s["redizo"].isdigit() and len(s["redizo"]) == 9 for s in schools)


def test_parse_list_deduplicates_redizo():
    html = LIST_HTML + '<a href="/Skoly/Skola/600004686/jiny-slug/SOS">duplicitní odkaz</a>'
    schools = ia.parse_list(html)
    assert [s["redizo"] for s in schools].count("600004686") == 1


# --------------------------------------------------------------------------- detail: obecná pole

def test_parse_detail_geninfo_fields():
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    assert data["velikost_skoly"] == "SŠ 451 - 500 žáků"
    assert data["ubytovani"] == "škola nezajišťuje"
    assert "bezbariérové" in data["vybaveni_a_nabidka"]
    assert data["cizi_jazyky"] == "anglický (A), německý (N), španělský (Š)"
    # Adresa/Okres/Typ školy se nevytahují (redundantní s MŠMT rejstříkem)
    assert "adresa" not in data
    assert "okres" not in data
    assert "typ_skoly" not in data


def test_parse_detail_contact_and_csi():
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    assert data["www"] == "http://www.betlemska.cz"
    assert data["email"] == "sekretariat@betlemska.cz"
    assert data["telefon"] == "251 092 161"
    assert data["csi_zpravy_url"] == "https://portal.csicr.cz/School/600004686"


def test_parse_detail_no_personal_data_beyond_msmt():
    """Nesmí obsahovat jméno ředitele ani jiné osobní údaje (zásada z datového modelu)."""
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    blob = json.dumps(data, ensure_ascii=False)
    assert "reditel" not in blob.lower()


# --------------------------------------------------------------------------- detail: obory

def test_parse_detail_obor_basic_fields():
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    assert len(data["obory"]) == 1
    obor = data["obory"][0]
    assert obor["kod_kkov"] == "18-20-M/01"
    assert obor["nazev_oboru"] == "Informační technologie"
    assert obor["delka_studia"] == "4,0"
    assert obor["forma_studia"] == "Denní"
    assert obor["pocet_povinnych_jazyku"] == 1
    assert obor["skolne_rocne"] == 0


def test_parse_detail_obor_loni_letos_split():
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    obor = data["obory"][0]
    # "LONI: přihlášení/plán přijmout" = 229 / 30, ne skutečný počet přijatých
    assert obor["loni_prihlaseni"] == 229
    assert obor["loni_plan_prijmout"] == 30
    assert obor["letos_plan_prijmout"] == 30


def test_parse_detail_obor_prijimaci_rizeni_and_poznamky():
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    obor = data["obory"][0]
    assert obor["prijimaci_zkouska_kona_se"] is True
    assert obor["prijimaci_rizeni"]["jednotna_prijimaci_zkouska"] == "ČJ a M"
    assert obor["prijimaci_rizeni"]["prihlasky_podejte_do"] == "20.2.2026"
    assert obor["poznamky_k_oboru"] == "výuka CAD/CAM."


def test_parse_detail_multi_svp_rows_matched_by_position_not_id():
    """Víc řádků ŠVP u jednoho oboru (např. konzervatoř): okna/poznámky se párují
    podle pořadí v HTML, ne podle číselného indexu v id (to je jiné číslo)."""
    data = ia.parse_detail(DETAIL_MULTI_SVP_HTML, "600004538")
    obory = data["obory"]
    assert len(obory) == 2
    assert obory[0]["svp_nazev"] == "Dirigování"
    assert obory[0]["loni_prihlaseni"] == 6
    assert obory[0]["prijimaci_rizeni"]["talentova_zkouska"] == "Dirigování"
    assert obory[0]["poznamky_k_oboru"] == "první poznámka (dirigování)."

    assert obory[1]["svp_nazev"] == "Hra na violu"
    assert obory[1]["loni_prihlaseni"] == 4
    assert obory[1]["prijimaci_rizeni"]["talentova_zkouska"] == "hra na nástroj"
    assert obory[1]["poznamky_k_oboru"] == "druhá poznámka (viola)."


# --------------------------------------------------------------------------- import do DB

def test_import_profil_stores_json_blob():
    conn = db.connect(":memory:")
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    ia.import_profil(conn, "600004686", data, stazeno="2026-09-22", url="https://example/x")
    row = conn.execute(
        "SELECT redizo, zdroj, stazeno, url, data FROM web_profil WHERE redizo = '600004686'"
    ).fetchone()
    assert row["zdroj"] == "infoabsolvent"
    assert row["stazeno"] == "2026-09-22"
    stored = json.loads(row["data"])
    assert stored["obory"][0]["kod_kkov"] == "18-20-M/01"


def test_import_profil_is_idempotent_same_day():
    """Reimport se stejným (redizo, zdroj, stazeno) přepíše řádek, nezdvojí ho."""
    conn = db.connect(":memory:")
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    ia.import_profil(conn, "600004686", data, stazeno="2026-09-22")
    ia.import_profil(conn, "600004686", data, stazeno="2026-09-22")
    n = conn.execute("SELECT COUNT(*) FROM web_profil WHERE redizo = '600004686'").fetchone()[0]
    assert n == 1


def test_import_profil_different_day_keeps_history():
    """Různá `stazeno` data jsou různé řádky (klíč zahrnuje datum stažení)."""
    conn = db.connect(":memory:")
    data = ia.parse_detail(DETAIL_SIMPLE_HTML, "600004686")
    ia.import_profil(conn, "600004686", data, stazeno="2026-09-22")
    ia.import_profil(conn, "600004686", data, stazeno="2026-09-23")
    n = conn.execute("SELECT COUNT(*) FROM web_profil WHERE redizo = '600004686'").fetchone()[0]
    assert n == 2


# --------------------------------------------------------------------------- robots.txt

class _FakeSession:
    def __init__(self, text: str):
        self._text = text

    def get(self, url: str) -> str:
        return self._text


ROBOTS_TXT = """User-agent: *
Disallow: /Obory/PorovnaniOboru
Disallow: /Skoly/KartaSkolyPorovnavaneObory/
Disallow: /Tools/SaveAsWord

User-agent: meta-externalagent
Disallow: /
"""


def test_check_robots_allows_school_list_and_detail():
    session = _FakeSession(ROBOTS_TXT)
    # nesmí vyhodit výjimku
    ia.check_robots_allows(session, ["/Skoly/Seznam/SOS", "/Skoly/Skola/600004686/x/SOS"])


def test_check_robots_disallowed_path_raises():
    session = _FakeSession(ROBOTS_TXT)
    try:
        ia.check_robots_allows(session, ["/Obory/PorovnaniOboru"])
    except ia.RobotsDisallowed:
        pass
    else:
        raise AssertionError("očekávána výjimka RobotsDisallowed")


def test_ratelimited_session_strips_bom_when_charset_undeclared(monkeypatch):
    """infoabsolvent.cz/robots.txt (ověřeno živě 2026-09-22) má UTF-8 BOM a
    `Content-Type: text/plain` bez deklarovaného charsetu — `requests` bez
    opravy defaultuje na ISO-8859-1 (staré HTTP chování pro text/*), takže BOM
    zmrzačí první řádek na nerozpoznatelné "ï»¿User-agent: *" a
    `check_robots_allows` pak nikdy nenajde sekci `User-agent: *`, takže
    potichu ignoruje všechna Disallow pravidla. `RateLimitedSession.get()`
    musí v tomhle případě použít `apparent_encoding`."""
    import requests

    raw = "﻿User-agent: *\r\nDisallow: /tajne\r\n".encode("utf-8-sig")
    resp = requests.Response()
    resp.status_code = 200
    resp._content = raw
    resp.headers["Content-Type"] = "text/plain"  # bez charsetu, jako živý server

    monkeypatch.setattr(requests.Session, "get", lambda self, url, timeout=None: resp)

    session = ia.RateLimitedSession()
    text = session.get("https://www.infoabsolvent.cz/robots.txt")
    assert text.splitlines()[0] == "User-agent: *"


def test_ratelimited_session_keeps_declared_charset(monkeypatch):
    """Stránky s deklarovaným charsetem (list/detail školy, vždy `charset=utf-8`)
    se nesmí přeurčovat podle `apparent_encoding` — jen chybějící charset
    (jako u robots.txt) je důvod k opravě, jinak riziko zbytečné regrese."""
    import requests

    raw = "Informační technologie".encode("utf-8")
    resp = requests.Response()
    resp.status_code = 200
    resp._content = raw
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.encoding = "utf-8"

    monkeypatch.setattr(requests.Session, "get", lambda self, url, timeout=None: resp)

    session = ia.RateLimitedSession()
    text = session.get("https://www.infoabsolvent.cz/Skoly/Skola/x")
    assert text == "Informační technologie"
