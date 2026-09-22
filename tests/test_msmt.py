import json
from pathlib import Path

import pytest

from jaknastredni import db, msmt

FIXTURE = Path(__file__).parent / "fixtures" / "rssz-praha-vzorek.jsonld"


@pytest.fixture
def data():
    return msmt.load(FIXTURE)


@pytest.fixture
def conn(data):
    c = db.connect(":memory:")
    msmt.import_data(c, data, soubor=FIXTURE)
    return c


def test_fixture_has_reference_school(data):
    redizos = {o["redIzo"] for o in data["list"]}
    assert "600006573" in redizos
    assert data["datumVystupu"] == "2026-09-22"


def test_import_counts(conn):
    n = lambda sql: conn.execute(sql).fetchone()[0]
    assert n("SELECT COUNT(*) FROM organizace") == 3
    assert n("SELECT COUNT(*) FROM skola") == 4  # OA, SPŠ+VOŠ, MŠ
    assert n("SELECT COUNT(*) FROM skola WHERE druh = 'C00'") == 2
    assert n("SELECT COUNT(*) FROM v_stredni_skola") == 3  # C00 + E00
    assert n("SELECT COUNT(*) FROM import_run WHERE zdroj = 'msmt'") == 1


def test_reference_school_detail(conn):
    org = conn.execute("SELECT * FROM organizace WHERE redizo = '600006573'").fetchone()
    assert org["nazev"].startswith("Obchodní akademie")
    assert org["obvod_prahy"] == "Praha 10"
    assert org["ico"] == "61385387"
    assert json.loads(org["emaily"]) == ["test@example.cz"]

    skola = conn.execute("SELECT * FROM skola WHERE redizo = '600006573'").fetchone()
    assert skola["izo"] == "000638510"
    assert skola["druh"] == "C00"

    kap = conn.execute("SELECT nejvyssi_povoleny_pocet FROM skola_kapacita WHERE izo = '000638510'").fetchone()
    assert kap[0] == 500

    obory = conn.execute(
        "SELECT kod_kkov, nazev, kapacita, delka FROM obor WHERE izo = '000638510' ORDER BY kod_kkov"
    ).fetchall()
    assert [o["kod_kkov"] for o in obory] == ["63-41-M/02", "78-42-M/02", "78-42-M/08"]
    assert obory[0]["nazev"] == "Obchodní akademie"
    assert obory[0]["kapacita"] == 240
    assert obory[0]["delka"] == "40"

    zr = conn.execute("SELECT nazev, ico FROM zrizovatel WHERE redizo = '600006573'").fetchone()
    assert zr["nazev"] == "Hlavní město Praha"
    assert zr["ico"] == "00064581"


def test_one_organisation_two_schools(conn):
    rows = conn.execute(
        "SELECT izo, druh FROM skola WHERE redizo = (SELECT redizo FROM skola WHERE izo = '000638595') ORDER BY izo"
    ).fetchall()
    assert [(r["izo"], r["druh"]) for r in rows] == [("000638595", "C00"), ("110025962", "E00")]


def test_reimport_is_idempotent(conn, data):
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("organizace", "skola", "obor", "skola_kapacita", "misto_vyuky", "zrizovatel")}
    msmt.import_data(conn, data, soubor=FIXTURE)
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
    assert before == after
    assert conn.execute("SELECT COUNT(*) FROM import_run").fetchone()[0] == 2


def test_prune_removes_missing_and_cascades(conn, data):
    smaller = {**data, "datumVystupu": "2026-09-23", "list": [o for o in data["list"] if o["redIzo"] != "600006573"]}
    stats = msmt.import_data(conn, smaller)
    assert stats["smazano_organizaci"] == 1
    assert conn.execute("SELECT COUNT(*) FROM organizace WHERE redizo = '600006573'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM obor WHERE izo = '000638510'").fetchone()[0] == 0
    assert conn.execute("SELECT aktualizovano FROM organizace LIMIT 1").fetchone()[0] == "2026-09-23"


def test_no_prune_keeps_missing(conn, data):
    smaller = {**data, "list": [o for o in data["list"] if o["redIzo"] != "600006573"]}
    msmt.import_data(conn, smaller, prune=False)
    assert conn.execute("SELECT COUNT(*) FROM organizace").fetchone()[0] == 3


def test_removed_school_within_organisation_is_deleted(conn, data):
    changed = json.loads(json.dumps(data))
    for o in changed["list"]:
        if o["redIzo"] == "600006573":
            o["skolyAZarizeni"] = []
    msmt.import_data(conn, changed)
    assert conn.execute("SELECT COUNT(*) FROM skola WHERE redizo = '600006573'").fetchone()[0] == 0


def test_load_rejects_wrong_structure(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"foo": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        msmt.load(bad)


def test_personal_data_not_stored(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(zrizovatel)")}
    assert "adresa" not in cols and "datum_narozeni" not in cols
    cols = {r[1] for r in conn.execute("PRAGMA table_info(organizace)")}
    assert "reditel_adresa" not in cols
